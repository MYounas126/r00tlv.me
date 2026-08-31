#!/usr/bin/env bash
# Submit the sitemap's URLs to IndexNow (Bing, Yandex, Seznam, Naver).
# Google does not participate in IndexNow; use Search Console for Google.
set -euo pipefail
KEY="5a8c75b4219849b9b974b1e209e76b52"
HOST="r00tlv.me"

python3 - "$KEY" "$HOST" <<'PY'
import json, sys, urllib.request, re
key, host = sys.argv[1], sys.argv[2]
sm_req = urllib.request.Request(f"https://{host}/sitemap.xml",
    headers={"User-Agent": "Mozilla/5.0 (compatible; r00tlv-indexnow/1.0)"})
sm = urllib.request.urlopen(sm_req, timeout=20).read().decode()
urls = re.findall(r"<loc>([^<]+)</loc>", sm)
payload = {"host": host, "key": key,
           "keyLocation": f"https://{host}/{key}.txt", "urlList": urls}
print(f"submitting {len(urls)} URLs to IndexNow")
req = urllib.request.Request(
    "https://api.indexnow.org/indexnow",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json; charset=utf-8"})
try:
    r = urllib.request.urlopen(req, timeout=30)
    print("HTTP", r.status, "- accepted")
except urllib.error.HTTPError as e:
    print("HTTP", e.code, "-", e.read().decode()[:200])
PY
