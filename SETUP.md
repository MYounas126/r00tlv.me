# Setup — Hugo + PaperMod → Cloudflare Pages → r00tlvr.me

Supersedes the Chirpy/Jekyll runbook in the Obsidian vault. Three things in
that version were wrong and are corrected here:

1. There is **no Domain.com offer** in the GitHub Student Pack. Free domains
   come from **Name.com**, **Namecheap** (`.me`) and **.TECH**.
2. Hosting is **Cloudflare Pages**, so the GitHub Pages `185.199.x.x`
   A records do not apply.
3. `.dev` is not being used. The domain is **r00tlvr.me**.

## Prerequisites

Already done on this machine:

- `hugo v0.165.0+extended` (`brew install hugo`)
- `git 2.50.1`, `gh 2.98.0`
- PaperMod pinned as a submodule at `themes/PaperMod`

## Local development

```bash
cd ~/Downloads/Project/blog
hugo server                # http://localhost:1313
```

Production build:

```bash
hugo --gc --minify         # output in ./public
```

## Writing a post

Archetypes are wired up, so use the right `--kind`:

```bash
hugo new content posts/htb-machinename.md   --kind htb
hugo new content posts/some-bug-class.md    --kind research
hugo new content posts/pwncollege-week3.md  --kind notes
```

Each is created with `draft: true`. Remove that line to publish. Preview
drafts with `hugo server -D`.

Do **not** date-prefix Hugo filenames the way Jekyll wants. Hugo does not
strip the prefix, so `2026-09-01-foo.md` becomes the URL `/posts/2026-09-01-foo/`.
The date lives in frontmatter only.

## Frontmatter reference

```yaml
---
title: "Post title"
date: 2026-08-29T20:00:00+05:00
categories: ["Writeups"]          # one of: Writeups, Research, HTB, Notes, pwn.college
tags: ["mobile", "xss"]           # fine-grained, several per post
description: "One or two sentences. Used for OG tags and search."
weight: 1                         # optional: pins the post to the top of the list
ShowToc: true
TocOpen: false
hiddenInRss: true                 # optional: keep a page out of the feed
---
```

## Step 1 — Register the domain (free)

1. Sign in to the Student Pack: https://education.github.com/pack
2. Find the **Namecheap** offer — free `.me` registration for 1 year.
3. Register **r00tlvr.me**.

(Name.com's offer covers 25+ extensions including `.app`, `.live`, `.studio`
if you ever want a second one. .TECH gives a free `.tech`.)

## Step 2 — Push to GitHub

```bash
gh repo create MYounas126/<repo-name> --public --source=. --remote=origin
git push -u origin main
```

The theme is a submodule, so anyone cloning needs
`git clone --recurse-submodules`. Cloudflare handles this automatically
because `.gitmodules` uses an HTTPS URL.

## Step 3 — Cloudflare Pages

1. https://dash.cloudflare.com → **Workers & Pages** → **Create** → **Pages**
   → **Connect to Git** → pick the repo.
2. Build settings:
   - Framework preset: **Hugo**
   - Build command: `hugo --gc --minify`
   - Build output directory: `public`
   - Environment variable: `HUGO_VERSION` = `0.165.0`

   The `HUGO_VERSION` variable is required. Cloudflare's default Hugo is
   older than PaperMod's `min_version = 0.146.0` and the build will fail
   without it.
3. Deploy. Confirm the `*.pages.dev` URL renders before touching DNS.

## Step 4 — Point the domain at Cloudflare

1. Cloudflare dash → **Add a site** → `r00tlvr.me` → Free plan.
2. Cloudflare gives you two nameservers.
3. Namecheap → Domain List → Manage → **Nameservers** → *Custom DNS* →
   paste both Cloudflare nameservers → save.
4. Wait for Cloudflare to report the zone as active (usually minutes,
   occasionally a few hours).
5. Pages project → **Custom domains** → add `r00tlvr.me` and `www.r00tlvr.me`.
   Cloudflare creates the DNS records itself — you do not add A records.

## Step 5 — HTTPS

Universal SSL provisions automatically once the zone is active, typically
within 15 minutes. Then set SSL/TLS mode to **Full (strict)**.

Verify:

```bash
curl -sI https://r00tlvr.me/ | head -1
curl -s  https://r00tlvr.me/rss.xml | head -5
```

## Step 6 — Medium canonicals

For each of the six imported articles, on Medium:
Story Settings → Advanced → Custom canonical URL → the new r00tlvr.me URL.
Do not delete the Medium posts.

## Verify

- `https://r00tlvr.me/` — post list
- `https://r00tlvr.me/posts/anatomy-of-ghsa-x24x-425w-326q/` — GHSA writeup
- `https://r00tlvr.me/about/`
- `https://r00tlvr.me/rss.xml`
- `https://r00tlvr.me/search/`
- `https://r00tlvr.me/tags/` and `/categories/`

## Troubleshooting

- **Cloudflare build fails on a template error** — almost always `HUGO_VERSION`
  unset or too old. PaperMod needs ≥ 0.146.0.
- **Theme directory empty on Cloudflare** — submodule not fetched; confirm
  `.gitmodules` uses `https://`, not `git@`.
- **Post doesn't appear** — either `draft: true` is still set, or the date is
  in the future (`buildFuture` is deliberately `false`).
- **Search returns nothing** — `/index.json` must be reachable; it is produced
  by `[outputs] home = ["HTML", "RSS", "JSON"]`.
