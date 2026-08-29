---
title: "{{ replace .Name "-" " " | title }}"
date: {{ .Date }}
draft: true
categories: ["Research"]
tags: []
description: ""
ShowToc: true
TocOpen: false
---

Two-sentence framing. What the bug class is, why it recurs.

## The mechanic

Named sink, named source, why the trust boundary is misplaced.

```js
// minimal code showing the bad shape
```

## Where it shows up

- Product or codebase where you saw this, redacted where needed
- Another
- Another

## Fix

```js
// minimal code showing the fix
```

What the fix actually does at the trust-boundary level. Not "sanitize input" — the specific transformation.

## Grep or Semgrep query

```bash
git grep -nE 'pattern' -- '*.js' '*.ts'
```

## Related

- CVE / GHSA / bug report links
- Prior writeups on the same class
