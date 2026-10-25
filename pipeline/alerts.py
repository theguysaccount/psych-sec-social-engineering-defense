"""Pull public scam alerts from the FTC, CISA and the FBI (IC3), tag them with this site's scam
types, and keep a running archive in data/alerts.json.

    python3 pipeline/alerts.py fetch        # fetch the feeds and update data/alerts.json
    python3 pipeline/alerts.py candidates   # write data/candidates.json: scam alerts no scam type covers yet
    python3 pipeline/alerts.py featured     # print this week's featured scam types

Fails safe: a feed that can't be fetched or parsed keeps its old entries, and the run still exits 0
so the site keeps building. It exits 1 only when no source has worked for STALE_DAYS, which is
worth a failed run (and GitHub's failure email).
"""
import datetime as dt
import email.utils
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALERTS = ROOT / "data" / "alerts.json"
TYPES = ROOT / "data" / "types.json"
KEEP = 300          # newest alerts kept in the archive
STALE_DAYS = 21     # fail the run if no source has worked for this long
UA = "SpotTheScamBot/1.0 (+https://github.com/theguysaccount/psych-sec-social-engineering-defense)"

SOURCES = {
    "ftc": {"name": "FTC", "url": "https://consumer.ftc.gov/blog/gd-rss.xml", "filter": False},
    "cisa-alerts": {"name": "CISA", "url": "https://www.cisa.gov/cybersecurity-advisories/alerts.xml", "filter": True},
    "cisa-news": {"name": "CISA", "url": "https://www.cisa.gov/news.xml", "filter": True},
    "fbi-psa": {"name": "FBI", "url": "https://www.ic3.gov/PSA/RSS", "filter": True},
}

# An alert is about scams if it says so.
SCAM_WORDS = ["scam", "impersonat", "imposter", "impostor", "phishing", "smishing", "vishing", "fraud", "fake",
              "con artist", "social engineering", "sextortion", "steal your", "spoof", "voice clon"]
# Words in a title that make an untyped FTC alert worth a "new scam type?" issue.
NEW_TYPE_WORDS = ["scam", "impersonat", "imposter", "fraud", "fake", "phishing", "spoof"]

# Scam types to feature when recent alerts don't name three. Month -> types.
SEASONAL = {
    1: ["government-impostor", "account-phishing", "romance"],
    2: ["romance", "government-impostor", "job-task"],
    3: ["government-impostor", "toll-text", "account-phishing"],
    4: ["government-impostor", "toll-text", "job-task"],
    5: ["toll-text", "job-task", "rental"],
    6: ["rental", "toll-text", "fake-store"],
    7: ["rental", "job-task", "wrong-number"],
    8: ["job-task", "rental", "qr-code"],
    9: ["health-insurance", "qr-code", "account-phishing"],
    10: ["health-insurance", "package-delivery", "account-phishing"],
    11: ["package-delivery", "fake-store", "health-insurance"],
    12: ["package-delivery", "fake-store", "charity"],
}


def today():
    return dt.datetime.now(dt.timezone.utc).date()


def load_types():
    return json.loads(TYPES.read_text(encoding="utf-8"))


