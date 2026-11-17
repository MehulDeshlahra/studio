# Studio operations notes (always read)

## What this is
Free, 24x7, self-running faceless Reels/Shorts engine on the Oracle server for 3 pages. Owner: Mehul.
- Kaise Tech (tech, @kaise.tech; YouTube @kaise.tech.official): how things work, dark "lab" look, real logos.
- Puraan Ki Katha (katha, @puraankikatha): Hindi mythology, festivals, 5-7 part series. HINDI ONLY.
- Aage Suno (raaz, @aagesuno): ORIGINAL fiction serials (~10 parts, cliffhanger each). Never mythology.
- English editions are OFF on every page (owner 18 Nov). A future English page would be a separate, natively written page.
- Owner prefers NEW PAGES over more versions of the same video (no A/B copies).

## Read first in every session
- knowledge/RESUME.md (latest state + open items), knowledge/mehul.md (how the owner thinks),
  knowledge/build-queue.md (tasks; `## Done by Kiro` = verified log), ~/studio-out/doctor-unknown.json on the server.

## Owner rules
- Rs 0. Free tools only. Never sign up or pay on his behalf. No on-screen AI label. No robotic voices.
- Do the work, don't ask: act inside the rules, verify on real frames/logs/numbers, then report. Ask only for money,
  sign-ups, deleting posted content, or his clicks. Never claim something works without checking (he caught me once on
  Stories: VAJRA already does IG Stories via a public URL).
- No self-imposed daily caps: free keys are the only limit; he brings more keys when asked.
- Fiction names: owner Mehul + friends (Raghav, Aditya, Shobhit, Shwetal, Saumya, Suhail, Jahnvi, Masood, Animesh, Jayesh,
  Aaryan, Dhruv, Mudit, Shruti), rotating. Villains always made-up names, never "Rohan", never a friend.
- Real photos/logos/faces of public figures are fine; on story pages real photos only for places/landmarks.
- Telegram "mehul: <opinion>" feeds knowledge/mehul.md (the Mehul agent + planner follow it).

## Server (shared with the job bot: never starve it)
- ssh: `ssh -i C:\Users\mehul\Desktop\job\oracle.key ubuntu@137.23.60.164`; python /home/ubuntu/studio-venv/bin/python;
  repo ~/studio (pull: `git pull -q --rebase --autostash`), outputs ~/studio-out.
- MEMORY: 18 Nov the server froze twice from memory exhaustion (a hand-started job). NEVER start a manual job when
  MemAvailable < 2.5 GB. Lanes wait below 1.8 GB; Studio units have MemoryHigh 2.6G / MemoryMax 3.4G, CPUWeight 20, Nice 15.
  Manual jobs: `sudo systemd-run --unit=studio-job-X --uid=ubuntu -p CPUWeight=20 -p Nice=15 -p MemoryHigh=2600M -p MemoryMax=3400M --working-directory=/home/ubuntu/studio -E HOME=/home/ubuntu ...`
- If the server is frozen: reboot through the Oracle API from the laptop, no console password:
  `node C:\Users\mehul\Desktop\job\oracle\reboot.js status|softreset|reset` (reset = hard power-cycle).
- PowerShell breaks inline quoting: write scripts to C:\Users\mehul\Desktop\studio\.tmp (gitignored), scp to /tmp,
  `sed -i 's/\r//'`, run with output to a log file, then cat it.
- Edit safely (a script once emptied tts.py): write file.new, os.replace, assert the pattern exists and the length is sane.
- Server helper `~/bq "line"` appends a verified line to build-queue.md and pushes.

## Keys and accounts
- Gemini: ~/.studio-gemini.key = free keys, one per line (KeyWatch in engine/tts.py skips a key/model once out for the
  day; dashboard Server page shows usage). Free tier: text, vision, TTS only (no Omni video, Lyria, image models).
  The billed project is retired; never use it.
- Meta: ~/.studio-meta-user.token; pages in ~/.studio-accounts/<page>.json (YouTube "yt" refresh tokens connected 18 Nov).
- Stories: public images via repo MehulDeshlahra/studio-media (server deploy key, Host github-media) -> raw.githubusercontent.
- Instagram research: official Business Discovery API reads any public business/creator account (engine/hookstudy.py).

## Engine map (engine/)
daily (prep/render lanes) -> make (research, plan, voice, assets, preflight, render, review) -> publish (IG, FB, YT).
plan, tts, align, pace, realmedia (real logos/photos/clips), musiclib, thumb (covers), preflight, review, serials
(Aage Suno arcs), extras (teasers, recap Story, festivals, katha series, myth Monday, long cut, sting, drop-off, best
cover), stories (daily IG+FB Stories), comments, seo, trends, hookstudy, ideas, brain, learn, radar, doctor, selfcheck,
mehul (acts-like-the-owner agent, 22:30), weekly (Sunday report). Dashboard: dashboard/api.py + app.js on
https://jobbot.taildd6388.ts.net:10000. Timers are created by engine/units.sh.

## Posting
Warm-up: no posts before 20 Nov; 1 a day (evening) until 27 Nov; then the page's posts_per_day.
