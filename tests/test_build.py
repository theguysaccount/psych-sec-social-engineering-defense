"""The built site: every page exists, links resolve, and search and share metadata is complete."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://example.org/spot"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.scripts, self.meta, self.ld, self.title = [], [], {}, [], ""
        self._in_title = self._in_ld = False
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag in ("a", "link") and a.get("href"):
            self.links.append((tag, a.get("rel", ""), a["href"]))
        if tag == "script":
            if a.get("src"):
                self.scripts.append(a["src"])
            self._in_ld = a.get("type") == "application/ld+json"
        if tag == "meta":
            key = a.get("name") or a.get("property")
            if key:
                self.meta[key] = a.get("content", "")
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self.ld.append(data)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp()) / "dist"
        env = dict(os.environ, SITE_URL=SITE, BUILD_DATE="2026-10-25", GOATCOUNTER_URL="", TEAM_VERSION_URL="")
        subprocess.run([sys.executable, str(ROOT / "pipeline" / "build.py"), "--out", str(cls.out)], check=True, env=env,
                       capture_output=True)
        cls.types = json.loads((ROOT / "data" / "types.json").read_text())
        cls.pages = {}
        for f in cls.out.rglob("*.html"):
            p = Page()
            p.feed(f.read_text(encoding="utf-8"))
            cls.pages[f.relative_to(cls.out).as_posix()] = p

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out.parent)

    def test_pages_exist(self):
        expected = {"index.html", "scams/index.html", "alerts/index.html", "about/index.html", "embed/index.html",
                    "how-to-spot-a-scam/index.html", "404.html"} | {f"scams/{t['slug']}/index.html" for t in self.types}
        self.assertEqual(set(self.pages), expected)

    def test_sitemap_matches_indexable_pages(self):
        xml = (self.out / "sitemap.xml").read_text()
        locs = re.findall(r"<loc>([^<]+)</loc>", xml)
        self.assertEqual(len(locs), len(self.types) + 5)  # home, hub, how-to, alerts, about
        self.assertNotIn(f"{SITE}/embed/", locs)
        for loc in locs:
            path = loc[len(SITE) + 1:]
            self.assertTrue((self.out / path / "index.html").exists() or (self.out / path).is_file(), loc)
        self.assertEqual((self.out / "urls.txt").read_text().split(), locs)
        self.assertIn(f"Sitemap: {SITE}/sitemap.xml", (self.out / "robots.txt").read_text())

    def test_internal_links_resolve(self):
        for name, page in self.pages.items():
            if name == "404.html":
                continue
            base = f"http://site/{name}"
            for tag, rel, href in page.links + [("script", "", s) for s in page.scripts]:
                if href.startswith(("http://", "https://", "mailto:", "sms:", "#")):
                    continue
                target = urlparse(urljoin(base, href)).path.lstrip("/")
                if target == "" or target.endswith("/"):
                    target += "index.html"
                with self.subTest(page=name, href=href):
                    self.assertTrue((self.out / target).exists(), target)

    def test_404_links_are_absolute(self):
        page = self.pages["404.html"]
        for tag, rel, href in page.links:
            if not href.startswith(("http", "mailto", "#")):
                self.assertTrue(href.startswith("/spot/"), href)

    def test_metadata(self):
        for name, page in self.pages.items():
            with self.subTest(name):
                self.assertTrue(page.title.strip())
                self.assertGreater(len(page.meta.get("description", "")), 20)
                self.assertTrue(page.meta.get("og:image", "").startswith(SITE + "/assets/og/"))
                self.assertEqual(page.meta.get("twitter:card"), "summary_large_image")
                canon = [h for t, rel, h in page.links if rel == "canonical"]
                self.assertEqual(len(canon), 1)
                self.assertTrue(canon[0].startswith(SITE + "/"))
                for block in page.ld:
                    json.loads(block)
        titles = [p.title for n, p in self.pages.items() if n not in ("404.html", "embed/index.html")]
        self.assertEqual(len(titles), len(set(titles)), "titles must be unique")

    def test_noindex_only_where_intended(self):
        for name, page in self.pages.items():
            noindex = page.meta.get("robots") == "noindex"
            self.assertEqual(noindex, name in ("embed/index.html", "404.html"), name)

    def test_no_third_party_scripts_by_default(self):
        for name, page in self.pages.items():
            for src in page.scripts:
                self.assertFalse(src.startswith(("http:", "https:", "//")), f"{name}: {src}")

    def test_quiz_data(self):
        bank = json.loads((self.out / "data" / "bank.json").read_text())
        items = json.loads((ROOT / "data" / "items.json").read_text())
        self.assertEqual(len(bank["items"]), len(items))
        self.assertEqual(set(bank["types"]), {t["slug"] for t in self.types})
        week = json.loads((self.out / "data" / "week.json").read_text())
        self.assertEqual(week["week"], "2026-W43")
        self.assertEqual(len(week["featured"]), 3)
        self.assertTrue(set(week["featured"]) <= set(bank["types"]))

    def test_lesson_pages(self):
        for t in self.types:
            html = (self.out / "scams" / t["slug"] / "index.html").read_text()
            with self.subTest(t["slug"]):
                self.assertIn(f'data-type="{t["slug"]}"', html)
                self.assertIn('class="msg revealed', html, "a revealed example")
                for s in t["sources"]:
                    self.assertIn(s["url"], html)

    def test_indexnow_key_file(self):
        key = (ROOT / "site" / "indexnow-key.txt").read_text().strip()
        self.assertRegex(key, r"^[a-f0-9]{32}$")
        self.assertEqual((self.out / f"{key}.txt").read_text(), key)

    def test_assets_are_versioned(self):
        html = (self.out / "index.html").read_text()
        ver = re.search(r"app\.js\?v=([0-9a-f]{10})", html).group(1)
        self.assertIn(f'from "./core.js?v={ver}"', (self.out / "assets" / "app.js").read_text())

    def test_optional_keys(self):
        out = Path(tempfile.mkdtemp())
        try:
            env = dict(os.environ, SITE_URL=SITE, BUILD_DATE="2026-10-25",
                       GOATCOUNTER_URL="https://example.goatcounter.com/count", TEAM_VERSION_URL="https://example.org/team")
            subprocess.run([sys.executable, str(ROOT / "pipeline" / "build.py"), "--out", str(out)], check=True, env=env,
                           capture_output=True)
            home = (out / "index.html").read_text()
            self.assertIn('data-goatcounter="https://example.goatcounter.com/count"', home)
            self.assertIn('"teamUrl": "https://example.org/team"', home)
            self.assertIn("https://example.org/team", (out / "about" / "index.html").read_text())
        finally:
            shutil.rmtree(out)


if __name__ == "__main__":
    unittest.main()
