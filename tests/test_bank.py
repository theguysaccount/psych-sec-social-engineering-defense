"""The quiz content: every item is well-formed, fair, and safe to publish."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPES = json.loads((ROOT / "data" / "types.json").read_text(encoding="utf-8"))
ITEMS = json.loads((ROOT / "data" / "items.json").read_text(encoding="utf-8"))
CHANNELS = {"sms", "email", "call", "voicemail", "dm", "popup", "letter", "sign", "ad", "app", "video"}
SLUGS = {t["slug"] for t in TYPES}


def message_text(item):
    return "\n".join(x for x in (item.get("from"), item.get("subject"), item["body"]) if x)


class TypesTest(unittest.TestCase):
    def test_fields(self):
        for t in TYPES:
            with self.subTest(t["slug"]):
                self.assertRegex(t["slug"], r"^[a-z0-9-]+$")
                for k in ("name", "title", "description", "short"):
                    self.assertTrue(t[k].strip(), k)
                self.assertLessEqual(len(t["description"]), 170, "meta description too long")
                self.assertGreaterEqual(len(t["how"]), 1)
                self.assertGreaterEqual(len(t["flags"]), 3)
                self.assertGreaterEqual(len(t["do"]), 2)
                self.assertGreaterEqual(len(t["keywords"]), 2)
                self.assertGreaterEqual(len(t["sources"]), 1)

    def test_sources_are_official(self):
        for t in TYPES:
            for s in t["sources"]:
                with self.subTest(s["url"]):
                    self.assertRegex(s["url"], r"^https://(consumer\.ftc\.gov|www\.cisa\.gov)/")

    def test_unique(self):
        self.assertEqual(len(SLUGS), len(TYPES))
        self.assertEqual(len({t["name"] for t in TYPES}), len(TYPES))


class ItemsTest(unittest.TestCase):
    def test_fields(self):
        ids = [i["id"] for i in ITEMS]
        self.assertEqual(len(ids), len(set(ids)), "duplicate item ids")
        for i in ITEMS:
            with self.subTest(i["id"]):
                self.assertRegex(i["id"], r"^[a-z0-9-]+$")
                self.assertIn(i["type"], SLUGS)
                self.assertIn(i["verdict"], ("scam", "legit"))
                self.assertIn(i["channel"], CHANNELS)
                self.assertTrue(i["body"].strip())
                self.assertTrue(i["why"].strip())
                self.assertTrue(i["do"].strip())
                self.assertGreaterEqual(len(i["flags"]), 2)
                if i["channel"] == "email":
                    self.assertTrue(i.get("subject"), "emails need a subject")

    def test_quotes_appear_in_one_paragraph(self):
        # Each tell is highlighted in the message, so its quote must be there verbatim.
        for i in ITEMS:
            parts = [x for x in (i.get("from"), i.get("subject")) if x] + re.split(r"\n{2,}", i["body"])
            for f in i["flags"]:
                if f.get("quote"):
                    with self.subTest(i["id"], quote=f["quote"]):
                        self.assertTrue(any(f["quote"] in p for p in parts))

    def test_every_type_can_be_tested(self):
        for t in TYPES:
            mine = [i for i in ITEMS if i["type"] == t["slug"]]
            with self.subTest(t["slug"]):
                self.assertGreaterEqual(len(mine), 2, "each lesson page has a mini test of 2+ items")
                self.assertTrue(any(i["verdict"] == "scam" for i in mine))

    def test_enough_for_a_weekly_test(self):
        scams = [i for i in ITEMS if i["verdict"] == "scam"]
        legit = [i for i in ITEMS if i["verdict"] == "legit"]
        self.assertGreaterEqual(len({i["type"] for i in scams}), 6)
        self.assertGreaterEqual(len(legit), 4)

    def test_phone_numbers_are_fictional(self):
        # North American numbers 555-0100..0199 are reserved for fiction.
        for i in ITEMS:
            text = message_text(i)
            for m in re.finditer(r"(?:\+1 )?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b|\b\d{3}-\d{3}-\d{4}\b", text):
                with self.subTest(i["id"], number=m.group(0)):
                    self.assertRegex(m.group(0), r"555[ .-]01\d\d$")

    def test_links_use_markup(self):
        # Every web address must be wrapped in [[...]] (rendered unclickable) or be an email address.
        for i in ITEMS:
            stripped = re.sub(r"\[\[.+?\]\]", "", i["body"])
            stripped = re.sub(r"[\w.+-]+@[\w.-]+", "", stripped)
            with self.subTest(i["id"]):
                self.assertIsNone(re.search(r"\b[\w-]+\.(com|net|org|info|top|vip|shop|click|cfd|co|gov|xyz)\b(?!\w)", stripped),
                                  "bare web address in the message body")

    def test_scam_links_are_not_official_domains(self):
        for i in ITEMS:
            if i["verdict"] != "scam":
                continue
            for link in re.findall(r"\[\[(.+?)\]\]", i["body"]):
                host = link.split("/")[0]
                with self.subTest(i["id"], host=host):
                    self.assertFalse(host.endswith(".gov"), "a scam example must not use a real .gov host")

    def test_no_placeholder_text(self):
        for i in ITEMS:
            blob = json.dumps(i)
            with self.subTest(i["id"]):
                self.assertNotRegex(blob, r"TODO|TBD|lorem|XXX")


if __name__ == "__main__":
    unittest.main()
