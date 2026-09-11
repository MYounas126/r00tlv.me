---
title: "An AI agent playbook for vulnerability research"
date: 2026-09-25T00:00:00+05:00
categories: ["Research"]
tags: ["methodology", "appsec", "disclosure", "automation"]
description: "The operating brief I give a coding agent before it touches a target: six rules it cannot break, eleven phases, and what it does versus what I decide."
summary: "The operating brief I give a coding agent before it touches a target: six rules it cannot break, eleven phases, and what it does versus what I decide."
cover:
  image: "/img/posts/re/mechanical-turk.webp"
  alt: "Racknitz's 1789 cutaway engraving of the Mechanical Turk, showing the human operator concealed inside the cabinet"
  hiddenInSingle: true
ShowToc: true
TocOpen: false
---

I use a coding agent for vulnerability research, though not for finding bugs on my behalf, as it is not reliably good at that. I use it for the breadth work which I am slow at, while I hold on to the judgement calls myself.

What follows is the brief I paste in before handing it a target. It exists because an agent with no constraints on it will quite happily suggest logging into somebody else's server using a credential you have only just recovered, and that is not the sort of mistake you are allowed to make twice.

Running this against Acode produced one credited advisory, one duplicate and one closed PR. The specifics of all three are written up separately: [the XSS](/posts/acode-cross-app-scripting-what-i-found/), [the RCE I lost](/posts/acode-exported-service-rce/), and [the patch that got rejected](/posts/first-security-pr-rejected/).

## Why write it down at all

The agent is quick at the things which I am slow at, such as enumerating every sink in a codebase, tracing a value through six different files, drafting a patch, writing a PR body, or replying to a review comment at midnight.

Where it is poor is at the things which actually matter in this line of work. It has no idea where the scope boundary lies. It will treat a recovered credential as an invitation to use it. It will suggest filing a public issue for an unpatched remote-code-execution bug, simply because a public issue is the more common shape in its training data.

The brief therefore does one job only. It encodes the lines which must not be crossed, so that I can hand over the breadth work without having to babysit every step of it.

## The brief

Paste the following in, and then give it a target.

```
ROLE: You are my open-source security research + contribution partner. We find vulnerabilities in
open-source software, prove them on my own devices, disclose them responsibly, and contribute fixes.
This is authorized, defensive, educational security work.

TARGET: <repo URL and/or installed app + version>. I have the source and a private test device/emulator.

NON-NEGOTIABLE RULES (never break, even if I ask in the heat of the moment):
1. Test ONLY on my own devices/emulator against public builds. Never touch third-party infrastructure.
2. Prove impact by READING/ENUMERATING with dummy data. Never run remote commands, exfiltrate data,
   mark files executable, build persistence, or log into a server I don't own, even with a credential
   in hand. The app author cannot authorize access to other people's servers.
3. Disclose UNPATCHED, directly-exploitable bugs PRIVATELY (GitHub Security advisory), never as a
   public issue. Public issues are only for defence-in-depth items that need local/root access.
4. Before reporting, check it isn't already fixed-on-main, already reported, or already CVE'd.
5. Write everything I'll post (advisory, PR body, comments) in MY plain first-person voice, not
   AI-polished, no "as an AI", no over-tidy structure. Be honest about what wasn't tested.
6. For anything outward-facing (push, PR, public comment), DRAFT it and show me first. I say yes/no.

WORKFLOW (run in order; report at each phase, wait for my go on transitions that push):
  0. Target selection: confirm open-source, high-value, ideally with a recent security fix.
  1. Recon: clone + checkout the release tag; pull and validate the shipped artefact; map the
     manifest (exported components, intent-filters, providers, permissions).
  2. Patch-diff + enumerate sinks: find the vendor's recent security fix, show EXACTLY what it
     touched, determine whether it fixed the source or only some sinks, then list every OTHER sink
     the same untrusted value reaches. Prefer sinks with NO fix commit anywhere.
  3. Trace source to sink: quote the code path. The question is "does the encoding match the context?"
  4. Trigger engineering: what state is needed, which parts I can drive from outside, which primitive
     gives it. Propose the minimal reliable trigger.
  5. Dynamic PoC: build a minimal PoC then a realistic zero-permission delivery; verify objectively
     with log markers, logcat, or the remote debugger.
  6. Impact: enumerate the bridge/capabilities; demonstrate confidentiality and integrity with DUMMY
     data only; score CVSS with explicit reasoning per metric.
  7. Prior art: published advisories? private reporting enabled? existing issue or PR? existing CVE?
  8. Disclosure: pick the channel by exploitability; draft the report (versions, source to sink, PoC,
     CVSS with reasoning, CWE, suggested fix, explicit CVE request). Show me before sending.
  9. Fix: trace the FULL data flow before designing; least-invasive design; migrations durable
     (commit() not apply()) and fail-closed (never silently downgrade to a weaker store); reuse the
     project's existing mechanisms. Run the project's linter locally so CI is green.
 10. PR: fork, branch, push, open the PR; honest body; then help me respond to every review point
     quickly, correctly, graciously. Rely on the project's CI and AI reviewers for what I can't build.
 11. Recognition: request the CVE; set the reward expectation honestly (credit, not cash, for
     third-party OSS).

OUTPUT STYLE: report each phase concisely; give me commands to run and expected output; when unsure,
give a recommendation not a survey; verify claims against the actual code, don't assume.
```

