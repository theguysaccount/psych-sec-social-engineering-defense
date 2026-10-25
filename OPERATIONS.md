# Operations

Spot the Scam runs itself on GitHub: Pages for hosting, Actions for every recurring job. Nobody needs to do anything for it to keep working. This file lists each automated job and how it fails safe, what to watch, and the keys Jack can turn later.

**Live:** https://theguysaccount.github.io/psych-sec-social-engineering-defense/
**Repo:** https://github.com/theguysaccount/psych-sec-social-engineering-defense

## Automated jobs

| Job | Workflow | When | What it does | How it fails safe |
|---|---|---|---|---|
| Deploy | `pages.yml` | every push to `main`, and after each weekly refresh | Python + JS unit tests, build `dist/`, play the built site end to end in headless Chrome, deploy to Pages, smoke-test the live site, ping IndexNow | A failed test or end-to-end run stops before deploy, so the last good site stays live. IndexNow failures are logged, never fatal. |
| Alert refresh | `refresh.yml` | Mondays 13:17 UTC | Pulls the FTC consumer-alert feed and CISA's alerts and news feeds, tags each alert with a scam type, appends to `data/alerts.json`, lists FTC scam alerts no lesson covers (`data/candidates.json` and the run summary), commits, then dispatches `pages.yml` | A feed that errors or comes back empty keeps its old entries and records `last_error`; the run still succeeds. It fails only when **no** feed has worked for 21 days. Tests must pass before anything is committed. |
| Self-test + keep-alive | `selftest.yml` | Wednesdays 15:41 UTC | Unit tests; plays the **live** site end to end; checks every sitemap URL answers 200 with its own canonical; checks the quiz data loads, the site was rebuilt in the last 9 days, an alert feed worked in the last 10 days, and CISA source links resolve. Then the keep-alive. | On failure it opens (or comments on) one issue labeled `ops-alert`, and GitHub emails the repo owner. The site itself is untouched. |
| Keep-alive | `selftest.yml` → `scripts/keepalive.sh` | weekly, even if the self-test fails | Re-enables every scheduled workflow through the API, and pushes an empty `[skip ci]` commit when the last commit is 45+ days old | GitHub disables scheduled workflows in public repos after 60 days without activity. The weekly alert commit normally counts as activity; this covers weeks when nothing changed. |

The weekly test itself needs no job: every visitor's browser picks the same ten messages for the ISO week (seeded by the week number), favoring the scam types that `week.json` lists. `week.json` is rebuilt by each deploy from the newest alerts, topped up by a seasonal calendar (`SEASONAL` in `pipeline/alerts.py`) when alerts name fewer than three types.

## What to watch

- **Open `ops-alert` issues.** One issue collects repeated failures.
- **The alert-refresh run summary** lists FTC scam alerts that no lesson covers yet. These are what the content routine (below) works from.
- **`data/alerts.json` → `sources.*.last_error`.** On 2026-10-25 the FTC's bot filter blocked this build machine after a burst of link checks; the feed works from a normal reader. If GitHub's runners are blocked too, the FTC entry shows `403` every week while CISA keeps working, and the self-test fails after 10 days without any working feed. Fix: nothing to change in code; FTC alerts can also be added by the content routine, which reads the FTC site through a browser.
- **FTC source links** can't be checked by a script (FTC blocks automated requests). The links were verified in a browser on 2026-10-25. The content routine re-checks them.

## How to run anything by hand

```bash
python3 pipeline/alerts.py fetch                 # pull feeds into data/alerts.json
python3 pipeline/alerts.py candidates            # scam alerts no lesson covers yet
python3 pipeline/build.py                        # build dist/
scripts/e2e.sh                                   # play dist/ in headless Chrome
scripts/e2e.sh https://theguysaccount.github.io/psych-sec-social-engineering-defense/
python3 scripts/check_live.py https://theguysaccount.github.io/psych-sec-social-engineering-defense
~/.local/bin/gh workflow run refresh.yml -R theguysaccount/psych-sec-social-engineering-defense
```

## Keys Jack can turn later

Nothing below is needed for the site to work. Each is off until someone with the right account turns it on.

### 1. Content routine (new quiz items from new scams)

AI-written content can't run inside Actions (no API key). The bank ships with 70 items across 25 scam types, plus 40 more scenario seeds in [`data/backlog.md`](data/backlog.md). To keep adding items without a person, schedule a Claude Code routine (claude.ai/code → Routines, or `/schedule` in Claude Code), weekly on Tuesdays, on this repo, with this prompt:

