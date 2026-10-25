"""Build the static site into dist/ from data/ and site/. Standard library only (Python 3.9+).

    python3 pipeline/build.py [--out dist]

Optional environment (GitHub repository variables in CI, see OPERATIONS.md):
    SITE_URL           canonical origin + path, no trailing slash (default: the GitHub Pages URL)
    GOATCOUNTER_URL    e.g. https://spotthescam.goatcounter.com/count  -> cookieless analytics on
    TEAM_VERSION_URL   link for the paid team-training version            -> "For teams" slot shown
    BUILD_DATE         YYYY-MM-DD, to reproduce a build (default: today, UTC)
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alerts as alertlib  # noqa: E402
from render import render_message, CHANNELS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SITE_URL = "https://theguysaccount.github.io/psych-sec-social-engineering-defense"
REPO_URL = "https://github.com/theguysaccount/psych-sec-social-engineering-defense"
INDEXNOW_KEY = (ROOT / "site" / "indexnow-key.txt").read_text().strip()
BRAND = "Spot the Scam"
MAKER = "Psych Sec"

LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false"><path d="M16 2 4 6.5v8.2c0 7.3 5.1 13.4 12 15.3 '
        '6.9-1.9 12-8 12-15.3V6.5L16 2z" fill="#0b5f8a"/><path d="m10.5 16.2 3.8 3.8 7.4-8" fill="none" stroke="#fff" '
        'stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')

IF_PAID = [
    "Contact the company you used to pay (your bank, card company, gift card company, payment app or wire service) right away and ask them to reverse the payment.",
    "If you shared a password, change it now and turn on two-factor authentication.",
    "If you gave out your Social Security number or other ID details, go to IdentityTheft.gov for a recovery plan.",
    "Report it to the FTC at ReportFraud.ftc.gov. For scams that happened online, you can also report to the FBI at ic3.gov.",
]
IF_PAID_SOURCE = {"title": "FTC: What to do if you were scammed", "url": "https://consumer.ftc.gov/articles/what-do-if-you-were-scammed"}

e = html.escape


def esc_attr(s):
    return html.escape(str(s), quote=True)


class Site:
    def __init__(self, out, today):
        self.out = out
        self.today = today
        self.site_url = os.environ.get("SITE_URL", DEFAULT_SITE_URL).rstrip("/")
        self.goatcounter = os.environ.get("GOATCOUNTER_URL", "").strip()
        self.team_url = os.environ.get("TEAM_VERSION_URL", "").strip()
        self.types = json.loads((ROOT / "data" / "types.json").read_text(encoding="utf-8"))
        self.items = json.loads((ROOT / "data" / "items.json").read_text(encoding="utf-8"))
        self.store = json.loads((ROOT / "data" / "alerts.json").read_text(encoding="utf-8"))
        self.by_slug = {t["slug"]: t for t in self.types}
        self.featured, self.why = alertlib.featured(self.store, self.types, on=today)
        self.week = "%d-W%02d" % tuple(today.isocalendar()[:2])
        self.pages = []  # (path, lastmod) for the sitemap
        self.ver = self._asset_version()

    # ---------- helpers ----------
    def _asset_version(self):
        h = hashlib.sha1()
        for p in sorted((ROOT / "site" / "assets").rglob("*")):
            if p.is_file():
                h.update(p.name.encode())
                h.update(p.read_bytes())
        h.update((ROOT / "data" / "items.json").read_bytes())
        return h.hexdigest()[:10]

    def url(self, path):
        return f"{self.site_url}/{path}"

    def og(self, slug):
        name = slug if (ROOT / "site" / "assets" / "og" / f"{slug}.png").exists() else "home"
        return f"{self.site_url}/assets/og/{name}.png"

    def items_of(self, slug):
        return [i for i in self.items if i["type"] == slug]

    def alerts_for(self, slug, n=5):
        return [a for a in self.store.get("alerts", []) if a.get("relevant") and slug in a.get("types", [])][:n]

    def fmt_date(self, iso):
        d = dt.date.fromisoformat(iso)
        return f"{d.strftime('%b')} {d.day}, {d.year}"

    def write(self, path, text):
        f = self.out / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    # ---------- layout ----------
    def layout(self, path, title, description, body, *, og=None, jsonld=None, noindex=False, current="", bare=False, root=None):
        depth = path.count("/")
        if root is None:
            root = "../" * depth if depth else "./"
        canonical = self.url(path)
        cfg = json.dumps({"root": root, "siteUrl": self.site_url, "teamUrl": self.team_url}, ensure_ascii=False)
        nav = [("", "Take the test"), ("scams/", "Scams"), ("alerts/", "Alerts"), ("about/", "About")]
        here = ' aria-current="page"'
        nav_html = "".join(f'<a href="{root}{p}"{here if p == current else ""}>{label}</a>' for p, label in nav)
        ld = ""
        for block in (jsonld or []):
            ld += '<script type="application/ld+json">%s</script>\n' % json.dumps(block, ensure_ascii=False).replace("</", "<\\/")
        gc = (f'<script data-goatcounter="{esc_attr(self.goatcounter)}" async src="https://gc.zgo.at/count.js"></script>\n'
              if self.goatcounter else "")
        privacy = ("We count page visits with GoatCounter, which uses no cookies and collects no personal data."
                   if self.goatcounter else "This site sets no cookies and collects no data. Your answers stay in your browser.")
        head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{esc_attr(description)}">
<link rel="canonical" href="{canonical}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:title" content="{esc_attr(title)}">
<meta property="og:description" content="{esc_attr(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og or self.og('home')}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0b5f8a">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}assets/site.css?v={self.ver}">
{ld}<script type="application/json" id="site-config">{cfg}</script>
<script type="module" src="{root}assets/app.js?v={self.ver}"></script>
{gc}</head>
<body>
"""
        if bare:
            return head + f'<main class="wrap">{body}</main>\n</body>\n</html>\n'
        return head + f"""<a class="skip" href="#main">Skip to content</a>
<header class="site-head"><div class="wrap">
<a class="logo" href="{root}">{LOGO}<span>{BRAND}</span></a>
<nav class="nav" aria-label="Main">{nav_html}</nav>
</div></header>
<main id="main" class="wrap">
{body}
</main>
<footer class="site-foot"><div class="wrap">
<nav aria-label="Footer"><a href="{root}how-to-spot-a-scam/">How to spot a scam</a><a href="{root}scams/">All scams</a><a href="{root}alerts/">Latest alerts</a><a href="{root}about/">About and privacy</a><a href="{REPO_URL}">Source code</a></nav>
<p>{BRAND} is a free project by {MAKER}. {privacy}</p>
<p>Lessons follow public guidance from the FTC and CISA. Not affiliated with any government agency or company. Company names in examples are invented; the tactics are real. Educational content, not legal or financial advice.</p>
<p>Lost money or shared information? Report it at <a href="https://reportfraud.ftc.gov/">ReportFraud.ftc.gov</a>.</p>
</div></footer>
</body>
</html>
"""

    def share_row(self, url, text, subject):
        from urllib.parse import quote
        body = f"{text} {url}"
        return (f'<div class="btn-row">'
                f'<button class="btn small" type="button" hidden data-share-native data-url="{esc_attr(url)}" data-text="{esc_attr(text)}" data-title="{esc_attr(subject)}">Share…</button>'
                f'<a class="btn small secondary" href="sms:?&amp;body={esc_attr(quote(body))}">Text it</a>'
                f'<a class="btn small secondary" href="mailto:?subject={esc_attr(quote(subject))}&amp;body={esc_attr(quote(text + chr(10) + chr(10) + url))}">Email it</a>'
                f'<a class="btn small secondary" href="https://wa.me/?text={esc_attr(quote(body))}" target="_blank" rel="noopener">WhatsApp</a>'
                f'<button class="btn small secondary" type="button" data-copy="{esc_attr(url)}">Copy link</button>'
                f'</div>')

    def alert_li(self, a, root):
        chips = "".join(f'<a class="chip" href="{root}scams/{t}/">{e(self.by_slug[t]["name"])}</a>' for t in a.get("types", []) if t in self.by_slug)
        return (f'<li><div class="src">{e(a["source"])} · <time datetime="{a["date"]}">{self.fmt_date(a["date"])}</time></div>'
                f'<a href="{esc_attr(a["url"])}" rel="noopener">{e(a["title"])}</a>'
                + (f'<p class="sum">{e(a["summary"])}</p>' if a.get("summary") else "")
                + (f'<div class="chips">{chips}</div>' if chips else "") + "</li>")

    def type_card(self, t, root):
        return (f'<a class="card" href="{root}scams/{t["slug"]}/"><h3>{e(t["name"])}</h3>'
                f'<p>{e(t["short"])}</p></a>')

    # ---------- pages ----------
    def home(self):
        root = "./"
        feat = [self.by_slug[s] for s in self.featured if s in self.by_slug]
        why_lines = "".join(
            f'<li><a href="{root}scams/{s}/">{e(self.by_slug[s]["name"])}</a>: '
            f'{e(w["source"])} alert, {self.fmt_date(w["date"])}, “<a href="{esc_attr(w["url"])}" rel="noopener">{e(w["title"])}</a>”</li>'
            for s, w in self.why.items())
        rest = [t for t in self.types if t["slug"] not in self.featured][:6]
        latest = [a for a in self.store.get("alerts", []) if a.get("relevant")][:5]
        share_text = "A free 2-minute test: can you tell scam texts, emails and calls from real ones? Scammers use AI now, so it's harder than it looks."
        body = f"""
<section class="hero">
<h1>Could you spot a scam written by AI?</h1>
<p class="lede">Ten realistic texts, emails and phone calls. For each one, decide: scam or legit? Then see the tricks you missed, with a short lesson for each.</p>
<p id="share-banner" class="banner" role="status" hidden></p>
<div data-quiz data-mode="weekly">
<div data-intro>
<div class="btn-row"><button class="btn" type="button" data-start>Start the 2-minute test</button></div>
<p class="meta">Free · No sign-up · Nothing you do here is saved or sent anywhere</p>
</div>
<div data-stage class="quiz" hidden></div>
</div>
<noscript><p class="callout">The test needs JavaScript. You can still read every lesson: <a href="scams/">common scams and how to spot them</a>.</p></noscript>
</section>

<section>
<h2>In this week's test</h2>
<p>Each week's test leans on the scams in the latest FTC alerts, so you practice on what's going around now.</p>
<ul class="chips">{''.join(f'<li><a class="chip" href="{root}scams/{t["slug"]}/">{e(t["name"])}</a></li>' for t in feat)}</ul>
{f'<ul class="sources">{why_lines}</ul>' if why_lines else ''}
</section>

<section>
<h2>Why practice?</h2>
<p>Scammers now use AI to write flawless messages and even clone voices, so the old advice to look for spelling mistakes doesn't work anymore. What still works is knowing their moves: a surprise problem or prize, pressure to act now, a request for secrecy, and strange ways to pay. A few minutes on realistic examples makes those moves easy to spot when a real one arrives.</p>
<p><a href="{root}how-to-spot-a-scam/">The 4 signs of a scam, and 5 habits that stop them →</a></p>
</section>

<section>
<h2>Scams to know right now</h2>
<div class="grid">{''.join(self.type_card(t, root) for t in feat + rest)}</div>
<p><a href="{root}scams/">All {len(self.types)} scams, with real examples →</a></p>
</section>

<section>
<h2>Latest scam alerts</h2>
<ul class="alerts">{''.join(self.alert_li(a, root) for a in latest)}</ul>
<p><a href="{root}alerts/">More alerts from the FTC, CISA and FBI →</a></p>
</section>

<section class="share-box">
<h2>Send it to someone you love</h2>
<p>Scams work best when they sound like someone you trust. Practicing together is the easiest way to protect parents, grandparents and teenagers.</p>
{self.share_row(self.site_url + "/?from=parents", share_text, "A 2-minute scam test worth taking")}
</section>
"""
        ld = [
            {"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": self.site_url + "/",
             "publisher": {"@type": "Organization", "name": MAKER}},
            {"@context": "https://schema.org", "@type": "Quiz", "name": "Spot the Scam: the 2-minute scam test",
             "url": self.site_url + "/", "inLanguage": "en", "isAccessibleForFree": True, "educationalUse": "assessment",
             "about": [{"@type": "Thing", "name": "Phishing"}, {"@type": "Thing", "name": "Fraud prevention"}],
             "description": "Judge ten realistic texts, emails and phone calls as scam or legit, then learn the tells."},
        ]
        self.write("index.html", self.layout(
            "", f"{BRAND}: free 2-minute scam test (texts, emails, calls)",
            "Can you tell a scam text, email or call from a real one? Take the free 2-minute test with realistic, AI-era examples, updated weekly from FTC alerts.",
            body, jsonld=ld, current=""))
        self.pages.append("")

    def scam_page(self, t):
        root = "../../"
        slug = t["slug"]
        items = self.items_of(slug)
        example = next((i for i in items if i["verdict"] == "scam"), None)
        alerts = self.alerts_for(slug)
        related = [x for x in self.types if x["slug"] != slug]
        k = self.types.index(t)
        related = (related[k:] + related[:k])[:3]
        path = f"scams/{slug}/"
        ex_html = ""
        if example:
            ex_html = f"""<h2>What it looks like</h2>
{f'<p class="context">{e(example["context"])}</p>' if example.get("context") else ''}
<div class="revealed-wrap">{render_message(example).replace('class="msg ', 'class="msg revealed ', 1)}</div>
<p><b>The tells:</b></p>
<ol>{''.join(f'<li>{e(f["text"])}</li>' for f in example["flags"])}</ol>
<p class="note">A training example written for this site. Names, numbers and links are made up, and links are disabled.</p>"""
        alerts_html = (f'<ul class="alerts">{"".join(self.alert_li(a, root) for a in alerts)}</ul>' if alerts else
                       "<p>No recent FTC, CISA or FBI alerts are tagged with this scam. The guidance below still applies.</p>")
        body = f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="{root}">Home</a> › <a href="{root}scams/">Scams</a> › {e(t["name"])}</nav>
