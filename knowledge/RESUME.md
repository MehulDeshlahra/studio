# RESUME (saved 17 Nov 2026, ~15:05 IST, owner went to the office, laptop off)

Say "resume" and read this file first. Server work keeps running without the laptop. Rule: owner's task list (below) is
done in order, no questions, check real frames/logs/numbers after each item, commit, one line in
knowledge/build-queue.md (server helper: `~/bq "line"`). Skip anything needing money / sign-up / owner click and list it at
the end. Report at the end: what was done, before/after numbers, what is left for the owner. Rs 0 only.

## Task list status
1. Check today's fixes (cv.log, real-02 frame by frame, real photos on Katha + Aage Suno): PARTLY.
   - cv.log: real-01 new match 76% (old 58%), katha 1117-0655 96%. Real-02 voice matched 93%.
   - real-02 (Kedarnath, katha) was RENDERING (job unit studio-job-real2, output ~/studio-out/katha/real-02). Preflight found
     4 bad scenes (empty centre, watermark on an alamy photo, 2 text overlaps) but the OLD code had no classic repair, so it
     rendered anyway. TODO: when it finishes, view its frames (ffmpeg contact sheet), check real photos look right
     (blurred backdrop layout), then re-make real-02 with the new code (classic preflight repair + watermark-site block).
   - Aage Suno (raaz) real-photo test NOT done yet: run `make.py raaz <topic> --job real-03 --no-send` and review frames.
2. First-pass rate: DONE. 3 causes fixed (voice-match false alarms; captions bleeding into end card; TTS reading the style
   line aloud -> bracket tag). Also classic pages now get preflight repair. Numbers: 4 of 42 reviews passed in 7 days.
   TODO: after 2-3 new videos, re-measure the pass rate (dashboard first-pass chart) for the before/after.
3. Hooks and retention: BUILT engine/hookstudy.py (channel discovery -> Shorts tabs -> Gemini watches first 3 s ->
   channels/<id>/hooks.md read by the planner + brain items). Timer studio-hooks (Mon 05:30). First run was started at
   ~14:58 (unit studio-hooks.service); check `channels/*/hooks.md` exist and read them. Retired 6 brain items from the
   earlier bad run. Our own posted-reels stats are EMPTY: nothing posted yet (warm-up, no posts before 20 Nov), so the
   "our reels vs winners" comparison starts after posting begins.
4. Music: BUILT engine/musiclib.py (incompetech CC BY, mood-tagged, ~25 tracks per page, planner field music_mood,
   30-day no-repeat, credit line appended to caption). Library build was running (unit studio-job-music); check
   `python engine/musiclib.py list`. TODO: VAJRA assets/music: add 10 free tracks (from the same library, local repo
   C:\Users\mehul\Desktop\vajra-automation\assets\music, currently 1 track) and make make_reel.py rotate them; commit + push
   with the gh account that works (mdeshlahra123 failed to switch earlier; MehulDeshlahra was active and the push worked).
   TODO: SFX source (Openverse audio needs license=cc0,by without category; freesound/jamendo sources worked).
5. Real pictures part 2: NOT started (real video clips Pexels/Pixabay/Commons video; logo pop-in then product photo; never
   repeat the same picture within 30 days: needs a usage ledger like musiclib's music-usage.json). Part 1 (photos + logos)
   works on tech; trimmed margins, white card, fake-transparency rejected, watermark stock sites skipped.
6. Trending topics: BUILT engine/trends.py (Google Trends RSS, Google News RSS, Reddit RSS; planner picks fits) -> knowledge/trends.json;
   ideas.py adds them with +1 bonus; timer studio-trends (06:00). First run was in progress at 15:02 (unit studio-trends).
   Reddit gives 429 on several subreddits (spaced out already). Check the log + trends.json.
7. Series and comments: NOT started (Part 2 kal series, pinned-comment question, replies to top comments with free Gemini
   keys, Studio pages only). Needs a comments.py + timer studio-comments (units.sh creates it if comments.py exists).
8. YouTube: NOT started. Known blocker: owner's OAuth login (once). Check what else blocks uploads for the Studio pages
   and prepare so the owner logs in once.
9. Captions and SEO per platform: NOT started.
10. Reliability keys: DONE (KeyWatch in engine/tts.py, dashboard Server page shows keys; alert only if all keys out of
    voice quota). Key state file ~/studio-out/gemini-keys.json.
11. Weekly report (Sunday Telegram): NOT started (engine/weekly.py + timer studio-weekly via units.sh).

## Things to remember
- Keys: Studio ~/.studio-gemini.key = 4 free keys; VAJRA GEMINI_API_KEY secret = 2 free keys. Billed project retired (Rs 0).
- Free tier has NO Omni video / Lyria / image models. Voice quota ~10 requests/day per key.
- Server ssh: `ssh -i C:\Users\mehul\Desktop\job\oracle.key ubuntu@137.23.60.164`. Python /home/ubuntu/studio-venv/bin/python.
  Long jobs: `sudo systemd-run --unit=studio-job-X --uid=ubuntu -p CPUWeight=20 -p Nice=15 --working-directory=/home/ubuntu/studio -E HOME=/home/ubuntu ...`
- PowerShell quoting breaks inline: write scripts to C:\Users\mehul\Desktop\studio\.tmp\ (gitignored) and scp them.
- EDIT SAFELY: a python edit script once emptied engine/tts.py (restored from git). Always write to file.new then os.replace
  and assert len(s) > N and the pattern exists. Commit pattern: `git add <files>; git commit; git pull -q --rebase; git push -q`.
- The server working tree has uncommitted engine outputs (done.json, lessons-auto.md, brain.jsonl, learned.json): leave them.
- Reviewer found on real-01: end-card caption bleed (fixed); voice-match check (fixed).
- Owner rules: do everything without asking; ₹0 only; no robotic voice; no on-screen AI label; nothing posted before 20 Nov.
- Posting warm-up: no posts before 20 Nov; 1/day at 20:00 until 27 Nov.
