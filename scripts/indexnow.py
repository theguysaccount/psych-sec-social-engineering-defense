"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver and others) which URLs changed.

    python3 scripts/indexnow.py dist/urls.txt

The key file (<key>.txt) is published at the site root by the build. A failed submission is
reported but exits 0: the site itself is already live, and the next deploy tries again.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SITE_URL = "https://theguysaccount.github.io/psych-sec-social-engineering-defense"


def main(path):
    key = (ROOT / "site" / "indexnow-key.txt").read_text().strip()
    base = os.environ.get("SITE_URL", DEFAULT_SITE_URL).rstrip("/")
    host = urlparse(base).hostname
    urls = [u for u in Path(path).read_text().split() if urlparse(u).hostname == host][:10000]
    body = json.dumps({"host": host, "key": key, "keyLocation": f"{base}/{key}.txt", "urlList": urls}).encode()
    # A new key answers 403 until the engine has fetched the key file; retry a few times.
    for attempt in range(4):
        if attempt:
            time.sleep(30 * attempt)
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"IndexNow: {r.status} for {len(urls)} URLs")
                return 0
        except urllib.error.HTTPError as e:
            print(f"IndexNow: {e.code} {e.reason}: {e.read()[:300]!r}")
            if e.code not in (403, 429) and e.code < 500:
                return 0
        except OSError as e:
            print(f"IndexNow: {e}")
    print("::warning::IndexNow submission didn't succeed; the next deploy will retry")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dist/urls.txt"))
