# Launch and distribution

The site launched on 2026-10-25 at https://theguysaccount.github.io/psych-sec-social-engineering-defense/, ahead of the November–December delivery-scam and fake-store season. Distribution is machine-only: nothing is posted by or as a person.

## Channels that run themselves

| Channel | How | Status |
|---|---|---|
| Search | 25 lesson pages, each titled for a search people make ("Unpaid toll text scams: how to spot them", "Family emergency and AI voice-clone scams"), plus "How to spot a scam" and a weekly-updated alerts page. Canonicals, sitemap, Article/Breadcrumb/Quiz structured data, Open Graph cards per page. | Live |
| IndexNow | Every deploy submits all URLs (Bing, Yandex, Seznam, Naver). Key file at the site root. | Live |
| Share loop | Results screen: "Send this test to your parents" and "Challenge a friend" (same test, shows the friend's score on arrival). Text, email, WhatsApp, native share, copy. Every lesson page has "Know someone who should see this?". | Live |
| Embed | `/embed/`: a weekly "scam or legit?" card for libraries, senior centers, schools and IT intranets. Snippet on the About page. | Live |
| GitHub | Public repo with description, topics and a README. | Live |
| Freshness | Weekly FTC/CISA pull updates the alerts page and lesson pages; the week's test features the scams in the news. | Live |

## Search terms the pages answer

- Test intent: "scam test", "phishing quiz", "spot the scam", "can you spot a scam", "scam quiz for seniors", "phishing test for employees".
- Scam-specific: "unpaid toll text scam", "USPS text scam", "fake bank fraud alert call", "FTC deactivate phone number call", "jury duty scam call", "grandparent scam voice clone", "tech support pop-up scam", "Geek Squad renewal email scam", "task scam job", "wrong number text crypto", "QR code parking scam", "Medicare card scam call", "rental deposit scam", "fake check overpayment scam".
- Advice: "how to spot a scam", "what to do if you were scammed", "latest scam alerts".

## The first 1,000 users (machine plan)

1. **Weeks 1–2:** indexation. IndexNow covers Bing-family engines on the first deploy. Google discovers the site through links and needs Search Console (key 5 in OPERATIONS.md) to be fast.
2. **Weeks 2–8:** holiday-season lesson pages (delivery texts, fake stores, charity, gift cards) are the most searched; the weekly test features them automatically through the seasonal calendar and FTC alerts.
3. **Share loop:** every completion offers two shares. Measurable once analytics are on (key 4): target 0.3+ shares per completion.
4. **Embeds:** each embed is a permanent referral source and a backlink.

Success at 14 days, once analytics are on: 1,000 completed tests, 30% of visitors who start finish, 0.3 shares per completion.

## Production domain

None owned for this idea. Three candidates, the DNS records, and the switch-over steps are in OPERATIONS.md (key 2). Nothing has been bought or pointed.
