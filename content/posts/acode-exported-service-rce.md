---
title: "Acode: an exported service RCE I found too late"
date: 2026-09-11T00:00:00+05:00
categories: ["Research"]
tags: ["android", "mobile", "rce", "disclosure", "methodology"]
description: "An exported Android service handed any installed app a shell as Acode. I found it, proved it, and got nothing: it was patched on main six weeks earlier."
summary: "An exported Android service handed any installed app a shell as Acode. I found it, proved it, and got nothing: it was patched on main six weeks earlier."
cover:
  image: "/img/posts/acode/acode-logo.webp"
  alt: "Acode logo"
  hiddenInSingle: true
ShowToc: true
TocOpen: false
---

While I was writing up [the Find-File XSS](/posts/acode-cross-app-scripting-what-i-found/) in Acode, I went looking for a second bug in the same app. I found one that was worse. Then I discovered it had already been fixed, six weeks before I started, and my report closed as a duplicate.

This is that bug, and the one-line check that would have told me not to bother.

## The bug in one paragraph

Acode shipped a `TerminalService` declared `exported="true"` with no permission guard. Bind to it from any installed app, send it a message, and it runs whatever shell command you supply as Acode's own user. No permissions, no user interaction, no root.

## Finding it took two commands

I was not being clever here. Exported-component analysis is the first thing you do to an APK, and it is two commands.

```console
$ apktool d acode.apk -o out
$ grep 'android:exported="true"' out/AndroidManifest.xml
```

`TerminalService` came back exported. More importantly, it came back with no `android:permission` attribute, which means the Android framework will let anything on the device bind to it.

An exported service on its own is not a bug. Plenty of apps export services deliberately. The question is always what the service does with the messages it receives, and whether it checks who sent them.

## Tracing what it does with your message

Opened the APK in jadx and followed the Messenger.

`onBind` returns the Messenger to any caller. No caller inspection at all. The handler reads a `what` code from the incoming message, and case 5 pulls a `cmd` string straight out of the Bundle:

```java
// handleMessage, what == 5
String cmd = data.getString("cmd");
// ...
ProcessManager.createProcessBuilder(...)
    // -> new ProcessBuilder("sh", "-c", cmd)
```

Then it hands the command to `ProcessBuilder("sh","-c", cmd)` and returns stdout to the caller's own Messenger, so the attacker gets the output back.

The thing I actually looked for next was any caller check at all:

```console
$ grep -rn "getCallingUid\|checkPermission\|checkCallingPermission" src/
$
```

Empty. Nothing verifies who is on the other end of that binding.

So the chain is: any app binds, sends `what=5` with a command string, gets arbitrary shell execution as Acode plus the output. There is no gate anywhere along it.

## Proving it

I wrote a zero-permission app that bound the service and sent a command. The interesting part of the log is the identity the shell ran as:

```
BOUND to com.foxdebug.acode/.rk.exec.terminal.TerminalService (no permission required)
REPLY isSuccess=true
uid=10229(u0_a229) ... context=u:r:untrusted_app_34:s0:c229
```

`uid=10229` is Acode. My attacking app had a different uid. So the command executed inside Acode's sandbox, with Acode's permissions, at the request of an app that held nothing but `INTERNET`.

That is worse than the XSS I had just reported. The XSS needed the victim to open a file and then press Ctrl-P. This needs the victim to do nothing at all.

Scored as CVSS v4.0:

```
AV:L/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H
```

The metric that moves it above the XSS is `UI:N`. No user interaction. Nothing to wait for.

## Where it went wrong

I checked prior art before reporting, which is the right instinct, but I checked it in the wrong order. I looked for published advisories and open issues. I did not check the commit history.

The bug had been fixed on `main` by [PR #2442](https://github.com/Acode-Foundation/Acode/pull/2442) on 3 July 2026. A one-line change, `exported="true"` to `exported="false"`.

The version I was testing, v1.12.6, was tagged on 18 June 2026. Before the fix. And no stable release had shipped the fix yet.

So both things were true at once. Real users on the current release were exposed for roughly six weeks. And the fix commit had been sitting in public the whole time, which meant anyone reading the repository could see exactly what had been wrong.

Someone else reported it first. My report closed as a duplicate. The advisory that came out of it, [GHSA-wm94-wp33-43gx](https://github.com/Acode-Foundation/Acode/security/advisories/GHSA-wm94-wp33-43gx), credits `RohitKushvaha01` and `michael-benedetti`. Not me.

## The lesson, which is not the obvious one

The obvious lesson is "check whether it is already fixed". True, but too vague to act on.

The sharper version is this: **a public fix commit advertises the vulnerability.** The moment a maintainer pushes `exported="true"` to `exported="false"` with a message like "fix(security) critical security issue", they have published a pointer to a live bug in every release that predates it. Anyone watching the repository can read that diff and write a report in an hour.

Which means fixed-but-unreleased bugs are the most contested findings in open source. You are not racing the maintainer. You are racing everyone else who read the same commit.

So the check has to come before the work, not before the report:

```console
$ git log --oneline --all -- path/to/suspicious/file
$ git log -S 'exported="true"' --oneline
```

And if you already have a candidate and want to know whether the fix is in the release you are holding:

```console
$ git merge-base --is-ancestor <fix-commit> <release-tag> && echo "already in this release"
```

If the fix exists on `main` but not in your release, you have found something real that will probably be reported by someone else this week. Treat it as a race you are likely to lose, and spend your time on a sink with no fix commit anywhere. That is what the [Find-File XSS](/posts/acode-cross-app-scripting-what-i-found/) was, and it is why that one stayed mine.

## What I would have done differently

Nothing about the analysis. The manifest grep, the jadx trace, the PoC app, the impact proof: all of that was the work I wanted to be doing, and I would do it the same way again.

The mistake was one command's worth of prior art, run at the wrong time. I checked whether the bug was *known publicly*. I should have checked whether it was *already fixed privately in the open*, which is a different question with a different command.

Reporting a duplicate costs you nothing but time. But time is the whole budget when you are doing this around a job.

## Related

- [Cross-app scripting in Acode, part 1: the bug](/posts/acode-cross-app-scripting-what-i-found/) is the finding in the same app that did stay mine
- [Part 2](/posts/acode-cross-app-scripting-how-i-found-it/) covers the patch-diffing method that found it
- [PR #2442](https://github.com/Acode-Foundation/Acode/pull/2442), the one-line fix that beat me to it
