"""Render the 1200x630 Open Graph share cards in site/assets/og/ with headless Chrome.

    python3 scripts/og.py            # home card + one card per scam type

Run it after adding a scam type (a type without a card falls back to home.png). Needs Google Chrome
or Chromium; set CHROME to its path if it isn't found.
"""
import html
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "assets" / "og"
CHROME = os.environ.get("CHROME") or next(
    (c for c in [shutil.which("google-chrome"), shutil.which("chromium"),
                 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"] if c and Path(c).exists()), None)

LOGO = ('<svg viewBox="0 0 32 32" width="64" height="64"><path d="M16 2 4 6.5v8.2c0 7.3 5.1 13.4 12 15.3 6.9-1.9 12-8 12-15.3V6.5L16 2z" '
        'fill="#5cb4e6"/><path d="m10.5 16.2 3.8 3.8 7.4-8" fill="none" stroke="#0c1620" stroke-width="2.8" stroke-linecap="round" '
        'stroke-linejoin="round"/></svg>')

CARD = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:1200px;height:630px;overflow:hidden}}
body{{background:#0f1720;color:#eef3f8;font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 display:flex;flex-direction:column;justify-content:space-between;padding:64px 72px;box-sizing:border-box;
 background-image:radial-gradient(circle at 92% 8%,rgba(92,180,230,.28),transparent 42%)}}
.top{{display:flex;align-items:center;gap:18px;font-size:34px;font-weight:750}}
.top span{{color:#9fb0c2;font-weight:500;font-size:26px}}
h1{{font-size:{size}px;line-height:1.08;margin:0;letter-spacing:-.02em;max-width:1000px}}
p{{font-size:32px;line-height:1.35;color:#b8c6d4;margin:18px 0 0;max-width:980px}}
.bottom{{display:flex;gap:16px;align-items:center}}
.pill{{background:#5cb4e6;color:#0c1620;font-weight:800;font-size:30px;padding:16px 30px;border-radius:999px}}
.tag{{border:2px solid #3a4b5c;color:#cdd8e3;font-size:26px;padding:12px 22px;border-radius:999px}}
</style></head><body>
<div class="top">{logo}<div>Spot the Scam <span>· free 2-minute test</span></div></div>
<div><h1>{title}</h1><p>{sub}</p></div>
<div class="bottom"><div class="pill">{cta}</div><div class="tag">Texts · emails · calls</div></div>
</body></html>"""


def render(name, title, sub, cta, work):
    size = 76 if len(title) < 40 else 64 if len(title) < 60 else 54
    page = work / f"{name}.html"
    page.write_text(CARD.format(logo=LOGO, title=html.escape(title), sub=html.escape(sub), cta=html.escape(cta), size=size),
                    encoding="utf-8")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                    f"--user-data-dir={work / 'profile'}", "--window-size=1200,630", "--virtual-time-budget=2000",
                    f"--screenshot={OUT / (name + '.png')}", page.as_uri()], check=True, capture_output=True)
    print(OUT / f"{name}.png")


def main():
    if not CHROME:
        raise SystemExit("Chrome not found; set CHROME")
    OUT.mkdir(parents=True, exist_ok=True)
    types = json.loads((ROOT / "data" / "types.json").read_text(encoding="utf-8"))
    work = Path(tempfile.mkdtemp())
    try:
        render("home", "Could you spot a scam written by AI?",
               "Ten realistic texts, emails and calls. Scam or legit? See the tricks you missed.", "Take the test", work)
        for t in types:
            render(t["slug"], t["name"], t["short"], "Could you spot it?", work)
    finally:
        shutil.rmtree(work)


if __name__ == "__main__":
    main()