## The rules that earn their place

Of these, rules 1 and 2 are the only ones I would describe as non-negotiable in a moral sense rather than merely a practical one.

Rule 2 is the one which actually gets tested. While working on Acode I recovered stored SFTP credentials for a server. These credentials were real, in the sense that they were correctly formatted and would have worked. Using them would have amounted to unauthorised access to a third party's infrastructure, and the fact that a vulnerability in Acode had handed them to me does not change that in the slightest. The author of the app is able to authorise me to test the app itself. They are not able to authorise me to log into somebody else's server.

The impact proof therefore used a dummy credential pointed at `198.51.100.23`, which is RFC 5737 TEST-NET-2 and is non-routable. The report demonstrates that the credentials are readable, without demonstrating that I went and read anybody's.

Rule 3 matters because the agent's default instinct is simply wrong on this point. Filing a public issue for an unpatched and directly exploitable bug amounts to a zero-day drop with some extra steps attached. The heuristic I gave it is based on exploitability, so anything directly exploitable goes private while defence-in-depth items may go public. That is how [the XSS](/posts/acode-cross-app-scripting-what-i-found/) ended up as a private advisory and [the plaintext credentials](/posts/first-security-pr-rejected/) ended up as a public issue.

Rule 4 is there because I ignored it on one occasion and it cost me a finding, as described in [the RCE writeup](/posts/acode-exported-service-rce/).

Rule 5 sounds cosmetic but it really is not. A report which reads as machine-generated is going to be treated as machine-generated. Maintainers these days are drowning in low-quality automated reports, and the quickest way to be ignored is to sound like one of them. Being honest about what you did not test will do far more for your credibility than any amount of polish.

## Where it actually helps, and where it does not

| Agent does well | I keep |
| :-- | :-- |
| Enumerating sinks across a codebase | Deciding which sink is worth the week |
| Tracing a value through many files | Trigger engineering |
| Drafting the patch | Choosing the fix design |
| PR mechanics and review replies | The yes or no on anything outward-facing |
| Patch-diffing a security commit | Scope discipline |
| Writing the report in my voice | The disclosure channel |

The clearest example of this split is the command which found the XSS. That was the agent's contribution, being a set difference between the files containing `innerHTML` and the files importing DOMPurify. It was mechanical and quick, and I would have got round to writing it myself eventually.

Working out that a `content://` display name carries no length or character limit, and that Ctrl-P is a trigger which users hit all the time rather than something you need to socially engineer, was my own contribution. That is the part which turned a candidate into a High.

## Two failure modes worth naming

**Trusting a finding which it has not traced from end to end.** An agent will tell you that a sink is reachable with a good deal more confidence than it has actually earned. Make it quote the code path for you, from source right through to sink, with the file and line numbers. If it cannot manage that, then it is guessing.

**Assuming that the patch compiles.** I was unable to build Acode locally, and my patch turned out to be missing a `<source-file>` declaration, so it would not have compiled at all. The project's own CI and its AI reviewer caught that along with three other genuine bugs. It is better to lean on the target project's own verification than on the agent's confidence.

## The honest summary

None of this is automation. It is not a case of pointing the agent at a repository and collecting CVEs, and anybody selling that idea has not tried it against a real target.

What it is, rather, is a way of spending your limited hours on the parts which need a person: deciding what to look at, working out what the trigger actually is, judging how far the proof ought to go, and knowing where the line sits. The agent does the reading.

## Related

- [Cross-app scripting in Acode, part 2: finding it](/posts/acode-cross-app-scripting-how-i-found-it/) walks the patch-diff method in detail
- [Acode: an exported service RCE I found too late](/posts/acode-exported-service-rce/) is what skipping phase 7 costs
- [Why my first security PR should have been rejected](/posts/first-security-pr-rejected/) is phases 9 and 10 going wrong in an instructive way

---

Image: [Racknitz's cutaway of the Mechanical Turk, 1789](https://commons.wikimedia.org/wiki/File:Racknitz_-_The_Turk_3.jpg) by Joseph Racknitz, Humboldt University Library. Public domain. Cropped and resized.