<h1>{e(t["title"])}</h1>
<p class="lede">{e(t["short"])}</p>

<div class="card" data-quiz data-mode="type" data-type="{slug}">
<div data-intro>
<h2 style="margin-top:0">Could you spot it?</h2>
<p>{len(items)} quick example{'s' if len(items) != 1 else ''}. Decide scam or legit for each.</p>
<button class="btn" type="button" data-start>Test yourself</button>
</div>
<div data-stage class="quiz" hidden></div>
</div>

<h2>How it works</h2>
{''.join(f'<p>{e(p)}</p>' for p in t["how"])}

<h2>Red flags</h2>
<ul class="flags">{''.join(f'<li>{e(f)}</li>' for f in t["flags"])}</ul>

{ex_html}

<h2>What to do</h2>
<ol class="steps">{''.join(f'<li>{e(d)}</li>' for d in t["do"])}</ol>

<h2>If you already paid or shared information</h2>
<ol class="steps">{''.join(f'<li>{e(d)}</li>' for d in IF_PAID)}</ol>
<p class="note">From <a href="{IF_PAID_SOURCE["url"]}" rel="noopener">{e(IF_PAID_SOURCE["title"])}</a>.</p>

<h2>Latest alerts about this scam</h2>
{alerts_html}

<h2>Sources</h2>
<ul class="sources">{''.join(f'<li><a href="{esc_attr(s["url"])}" rel="noopener">{e(s["title"])}</a></li>' for s in t["sources"])}</ul>

