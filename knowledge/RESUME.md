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