def clean(text):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = html.unescape(text)
    text = re.sub(r"^\s*By [A-Z][^\n]{0,40}?Staff\s*", "", text.strip())
    text = re.sub(r"\s*Read more\s*>?\s*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:  # RFC 822 (CISA): "Wed, 21 Oct 26 12:00:00 +0000"
        return email.utils.parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError):
        pass
    head = raw.split("|")[0].strip()  # FTC: "October 22, 2026 | 9:49AM"
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(head, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_feed(xml_text, source):
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter("item"):
        url = (it.findtext("link") or "").strip()
        title = clean(it.findtext("title"))
        if not url.startswith("https://") or not title:
            continue
        summary = clean(it.findtext("description"))
        if len(summary) > 320:
            summary = summary[:317].rsplit(" ", 1)[0] + "…"
        out.append({"url": url, "title": title, "date": parse_date(it.findtext("pubDate")),
                    "source": SOURCES[source]["name"], "feed": source, "summary": summary})
    return out


def has(word, text):
    """Word-start match: "impersonat" matches "impersonating", "pet" doesn't match "compete"."""
    return re.search(r"(?<![a-z0-9])" + re.escape(word), text) is not None


def classify(alert, types):
    title = alert["title"].lower()
    hay = title + " " + alert["summary"].lower()
    scores = {}
    for t in types:
        s = 0
        for kw in t["keywords"]:
            if has(kw, title):
                s += 3
            elif has(kw, hay):
                s += 1
        if s >= 2:
            scores[t["slug"]] = s
    ranked = sorted(scores, key=lambda k: (-scores[k], k))[:2]
    # CISA feeds are mostly software flaws, so their titles must be about scams. FTC alerts
    # qualify when the title or summary is.
    text = title if SOURCES[alert["feed"]]["filter"] else hay
    relevant = any(has(w, text) for w in SCAM_WORDS)
    return ranked if relevant else [], relevant


def fetch(url, timeout=30, tries=3):
    """GET a feed. Retries a couple of times: CISA answers some GitHub runner addresses with a 403."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.5"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(20 * (attempt + 1))


def merge(store, fresh, now):
    by_url = {a["url"]: a for a in store.get("alerts", [])}
    added = 0
    for a in fresh:
        if a["url"] in by_url:
            old = by_url[a["url"]]
            a["first_seen"] = old.get("first_seen", now)
        else:
            a["first_seen"] = now
            added += 1
        by_url[a["url"]] = a
    alerts = sorted(by_url.values(), key=lambda a: (a.get("date") or "", a["url"]), reverse=True)
    store["alerts"] = alerts[:KEEP]
    return added


def cmd_fetch(fetcher=fetch, now=None):
    now = now or today().isoformat()
    store = json.loads(ALERTS.read_text(encoding="utf-8")) if ALERTS.exists() else {"sources": {}, "alerts": []}
    types = load_types()
    fresh, status = [], store.setdefault("sources", {})
    for key, src in SOURCES.items():
        st = status.setdefault(key, {"url": src["url"]})
        try:
            items = parse_feed(fetcher(src["url"]), key)
            if not items:
                raise ValueError("feed parsed but had no items")
            for a in items:
                a["types"], a["relevant"] = classify(a, types)
            fresh.extend(items)
            st.update({"last_ok": now, "last_error": None, "items": len(items)})
            print(f"{key}: {len(items)} items, {sum(a['relevant'] for a in items)} about scams")
        except Exception as e:  # keep the old entries; report and carry on
            st["last_error"] = f"{now}: {type(e).__name__}: {e}"[:300]
            print(f"::warning::{key} failed: {e}")
    added = merge(store, fresh, now)
    store["checked"] = now
    ALERTS.write_text(json.dumps(store, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{added} new alerts; {len(store['alerts'])} in the archive")
    oks = [s.get("last_ok") for s in status.values() if s.get("last_ok")]
    if not oks or (dt.date.fromisoformat(now) - dt.date.fromisoformat(max(oks))).days > STALE_DAYS:
        print(f"::error::No alert source has worked for over {STALE_DAYS} days")
        return 1
    return 0


def featured(store, types, on=None, days=60, n=3):
    """The scam types recent alerts are about, newest and most frequent first, topped up by season."""
    on = on or today()
    slugs = {t["slug"] for t in types}
    score, why = {}, {}
    for a in store.get("alerts", []):
        if not a.get("relevant") or not a.get("date"):
            continue
        age = (on - dt.date.fromisoformat(a["date"])).days
        if age < 0 or age > days:
            continue
        for t in a.get("types", []):
            if t in slugs:
                score[t] = score.get(t, 0) + 1 / (1 + age / 14)
                if t not in why or a["date"] > why[t]["date"]:
                    why[t] = {"title": a["title"], "url": a["url"], "date": a["date"], "source": a["source"]}
    picks = sorted(score, key=lambda k: (-score[k], k))[:n]
    for t in SEASONAL[on.month]:
        if len(picks) >= n:
            break
        if t not in picks and t in slugs:
            picks.append(t)
    return picks, {k: why[k] for k in picks if k in why}


def candidates(store, days=120, on=None):
    on = on or today()
    out = []
    for a in store.get("alerts", []):
        if (a.get("relevant") and not a.get("types") and a.get("date") and a["source"] in ("FTC", "FBI")
                and any(has(w, a["title"].lower()) for w in NEW_TYPE_WORDS)):
            if (on - dt.date.fromisoformat(a["date"])).days <= days:
                out.append(a)
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "fetch"
    if cmd == "fetch":
        return cmd_fetch()
    store = json.loads(ALERTS.read_text(encoding="utf-8"))
    if cmd == "candidates":
        found = candidates(store)
        out = ROOT / "data" / "candidates.json"
        out.write_text(json.dumps([{k: a[k] for k in ("date", "title", "url", "summary")} for a in found],
                                  indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        for a in found:
            print(f"- {a['date']} [{a['title']}]({a['url']})")
        return 0
    if cmd == "featured":
        picks, why = featured(store, load_types())
        print(json.dumps({"featured": picks, "why": why}, indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
