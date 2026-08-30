---
title: "Cross-app scripting in Acode, part 3: how to prevent it"
date: 2026-08-17T19:00:00+05:00
categories: ["Research"]
tags: ["android", "webview", "cordova", "xss", "appsec", "mobile"]
description: "The same codebase fixed this class of bug three times and missed a sibling sink each time. Why sink-side sanitisation keeps failing, what the durable fix is, and how to audit your own hybrid app."
weight: 3
ShowToc: true
TocOpen: false
cover:
  image: "/img/posts/acode/acode-logo.webp"
---

This is part 3 of three.

1. [What I found](/posts/acode-cross-app-scripting-what-i-found/), the bug and its impact
2. [How I found it](/posts/acode-cross-app-scripting-how-i-found-it/), the methodology
3. **How to prevent it**, you're here

---

Parts 1 and 2 covered a specific bug in a specific app. This part is the bit that transfers, because
Acode isn't unusual. It's a well-maintained project with a responsive maintainer who fixed my report in
about nineteen hours. It still shipped this bug, and the reason is structural rather than careless.

## The class

Stated generally:

> Any string that originates outside your app, reaching `innerHTML` without escaping, is a stored XSS
> sink in a Cordova, Capacitor or WebView application.

The part people miss is how many strings originate outside the app on a mobile OS. On a server you've
got a clear mental model of untrusted input: request bodies, query parameters, headers. On Android the
equivalent list is longer and much less obvious:

- **filenames**, specifically `OpenableColumns.DISPLAY_NAME` from a `content://` URI
- contact names
- notification titles and text
- share-intent subjects and `EXTRA_TEXT`
- clipboard contents
- Bluetooth and Wi-Fi device names
- calendar event titles
- media metadata: ID3 tags, EXIF fields

Every one of those is a string chosen by something you don't control. In Acode's case it was the
filename, and the crucial detail is that a `content://` display name **isn't a filename at all**. It's
an arbitrary string a third-party app returns from a cursor. No 255-byte cap, no forbidden characters.
It only looks like a filename.

Google names this class in its own guidance: `untrustworthy-contentprovider-provided-filename`.

## Why the fix kept failing

Acode's history with this exact class is the interesting part. Three rounds:

| When | What was fixed | What was missed |
|---|---|---|
| Dec 2024, commit `42002a67` | `DOMPurify` added at `alert.js`, `confirm.js`, `loader.js` | every source, `select.js`, `inputhints.js` |
| later | `select.js:122` sanitised | `inputhints.js` |
| Aug 2026, PR #2559 (my report) | `inputhints/index.js:371` sanitised | the source in `findFile/index.js` is still raw |

Same class, same codebase, three fixes, and each one repaired the reported call site rather than the
pattern.

That isn't carelessness. It's what happens when your defence lives at the sink. Compare what each
strategy requires.

**Sanitising at the sink** requires that *every current and future sink* remembers to sanitise. It's a
rule enforced by human vigilance, applied at a place that keeps growing. Add a new UI component that
renders a hint, a tooltip, a label, and that's a new sink with the raw value still flowing toward it.
The new component is an instant reintroduction of the old bug.

**Escaping at the source** requires that one function is correct, once. New sinks inherit the safety.

The state of Acode after my fix shows it precisely. The sink now sanitises, so the bug is closed, but
`hintItem()` in `findFile/index.js` still interpolates `${name}` and `${subText}` raw. The dangerous
value is still flowing. The next component that renders it without sanitising reopens the whole thing.

To be fair to the maintainer, that choice was reasonable. It was the minimal correct fix for the
reported issue, it shipped in a day, and it works. The structural point is about what stays true
afterwards.

## The fixes, in order of durability

### 1. Don't build HTML from untrusted strings at all

The most durable fix removes the sink rather than guarding it. Instead of assembling a string:

```js
// before: the value becomes markup
return {
  text: `<div style="display: flex; flex-direction: column;">
      <strong style="font-size: 1rem;">${name}</strong>
      <span style="font-size: 0.8rem; opacity: 0.8;">${subText}</span>
    <div>`,
  value: url,
};
```

build the nodes and let the DOM keep text as text:

```js
// after: the value can never be markup
const row = document.createElement("div");
row.className = "hint-row";

const title = document.createElement("strong");
title.textContent = name;          // parsed as text, always

const sub = document.createElement("span");
sub.className = "hint-sub";
sub.textContent = subText;

row.append(title, sub);
return { node: row, value: url };
```

`textContent` has no parsing mode where `<img src=x onerror=...>` becomes an element. Nothing to
escape, nothing to remember. Move the inline styles to a stylesheet while you're in there.

### 2. If you must produce a string, escape at the source

Where returning a node is too big a refactor, escape at the point of interpolation so the invariant
holds no matter which sink consumes the result:

```js
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

return {
  text: `<div class="hint-row">
      <strong>${esc(name)}</strong>
      <span class="hint-sub">${esc(subText)}</span>
    </div>`,
  value: url,
};
```

Escape all five characters. Escaping only `<` and `>` leaves attribute-context injection open when the
value lands in an unquoted attribute, which as part 2 showed is exactly the situation here.

### 3. Sanitise at the sink as defence in depth

This is what shipped, and it's correct as a second layer:

```js
import DOMPurify from "dompurify";
...
return <li attr-action="hint" attr-value={value} innerHTML={DOMPurify.sanitize(text)}></li>;
```

Verified behaviour on the real payload:

```
OUTPUT: <strong style="font-size: 1rem;"><img src="x">.txt</strong>
onerror survived? false   eval/atob survived? false
```

Note what survives: the `<img>` element itself. DOMPurify strips *script execution*, not *markup*. An
attacker can still inject arbitrary bold text, links, images and layout into your UI. Inside a
security-relevant dialog that's its own problem, because you can spoof a confirmation prompt without
running any JavaScript.

Which leads to the next one.

### 4. Make `textContent` the default and HTML the opt-in

Acode already has the right pattern in one place. `confirm.js` takes an `isHTML` flag and only treats
its input as markup when the caller explicitly asks. `checkFiles.js` calls it without the flag, so the
filename lands in `textContent` and is safe.

`alert.js` has no such flag, which is why the same variable from the same file was dangerous in one
dialog and harmless in the other.

For a display function taking a filename or an error string, markup is never wanted. Make the safe path
the one you get by default:

```js
function showMessage(msg, { isHTML = false } = {}) {
  const el = document.createElement("div");
  if (isHTML) el.innerHTML = DOMPurify.sanitize(msg);
  else el.textContent = msg;      // default
  return el;
}
```

### 5. Stop funnelling error strings into HTML

Acode's `helpers.errorMessage()` joins its arguments with `<br>` and returns `err.message` verbatim,
then hands the result to `alert()`. Roughly 35 call sites, carrying SSH hostnames, remote paths and
filenames.

That single helper is the app's largest "attacker string becomes markup" funnel. Fix is to stop
producing markup for layout reasons:

```js
// return data, not markup
function errorMessage(...parts) {
  return { message: parts[0], extra: parts.slice(1) };
}
```

and do line breaks with CSS, `white-space: pre-wrap`, which the codebase already uses elsewhere.

### 6. Add a rule, because vigilance already failed three times

This is the recommendation I care most about, and the history justifies it. A lint rule catches what
review missed three times running.

ESLint, if you're on a DOM-aware config:

```json
{
  "rules": {
    "no-unsanitized/property": "error",
    "no-unsanitized/method": "error"
  }
}
```

Or a Semgrep rule targeting the specific shape, a template literal reaching `innerHTML`:

