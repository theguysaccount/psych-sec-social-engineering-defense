"""The weekly alert pull: parsing, tagging, merging and failing safe."""
import contextlib
import datetime as dt
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import alerts as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def fixture_fetcher(url):
    name = {"consumer.ftc.gov": "ftc.xml", "alerts.xml": "cisa-alerts.xml", "news.xml": "cisa-news.xml", "ic3.gov": "ic3-psa.xml"}
    for key, file in name.items():
        if key in url:
            return (FIX / file).read_text(encoding="utf-8")
    raise AssertionError(url)


class ParseTest(unittest.TestCase):
    def test_ftc_feed(self):
        items = A.parse_feed((FIX / "ftc.xml").read_text(encoding="utf-8"), "ftc")
        self.assertEqual(len(items), 10)
        first = items[0]
        self.assertEqual(first["title"], "The FTC is not calling to deactivate your phone number")
        self.assertEqual(first["date"], "2026-10-22")
        self.assertTrue(first["url"].startswith("https://consumer.ftc.gov/consumer-alerts/2026/10/"))
        self.assertNotIn("<", first["summary"])
        self.assertFalse(first["summary"].startswith("By "), "byline stripped")
        self.assertLessEqual(len(first["summary"]), 320)

    def test_fbi_feed(self):
        items = A.parse_feed((FIX / "ic3-psa.xml").read_text(encoding="utf-8"), "fbi-psa")
        self.assertEqual(len(items), 5)
        self.assertEqual(items[0]["date"], "2026-10-23")
        tagged = {a["title"]: A.classify(a, A.load_types()) for a in items}
        self.assertTrue(tagged["Scammers Exploit 2026 U.S. Midterm Election to Perpetrate Multiple Fraud Schemes"][1])
        self.assertFalse(tagged["Critical Vulnerability Alert: PHP Core"][1])

    def test_cisa_feeds(self):
        alerts = A.parse_feed((FIX / "cisa-alerts.xml").read_text(encoding="utf-8"), "cisa-alerts")
        news = A.parse_feed((FIX / "cisa-news.xml").read_text(encoding="utf-8"), "cisa-news")
        self.assertEqual(len(alerts), 12)
        self.assertEqual(len(news), 10)
        self.assertTrue(all(a["date"] and a["date"].startswith("2026-") for a in alerts + news))

    def test_dates(self):
        self.assertEqual(A.parse_date("October 22, 2026 | 9:49AM"), "2026-10-22")
        self.assertEqual(A.parse_date("September 28, 2026 | 12:41"), "2026-09-28")
        self.assertEqual(A.parse_date("Wed, 21 Oct 26 12:00:00 +0000"), "2026-10-21")
        self.assertIsNone(A.parse_date("not a date"))


