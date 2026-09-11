---
title: "Why my first security PR should have been rejected"
date: 2026-09-18T00:00:00+05:00
categories: ["Research"]
tags: ["android", "appsec", "disclosure", "methodology", "cordova"]
description: "I reported plaintext SSH passwords in Acode, then wrote the fix. Five review rounds found four real bugs, and the maintainer's design beat mine."
summary: "I reported plaintext SSH passwords in Acode, then wrote the fix. Five review rounds found four real bugs, and the maintainer's design beat mine."
cover:
  image: "/img/posts/acode/acode-logo.webp"
  alt: "Acode logo"
  hiddenInSingle: true
ShowToc: true
TocOpen: false
---

While I was proving the impact of [the Find-File XSS](/posts/acode-cross-app-scripting-what-i-found/), I managed to read Acode's saved FTP and SFTP passwords out of `localStorage` in plaintext. It took a single read and no bridge call was needed at all.

That was a second finding in its own right, so I filed it and then went ahead and wrote the patch as well. It came to ten files and 367 lines added. The PR went through five rounds of review, after which the maintainer closed it in favour of his own approach.

He was right to do so, and the reason he was right is the interesting part of this story.

## The finding

`remoteStorage.addFtp` and `addSftp` build a connection URL and store it in `localStorage.storageList`. The URL is assembled in `src/utils/Url.js`:

```js
if (username && password) string += enc(username) + ":" + enc(password) + "@"
```

So the credential ends up embedded in the URL, and the whole thing lands in `localStorage`, which a WebView writes to disk in cleartext.

What made this worth reporting rather than simply shrugging at was that **Acode already knew how to do this properly.** Its own account token is kept in `shared_prefs/acode_auth_secure.xml`, encrypted using AndroidX Security Crypto. So the capability was already sitting there in the app, it had just not been applied to the server credentials.

That makes for a much easier report to write than "you should add encryption". It becomes "you have already added encryption over here, and these particular secrets have been left out of it".

## Choosing a channel

