# Spot the Scam

**Live:** https://theguysaccount.github.io/psych-sec-social-engineering-defense/ · **Screens:** [desktop and phone](docs/screens/)

A free two-minute test of the scams of the AI era. You see ten realistic texts, emails, phone calls, chats, letters and ads, and decide for each: scam or legit? Then you see the tells, highlighted in the message, and a short lesson. It's built for anyone, and especially for sending to parents.

- **25 scam types**, each with a lesson page: how it works, red flags, a real-looking example, what to do, a mini test, and the latest FTC and CISA alerts about it.
- **70 messages** in the bank, about a quarter of them legitimate, so you have to judge rather than say "scam" to everything.
- **Updated weekly from public alerts.** A GitHub Action pulls the FTC's consumer alerts, CISA's feeds and the FBI's IC3 announcements every Monday, tags them by scam type, and the week's test leans on the scams in the news. (The FTC blocks GitHub's servers, so FTC alerts also arrive through the content routine; see OPERATIONS.md.)
- **Share loop built in.** "Send this test to your parents" and "Challenge a friend" links replay the same test; a friend's link carries only the test code and the score.
- **No server, no tracking.** Static files on GitHub Pages. Answers stay in the browser.

Made by Psych Sec. Not affiliated with the FTC, CISA or any company named in examples (the names are invented).

## How it runs (no human in the loop)

| What | Where | When |
|---|---|---|
| Test, build, play end to end in headless Chrome, deploy, smoke-test live, IndexNow | `.github/workflows/pages.yml` | every push, and weekly after the refresh |
| Pull FTC, CISA and FBI alerts, tag, commit, redeploy | `.github/workflows/refresh.yml` | Mondays |
| Live end-to-end test, page and data health checks, keep-alive | `.github/workflows/selftest.yml` | Wednesdays |

Details, failure modes and the keys that switch on a custom domain, analytics and a paid team version: [OPERATIONS.md](OPERATIONS.md).

## Layout

```
data/types.json        25 scam types: lesson text, red flags, what to do, FTC/CISA sources, alert keywords
data/items.json        the message bank (see OPERATIONS.md, "Writing items")
data/alerts.json       FTC, CISA and FBI alert archive, updated weekly by refresh.yml
data/backlog.md        scenario seeds for future items
pipeline/alerts.py     fetch, parse, tag and merge alerts; pick the week's featured scam types
pipeline/build.py      static site generator (standard library only) -> dist/
pipeline/render.py     message rendering at build time (mirrors site/assets/core.js)
site/assets/           core.js (quiz logic), app.js (UI), selftest.js (end-to-end driver), site.css, og/ cards
scripts/               e2e.sh, screens.sh, og.py, indexnow.py, check_live.py, keepalive.sh
tests/                 Python tests (content, alerts, build) and tests/js (logic, renderer parity)
```

## Run, test, deploy

Python 3.9+ and Google Chrome. Node 18+ for the JS tests.

```bash
python3 pipeline/build.py                 # build dist/
python3 -m http.server -d dist 8000       # open http://localhost:8000
python3 -m unittest discover -s tests     # content, alerts, build
node --test tests/js/*.test.mjs           # quiz logic, Python/JS renderer parity
scripts/e2e.sh                            # play dist/ end to end in headless Chrome
scripts/screens.sh                        # refresh docs/screens/
python3 scripts/og.py                     # refresh share cards after adding a scam type
```

Deploy is a push to `main`: `pages.yml` tests, builds and publishes to GitHub Pages.

## License

Code: MIT (see LICENSE). Lesson text and example messages: CC BY 4.0. Alert titles and summaries are from the FTC, CISA and FBI (U.S. government works) and link to the originals.
