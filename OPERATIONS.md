# Operations

Spot the Scam runs itself on GitHub: Pages for hosting, Actions for every recurring job. Nobody needs to do anything for it to keep working. This file lists each automated job and how it fails safe, what to watch, and the keys Jack can turn later.

**Live:** https://scams.systemicaltruism.org/ (since 2026-11-22; the first address, https://theguysaccount.github.io/psych-sec-social-engineering-defense/, redirects there)
**Repo:** https://github.com/theguysaccount/psych-sec-social-engineering-defense

## Automated jobs

| Job | Workflow | When | What it does | How it fails safe |
|---|---|---|---|---|
| Deploy | `pages.yml` | every push to `main`, and after each weekly refresh | Python + JS unit tests, build `dist/`, play the built site end to end in headless Chrome, deploy to Pages, smoke-test the live site, ping IndexNow | A failed test or end-to-end run stops before deploy, so the last good site stays live. IndexNow failures are logged, never fatal. |
| Alert refresh | `refresh.yml` | Mondays 13:17 UTC | Pulls the FTC consumer-alert feed, CISA's alerts and news feeds and the FBI's IC3 public service announcements, tags each alert with a scam type, appends to `data/alerts.json`, lists FTC scam alerts no lesson covers (`data/candidates.json` and the run summary), commits, then dispatches `pages.yml` | A feed that errors or comes back empty keeps its old entries and records `last_error`; the run still succeeds. It fails only when **no** feed has worked for 21 days. Tests must pass before anything is committed. |
| Self-test + keep-alive | `selftest.yml` | Wednesdays 15:41 UTC | Unit tests; plays the **live** site end to end; checks every sitemap URL answers 200 with its own canonical; checks the quiz data loads, the site was rebuilt in the last 9 days, an alert feed worked in the last 10 days, and CISA source links resolve. Then the keep-alive. | On failure it opens (or comments on) one issue labeled `ops-alert`, and GitHub emails the repo owner. The site itself is untouched. |
| Keep-alive | `selftest.yml` → `scripts/keepalive.sh` | weekly, even if the self-test fails | Re-enables every scheduled workflow through the API, and pushes an empty `[skip ci]` commit when the last commit is 45+ days old | GitHub disables scheduled workflows in public repos after 60 days without activity. The weekly alert commit normally counts as activity; this covers weeks when nothing changed. |

The weekly test itself needs no job: every visitor's browser picks the same ten messages for the ISO week (seeded by the week number), favoring the scam types that `week.json` lists. `week.json` is rebuilt by each deploy from the newest alerts, topped up by a seasonal calendar (`SEASONAL` in `pipeline/alerts.py`) when alerts name fewer than three types.

## What to watch

- **Open `ops-alert` issues.** One issue collects repeated failures.
- **Retried fetches.** Since 2026-11-22 the self-test and the smoke test after each deploy load a page again after 10, 20 and 30 seconds when GitHub Pages answers with a 5xx, times out or drops the connection: at most six retries per run in `scripts/check_live.py` and four in `scripts/e2e.sh`, so a site that's really down still fails within minutes. Each retry leaves a warning on the run, and only a page that still fails counts. A 403 or 404 fails at once, so CISA's bot filter (which answers 403) is never asked twice.
- **The alert-refresh run summary** lists FTC scam alerts that no lesson covers yet. These are what the content routine (below) works from.
- **`data/alerts.json` → `sources.*.last_error`.** The FTC's bot filter (Akamai) answers GitHub's runners with `403`, tested 2026-10-25, so the weekly job can't read the FTC feed from Actions. It still tries every week and keeps every FTC alert it already has. CISA answers some runner addresses with `403` too, so each feed gets three tries. The FBI's IC3 feed works. The self-test fails only if **no** feed has worked for 10 days. The site doesn't route around the FTC's block (no browser disguises, no proxies). FTC alerts reach the site in two ways: whenever a weekly fetch gets through, and through the content routine (key 1), which reads the FTC site in a browser and adds new alerts to `data/alerts.json`.
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

> In theguysaccount/psych-sec-social-engineering-defense: open https://consumer.ftc.gov/consumer-alerts in a browser and add any alerts from the last two weeks that `data/alerts.json` lacks (same fields as the existing FTC entries, tagged with `pipeline/alerts.py`'s `classify`). Then read `data/candidates.json`, the newest entries in `data/alerts.json`, and `data/backlog.md`. For any scam the FTC warned about that no type covers, add a type to `data/types.json` (FTC/CISA sources only, verified in a browser). Then write 2–4 new items in `data/items.json`: at least one scam and, where one exists, one legitimate look-alike. Follow the rules in OPERATIONS.md ("Writing items"). Remove used seeds from `data/backlog.md`. Run `python3 -m unittest discover -s tests`, `node --test tests/js/*.test.mjs` and, for new types, `python3 scripts/og.py`. Commit and push to `main` only if every test passes. Never post anywhere else.

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