I reported this one as a [public issue (#2561)](https://github.com/Acode-Foundation/Acode/issues/2561) rather than as a private advisory, and that was a deliberate choice.

On a device which is not rooted, the app sandbox protects `localStorage`, so on its own this is not directly exploitable from remote. It is a matter of defence in depth, in the sense that it turns any *future* WebView data leak into a full credential disclosure. Something requiring local or root access to exploit does not really need to be embargoed.

The XSS and [the exported service RCE](/posts/acode-exported-service-rce/) were both directly exploitable, so both of those went in privately. The channel should be matched to the actual exploitability and not to how bad the bug happens to feel.

## Writing the fix, and the design discovery

My first plan was the obvious one, which was to strip the password out of the URL and keep it somewhere separate.

That turns out to break the app. `Url.parse(url).url` retains the password in the value it returns, and `helpers.getVirtualPath` regex-matches active URIs against the complete URL string. If you pull the password out, file paths stop displaying correctly.

So I changed my approach. The idea became to keep the URL intact in memory, just as it is at present, and to change only where the bytes come to rest on disk:

- A new `SecureStore.java` using EncryptedSharedPreferences with AES256-GCM
- A `system.secureSet` / `secureGet` / `secureRemove` bridge to reach it from JS
- A `secureStorageList.js` holding an in-memory cache, hydrated at boot, with a one-time migration of the legacy plaintext copy
- Eight read and write sites rerouted through it

The in-memory shape stayed identical to before, so nothing downstream needed changing. That felt like the right instinct at the time, which is to read the whole data flow before you design anything, and then pick the least invasive change which still moves the secret.

## Five rounds of review, four real bugs

I was not able to build Acode locally, as the Cordova toolchain is quite heavy and I never got it working. I therefore had to rely on the project's CI, its AI reviewer and the maintainers themselves. Every single round caught something real.

**Round 1.** Greptile: `SecureStore.java` was missing its `<source-file>` declaration in `plugin.xml`. It would not have compiled. Added the declaration.

**Round 2.** Greptile: I used `apply()` to write the encrypted copy. `apply()` is asynchronous. The migration then deleted the plaintext original. So on a crash or kill between the two, the secret is gone from both places. Changed to `commit()` and propagated the failure.

That is a data-loss bug sitting inside a security patch, and it is the sort of thing which gets shipped when somebody patches security without giving any thought to durability.

**Round 3.** bajrangCoder: my header comment over-explained the change, and in doing so documented the on-disk path of the cleartext file. Trimmed it. A comment that tells an attacker where to look is not a good comment.

**Round 4.** bajrangCoder found the worst one. My code had a fallback: if the secure store was unavailable, fall back to plaintext and report success. Then the migration, seeing success, deletes the localStorage copy. But EncryptedSharedPreferences encrypts its keys as well as its values, so the fallback write is not readable back. Credentials silently destroyed.

I removed the fallback altogether and made it fail closed instead. Cleartext should never be written, not even as a fallback, and if the secure store is unavailable then it ought to fail loudly.

**Round 5.** UnschooledGamer: moving `storageList` out of `localStorage` could break plugins that read it. I argued that it is not a public API, and that plugins reading it *is* the vulnerability, then offered a sanitised `acode.getStorageList()` accessor as a compromise.

Greptile was right five times out of five. Each one was a real bug in my code, and all of them were caught before any user ever saw them.

## Then the maintainer closed it

bajrangCoder pointed me at [#2694](https://github.com/Acode-Foundation/Acode/pull/2694), his own work in progress, and said he had a different solution: profiles.

I read through it, and it is better than mine for two reasons.

**The URL carries nothing at all.** His approach stores `sftp://profile-<uuid>/path`, so there is no hostname, no username and no port left anywhere in `localStorage`. Mine had only removed the password, which meant `user@host:port` was still sitting there in plaintext. I had fixed the worst field and left the rest of the target's attack surface lying on disk.

**Secrets never reach the JS thread.** This is the reason which actually settles the matter.

My design exposed `system.secureGet` to JavaScript, which meant any JS running in Acode's origin could call it and read the passwords straight back out. A malicious plugin would be able to do this, and so, of course, would an XSS.

I had just spent a fortnight proving that you can get arbitrary JavaScript running in Acode's origin from a zero-permission app. That was the entire point of the [Find-File finding](/posts/acode-cross-app-scripting-what-i-found/). Acode serves its whole UI from one origin, so injected JS is same-origin with the app and reaches the full bridge.

My fix had moved the credentials from a place where XSS could read them to a place where XSS could simply ask for them. Against the very attacker I had just finished demonstrating, it bought very little.

The maintainer's design does not suffer from this, because the secret never crosses into JavaScript in the first place. The native side holds it and uses it there, and there is no bridge method available to call.

bajrangCoder's reply on the thread was blunter than mine and correct: my URL-stripping approach was error-prone, and secret material should not come to the JS thread at all, otherwise a plugin can do malicious things with it.

## What I actually take from this

**Fixing is a completely separate skill from finding.** I found the bug in one afternoon, whereas the patch took a week and was still wrong in four places and second best architecturally. Being good at finding vulnerabilities does not make a person good at fixing them, and pretending otherwise is how you end up shipping a data-loss bug inside a security patch.

**Think about your fix using your own threat model.** I had a working exploit for arbitrary JS in that origin, and I then went and designed a fix which was reachable from arbitrary JS in that same origin. Nobody needed to point out that these two were incompatible, I simply never held both thoughts in my head at the same time. When you write a patch, do run your own PoC against it mentally before opening the PR.

**A closed PR is not a failed contribution.** The issue is still open, the maintainer has confirmed he will apply the same treatment to the FTP path after #2694 merges, and the credential storage is getting fixed properly rather than adequately. That is the outcome I wanted. My patch not being the vehicle for it is a much smaller thing than I would have guessed before I started.

**The review is itself the contribution.** I could not even compile the project, and in the end that did not matter very much. What moved a first PR forward was responding to each review point quickly, honestly and correctly, and conceding the point when somebody else has a better design is part of that rather than an exception to it.

## Related

- [Cross-app scripting in Acode, part 1: the bug](/posts/acode-cross-app-scripting-what-i-found/), the finding that surfaced these credentials
- [Part 3: fixing it](/posts/acode-cross-app-scripting-how-to-prevent-it/), on why sink-side patches keep failing in this codebase
- [Issue #2561](https://github.com/Acode-Foundation/Acode/issues/2561) and [PR #2566](https://github.com/Acode-Foundation/Acode/pull/2566)