<section class="share-box">
<h2>Know someone who should see this?</h2>
<p>Send them this page. It takes two minutes to read.</p>
{self.share_row(self.url(path), f"Have you seen this scam? {t['name']}: how it works and how to spot it.", f"Watch out for this scam: {t['name']}")}
</section>

<h2>Related scams</h2>
<div class="grid">{''.join(self.type_card(x, root) for x in related)}</div>
<p><a class="btn" href="{root}">Take the full 10-message test</a></p>
"""
        ld = [
            {"@context": "https://schema.org", "@type": "Article", "headline": t["title"], "description": t["description"],
             "dateModified": self.today.isoformat(), "inLanguage": "en", "mainEntityOfPage": self.url(path),
             "image": self.og(slug), "author": {"@type": "Organization", "name": MAKER},
             "publisher": {"@type": "Organization", "name": MAKER},
             "citation": [s["url"] for s in t["sources"]]},
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": self.site_url + "/"},
                {"@type": "ListItem", "position": 2, "name": "Scams", "item": self.url("scams/")},
                {"@type": "ListItem", "position": 3, "name": t["name"], "item": self.url(path)}]},
        ]
        self.write(path + "index.html", self.layout(path, f"{t['title']} | {BRAND}", t["description"], body,
                                                    og=self.og(slug), jsonld=ld, current="scams/"))
        self.pages.append(path)

    def scams_hub(self):
        root = "../"
        body = f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="{root}">Home</a> › Scams</nav>
<h1>{len(self.types)} common scams, and how to spot each one</h1>
<p class="lede">How each scam works, its red flags, a realistic example, and what to do. Each page has a short test so you can check yourself.</p>
<div class="grid">{''.join(self.type_card(t, root) for t in self.types)}</div>
<p><a class="btn" href="{root}">Take the 2-minute test</a></p>
"""
        self.write("scams/index.html", self.layout("scams/", f"{len(self.types)} common scams and how to spot them | {BRAND}",
                                                   "Toll texts, fake bank alerts, AI voice clones, task scams and more: how each scam works, its red flags and what to do.",
                                                   body, current="scams/"))
        self.pages.append("scams/")

    def how_to(self):
        root = "../"
        signs = [
            ("They pretend to be someone you trust.", "A government agency, your bank, a delivery company, your boss, a grandchild. Caller ID, logos and email names can all be faked, and AI can copy a voice or a face."),
            ("There's a problem or a prize.", "You owe money, your account is locked, a package is stuck, someone you love is in trouble, or you've won something."),
            ("They pressure you to act now.", "Pay today, stay on the line, don't tell anyone. Urgency is there to stop you from thinking or checking."),
            ("They tell you to pay in a specific way.", "Gift cards, crypto, a Bitcoin ATM, a wire transfer, a payment app or cash handed to a courier. No real agency or business insists on these."),
        ]
        habits = [
            "Don't use the link, number or code in a message you didn't expect. Open the app or type the website yourself, or call the number on your card or bill.",
            "Never share a verification code, password or PIN with anyone who contacts you.",
            "Slow down. Anyone who won't let you hang up and call back is a scammer.",
            "Talk to someone you trust before you pay. Scammers ask for secrecy because a second opinion stops them.",
            "Agree on a family code word, so a voice on the phone has to prove who it is.",
        ]
        body = f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="{root}">Home</a> › How to spot a scam</nav>
