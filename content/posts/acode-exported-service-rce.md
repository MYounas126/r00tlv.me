---
title: "Acode: an exported service RCE I found too late"
date: 2026-09-11T00:00:00+05:00
categories: ["Research"]
tags: ["android", "mobile", "rce", "disclosure", "methodology"]
description: "An exported Android service gave any installed app a shell as Acode. I found it and proved it, but it had already been patched on main six weeks earlier."
summary: "An exported Android service gave any installed app a shell as Acode. I found it and proved it, but it had already been patched on main six weeks earlier."
cover:
  image: "/img/posts/acode/acode-logo.webp"
  alt: "Acode logo"
  hiddenInSingle: true
ShowToc: true
TocOpen: false
---

While I was writing up [the Find-File XSS](/posts/acode-cross-app-scripting-what-i-found/) in Acode, I thought I should look for a second bug in the same app. I found one, and it was worse than the first. Unfortunately it had already been fixed six weeks before I even started, so my report was closed as a duplicate.

This post is about that bug, and about the one check I should have run before spending a weekend on it.

## The bug in one paragraph

Acode was shipping a `TerminalService` declared as `exported="true"` without any permission guard on it. Any installed app could bind to this service, send it a message, and have it run whatever shell command it liked as Acode's own user. The attacking app needed no permissions of its own, and the victim did not have to do anything.

## Finding it took two commands

There was nothing clever about this part. Looking at exported components is the first thing anyone does with an APK, and it is two commands.

```console
$ apktool d acode.apk -o out
$ grep 'android:exported="true"' out/AndroidManifest.xml
```

`TerminalService` came back as exported. More importantly it came back without any `android:permission` attribute, which means the Android framework will happily let anything on the device bind to it.

Now, an exported service is not automatically a bug. Many apps export services on purpose and there is nothing wrong with that. What matters is what the service does with the messages it receives, and whether it bothers to check who sent them.

## Tracing what it does with your message

I opened the APK in jadx and followed the Messenger through.

`onBind` returns the Messenger to whoever asks for it, without inspecting the caller at all. The handler then reads a `what` code from the incoming message, and in case 5 it pulls a `cmd` string directly out of the Bundle:

```java
// handleMessage, what == 5
String cmd = data.getString("cmd");
// ...
ProcessManager.createProcessBuilder(...)
    // -> new ProcessBuilder("sh", "-c", cmd)
```

That command then goes to `ProcessBuilder("sh","-c", cmd)`, and stdout is returned to the caller's own Messenger, so the attacker also gets the output back.

The next thing I wanted to know was whether there was any caller check anywhere in the service:

```console
$ grep -rn "getCallingUid\|checkPermission\|checkCallingPermission" src/
$
```

Nothing came back. There is no verification anywhere of who is on the other end of that binding.

So the full chain is quite short. Any app binds to the service, sends `what=5` along with a command string, and receives arbitrary shell execution as Acode together with the output. There is no gate at any point in it.

## Proving it

I wrote a small app with no permissions at all, bound the service from it and sent a command. The useful part of the log is the identity that the shell ended up running as:

```
BOUND to com.foxdebug.acode/.rk.exec.terminal.TerminalService (no permission required)
REPLY isSuccess=true
uid=10229(u0_a229) ... context=u:r:untrusted_app_34:s0:c229
```

Here `uid=10229` is Acode. My attacking app was running under a different uid, so the command had executed inside Acode's sandbox and with Acode's permissions, on behalf of an app that held nothing more than `INTERNET`.

This is a good deal worse than the XSS I had reported a few days earlier. For the XSS, the victim had to open a file and then press Ctrl-P. Here the victim does not have to do anything at all.

Scored as CVSS v4.0:

```
AV:L/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H
```

The metric that pushes it above the XSS is `UI:N`, since there is no user interaction to wait for.

## Where I went wrong

I did check for prior art before reporting, which is the right instinct, but I checked in the wrong order. I looked for published advisories and open issues, and I did not look at the commit history.

The bug had in fact been fixed on `main` by [PR #2442](https://github.com/Acode-Foundation/Acode/pull/2442) on 3 July 2026. It was a one-line change, `exported="true"` becoming `exported="false"`.

The version I was testing was v1.12.6, tagged on 18 June 2026, which is before that fix. No stable release had shipped the fix yet either.

So two things were true at the same time. Real users on the current release had been exposed for roughly six weeks, and the fix commit had been sitting in public for all of that period, which meant anybody reading the repository could see what the problem was.

Someone else reported it before me and my report was closed as a duplicate. The advisory that came out of it, [GHSA-wm94-wp33-43gx](https://github.com/Acode-Foundation/Acode/security/advisories/GHSA-wm94-wp33-43gx), credits `RohitKushvaha01` and `michael-benedetti`, and not me.

## The actual lesson

The obvious lesson here is to check whether something is already fixed, which is true enough but too vague to be of much use.

The more useful way to put it is that **a public fix commit is an advertisement for the vulnerability**. The moment a maintainer pushes `exported="true"` to `exported="false"` with a message along the lines of "fix(security) critical security issue", they have published a pointer to a live bug in every release made before that commit. Anyone watching the repository can read the diff and write up a report within an hour.

This is why fixed-but-unreleased bugs are the most heavily contested findings in open source. The person you are competing with is not the maintainer. It is everybody else who happened to read the same commit.

The practical consequence is that this check belongs before the work, not before the report:

```console
$ git log --oneline --all -- path/to/suspicious/file
$ git log -S 'exported="true"' --oneline
```

And if you already have a candidate and want to know whether the fix made it into the release you are actually holding:

```console
$ git merge-base --is-ancestor <fix-commit> <release-tag> && echo "already in this release"
```

If the fix is present on `main` but not in your release, then you have found something real which will most likely be reported by somebody else within the week. It is better to treat that as a race you are going to lose, and put your time into a sink that has no fix commit anywhere against it. The [Find-File XSS](/posts/acode-cross-app-scripting-what-i-found/) was that sort of sink, which is why that one remained mine.

## What I would do differently

Nothing at all about the analysis itself. The manifest grep, the jadx trace, the PoC app and the proof of impact were all the work I actually wanted to be doing, and I would go about it the same way again.

The mistake was one command's worth of prior art, run at the wrong point. What I checked was whether the bug was publicly known. What I should have checked was whether it had already been quietly fixed in the open, which is a different question and needs a different command.

A duplicate report costs nothing except time. But when you are doing this alongside a full-time job, time is more or less the entire budget.

## Related

- [Cross-app scripting in Acode, part 1: the bug](/posts/acode-cross-app-scripting-what-i-found/) is the finding in the same app that did stay mine
- [Part 2](/posts/acode-cross-app-scripting-how-i-found-it/) covers the patch-diffing method that found it
- [PR #2442](https://github.com/Acode-Foundation/Acode/pull/2442), the one-line fix that got there before me
