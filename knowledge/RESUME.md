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