<h1>How to spot a scam: 4 signs, and 5 habits that stop them</h1>
<p class="lede">Scams change their stories every season, and AI has removed the spelling mistakes. The moves underneath don't change. Learn these and you'll spot most scams in seconds.</p>
<h2>The 4 signs</h2>
<ol>{''.join(f'<li><b>{e(a)}</b> {e(b)}</li>' for a, b in signs)}</ol>
<h2>5 habits that stop almost every scam</h2>
<ol class="steps">{''.join(f'<li>{e(h)}</li>' for h in habits)}</ol>
<div class="callout"><b>What AI changed:</b> perfect grammar, your name, your town and your boss's name are easy for scammers to fake now. A familiar voice or face on a call isn't proof either. Judge a message by what it asks you to do, not by how real it looks.</div>
<p><a class="btn" href="{root}">Practice on 10 real-world examples</a></p>
<h2>If you already paid or shared information</h2>
<ol class="steps">{''.join(f'<li>{e(d)}</li>' for d in IF_PAID)}</ol>
<h2>Sources</h2>
<ul class="sources">
<li><a href="https://consumer.ftc.gov/articles/how-avoid-scam" rel="noopener">FTC: How to avoid a scam</a></li>
<li><a href="{IF_PAID_SOURCE["url"]}" rel="noopener">{e(IF_PAID_SOURCE["title"])}</a></li>
<li><a href="https://www.cisa.gov/secure-our-world/recognize-and-report-phishing" rel="noopener">CISA: Recognize and report phishing</a></li>
</ul>
<h2>Learn the scams one by one</h2>
<div class="grid">{''.join(self.type_card(t, root) for t in self.types[:6])}</div>
<p><a href="{root}scams/">See all {len(self.types)} →</a></p>
"""
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": "How to spot a scam: 4 signs, and 5 habits that stop them",
               "dateModified": self.today.isoformat(), "inLanguage": "en", "mainEntityOfPage": self.url("how-to-spot-a-scam/"),
               "author": {"@type": "Organization", "name": MAKER}, "publisher": {"@type": "Organization", "name": MAKER}}]
        self.write("how-to-spot-a-scam/index.html", self.layout(
            "how-to-spot-a-scam/", f"How to spot a scam: 4 signs and 5 habits | {BRAND}",
            "The 4 signs every scam shares, 5 habits that stop them, and what AI changed. Based on FTC guidance.",
            body, jsonld=ld))
        self.pages.append("how-to-spot-a-scam/")

    def alerts_page(self):
        root = "../"
        rel = [a for a in self.store.get("alerts", []) if a.get("relevant")][:60]
        checked = self.store.get("checked")
        body = f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="{root}">Home</a> › Alerts</nav>
<h1>Latest scam alerts from the FTC, CISA and FBI</h1>
<p class="lede">The newest public warnings about scams, each linked to the original and to our lesson on that scam.</p>
<p class="note">Checked {self.fmt_date(checked) if checked else "weekly"}. This page updates itself every week from the <a href="https://consumer.ftc.gov/consumer-alerts" rel="noopener">FTC's consumer alerts</a>, <a href="https://www.cisa.gov/news-events/cybersecurity-advisories" rel="noopener">CISA's alerts</a> and the <a href="https://www.ic3.gov/PSA" rel="noopener">FBI's IC3 public service announcements</a>; only alerts about scams are listed.</p>
<ul class="alerts">{''.join(self.alert_li(a, root) for a in rel)}</ul>
<p><a class="btn" href="{root}">Test yourself on this week's scams</a></p>
"""
        self.write("alerts/index.html", self.layout("alerts/", f"Latest scam alerts from the FTC, CISA and FBI | {BRAND}",
                                                    "This week's public scam warnings from the FTC, CISA and FBI, linked to the originals and to how to spot each scam.",
                                                    body, current="alerts/"))
        self.pages.append("alerts/")

    def about(self):
        root = "../"
        embed = f'<iframe src="{self.site_url}/embed/" title="Spot the Scam: scam or legit?" width="100%" height="760" style="border:0;max-width:640px" loading="lazy"></iframe>'
        team = (f'<p><a class="btn" href="{esc_attr(self.team_url)}" rel="noopener">Get the team version</a></p>' if self.team_url else
                "<p>A team version with your own staff's results is planned but not available yet. The public test is free for anyone to use with their team today.</p>")
        body = f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="{root}">Home</a> › About</nav>