**Switched on 2026-11-22.** The domain rollout session pointed `scams.systemicaltruism.org` at GitHub (`CNAME scams → theguysaccount.github.io` in Namecheap's DNS), made it the Pages custom domain (certificate approved, HTTPS enforced), set `SITE_URL` = `https://scams.systemicaltruism.org` and redeployed. The self-test passed against the new address at 08:11 UTC; a run three minutes earlier failed only because the CDN still held the old home page (see step 4 below).

#### Exact commands to switch the base URL (added 2026-11-22)

The steps above as commands, for the domain rollout session or anyone with `gh` signed in as theguysaccount: to redo the switch, move to another name, or undo it. Every address the build writes into the site (canonicals, sitemap, robots.txt, Open Graph tags, JSON-LD, IndexNow) comes from the one repo variable `SITE_URL`, and the deploy smoke test and the weekly self-test follow it too, so no file needs editing. DNS is the domain rollout session's job; nothing in this repo changes DNS. Don't add a `CNAME` file: this site deploys through Actions, which ignores one.

```bash
REPO=theguysaccount/psych-sec-social-engineering-defense
DOMAIN=scams.systemicaltruism.org   # the chosen name: no https://, no trailing slash

# 0. DNS must already point at GitHub. Ask a public resolver (a local cache can be stale):
curl -s "https://dns.google/resolve?name=$DOMAIN&type=A"   # expect theguysaccount.github.io. and 185.199.108-111.153

# 1. Make it the Pages custom domain. GitHub requests a certificate, and github.io starts redirecting to it.
gh api -X PUT "repos/$REPO/pages" -f cname="$DOMAIN"

# 2. Enforce HTTPS once the certificate exists (minutes, sometimes hours). This tries every 2 minutes for 2 hours.
for i in $(seq 60); do gh api -X PUT "repos/$REPO/pages" -F https_enforced=true --silent 2>/dev/null && break; sleep 120; done
gh api "repos/$REPO/pages" --jq '{cname, https_enforced, certificate: .https_certificate.state}'   # expect true, "approved"

# 3. Switch the base URL and redeploy.
gh variable set SITE_URL -R "$REPO" --body "https://$DOMAIN"
gh workflow run pages.yml -R "$REPO"
sleep 20; gh run watch -R "$REPO" --exit-status "$(gh run list -R "$REPO" --workflow pages.yml --limit 1 --json databaseId --jq '.[0].databaseId')"

# 4. Pages' CDN keeps each page for up to 10 minutes (max-age=600), so wait before checking canonicals.
#    Then, from a checkout of this repo. (A machine whose DNS cache doesn't know the new name yet fails
#    these with "nodename nor servname provided"; the selftest.yml run on GitHub's runners still counts.)
sleep 600
scripts/e2e.sh "https://$DOMAIN/"
python3 scripts/check_live.py "https://$DOMAIN"
curl -sI "https://theguysaccount.github.io/${REPO#*/}/" | grep -i '^location'   # expect https://$DOMAIN/
gh workflow run selftest.yml -R "$REPO"
```

Afterwards: `gh repo edit "$REPO" --homepage "https://$DOMAIN"`, put the new address in the **Live:** line at the top, and add the domain to Google Search Console (key 5). To undo: `gh variable delete SITE_URL -R "$REPO"`, `gh api -X PUT "repos/$REPO/pages" -F cname=null`, then `gh workflow run pages.yml -R "$REPO"`.

### 3. Money: the team version

GitHub Pages is for non-commercial use, so the public test stays free and has no checkout. The money slot is a "Training a team? Get the team version" link on the results screen and the About page, hidden until the variable is set:

- Repo variable `TEAM_VERSION_URL` = the URL of the paid product (for example a Stripe Payment Link or a page on separate hosting). Then `gh workflow run pages.yml`.

The paid product itself (admin-authorized phishing and SMS simulations with a team dashboard) needs separate hosting, Stripe and written client authorization flows. It isn't built.

### 4. Analytics (activation metric)

Off by default, so the site can say "no cookies, no data". The code already counts these events when analytics are on: `test_start`, `test_complete/<score>-<total>` (**activation**), `share/<channel>`, `lesson_test_start`, `lesson_test_complete`, `embed_start`, `embed_answer`.

- Create a free GoatCounter site (needs an account), then set repo variable `GOATCOUNTER_URL` = `https://<code>.goatcounter.com/count`, and redeploy. The footer and About page switch their privacy text automatically.

### 5. Search Console

- Google: verify the site in Search Console (an HTML-file or DNS method needs Jack's Google account) and submit `/sitemap.xml`. Bing, Yandex and others already get every deploy through IndexNow.
- Crawlers read robots.txt only at the host root. That's handled account-wide: the [theguysaccount.github.io](https://github.com/theguysaccount/theguysaccount.github.io) repo rebuilds `https://theguysaccount.github.io/robots.txt` daily, listing this site's sitemap with every other live project's. Nothing to do here; on a custom domain, this repo's own `robots.txt` (already built) takes over.

## Writing items

Rules the tests enforce, and rules they can't:
- Fields: `id`, `type`, `verdict` (`scam`/`legit`), `channel`, `context`, `from`, `subject` (emails), `body`, `flags` (each `{text, quote}`), `why`, `do`. Each `quote` must appear verbatim in one paragraph of the message.
- Phone numbers: only the fictional 555-0100 to 555-0199 range. Links: always `[[like.this/path]]`, so they render unclickable.
- Company names are invented. Scam domains must be unregistered (check DNS) and never on `.gov`.
- Legit items must be fair: the context gives the fact a careful person would know (you ordered it, you requested the code).
- No sexual content, no real people, no real victims. Lures stay non-personal (the original idea's "intimate image" lure is ruled out).
- Lessons follow published FTC/CISA guidance and link to it. No legal, medical or financial advice beyond that guidance.
