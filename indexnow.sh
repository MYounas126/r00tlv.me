#!/usr/bin/env bash
# Submit the sitemap's URLs to IndexNow (Bing, Yandex, Seznam, Naver).
# Google does not participate in IndexNow - use Search Console for Google.
set -euo pipefail
KEY="5a8c75b4219849b9b974b1e209e76b52"
HOST="r00tlv.me"
URLS=$(curl -s "https://${HOST}/sitemap.xml" | grep -oE '<loc>[^<]+</loc>' | sed 's|</\?loc>||g')
JSON=$(python3 - "$KEY" "$HOST" <<'PY'
import json, sys
key, host = sys.argv[1], sys.argv[2]
urls = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
print(json.dumps({"host": host, "key": key,
                  "keyLocation": f"https://{host}/{key}.txt", "urlList": urls}))
PY
<<< "$URLS")
echo "$JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'submitting {len(d[\"urlList\"])} URLs')"
curl -sS -X POST "https://api.indexnow.org/indexnow" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d "$JSON" -w "\nHTTP %{http_code}\n"