<h1>About {BRAND}</h1>
<p class="lede">A free practice test for spotting the scams of the AI era, by {MAKER}. The idea behind it: the weakest point in security is human psychology, not code, and the best defense is practice.</p>
<h2>How it works</h2>
<p>Each test shows ten messages: texts, emails, calls, chats, letters and ads. About six are scams and four are legitimate, so you have to judge, not just say “scam” to everything. After each answer you see the tells, highlighted in the message, and the safe move.</p>
<p>Everyone gets the same test each week, which makes scores comparable when you challenge a friend. It favors the scams named in the newest FTC alerts. “Take another test” gives you a fresh random set.</p>
<h2>Where the examples come from</h2>
<p>Every example was written for this site, modeled on scams described in public FTC and CISA alerts. Company names are invented, phone numbers use the 555-01xx range reserved for fiction, links are disabled, and the scam web addresses were checked to be unregistered when written. Lessons follow the FTC's and CISA's published guidance, linked on every page.</p>
<h2 id="privacy">Privacy</h2>
<p>{'We count visits with GoatCounter, which uses no cookies and collects no personal data. ' if self.goatcounter else 'No cookies, no tracking, no accounts. '}Your answers never leave your browser. A share link carries only the test's code and, if you choose, your score.</p>
<h2>Updates</h2>
<p>The site checks the FTC's consumer alerts, CISA's feeds and the FBI's IC3 announcements every week, updates the <a href="{root}alerts/">alerts page</a> and the lessons, and picks the next week's featured scams. New examples are added as new scams appear.</p>
<h2>Put the test on your site</h2>
<p>Libraries, senior centers, schools and IT teams can embed a weekly “scam or legit?” card. Paste this where you want it:</p>
<pre><code>{e(embed)}</code></pre>
<h2>For teams</h2>
{team}
<h2>Open source</h2>
<p>The code and content are on <a href="{REPO_URL}">GitHub</a>. Spotted a mistake, or a scam we should cover? <a href="{REPO_URL}/issues/new">Open an issue</a>.</p>
<h2>Not affiliated</h2>
<p>{BRAND} isn't affiliated with the FTC, CISA, any government agency or any company. It's educational and isn't legal or financial advice. If you lost money or shared personal information, report it at <a href="https://reportfraud.ftc.gov/">ReportFraud.ftc.gov</a>.</p>
"""
        self.write("about/index.html", self.layout("about/", f"About {BRAND} | {MAKER}",
                                                   "How the Spot the Scam test works, where its examples come from, privacy, and how to embed it.",
                                                   body, current="about/"))
        self.pages.append("about/")

    def embed(self):
        body = f"""
