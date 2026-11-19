# MONEY.md: the master plan (owner 18 Nov: "the ultimate goal is to earn money")

Read this at the start of every session, after STATE.md. Update the checklist when something is done (date + proof).
Owner rules that shape it: Rs 0 spend, free tools, no on-screen AI label, never sign up or pay on his behalf (ask him),
he prefers NEW PAGES over more versions of the same video, don't be defensive, use the server AND the laptop fully.

## 1. Where money comes from (checked 18 Nov 2026)
| Stream | Gate | Typical pay (India) | Source |
|---|---|---|---|
| Brand deals (sponsored reels, integrations) | ~10k followers with steady views; brands pay for VIEWS and audience fit | micro 10k-100k: Rs 8,000-50,000 a reel; mid: Rs 50,000-3.5 lakh | [upGrowth](https://upgrowth.in/influencer-marketing-pricing-india-2026/), [Tring](https://www.tring.co.in/brands/blogs/top-indian-influencers-per-post-charges-2026-edition) |
| YouTube fan funding + Shopping (affiliate) | 500 subs + 3 uploads/90 d + 3M Shorts views/90 d | Super Thanks, memberships, product commissions | [YouTube help](https://support.google.com/youtube/answer/94522) |
| YouTube ad share (YPP) | 1,000 subs + 10M Shorts views/90 d (20M for new applicants from Feb 2027) | Shorts RPM is tiny: ~$0.01-0.06 per 1,000 views | [YouTube help](https://support.google.com/youtube/answer/72851), [vidIQ](https://vidiq.com/blog/post/youtube-shorts-monetization/) |
| Instagram | Gifts 500, Creator Marketplace 1,000 (brands find you), Subscriptions 10,000; bonuses invite-only | brand deals are the real money | [Blotato](https://www.blotato.com/blog/how-to-monetize-instagram) |
| Facebook | Stars 500 followers for 30 days; Content Monetization invite-only | per-view payouts once invited | [creators.facebook.com](https://creators.facebook.com/programs/bonuses) |
| Affiliate links (Amazon/Flipkart, apps) | none (needs Mehul's sign-up) | % of sales; fits tech reviews and katha (puja items, books) | owner decision |
| Later: own products (ebooks of the serials, katha audio series, wallpapers), page sales, services | audience first | | |

Conclusion: Shorts ad revenue alone is small. The money is BRAND DEALS + affiliate + fan funding, and all of them
need (a) real followers in a clear niche, (b) steady views, (c) a page a brand can trust. So: growth first, brand
readiness in parallel, money streams switched on the day each gate opens (engine/money.py tracks every gate).

## 2. Why would a brand pick us (think like the brand)
A brand buys: the right audience (Indian, Hindi, age 16-35), real reach (views per reel, not followers), trust (the
page looks professional, consistent, no fake engagement), safety (no controversy), proof (past results, a media kit),
and easy work (fast reply, clear rates, creative that fits their ad). Our edge: 3 niche pages = 3 audiences in one deal,
daily posting, fast turnaround, original formats (no reposts), a consistent premium look.
Brand categories that sponsor our niches (to confirm from knowledge/brands.json):
- tech: phones (Samsung, OnePlus, Realme, iQOO, Nothing), apps (finance, edtech, VPN, AI tools), gadgets, telecom.
- katha: devotional apps (Sri Mandir, Kundli/astrology apps), puja/ayurveda products, spiritual books, pilgrim travel.
- raaz: story/audio apps (Pocket FM, Kuku FM, Pratilipi), OTT thrillers, mobile games.

## 3. What is built (for this goal)
- engine/rivals.py (daily 05:10): leaders + climbers per niche, subscriber growth, usual views, 3x outliers ->
  channels/<id>/rivals.md (ideas.py uses the proven topics); sponsor lines -> knowledge/brands.json (outreach list);
  Sunday strategy read -> knowledge/rivals.md ("what the leaders do that we do not", gap, money moves) + brain.
- engine/money.py (daily 08:50): followers/subs/90-day views vs every gate, ETA at the 7-day pace -> STATE.md.
- Laptop (tools/laptop_worker.py): renders (3x faster) and, when idle, measures the winners' Shorts (length, cuts per
  10 s, first cut, loudness) -> knowledge/edit-metrics.json -> rivals.md "How the winners edit".
- Learning: deep repo reader (32 repos, 3 runs a day), web articles (learn.py web), radar (06:30), trends (06:00),
  hook study (Mon), brain with scored items. Captions carry a "send it to a friend" line (IG ranks sends highest).

## 4. Server vs laptop (no idle time)
- Server (2 cores, 24x7): planning, voice, pictures, captions, pre-render checks, posting, Stories, comments, all the
  learning/radar/rivals jobs (network + free LLM bound, not CPU), healer. Builds the next video while the laptop renders.
- Laptop (8 threads + GTX 1650, when on): renders first; idle time -> competitor measurement; next candidates:
  pre-render snapshots, the hand-made Lemo specials (WebGL), heavier analysis of our own posted videos (drop-off frames).
- LLM-bound work (learning) gains nothing from the laptop: the limit is free model quota, already spread over 11 Gemini
  keys + 2 Groq + OmniRoute. Rule: add laptop jobs only when they need CPU/GPU.

## 5. Plan (do in order; tick with date + proof)
### Now: launch and grow (20 Nov onwards)
- [x] 18 Nov rivals tracker, money tracker, laptop renders + measurement, web learning, send line in captions.
- [ ] 20 Nov first posts on all 3 pages; verify IG, FB, YT, Stories, first comment (launch checklist in RESUME).
- [ ] Weekly: read knowledge/rivals.md, turn the 5 money moves into build-queue items, apply the proven topics.
- [ ] Posting pace after warm-up (27 Nov): tech 2/day, katha 1, raaz 1; raise when the first-pass rate allows.
- [ ] Series formats that bring followers back daily (raaz serials exist; katha 5-7 part series; tech "myth vs sach").
- [x] 18 Nov https://scrollhouse.in live (GitHub Pages, HTTPS enforced, cert approved; www -> apex). Bios: Mehul pastes.
### Brand readiness (start before 10k, so the first brand finds us ready)
- [x] 19 Nov brand kit automated (engine/brand.py, daily 06:20): real IG DPs -> Facebook DP + cover set via Graph API on all 5 pages
      (proof: journal studio-job-brand "Facebook DP set"/"cover set" x5), circle-safe DP, YouTube banner, IG highlight covers in
      brand/<id>/ on the server. Not possible by API (Mehul uploads): IG DP + highlights, YouTube DP + banner.
- [x] 19 Nov media kit per page LIVE: https://scrollhouse.in/kit/<page>.html (auto-built daily, engine/mediakit.py); link-in-bio pages https://scrollhouse.in/go/<page>.html; internal rate card knowledge/ratecard.md fills once 3 reels have views.
- [ ] (was) Media kit page per page (GitHub Pages, auto-updated from money.json + results): audience, reach, best reels,
      formats offered, contact. Build when each page has ~2 weeks of numbers.
- [ ] Business contact: a dedicated email for brand inquiries (ASK MEHUL: a sign-up), shown in every bio.
- [ ] Rate card draft from real views (rule of thumb: Rs 0.3-1 per expected view, checked against pricemyreel-type data).
- [ ] Instagram Creator Marketplace when IG hits 1,000 (brands search it).
- [ ] Outreach list: brands from knowledge/brands.json with the exact creator they sponsored and the format. Outreach
      emails only after Mehul approves the wording (sending = his click or his OK).
### Money switches (the day each gate opens; money.py shows the ETA)
- [ ] YouTube fan funding + Shopping at 500 subs / 3M views (90 d).
- [ ] Facebook Stars at 500 followers; ask for Content Monetization access in the Professional Dashboard.
- [ ] Instagram Gifts at 500.
- [ ] Affiliate: Amazon Associates / Flipkart (ASK MEHUL to sign up when tech has steady views).
- [ ] YPP ads at 1,000 subs + 10M Shorts views (before Feb 2027, when it becomes 20M).
### More inventory (owner likes new pages; expansion on hold until the 3 pages run clean, then)
- [x] 18 Nov 22:30: Navkar Bhav (channels/jain, @navkarbhav, Jain stories) + Finance Fuel (channels/finance, @finance.fuel, money explainers, lab look, SEBI-safe rules + not-advice caption footer) added; first videos building; posting from 22 Nov (warm-up). Proof: Meta page keys + IG ids resolved on the server.
- [ ] English stories page (next in the agreed order).

### 5a. Finance Fuel: the highest-paying niche (deep dive 19 Nov; data in knowledge/brands.json "finance")
- Proof of who pays (their own video descriptions, YouTube API, 19 Nov): Ditto (Warikoo, Pranjal Kamra, CA Rachana
  Ranade), Zerodha/Coin (4 big creators), INDmoney, slice (Labour Law Advisor promo code), Scapia + Tata Neu card
  referrals (Rajesh Singh, 47.7k subs), Monzy card finder, CreditCase, smallcase, Tickertape, CG Police awareness collab.
- Rates (India 2026): nano ₹2,000-8,000 per post; micro (10k-100k) ₹8,000-80,000 per deliverable (Tring, upGrowth);
  rates follow average views; finance sits at the top of each band.
- SEBI line we never cross: education only, no tips, no return claims, no market prices from the last 3 months.
  That keeps brokers/AMCs possible (SEBI Common Advertisement Code, approved 24 Sep 2026); banks, cards, insurance,
  payments and tax apps are not SEBI-regulated and can work with us from day 1.
- [ ] NOW (ASK MEHUL, sign-ups): card referral programs (Scapia, Tata Neu, slice) and an insurance partner link
      (Ditto) in the bio link; each needs his own account.
- [ ] At 10k followers or 3 reels over 100k views: pitch slice, CRED, Ditto, Jupiter, Fi (paid reel, ₹8k-25k at that size).
- [ ] Scam-alert series + numbers: offer it to bank fraud-awareness / police campaigns.
- [ ] ITR season (June-July 2027): tax-filing affiliates (ClearTax, Quicko, TaxBuddy).

## 5b. Parent brand: Scroll House (owner picked 18 Nov)
- Genre-, language- and format-neutral network name. Every page bio: "A Scroll House page".
- Domain scrollhouse.in (Mehul bought it 18 Nov). Instagram @scrollhouse.in (Mehul created). YouTube @scrollhouse free (claim it).
  Taken by others: scrollhouse.com (2021), .co.in and .co (2026). Optional backup: scrollhousemedia.com (free 18 Nov).
- Site: engine/site.py -> docs/ (GitHub Pages of offhours-lab/studio), rebuilt daily 09:05 from money.json + done.json;
  numbers appear once they exist ("Launching 20 Nov" until then). Brand email to add when Mehul makes it.
- LIVE 18 Nov: https://scrollhouse.in (DNS at GoDaddy: 4 A records to GitHub + CNAME www; .IN KYC approved same day).

## 6. What only Mehul can do (ask, don't wait silently)
- A business email for brand deals (one free Gmail, e.g. kaise.tech.collab@...): needs his sign-up.
- Affiliate accounts (Amazon Associates, Flipkart, app referral programs) when the gates are close.
- Approve outreach wording and rates before any brand is contacted; sign contracts; receive payments.
- Bank/tax details inside YouTube AdSense, Meta payouts when each program opens.

## Cut Capsule: paid clipping (19 Nov, built)
How it pays: Whop Content Rewards campaigns pay per 1,000 verified views of our posts of their footage (live today: $1-3
per 1K, caps $150-1,200 per clip, 120 campaigns, top: Jo Koy comedy special $2/1K cap $500, Eneba gaming $3/1K, Call of
Duty DMZ $1.50/1K cap $1,200, FaZe tournament $2/1K). Whop keeps 10%. Money = many clips at 20-60K views on campaigns
with budget left.
The loop (all automatic except the owner's clicks):
1. engine/campaigns.py (every 6 h): ranks every campaign (rate, cap, budget left + runway, competition, fit; no betting,
   no other-language, no zero-rate) -> Telegram "worth joining" + dashboard Channels > Clipping campaigns.
2. OWNER: join on Whop, then dashboard "I joined" -> paste the footage channel/video links + the brief's rules.
3. engine/clipwatch.py (hourly): new uploads of those sources -> engine/clipper.py -> laptop clipcore (~1 min/clip on
   NVENC) -> checks -> Telegram for approval (first 3) -> publish.py posts IG + FB (YT once connected).
4. After each campaign post: Telegram "submit this link to <campaign>" (OWNER: paste it in Whop; views count from there).
5. stats.py views -> clipper.what_worked() feeds the best/worst hooks back into moment picking (results-clips.md).
- [ ] Owner: join 3-5 top campaigns (Telegram digest 19 Nov 06:41 has 17)
- [ ] Owner: Cut Capsule YouTube channel (most campaigns also pay YouTube Shorts views; doubles reach per clip)
- [ ] After warm-up (27 Nov): posts_per_day 2 -> 4 if the account stays healthy (more posts = more paid views)
