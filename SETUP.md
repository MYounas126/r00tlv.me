# Setup, Hugo + PaperMod → Cloudflare Pages → r00tlv.me

Supersedes the Chirpy/Jekyll runbook in the Obsidian vault. Three things in
that version were wrong and are corrected here:

1. There is **no Domain.com offer** in the GitHub Student Pack. Free domains
   come from **Name.com**, **Namecheap** (`.me`) and **.TECH**.
2. Hosting is **Cloudflare Pages**, so the GitHub Pages `185.199.x.x`
   A records do not apply.
3. `.dev` is not being used. The domain is **r00tlv.me**.

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

## Step 1, Register the domain (free)

1. Sign in to the Student Pack: https://education.github.com/pack
2. Find the **Namecheap** offer, free `.me` registration for 1 year.
3. Register **r00tlv.me**.

(Name.com's offer covers 25+ extensions including `.app`, `.live`, `.studio`
if you ever want a second one. .TECH gives a free `.tech`.)

## Step 2, Push to GitHub

```bash
gh repo create MYounas126/<repo-name> --public --source=. --remote=origin
git push -u origin main
```

The theme is a submodule, so anyone cloning needs
`git clone --recurse-submodules`. Cloudflare handles this automatically
because `.gitmodules` uses an HTTPS URL.

## Step 3, Cloudflare Pages

1. https://dash.cloudflare.com, **Workers & Pages**, **Create**, **Pages**,
   **Connect to Git**, pick `MYounas126/r00tlv.me`.
2. Build settings:

   | Field | Value |
   |---|---|
   | Framework preset | Hugo |
   | Build command | `hugo --gc --minify` |
   | Build output directory | `public` |
   | Root directory | *(leave blank)* |

3. Environment variable, **required**:

   | Name | Value |
   |---|---|
   | `HUGO_VERSION` | `0.165.0` |

   Cloudflare's default Hugo is older than PaperMod's `min_version = 0.146.0`.
   Without this the build fails on template syntax.

4. Deploy, then confirm the `*.pages.dev` URL renders before touching DNS.

### Submodule warning

The theme is a git submodule. Cloudflare fetches submodules automatically because
`.gitmodules` uses an HTTPS URL, but if it ever fails to, **Hugo does not error**.
It exits 0 and emits a site with no `index.html` at all. The CI workflow guards
against this explicitly. If a deploy ever looks blank, check the theme first.

### Security headers

`static/_headers` ships a CSP plus the usual hardening headers, and Cloudflare
Pages applies it automatically from the output root. Verified with the real headers
applied: 0 CSP violations across home, post list, a post, about, search and a tag
page, with the theme toggle, TOC scroll-spy and Fuse.js search all still working.

`script-src` needs `'unsafe-inline'` because PaperMod emits inline scripts for the
theme toggle and JSON-LD. Every actual script file is self-hosted, so the policy
still blocks any externally-hosted script.

## Step 4, Point the domain at Cloudflare

1. Cloudflare dash → **Add a site** → `r00tlv.me` → Free plan.
2. Cloudflare gives you two nameservers.
3. Namecheap → Domain List → Manage → **Nameservers** → *Custom DNS* →
   paste both Cloudflare nameservers → save.
4. Wait for Cloudflare to report the zone as active (usually minutes,
   occasionally a few hours).
5. Pages project → **Custom domains** → add `r00tlv.me` and `www.r00tlv.me`.
   Cloudflare creates the DNS records itself, you do not add A records.

## Step 5, HTTPS

Universal SSL provisions automatically once the zone is active, typically
within 15 minutes. Then set SSL/TLS mode to **Full (strict)**.

Verify:

```bash
curl -sI https://r00tlv.me/ | head -1
curl -s  https://r00tlv.me/rss.xml | head -5
```

## Step 6, Medium canonicals

For each of the six imported articles, on Medium:
Story Settings → Advanced → Custom canonical URL → the new r00tlv.me URL.
Do not delete the Medium posts.

## Verify

- `https://r00tlv.me/`, post list
- `https://r00tlv.me/posts/anatomy-of-ghsa-x24x-425w-326q/`, GHSA writeup
- `https://r00tlv.me/about/`
- `https://r00tlv.me/rss.xml`
- `https://r00tlv.me/search/`
- `https://r00tlv.me/tags/` and `/categories/`

## Troubleshooting

- **Cloudflare build fails on a template error**, almost always `HUGO_VERSION`
  unset or too old. PaperMod needs ≥ 0.146.0.
- **Theme directory empty on Cloudflare**, submodule not fetched; confirm
  `.gitmodules` uses `https://`, not `git@`.
- **Post doesn't appear**, either `draft: true` is still set, or the date is
  in the future (`buildFuture` is deliberately `false`).
- **Search returns nothing**, `/index.json` must be reachable; it is produced
  by `[outputs] home = ["HTML", "RSS", "JSON"]`.