<div data-quiz data-mode="embed"><div data-stage class="quiz"></div></div>
<p class="note">From <a href="{self.site_url}/" target="_blank" rel="noopener">{BRAND}</a>, a free scam-spotting test. New message every week.</p>
"""
        self.write("embed/index.html", self.layout("embed/", f"Scam or legit? | {BRAND}", "This week's scam-or-legit question.",
                                                   body, noindex=True, bare=True))

    def not_found(self):
        # GitHub Pages serves 404.html at any depth, so its links are absolute.
        after_host = self.site_url.split("://", 1)[1]
        prefix = "/" + after_host.split("/", 1)[1] + "/" if "/" in after_host else "/"
        body = f"""
<h1>Page not found</h1>
<p>That page doesn't exist, or it moved.</p>
<p><a class="btn" href="{prefix}">Take the 2-minute scam test</a></p>
<p><a href="{prefix}scams/">Browse common scams</a></p>
"""
        self.write("404.html", self.layout("404.html", f"Page not found | {BRAND}",
                                           "That page doesn't exist. Take the free 2-minute scam test instead.", body, noindex=True, root=prefix))

    # ---------- data and meta files ----------
    def data_files(self):
        bank = {"types": {t["slug"]: {"name": t["name"], "short": t["short"]} for t in self.types}, "items": self.items}
        self.write("data/bank.json", json.dumps(bank, ensure_ascii=False, separators=(",", ":")))
        week = {"week": self.week, "built": self.today.isoformat(), "featured": self.featured, "why": self.why}
        self.write("data/week.json", json.dumps(week, ensure_ascii=False, indent=1))

    def meta_files(self):
        lastmod = self.today.isoformat()
        urls = "".join(f"<url><loc>{self.url(p)}</loc><lastmod>{lastmod}</lastmod></url>\n" for p in self.pages)
        self.write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
        self.write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {self.site_url}/sitemap.xml\n")
        self.write(f"{INDEXNOW_KEY}.txt", INDEXNOW_KEY)
        self.write(".nojekyll", "")
        (self.out / "urls.txt").write_text("".join(self.url(p) + "\n" for p in self.pages), encoding="utf-8")

    def assets(self):
        src = ROOT / "site" / "assets"
        dst = self.out / "assets"
        shutil.copytree(src, dst)
        app = dst / "app.js"
        app.write_text(app.read_text(encoding="utf-8").replace('from "./core.js"', f'from "./core.js?v={self.ver}"')
                       .replace('import("./selftest.js")', f'import("./selftest.js?v={self.ver}")'), encoding="utf-8")
        shutil.copy(ROOT / "site" / "favicon.svg", self.out / "favicon.svg")

    def build(self):
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        self.assets()
        self.home()
        self.scams_hub()
        for t in self.types:
            self.scam_page(t)
        self.how_to()
        self.alerts_page()
        self.about()
        self.embed()
        self.not_found()
        self.data_files()
        self.meta_files()
        return self


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    args = ap.parse_args()
    today = dt.date.fromisoformat(os.environ["BUILD_DATE"]) if os.environ.get("BUILD_DATE") else dt.datetime.now(dt.timezone.utc).date()
    site = Site(Path(args.out), today).build()
    print(f"built {len(site.pages)} pages into {args.out} (week {site.week}, featured: {', '.join(site.featured)})")


if __name__ == "__main__":
    main()
