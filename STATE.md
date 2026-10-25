# State (2026-10-25)

- **Existing material:** two one-line Apple Notes (Dec 2025): "Automated pentesting/phishing firm, Psych Sec > Cyber Sec" and a 2023 "Anti Psy Ops" note about an AI that runs a scam, then tells the person and returns the money. No code, site, brand or users. The notes were read through the screening dossier; Apple Notes itself wasn't opened (it would need a macOS permission prompt nobody was there to answer).
- **What works now:** a live static site with a 10-message weekly test, 25 lesson pages, an alerts page, an embeddable card, share links, and three scheduled workflows (deploy, alert refresh, self-test with keep-alive).
- **What's limited:** the FTC's site blocks GitHub's runners (403), so the weekly job gets CISA and FBI alerts but FTC alerts only when a fetch gets through or the content routine adds them (OPERATIONS.md). The archive holds 33 FTC alerts from June–October 2026, read once in a browser.
- **Worth reusing elsewhere:** the static-quiz engine (`site/assets/core.js`: seeded weekly tests, share links that carry only a seed and score), the headless-Chrome self-test pattern (`?selftest=1` + `scripts/e2e.sh`), the keep-alive script, and the IndexNow script.
- **Not built (by design):** the B2B phishing-simulation product. It needs separate hosting, payments and written client authorization; it's the paid "team version" key.
