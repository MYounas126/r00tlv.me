---
title: "Cross-app scripting in Acode via innerHTML filename sink"
date: 2026-08-29T20:00:00+05:00
categories: ["Writeups"]
tags: ["mobile", "cordova", "xss", "disclosure"]
description: "Acode, a Cordova-based Android editor with 1M+ installs, shipped a stored XSS via an innerHTML sink on filenames, reachable cross-app through Android intents. GHSA-x24x-425w-326q, CVSS 8.3."
summary: "Acode, a Cordova-based Android editor with 1M+ installs, shipped a stored XSS via an innerHTML sink on filenames, reachable cross-app through Android intents. GHSA-x24x-425w-326q, CVSS 8.3."
weight: 1
ShowToc: true
TocOpen: false
---

Acode is a Cordova-based Android code editor with 1M+ installs. It shipped a stored XSS via an `innerHTML` sink on filenames, reachable cross-app through Android intents. Advisory: [GHSA-x24x-425w-326q](https://github.com/Acode-Foundation/Acode/security/advisories/GHSA-x24x-425w-326q). CVSS 8.3, patched in 1.12.9.

## The sink

Find-File palette renders suggestion rows:

```javascript
function renderSuggestions(matches) {
  const container = document.querySelector('.inputhints');
  container.innerHTML = matches
    .map(m => `<li class="hint" data-path="${m.path}">${m.name}</li>`)
    .join('');
}
```

`m.name` is the workspace filename, unescaped, into `innerHTML`.

## PoC

Create a file:

```
</li><img src=x onerror=alert(document.domain)>.txt
```

Open Find-File palette. Payload fires in the WebView.

Debugging setup: sideload the APK, `chrome://inspect` over ADB to attach DevTools to the WebView.

## Cross-app delivery

Acode registers an intent filter for opening files from other apps. Any installed app can send a file with an attacker-controlled filename via `Intent.ACTION_VIEW`. No permission, no user prompt. Acode stores the filename in its recents. Next time Find-File is opened, payload fires.

Delivery vectors seen in similar Cordova apps:

- Compromised or malicious file manager
- Share targets in messengers
- Downloader apps
- Any app with an "open in editor" affordance

## Impact

WebView has the Cordova JS bridge — filesystem, plugin APIs, `fetch()`. Not cookie theft. Arbitrary code execution as Acode with Acode's file permissions:

- Read every file in workspace (SSH keys, .env files, source)
- Write to any open file
- Invoke plugin APIs
- Exfiltrate over `fetch()` to any host

## Fix

Escape at the sink:

```javascript
const esc = (s) => s.replace(/[&<>"']/g, c => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));

container.innerHTML = matches
  .map(m => `<li class="hint" data-path="${esc(m.path)}">${esc(m.name)}</li>`)
  .join('');
```

Or drop `innerHTML` for `textContent` + `createElement`.

Acode took option one. Shipped in 1.12.9.

## Pattern

Any string from the OS into `innerHTML` without escaping is a stored XSS sink in a Cordova/Capacitor/WebView app. OS strings include filenames, contact names, notification titles, share intent subjects, clipboard content.

Grep query for the same class in your own hybrid apps:

```bash
git grep -nE 'innerHTML\s*=' -- '*.js' '*.ts'
```

Then trace the string back. If it originates from `cordova-plugin-file`, `capacitor-filesystem`, `contacts`, `share`, or a notification receiver — the bug is worth checking for.

## Timeline

| | |
|---|---|
| 2026-08-11 | Bug found |
| 2026-08-14 | Disclosed via GitHub Security Advisory draft |
| 2026-08-19 | Maintainer confirmed on 1.12.6 |
| 2026-08-21 | Patched in 1.12.9 |
| 2026-08-22 | Advisory published as GHSA-x24x-425w-326q |
