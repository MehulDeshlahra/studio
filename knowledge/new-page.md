# New page playbook (owner 18 Nov: "whenever a new page comes, this activity needs to be done")
Run all 5 parts for every new page before its first post. Verify on real data (Business Discovery API, YouTube Data
API, web); never guess numbers. Finish all 5, then send the owner a short report.

0. WIRING (engine): channels/<id>/ with channel.json, bible.md, hooks.md, lessons.md, done.json; ~/.studio-accounts/<id>.json
   (page_id; publish.resolve fills keys); per-page tables (dm, rivals, hookstudy, site, trends, stories, musiclib, thumb);
   dashboard CHANNELS. core.pages() picks the folder up everywhere else. Old account = no warm-up (owner 18 Nov).
1. RIVALS: top pages in the niche on Instagram + YouTube Shorts (big names + small fast-growing ones found by the
   niche hashtags). For each: followers, posts per week, the 10 best reels of the last 30 days with views, and what
   made each work (hook in the first 3 s, topic, length, format, on-screen style).
   -> channels/<id>/rivals.md + knowledge/rivals.json.  Tools: engine/hookstudy.py (Business Discovery, hashtag_top),
   engine/rivals.py (YouTube API).
2. TRENDING NOW: what the niche talks about this week (news, regulators, Google Trends India, Reddit). 20 ranked
   video ideas, each with its hook line. Best ones -> channels/<id>/ideas.json (front of the queue).
3. FORMAT: from step 1, our best format: length, hook pattern, look, cover style, caption, hashtags.
   -> channels/<id>/bible.md, hooks.md, channel.json. Keep the niche's legal rules (finance: SEBI, education only).
4. MONEY: brands that sponsor creators of our size in the niche, what they pay, when to approach.
   -> knowledge/brands.json + MONEY.md.
5. SHIP: 3+ approved videos before the first slot; check every fact/number in each yourself; show the owner the
   frames before the first one posts.
History: Finance Fuel 19 Nov (first run of this playbook).