class ClassifyTest(unittest.TestCase):
    types = A.load_types()

    def tag(self, title, summary="", feed="ftc"):
        return A.classify({"title": title, "summary": summary, "feed": feed}, self.types)

    def test_known_alerts(self):
        self.assertEqual(self.tag("The FTC is not calling to deactivate your phone number",
                                  "someone claiming to be an FTC official (who's really a scammer)")[0][0], "government-impostor")
        self.assertIn("qr-code", self.tag("See a QR code parked somewhere? Don't scan it…yet!", "scammers like using QR codes")[0])
        self.assertIn("toll-text", self.tag("Got a text about unpaid tolls? It's probably a scam")[0])
        self.assertIn("jury-duty", self.tag("Ignore calls threatening to arrest you for missing jury duty", "a scam")[0])

    def test_vulnerability_bulletins_are_not_scams(self):
        types, relevant = self.tag("CISA Adds Two Known Exploited Vulnerabilities to Catalog",
                                   "Microsoft Windows Spoofing Vulnerability", feed="cisa-alerts")
        self.assertFalse(relevant)
        self.assertEqual(types, [])

    def test_cisa_phishing_guidance_is_kept(self):
        self.assertTrue(self.tag("CISA Releases Guidance on Phishing-Resistant MFA", "", feed="cisa-news")[1])

    def test_word_starts_only(self):
        self.assertFalse(A.has("pet", "compete with others"))
        self.assertTrue(A.has("impersonat", "scammers are impersonating farm businesses"))


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.orig = A.ALERTS
        A.ALERTS = self.tmp / "alerts.json"
        # The fetcher prints GitHub annotations for failed feeds; keep them out of test logs.
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()

    def tearDown(self):
        self.quiet.__exit__(None, None, None)
        A.ALERTS = self.orig
        shutil.rmtree(self.tmp)

    def test_fetch_and_merge(self):
        self.assertEqual(A.cmd_fetch(fixture_fetcher, now="2026-10-25"), 0)
        store = json.loads(A.ALERTS.read_text())
        self.assertEqual(len(store["alerts"]), 10 + 12 + 10 + 5)
        self.assertEqual(store["checked"], "2026-10-25")
        self.assertTrue(all(s["last_ok"] == "2026-10-25" for s in store["sources"].values()))
        # A second run a week later keeps first_seen and doesn't duplicate.
        self.assertEqual(A.cmd_fetch(fixture_fetcher, now="2026-11-01"), 0)
        store = json.loads(A.ALERTS.read_text())
        self.assertEqual(len(store["alerts"]), 37)
        self.assertTrue(all(a["first_seen"] == "2026-10-25" for a in store["alerts"]))
        dates = [a["date"] for a in store["alerts"]]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_a_failing_source_keeps_old_entries(self):
        A.cmd_fetch(fixture_fetcher, now="2026-10-25")

        def ftc_down(url):
            if "ftc.gov" in url:
                raise OSError("HTTP Error 403: Forbidden")
            return fixture_fetcher(url)

        self.assertEqual(A.cmd_fetch(ftc_down, now="2026-11-01"), 0)
        store = json.loads(A.ALERTS.read_text())
        self.assertEqual(len([a for a in store["alerts"] if a["source"] == "FTC"]), 10)
        self.assertIn("403", store["sources"]["ftc"]["last_error"])
        self.assertEqual(store["sources"]["ftc"]["last_ok"], "2026-10-25")

    def test_empty_feed_counts_as_failure(self):
        A.cmd_fetch(fixture_fetcher, now="2026-10-25")
        empty = '<?xml version="1.0"?><rss><channel><title>x</title></channel></rss>'
        self.assertEqual(A.cmd_fetch(lambda url: empty, now="2026-10-26"), 0)
        store = json.loads(A.ALERTS.read_text())
        self.assertEqual(len(store["alerts"]), 37)
        self.assertTrue(all(s["last_error"] for s in store["sources"].values()))

    def test_stale_sources_fail_the_run(self):
        A.cmd_fetch(fixture_fetcher, now="2026-10-01")

        def down(url):
            raise OSError("offline")

        self.assertEqual(A.cmd_fetch(down, now="2026-10-10"), 0)   # 9 days: warn only
        self.assertEqual(A.cmd_fetch(down, now="2026-10-31"), 1)   # 30 days: fail


class FeaturedTest(unittest.TestCase):
    types = A.load_types()

    def store(self, *alerts):
        return {"alerts": [dict(title="t", url=f"u{n}", source="FTC", relevant=True, **a) for n, a in enumerate(alerts)]}

    def test_recent_alerts_lead(self):
        s = self.store({"date": "2026-10-20", "types": ["toll-text"]}, {"date": "2026-10-21", "types": ["toll-text"]},
                       {"date": "2026-10-10", "types": ["romance"]})
        picks, why = A.featured(s, self.types, on=dt.date(2026, 10, 25))
        self.assertEqual(picks[:2], ["toll-text", "romance"])
        self.assertEqual(len(picks), 3)
        self.assertEqual(why["toll-text"]["url"], "u1")

    def test_old_alerts_ignored_and_season_fills(self):
        s = self.store({"date": "2026-01-02", "types": ["toll-text"]})
        picks, why = A.featured(s, self.types, on=dt.date(2026, 12, 1))
        self.assertEqual(picks, A.SEASONAL[12])
        self.assertEqual(why, {})

    def test_seasonal_types_exist(self):
        slugs = {t["slug"] for t in self.types}
        for month, types in A.SEASONAL.items():
            self.assertEqual(len(types), 3)
            self.assertTrue(set(types) <= slugs, month)


if __name__ == "__main__":
    unittest.main()