```yaml
rules:
  - id: innerhtml-template-literal
    languages: [javascript, typescript]
    severity: ERROR
    message: >
      Template literal assigned to innerHTML. If any interpolated value can come
      from outside the app (filenames, contact names, notification text, share
      intents, clipboard), this is an XSS sink. Use textContent or build nodes.
    patterns:
      - pattern-either:
          - pattern: $EL.innerHTML = `...`
          - pattern: innerHTML={`...`}
      - pattern-not: $EL.innerHTML = DOMPurify.sanitize(...)
```

Allowlist the sanitising wrapper, fail everything else.

### 7. Encrypt the credentials

Separate from the XSS, and worth its own issue. Acode stores saved FTP and SFTP servers in
`localStorage.storageList`, with username and password embedded in the URL:

```
ftp://user:password@host:21/
```

The XSS is fixed, but any future WebView data leak still discloses every saved server password.

The notable part is that the app already knows how to do this properly. Its own account token lives in
`shared_prefs/acode_auth_secure.xml` using AndroidX Security Crypto. The capability is there, it just
isn't used for these secrets.

## Auditing your own hybrid app

Roughly a two-hour pass on a codebase you know.

**Step 1, enumerate the sinks:**

```bash
git grep -nE 'innerHTML|outerHTML|insertAdjacentHTML|document\.write' -- \
  '*.js' '*.ts' '*.jsx' '*.tsx' | grep -v node_modules | grep -v vendor
```

**Step 2, triage by the one useful question.** For each hit: does it interpolate, or pass a constant?
Constants are safe by construction, so stop reading. Only interpolations need a trace. That's what
makes a twenty-hit list finish in an afternoon.

**Step 3, trace each interpolated value back to its origin.** You're looking for values that entered
from the OS:

```bash
git grep -nE 'DISPLAY_NAME|OpenableColumns|getContactName|EXTRA_SUBJECT|EXTRA_TEXT|ClipData|getExtras'
```

For Cordova and Capacitor specifically, check anything arriving from `cordova-plugin-file`,
`@capacitor/filesystem`, contacts, share targets, and notification receivers.

**Step 4, check what your bridge exposes.** Severity is reachability times capability. The same XSS in a
WebView with no bridge is close to worthless. In a WebView exposing an SFTP client it's critical.
Enumerate what a script in your WebView can actually reach:

```js
Object.keys(window).filter((k) => typeof window[k] === "object" && window[k] &&
  !["document", "location", "navigator"].includes(k));
```

Acode's bridge grew between releases. `Terminal` and `iap` were added after 1.10.5. The severity of any
XSS in a hybrid app rises every time you add a plugin, even if that release introduced no XSS.

**Step 5, check whether past fixes touched sources or only sinks.** If a previous security fix only
guarded sinks, you almost certainly still have unfixed siblings. That's not hypothetical. It's exactly
how this bug survived two years and two rounds of fixes.

## Three things to take away

**Untrusted input on mobile is wider than you think.** A filename that arrived over a `content://` URI
is an arbitrary attacker-chosen string with no length or character limits. It looks like a filename and
it isn't one.

**Sink-side sanitisation is a single point of failure by design.** It requires every future sink to
remember. Escape at the source and new sinks inherit safety instead of reintroducing the bug.

**Severity is reachability times bridge capability.** "XSS in an editor" sounds cosmetic until you
enumerate what the JavaScript inherits. Here that was the SFTP client, the FTP client, the filesystem
and the stored server passwords, and that's what made a filename-rendering bug an 8.3.

---

The full advisory is
[GHSA-x24x-425w-326q](https://github.com/Acode-Foundation/Acode/security/advisories/GHSA-x24x-425w-326q),
and the fix is [PR #2559](https://github.com/Acode-Foundation/Acode/pull/2559).

[Part 1: What I found](/posts/acode-cross-app-scripting-what-i-found/) ·
[Part 2: How I found it](/posts/acode-cross-app-scripting-how-i-found-it/)