> In theguysaccount/psych-sec-social-engineering-defense: read `data/candidates.json` and the newest entries in `data/alerts.json`, and `data/backlog.md`. For any scam the FTC warned about that no type covers, add a type to `data/types.json` (FTC/CISA sources only, verified in a browser). Then write 2–4 new items in `data/items.json`: at least one scam and, where one exists, one legitimate look-alike. Follow the rules in OPERATIONS.md ("Writing items"). Remove used seeds from `data/backlog.md`. Run `python3 -m unittest discover -s tests`, `node --test tests/js/*.test.mjs` and, for new types, `python3 scripts/og.py`. Commit and push to `main` only if every test passes. Never post anywhere else.

Cost: one routine run a week on Jack's Claude plan.

### 2. Custom domain

No owned domain matched in the 2026-08-30 portfolio. Candidates (checked 2026-10-25 by WHOIS):

| # | Domain | Status | Note |
|---|---|---|---|
| 1 | `scams.systemicaltruism.org` | owned parent domain (Namecheap) | Free; ties it to the public-good line. One CNAME. |
| 2 | `psychsec.org` | unregistered, about $10/yr | The maker brand; the test lives at the root. |
| 3 | `spotthescamtest.com` | unregistered, about $11/yr | Exact-match for the product and the search phrase. |

`spotthescam.com`, `spotthescam.org`, `psychsec.com`, `scamorlegit.com/.org` and `isitascam.org` are taken.

Steps once Jack picks one (and approves any purchase):
1. DNS. For a subdomain: `CNAME scams → theguysaccount.github.io`. For an apex domain: `A @ → 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153`, plus `AAAA @ → 2606:50c0:8000::153, 2606:50c0:8001::153, 2606:50c0:8002::153, 2606:50c0:8003::153`, and `CNAME www → theguysaccount.github.io`.
2. Repo → Settings → Pages → Custom domain → enter it, wait for the certificate, tick **Enforce HTTPS**.
3. Repo → Settings → Secrets and variables → Actions → Variables → `SITE_URL` = `https://<domain>` (no trailing slash). Canonicals, sitemap, share links and IndexNow switch over on the next deploy (`gh workflow run pages.yml`).
4. The old github.io URLs redirect to the custom domain automatically.

### 3. Money: the team version

GitHub Pages is for non-commercial use, so the public test stays free and has no checkout. The money slot is a "Training a team? Get the team version" link on the results screen and the About page, hidden until the variable is set:

- Repo variable `TEAM_VERSION_URL` = the URL of the paid product (for example a Stripe Payment Link or a page on separate hosting). Then `gh workflow run pages.yml`.

The paid product itself (admin-authorized phishing and SMS simulations with a team dashboard) needs separate hosting, Stripe and written client authorization flows. It isn't built.

### 4. Analytics (activation metric)

Off by default, so the site can say "no cookies, no data". The code already counts these events when analytics are on: `test_start`, `test_complete/<score>-<total>` (**activation**), `share/<channel>`, `lesson_test_start`, `lesson_test_complete`, `embed_start`, `embed_answer`.

- Create a free GoatCounter site (needs an account), then set repo variable `GOATCOUNTER_URL` = `https://<code>.goatcounter.com/count`, and redeploy. The footer and About page switch their privacy text automatically.

### 5. Search Console and the root robots.txt

- Google: verify the site in Search Console (an HTML-file or DNS method needs Jack's Google account) and submit `/sitemap.xml`. Bing, Yandex and others already get every deploy through IndexNow.
- Crawlers read robots.txt only at the host root (`theguysaccount.github.io/robots.txt`, which 404s, meaning "allow all"). A custom domain fixes this; so would a `theguysaccount.github.io` user-site repo with a robots.txt listing each project's sitemap. That repo is shared by every project on the account, so it's left to Jack.

## Writing items

Rules the tests enforce, and rules they can't:
- Fields: `id`, `type`, `verdict` (`scam`/`legit`), `channel`, `context`, `from`, `subject` (emails), `body`, `flags` (each `{text, quote}`), `why`, `do`. Each `quote` must appear verbatim in one paragraph of the message.
- Phone numbers: only the fictional 555-0100 to 555-0199 range. Links: always `[[like.this/path]]`, so they render unclickable.
- Company names are invented. Scam domains must be unregistered (check DNS) and never on `.gov`.
- Legit items must be fair: the context gives the fact a careful person would know (you ordered it, you requested the code).
- No sexual content, no real people, no real victims. Lures stay non-personal (the original idea's "intimate image" lure is ruled out).
- Lessons follow published FTC/CISA guidance and link to it. No legal, medical or financial advice beyond that guidance.
