#!/usr/bin/env python3
"""Assert a built site is actually correct before it is allowed to deploy.

Run against a finished build:  python3 verify-build.py public

This exists because Hugo fails quietly. A missing theme submodule, a
future-dated post and a typo'd taxonomy all exit 0 and produce a site that
looks fine to a build log. Two of those shipped as near-misses on 11 Sep 2026
and were caught by hand, which is not a control.

Every expectation here is derived from content/ rather than hardcoded, so the
checks keep working as posts are added instead of going stale the moment
someone forgets to update a list.
"""
import os
import re
import sys
import glob
import datetime
import xml.etree.ElementTree as ET

PUB = sys.argv[1] if len(sys.argv) > 1 else "public"
SITE = "https://r00tlv.me"

failures = []
notes = []


def check(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(label)
    return ok


def read(p):
    with open(p, encoding="utf-8", errors="ignore") as f:
        return f.read()


def front_matter(path):
    """Minimal YAML front-matter reader; only the keys this script needs."""
    t = read(path)
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    if not m:
        return {}, t
    fm, body = {}, m.group(1)
    for key in ("date", "title", "draft"):
        k = re.search(rf"^{key}:\s*(.+)$", body, re.M)
        if k:
            fm[key] = k.group(1).strip().strip('"')
    tags = re.search(r"^tags:\s*\[(.*?)\]", body, re.M)
    fm["tags"] = re.findall(r'"([^"]+)"', tags.group(1)) if tags else []
    cats = re.search(r"^categories:\s*\[(.*?)\]", body, re.M)
    fm["categories"] = re.findall(r'"([^"]+)"', cats.group(1)) if cats else []
    return fm, t


print("=" * 72)
print("1. theme is present (a themeless build exits 0 and emits no homepage)")
print("=" * 72)
check(os.path.isfile("themes/PaperMod/theme.toml"), "themes/PaperMod/theme.toml exists")
idx = os.path.join(PUB, "index.html")
size = os.path.getsize(idx) if os.path.isfile(idx) else 0
check(size > 3000, "homepage is a real page, not a stub", f"{size} bytes")

print()
print("=" * 72)
print("2. every past-dated post produced a page")
print("=" * 72)
# The bug this catches: a post dated later today is silently dropped by
# buildFuture=false, the build succeeds, and nobody notices it is missing.
now = datetime.datetime.now(datetime.timezone.utc)
published, future = [], []
for src in sorted(glob.glob("content/posts/*.md")):
    slug = os.path.basename(src)[:-3]
    if slug == "_index":
        continue
    fm, _ = front_matter(src)
    if str(fm.get("draft", "")).lower() == "true":
        continue
    raw = fm.get("date", "")
    try:
        d = datetime.datetime.fromisoformat(raw)
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        failures.append(f"unparseable date in {src}: {raw!r}")
        print(f"  FAIL  unparseable date in {src}: {raw!r}")
        continue
    (future if d > now else published).append((slug, d, fm))

for slug, d, _ in published:
    check(os.path.isfile(os.path.join(PUB, "posts", slug, "index.html")),
          f"{slug} built", d.date().isoformat())
for slug, d, _ in future:
    built = os.path.isfile(os.path.join(PUB, "posts", slug, "index.html"))
    hours = (d - now).total_seconds() / 3600.0
    # Real scheduling is days out. A post dated a few hours ahead is almost
    # always meant to be live now and was written with a wall-clock time that
    # has not arrived yet: buildFuture=false then drops it and the build still
    # succeeds. That is how two posts nearly missed the 11 Sep 2026 deploy.
    if hours < 24:
        check(False,
              f"{slug} is future-dated by only {hours:.1f}h and was NOT built",
              f"{d.isoformat()} - if this should be live, use a start-of-day timestamp")
    else:
        check(not built, f"{slug} correctly withheld as future-dated",
              d.date().isoformat())
        notes.append(f"scheduled {d.date().isoformat()}: {slug}")

print()
print("=" * 72)
print("3. sitemap matches the posts that were actually built")
print("=" * 72)
sm = read(os.path.join(PUB, "sitemap.xml"))
locs = set(re.findall(r"<loc>([^<]+)</loc>", sm))
post_locs = {l for l in locs if "/posts/" in l and l.rstrip("/").count("/") > 3}
for slug, _, _ in published:
    check(any(f"/posts/{slug}/" in l for l in post_locs), f"{slug} in sitemap")
for slug, _, _ in future:
    check(not any(f"/posts/{slug}/" in l for l in post_locs),
          f"{slug} absent from sitemap")

print()
print("=" * 72)
print("4. indexing invariants (regressions here cost search visibility)")
print("=" * 72)
pages = glob.glob(os.path.join(PUB, "**", "*.html"), recursive=True)
allhtml = "".join(read(p) for p in pages)
# ?from= as a query string made every tag page exist at N URLs; Google
# indexed six of them. The marker must stay a fragment.
n_query = allhtml.count("?from=")
check(n_query == 0, "no ?from= query-string URLs emitted", f"found {n_query}")
check(allhtml.count("#from=") > 0, "tag origin markers still present as fragments")

search_html = os.path.join(PUB, "search", "index.html")
if os.path.isfile(search_html):
    robots = re.search(r'name=["\']?robots["\']? content=["\']?([^"\'>]+)', read(search_html))
    check(bool(robots) and "noindex" in robots.group(1),
          "/search/ is noindex", robots.group(1) if robots else "no robots meta")
    check(not any("/search/" in l for l in locs),
          "/search/ absent from sitemap (agrees with its noindex)")

print()
print("=" * 72)
print("5. no empty taxonomy pages (thin content)")
print("=" * 72)
# Shipping a tag dir whose posts are all still unpublished produces an empty
# listing page that Google files as thin content. A taxonomy that is empty
# only because every post carrying it is scheduled is a different thing: it
# is a staging artifact that must not be committed yet, but it is not a bug
# in what was built, so it is reported separately.
scheduled_terms = set()
for _slug, _d, _fm in future:
    scheduled_terms |= {t.lower() for t in _fm.get("tags", [])}
    scheduled_terms |= {c.lower() for c in _fm.get("categories", [])}

empty, staged = [], []
for f in sorted(glob.glob(os.path.join(PUB, "tags", "*", "index.html"))
                + glob.glob(os.path.join(PUB, "categories", "*", "index.html"))):
    if re.findall(r"<article[^>]*data-url=", read(f)):
        continue
    rel = os.path.dirname(f).replace(PUB + os.sep, "")
    (staged if os.path.basename(rel).lower() in scheduled_terms else empty).append(rel)

check(not empty, "every tag and category lists at least one published post",
      ", ".join(empty) if empty else "")
if staged:
    print(f"  note  {len(staged)} taxonomy page(s) empty because their only posts are")
    print(f"        scheduled: {', '.join(staged)}")
    print("        Fine locally. Do NOT commit these until the wave that fills them.")
    notes.append("do not commit yet: " + ", ".join(staged))

print()
print("=" * 72)
print("6. every internal link and image resolves")
print("=" * 72)
imgs, links = set(), set()
for p in pages:
    h = read(p)
    imgs |= set(re.findall(r'<img\b[^>]*?src=["\']?([^"\'\s>]+)', h, re.S))
    links |= set(re.findall(r'href=["\']?(/[^"\'\s>#?]*)', h))


def resolves(u):
    u = u.split("?")[0].split("#")[0]
    if u.startswith(("http", "data:", "//", "mailto:")):
        return True
    rel = u.replace(SITE, "").lstrip("/")
    full = os.path.join(PUB, rel)
    return os.path.exists(full) or os.path.exists(os.path.join(full, "index.html"))


broken = sorted([f"IMG {i}" for i in imgs if not resolves(i)]
                + [f"LINK {l}" for l in links if not resolves(l)])
check(not broken, f"{len(imgs)} images and {len(links)} internal links resolve",
      "; ".join(broken[:5]) if broken else "")

print()
print("=" * 72)
print("7. feeds, search index and the legacy redirect")
print("=" * 72)
for f in ["rss.xml", "index.json", "sitemap.xml", "about/index.html",
          "posts/index.html", "tags/index.html", "categories/index.html"]:
    p = os.path.join(PUB, f)
    check(os.path.isfile(p) and os.path.getsize(p) > 0, f"{f} exists and is non-empty")

alias = os.path.join(PUB, "posts", "anatomy-of-ghsa-x24x-425w-326q", "index.html")
if os.path.isfile(alias):
    check("acode-cross-app-scripting-what-i-found" in read(alias),
          "legacy GHSA URL still redirects")

try:
    ch = ET.parse(os.path.join(PUB, "rss.xml")).getroot().find("channel")
    titles = [i.find("title").text for i in ch.findall("item")]
    check(bool(titles), "rss.xml has items", f"{len(titles)} item(s)")
    check("About" not in titles, "About page did not leak into RSS")
except ET.ParseError as e:
    check(False, "rss.xml parses", str(e))

print()
print("=" * 72)
if notes:
    print("scheduled, intentionally not yet published:")
    for n in notes:
        print(f"  - {n}")
    print()
if failures:
    print(f"FAILED: {len(failures)} check(s)")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"PASSED: {len(published)} post(s) published, {len(future)} scheduled")
