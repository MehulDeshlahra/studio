# RESUME
## 18 Nov 11:00-15:00: money plan, laptop, competitors, Scroll House (details: knowledge/MONEY.md, laptop.md, lemo.md)
- DONE + verified: laptop render worker (3x faster, auto/fast/quiet/off toggle, 4 live renders); prep builds while the
  laptop renders; deep repo reader (32 repos, 3 runs/day, Lemo 25/194); web article learning; GitHub token (5000/h,
  expiry <= 366 d for the org); real brand logos (Wikidata official files; tech bible no longer bans logos); web facts in
  research; rivals.py (leaders + climbers, 3x outliers, sponsor scan via YouTube Data API: 35 brand lines, weekly read in
  knowledge/rivals.md); money.py (gates + ETA in STATE.md); Meta page keys cached 12 h (the #4 limit); parent brand
  Scroll House: https://scrollhouse.in live (GitHub Pages /docs, HTTPS, daily rebuild), IG @scrollhouse.in.
- FIXED 14:45: raaz serial made Parts 1-8 in a day, all held (length 58-64 s > 55): raaz length now 25-68 s, a serial makes
  no new part while 2+ parts are held; Parts 1, 2, 4 re-checked from qc -> approved 10 (raaz 1 -> 4 approved). Mastering kept the worst of 3 tries (TP +0.3):
  now best of 4 with a lower limiter ceiling (tested on 1118-1328: -14.5 LUFS, TP -2.6).
- TECH V2 LOOK (18 Nov 15:00, owner: 'stage' pilot looked the same; use the skills): theme "film": true in
  channels/tech/channel.json (or STUDIO_LAB_FILM=1). Every scene gets a full-frame picture behind its card (make.py bg:
  real photo/screen via 'real', else FLUX from 'bg_prompt' / label+keywords, never the spoken line), the picture moves and
  the type stays still, a camera move per scene, 4 cause-driven seams, no pill+HUD per scene, bigger type, blur-in captions,
  motion blur, numbers sized to one line. Pilot: Desktop\kaise-tech-OLD-vs-V2.mp4. OFF until Mehul approves.
- OWNER: approve tech V2? pick the first Lemo special; paste bios (Scroll House line); claim YT @scrollhouse;
  brand email; optional Mistral key.
- WATCH: first logo in a new tech video; laptop measuring the 45 queued winner Shorts; deep reader 15:30; held katha (healer).
## 18 Nov 09:30-10:45: focus week + new keys + Lemo-Opuscar
- Keys: 7 new Gemini (key file 4 -> 11; OmniRoute studio-gemini-5..11) and 2 Groq (studio-groq-1/2), each tested with a
  real call. omnimap rebuilt 10:25: studio-fast starts with groq qwen3.8-27b, long text passes on groq gpt-oss-120b.
- Fixed: duplicate FOLLOW card before the end card; lab compare values clipped ("Base+New"); healer counted crashed or
  skipped code steps as tries; healer --dry wrote its state; Mehul agent invented file paths; a Gemini model that times
  out / 503s goes last for 30 min (preflight, review, plan each waited 180-600 s on gemini-3.8-flash).
- Lemo-Opuscar: see knowledge/lemo.md (licence rules, pilots behind switches, specials after launch). Pilot results in
  ~/studio-out/pilot/. Waiting for Mehul's OK on the tech "stage" layout and the katha/raaz textures.
- Owner rule repeated: NEVER sleep; run long jobs in the background and work in parallel.
## 18 Nov 04:00-05:00: self-healing server + full OmniRoute (read knowledge/selfheal.md for the details)
- Current state is NOT in this file any more: read knowledge/STATE.md on the server (written every 15 min by the server).
  The OPEN ITEMS list below is history; several items there were stale when checked on 18 Nov.
- Owner decisions: never use workflows in this workspace; never sleep-wait; the server must fix things itself
  (doctor -> healer -> coding agent), Kiro builds new abilities. Use every free key and model fully (OmniRoute).
- Built: engine/healer.py, engine/healcode.py (aider in a worktree, verified merges), engine/omnimap.py (daily model
  probe + Studio combos), engine/state.py (STATE.md), Studio OmniRoute key + 4 Gemini keys inside OmniRoute,
  every Gemini caller falls back to OmniRoute, free FLUX.1-dev pictures, doctor hands every failure to the healer.
- Found + fixed: render lane rebuilt the same held job every 10 min (pipeline stalled); prep lane stopped when Muse
  was out; compose end-card overlap (katha holds) and motion "none" crash.
- Not touched on purpose: the job bot's OmniRoute combos (claude-free etc. start with the slowest model; changing them is
  the job bot's decision).
- DONE 18 Nov 08:38 (owner approved): job bot CPU/memory fixes, see Desktop\job\careers\CPU-18NOV.md. Cause of the 4.8 GB
  tab: careers-watch's 12-hourly render pass hung 3 h on a page stuck in JavaScript ($$eval has no timeout). jb-careers
  now has MemoryHigh 4.5G / MemoryMax 5.5G / OOMPolicy=continue.

# RESUME (updated 17 Nov 2026 ~21:55 IST)

Owner's list was worked in order. "Done" = built, deployed, checked on the server (frames / logs / numbers).
Server helper `~/bq "line"` appends a verified line to knowledge/build-queue.md and pushes.

## Status of the owner's 11 items
1. Check today's fixes: DONE. cv.log: real-01 voice-match 58% -> 76%, katha 1117-0655 96%, real-02 93%. real-02 frames
   reviewed (all painted AI scenes, consistent, readable captions; its real Kedarnath photos were dropped by preflight
   repair because of an alamy watermark: the watermark sites are now blocked in realmedia). Katha/Aage Suno rule: real photos
   only for PLACES (max 2), never gods/heroes/victims (plan.py). Aage Suno live test with real photos NOT run (rule says none
   for people, so little to test).
2. First-pass rate: DONE. Before the fixes (to 15:00): 3 pass / 36 hold (8%). After: every NEW video passed (6 passes);
   the only repeated holds were real-02 (reviewer was not told the card words: fixed). Fixes: voice-match metric (matchable
   words only), voice length floor 4.3 w/s, captions clamped before end card, TTS style as bracket tag (was read aloud),
   preflight repair now also for classic pages, reviewer sees intended card words, free-tier 429/503 fallbacks no longer
   listed as issues. Re-measure after more videos (weekly report prints it).
3. Hooks: DONE (engine/hookstudy.py, timer studio-hooks Mon 05:30). katha hooks.md written from 4 on-niche videos (tech and
   raaz re-run queued as unit studio-job-hooks6 with broader niche wording; check channels/tech|raaz/hooks.md).
   Our own reels have no stats yet (nothing posted before 20 Nov).
4. Music: DONE. engine/musiclib.py 25 tracks/page; VAJRA assets/music 12 beds (commit dd9aca5).
5. Real pictures part 2: DONE and verified for logo-then-photo (tech real-03 frames). Real video clips (Commons) fetch OK
   (Varanasi ghat clip downloaded and cut); the katha clip RENDER test is unit studio-job-real5 (katha/real-05, preflight
   off): look at its frames when done. 30-day no-repeat ledger in ~/studio-out/realmedia-usage.json.
6. Trends: DONE (engine/trends.py, timer 06:00; series.scan() runs after it).
7. Series + comments: BUILT (series.py, comments.py), reply prompt tested, NOT live-tested (needs posted videos).
8. YouTube: READY. Owner runs once per page on the laptop: python tools/yt_login.py tech|katha|raaz
9. Captions/SEO: DONE (engine/seo.py), tested on katha 1117-0655-en. seo.json for katha is real; tech/raaz refreshed by hooks6.
10. Keys: DONE (+ models out of quota are skipped for the day; dashboard Server shows keys).
11. Weekly report: DONE (engine/weekly.py, Sunday 20:00). Preview printed.

## Closing notes (22:30)
- Katha clip render test passed (clip plays, reviewer flags off-style clips). Test jobs real-01..05 deleted from the server and done.json.
- hooks.md exist for tech, katha, raaz; seo.json for all three.

## To finish when resuming
- Look at real-05 (katha clip test) frames; then delete test jobs real-01..05 from ~/studio-out if wanted (keep disk < 80%).
- Read channels/tech|raaz/hooks.md and seo.json after hooks6 finishes; if still empty for raaz, widen queries.
- Final report to the owner: what was done, before/after numbers, what is left for the owner (YouTube logins x3; pin comments by hand if wanted).
- Rule: owner said no questions; Rs 0; nothing posts before 20 Nov.

## Reminders
- Keys: Studio ~/.studio-gemini.key = 4 free keys (3.8-flash text model is out by afternoon: 50 calls/key/day; 3.5-flash-lite carries the rest); VAJRA secret GEMINI_API_KEY = 2 free keys.
- Edit safely (an edit script once emptied tts.py): write file.new, os.replace, assert length; never trust a silent success.
- Scripts: write to C:\Users\mehul\Desktop\studio\.tmp (gitignored), scp to /tmp, `sed -i 's/\r//'`, run with output to a log file, then cat it.
- Wikimedia asks for a polite User-Agent and returns 429 when fast (handled in realmedia._get).

## 18 Nov 01:40 (owner decisions round 2)
- Katha Hindi only; Aage Suno = fiction serials (engine/serials.py; first story 'Chouthi Manzil Ka Raaz', 10 parts); brand guard; English never posted on Hindi pages.
- Mehul agent: engine/mehul.py + knowledge/mehul.md, timer studio-mehul 22:30, Telegram 'mehul: ...' adds to the profile. Dry run on katha scored 6/10 with 4 actions; the full run crashed once on low memory (fixed).
- extras.py: teaser line, recap Story (FB; IG needs a public image URL), guess comment, festivals, Katha series, Tech myth Monday, long cut, sting, drop-off, best cover picture.
- 01:14-01:34 the server hit load 300 (memory pressure 99%: job bot + Studio prep + a manual rebuild + agent sheets). Fixed: lanes wait below 1.8 GB free; all Studio units MemoryHigh 2.6G / Max 3.4G / IOWeight 20.
- TODO: re-run katha 1117-1935 rebuild (own handle) when memory allows; run engine/mehul.py --dry again and read its actions; Rohan's look for Part 8 of the serial.

## 18 Nov 02:20 server freeze + reboot
- 01:50 a hand-started Mehul agent dry run on a server with ~800 MB free froze it (memory thrash). Rebooted 02:19 through the Oracle API: node C:\Users\mehul\Desktop\job\oracle\reboot.js status|softreset|reset (API key in job/oci-config; no console password needed). All jb-* services, studio-dash and 21 timers came back.
- Rule: never start a manual job (systemd-run) when MemAvailable < 2.5 GB. mehul.py now skips itself below 2.5 GB.

## OPEN ITEMS (18 Nov, chat moved from the Vajra workspace to this repo)
1. Mehul agent first real run: read its proposals (knowledge/mehul-log.json); the earlier manual dry run froze the server.
2. Narakasura reel katha/1117-1935 with @puraankikatha: held by preflight (scene 10 overlap); fix + render.
3. Own-video review leftovers: one-word captions, long static holds (katha), empty black frames + one-step flow (tech), duplicate TEST KARO end frame.
4. Serial teaser lines: Hindi not always natural; better prompt.
5. Listen to the first slower voice (2.4-2.5 w/s).
6. Review Part 1 of 'Chouthi Manzil Ka Raaz' (Mehul, Raghav, villain Vikrant) once made.
7. Read the new hooks.md per page after the Instagram + YouTube study.
8. 20 Nov launch: check first posts, Stories (IG + FB), first comments, YouTube uploads actually work.
9. After stats exist: comment replies, Part 2 series, drop-off lessons.
10. Katha Hindi caption timing still weak.
11. Later: new pages (owner prefers new pages over more versions).

## 18 Nov 22:30 new pages
- Navkar Bhav (jain, page 1498175213370788, IG 17841410169576875) and Finance Fuel (finance, page 1445486545315323, IG 17841423953560807). Account files ~/.studio-accounts/jain.json, finance.json (page_id only; keys resolved).
- Page list now comes from channels/ (core.pages()); per-page tables (dm, rivals, hookstudy, site, trends, stories, musiclib, thumb) have both pages.
- Finance = lab film look (theme.hud FINANCE.FUEL, finance brands in make.BRANDS), caption_footer 'Education only, not financial advice.' (seo.text_for, all platforms). Jain = story look, Tirthankara forms in iconography.py, looks (manuscript) OFF until a picture pilot.
- Owner: YouTube channels for both (his sign-up), bios 'A @scrollhouse.in page', warm-up likes/comments 19-21 Nov. Business pages Getmeflat + Fibbi added to the dashboard (manual).

## 19 Nov 00:00 Finance Fuel deep dive (playbook knowledge/new-page.md, run for every new page)
- Owner: Finance Fuel is an old account: no warm-up, posts from 19 Nov (evening slot, 1/day). First 3 videos need his approval (schedule.manual_first=3).
- Data: ~/studio-out/research/finance/{youtube,instagram,instagram2,hashtags,trending,watched,sponsors2}.json; scripts .tmp/fin_a.py, fin_a2.py, fin_b.py, fin_spons2.py.
- Outputs: channels/finance/rivals.md (16 YT + 10 IG rivals, top 10 reels each), queue.json (20 ranked ideas, made first by make.pick_topic), bible.md + hooks.md (format), knowledge/brands.json finance (58 sponsor lines, 11 targets), MONEY.md 5a.
- Engine: make.pick_topic reads channels/<id>/queue.json first; plan word range per page (edit.words, finance 72-118); numbers check 2 fix rounds; send.auto_approve honours schedule.manual_first.
- Not available: Reddit (blocks the server, login wall in the browser). Instagram gives no view counts for other accounts (likes + comments used).

## 19 Nov 00:40 brand kit, media kits, link pages, playlists (owner: "do all you can, automate everything")
- engine/brand.py (daily 06:20, unit studio-brand): the owner's real Instagram DP (Meta API) is the source. Renders (engine/brandimg.py, Pillow, system python3 because the venv has none) circle-safe DP, YouTube banner, FB cover, 3 IG highlight covers into brand/<id>/ (gitignored images; server is master; copies on the laptop under brand/). Sets by API: Facebook DP + cover + about + website (pages_manage_metadata), YouTube banner + description + country (scope youtube). NOT possible by API: Instagram DP/bio/highlights, YouTube DP. A zip per page goes to Telegram, a "Needs you" task per page to the dashboard, bios in knowledge/bios.md.
- engine/mediakit.py (called by site.py daily 09:05): docs/kit/<page>.html (brand-facing; curated SAFE lines, never channel.json rules, which hold internal notes such as the no-AI-label rule), docs/go/<page>.html (link-in-bio; every page's FB website + bio link), sitemap.xml, robots.txt, knowledge/ratecard.md (INTERNAL, needs 3 reels with views), knowledge/audience.json (measured IG audience once a page has 100 followers). Numbers on the site appear only from 100 followers or 1,000 views.
- sync.py now commits docs/ with add -f (the daily site rebuild was never committed before, live numbers never changed).
- publish.py -> engine/ytlists.py: every serial / series part uploaded to YouTube joins a playlist named after the story (ids in channels/<id>/playlists.json).
- seo.clamp_tags: IG/FB at most 5 hashtags, broad reach tags dropped (Instagram cap since Dec 2025). plan.clean drops English articles from on-screen text. compose_lab stat count-up now ends before the pre-render still (98+ vs 100+ holds). channels/raaz visuals.avoid (no deities in fiction pictures; make.py honours visuals.avoid).
- LESSONS: never write repo files with PowerShell Set-Content -Encoding utf8 (adds a BOM; json.load fails; it briefly broke raaz channel.json on the server). Use python io.open(newline="\n") or [IO.File]::WriteAllText with UTF8Encoding($false). An ssh call right after scp often prints nothing: run the ssh again.
## 19 Nov 00:35 finance first 3 videos (hand-checked; owner approves, manual_first=3)
- 1118-2334 UPI fail ₹100/day: script fixed by hand (bank pays, not RBI; after T+1/T+5; source card 20 Sep 2019), scenes rebuilt; preflight OK 10; rendering on the laptop.
- 1119-0005 property papers ₹5,000/day: fixed by hand (gold loan removed, circular 13 Sep 2023, one RBI logo), rebuilding from voice.
- 1119-0028 jumped-deposit scam: building (queue #3; sources Sanchar Saathi + SBI 10 Oct 2026).
- Engine fixes tonight: numbers check (sources only, blind recompute, two agreeing answers, script-only numbers), lab_fix (types + data, logo = card, after every repair), lab repair re-fetches pictures, visual director once per video, preflight: real logos ok + no bar/pill nitpicks, stat 'None', YouTube thumbnails blocked, lessons agent + rule book.

- Dashboard (19 Nov): every channel shows its real DP (dashboard/app.js dp(), route /dp/<id>.jpg from ~/studio-out/dp, refreshed daily by brand.py avatars(): studio pages from the IG DP, business accounts via Instagram Business Discovery). Hardcoded "6 channels" replaced by the real count.
- scrollhouse.in: docs/og.png link-preview card, canonical, favicon. Brand email: when Mehul makes hello@scrollhouse.in (task "brand-email" on the dashboard), write the address into ~/.studio-brand-email on the server: site, media kits and the Facebook page email pick it up on the next daily run.
- YouTube channels list each other as featured channels ("More from Scroll House"), set by brand.py once every page's channel id is known (brand/state.json yt_id).
- dm.py skips the FB "posts" edge (#10, needs Page Public Content Access); our posts are Reels, the video_reels edge works.
## 19 Nov 01:45 Finance Fuel phone look (owner: first video 'similar to tech, not catchy, random logos, euro showing')
- New look engine/phone_scenes.py (theme.phone): wa (WhatsApp chat), sms (lock screen bank SMS), pay (payment status), bill (receipt maths), rule (official rule card, the only real logo). No AI pictures. Planner prompt plan.PHONE; lab_fix(phone) converts picture scenes; make skips real brands/looks/backgrounds; numbers check reads on-screen numbers; finance facts_strict (money exact, unsourced facts held).
- Test renders checked frame by frame (.tmp/phone_test.py -> studio-render/phonetest). Fixes from frames: bigger phone, captions below it, hook on screen at frame 0, items in by 45% of a scene, no count-up on money, wide logos, long titles fit.
- 3 videos rebuilt in the phone look (same checked voice): 1118-2334 UPI, 1119-0005 property papers, 1119-0028 jump-deposit scam. Final recomposes queued (/tmp/after3.sh, /tmp/after4.sh); all go to Telegram for owner approval (manual_first 3).
- Engine-written gold script test: strict check found wrong maths + an unsourced claim after 2 rounds -> would be held (correct). Queue #4 source updated with verified HUID/GST facts.
## 19 Nov 03:50 Finance: real-life world behind the phone (owner: "good now, can be better... images/videos in background like v2, v3 of tech; don't change these 3")
- The 3 phone videos (1118-2334, 1119-0005, 1119-0028) are all "made", review clean, and untouched: their plans have no "phone_bg".
- theme.phone_bg (finance channel.json) -> plan.PHONE_BG asks a "bg_prompt" per scene (candid Indian moment, no screens/text) or "bg_real" (real building) on a rule card; plan.make sets plan["phone_bg"]=True. Only such plans get pictures.
- make._phone_bg: bg_real via realmedia (s{i}pr.jpg) else Muse/omni/cloudflare/pollinations still (s{i}pb*), with PHONE_BG_SAFE suffix; scene 0 also tries a Muse clip (s0pv.mp4) -> a["bgvid"].
- compose_lab: phone scene with bgvid = top-level <video class="vid pbg">, scene "over", still takes over if the clip ends early. phone_scenes.css: picture brightness .78, blur 2px, dark band only behind captions.
- Tested on 5 real FLUX pictures + frames: first prompt left fake signboard text (SAPPRCT, TADLET) -> "no signboards/posters/writing on vehicles" fixed it (0 of 5 readable); first shade (brightness .5) hid the pictures -> lightened.
## 19 Nov 06:00 Cut Capsule (@cutcapsule, clip page, FB page 1443258675911320)
- channels/cutcapsule (kind "clips": the daily script lanes and the healer skip it), ~/.studio-accounts/cutcapsule.json,
  dashboard CHANNELS entry, hookstudy niche/queries/hashtags. Research: knowledge/clipping.md; format: bible.md.
- Engine: engine/clipper.py (server: info + Gemini moments + checks + jobs) -> laptop worker "info"/"clip" jobs ->
  engine/clipcore.py (download once, whisper GPU, sentence cuts, quiet-gap trim, per-shot layout stack/crop/fill,
  pop captions, @cutcapsule handle, -14 LUFS). Dashboard "Make a video now" takes a YouTube link.
- PERMISSION GATE: only sources in channels/cutcapsule/sources.json post (campaign / creator OK). Everything else = test,
  held. First test (Foltyn Reacts "DAD DESTROYS GTA 6!"): 3 clips, vision 9/10/10, held as TEST.
- NVIDIA driver 621.24 installed 19 Nov (NVENC: 28 s clip in 61 s). Logo watermark from the IG dp (assets/brand).
- Money loop built 19 Nov: engine/campaigns.py (6-hourly ranking + Telegram), engine/clipwatch.py (hourly auto-clip of
  joined sources), dashboard "Clipping campaigns" + "Add a source" (/api/source writes sources.json + starts clipwatch),
  publish.py "submit to campaign" Telegram after each campaign post, clipper.what_worked() learning from views.
  Untested end to end: a real joined source (needs the owner's Whop join).
- Owner to do: join campaigns (digest sent 06:41) and add each in the dashboard; Cut Capsule YouTube channel.
- 19 Nov (later): automation instead of owner work. YouTube @cut.capsule connected. tools/whop.py (Playwright, owner's
  saved Content Rewards login on the laptop) + engine/whopbot.py (2-hourly): adopt_joined (campaigns the owner joined get
  a source), join_best (joins top-scored ones up to 5 active), submit_all (posts links after publish), retire. Briefs:
  "Reference materials" Google Docs are read; named official videos found on YouTube. Drive footage -> laptop
  "transcribe" (gdown list, sound files only, rotates files) -> text moments. publish.py posts a campaign clip only to the
  platforms its source allows. Cut Capsule posts at US hours 06:30 + 22:30 IST (studio-post-us): campaigns do NOT pay
  India/Pakistan/Bangladesh views, several need 50-70% US audience.
- Owner's 5 joined: Jo Koy (Drive, IG only, 70% US), Daise (Drive UGC), SEGA (YouTube trailers, 50% US), CoD MW4 (Google
  Doc footage, @callofduty + #Ad), Eneba BroPacks (brief bans automated clipping: skipped).
