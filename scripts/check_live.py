"""Weekly health check of the live site and its data.

    python3 scripts/check_live.py https://theguysaccount.github.io/psych-sec-social-engineering-defense

Checks: every sitemap URL answers 200 with its own canonical URL; the quiz data loads; the weekly
rebuild ran in the last 9 days; the alert pull worked in the last 10 days; CISA source links haven't
gone (404/410).
(FTC pages block automated requests, so FTC links are checked by people, not by this script.)
Exits 1 on any failure.
"""
import datetime as dt
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "SpotTheScamHealthCheck/1.0 (+https://github.com/theguysaccount/psych-sec-social-engineering-defense)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


# Retries (added 2026-11-22). GitHub Pages now and then answers a single request with a 5xx; one 503
# failed LifeClock's self-test on 2026-11-17. get() above stays as the single attempt (get_once); the
# get() below wraps it and tries a failed fetch up to three more times, after 10, 20 and 30 seconds.
# An answer a retry won't change (403, 404 and the like) still fails at once, and a run gets at most
# six retries, so a site that is really down still fails within minutes.
get_once = get
RETRY_PAUSES = (10, 20, 30)  # seconds before the 2nd, 3rd and 4th tries
RETRY_BUDGET = 6  # retries per run
retries_used = 0


def transient(e):
    """True for a failure worth retrying: HTTP 408, 429 or 5xx, a timeout or a dropped connection."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code in (408, 429) or e.code >= 500
    return isinstance(e, (OSError, http.client.HTTPException))


def get(url):
    global retries_used
    for pause in RETRY_PAUSES + (None,):
        try:
            return get_once(url)
        except Exception as e:
            if pause is None or not transient(e) or retries_used >= RETRY_BUDGET:
                raise
            retries_used += 1
            print(f"::warning::{url}: {e}; trying again in {pause} s", flush=True)
            time.sleep(pause)


def main(base):
    base = base.rstrip("/")
    problems = []
    today = dt.datetime.now(dt.timezone.utc).date()
    status, sitemap = get(f"{base}/sitemap.xml")
    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    if len(urls) < 10:
        problems.append(f"sitemap has only {len(urls)} URLs")
    for u in urls:
        try:
            status, page = get(u)
            canon = re.search(r'<link rel="canonical" href="([^"]+)"', page)
            if status != 200 or not canon or canon.group(1) != u:
                problems.append(f"{u}: status {status}, canonical {canon.group(1) if canon else None}")
        except Exception as e:
            problems.append(f"{u}: {e}")
    try:
        bank = json.loads(get(f"{base}/data/bank.json")[1])
        week = json.loads(get(f"{base}/data/week.json")[1])
        if len(bank["items"]) < 40:
            problems.append(f"bank has only {len(bank['items'])} items")
        built = dt.date.fromisoformat(week["built"])
        if (today - built).days > 9:
            problems.append(f"site last rebuilt {built}: the weekly refresh isn't redeploying")
    except Exception as e:
        problems.append(f"quiz data: {e}")
    store = json.loads((ROOT / "data" / "alerts.json").read_text(encoding="utf-8"))
    oks = [s.get("last_ok") for s in store.get("sources", {}).values() if s.get("last_ok")]
    if not oks or (today - dt.date.fromisoformat(max(oks))).days > 10:
        problems.append(f"no alert source has worked since {max(oks) if oks else 'ever'}")
    for key, s in store.get("sources", {}).items():
        if s.get("last_error"):
            print(f"::warning::alert source {key}: {s['last_error']}")
    types = json.loads((ROOT / "data" / "types.json").read_text(encoding="utf-8"))
    # CISA's bot filter answers some runner addresses with 403; only a 404 or 410 means a link is gone.
    for url in sorted({s["url"] for t in types for s in t["sources"] if "cisa.gov" in s["url"]}):
        try:
            get(url)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                problems.append(f"source link {url}: {e}")
            else:
                print(f"::warning::couldn't verify {url}: {e}")
        except Exception as e:
            print(f"::warning::couldn't verify {url}: {e}")
    print(f"checked {len(urls)} pages")
    for p in problems:
        print(f"::error::{p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
