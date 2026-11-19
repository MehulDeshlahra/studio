# Studio operations notes (always read)

## GOLDEN RULE (owner 19 Nov, after a low-effort Finance Fuel Story went live): NEVER LOW EFFORT
- Every piece of content and every feature must be the BEST OF THE BEST. Money comes after hard work, not shortcuts.
- Before building or posting anything: research first (what the top pages do, what works, what NOT to do), write the
  findings down, then build. No research = do not ship.
- Then judge it hard: "is this good?" If it is only good, discard it and make it better. Ship only what beats the best
  page in that niche. Look at the real output (frames, the live post) before it goes out; never trust that it rendered.
- A format that has not passed this bar stays OFF (Stories were paused 19 Nov until rebuilt to this standard).

## What this is
Free, 24x7, self-running faceless Reels/Shorts engine on the Oracle server for 3 pages. Owner: Mehul.
- Kaise Tech (tech, @kaise.tech; YouTube @kaise.tech.official): how things work, dark "lab" look, real logos.
- Puraan Ki Katha (katha, @puraankikatha): Hindi mythology, festivals, 5-7 part series. HINDI ONLY.
- Aage Suno (raaz, @aagesuno): ORIGINAL fiction serials (~10 parts, cliffhanger each). Never mythology.
- English editions are OFF on every page (owner 18 Nov). A future English page would be a separate, natively written page.
- Owner prefers NEW PAGES over more versions of the same video (no A/B copies).

## The goal: MONEY (owner 18 Nov)
- Everything serves earning (brand deals, affiliate, fan funding, ads): knowledge/MONEY.md is the master plan and
  checklist; read it every session, tick items with date + proof, recommend the next moves yourself. Keep both the server
  and the laptop busy (MONEY.md section 4). Competitors: knowledge/rivals.md + rivals.json; brands: knowledge/brands.json.

## Read first in every session
- knowledge/STATE.md ON THE SERVER (`cat ~/studio/knowledge/STATE.md`): written by the server every 15 min (memory,
  running jobs, held videos, healer actions, models, owner tasks). It is the truth; never report items from notes
  without checking them against it and the live server (owner 18 Nov: "be honest, you brought stale data").
- knowledge/selfheal.md (how the server heals itself), knowledge/RESUME.md (decisions + history),
  knowledge/mehul.md (how the owner thinks), end of knowledge/build-queue.md.
- knowledge/kiro-lessons.md: Kiro's own mistakes and the rule that stops each; add a line the same day a mistake
  happens (owner 19 Nov: "learn from mistakes, it should tend to very less; auto think, I will not be there").
  knowledge/lessons-learnt.md: the engine's rule book from every page's mistakes (engine/lessons.py, daily).
- A NEW PAGE: run knowledge/new-page.md fully before its first post, without being asked.
- Never use workflows in this workspace (owner 18 Nov).
- NEVER SLEEP (owner, said 3 times, 18 Nov). No `sleep`/`Start-Sleep`/wait loops, no command that blocks on a long job
  (`systemctl start` of a long unit: use `--no-block`). Start long jobs in the background, then do other useful work in
  parallel and check the result later with a quick status call.

## Self-healing (18 Nov) - the server fixes itself; Kiro builds new abilities, not repairs
- doctor (10 min): services, timers, disk, git, OmniRoute; hands every unknown failure to the healer.
- healer (engine/healer.py, :07/:22/:37/:52): held-video ladder (known fix -> rebuild after code change -> re-plan the
  failing scenes -> verified code fix -> park), unknown errors, [mehul] tasks; learns into knowledge/fixes.json.
- healcode (engine/healcode.py): aider (~/aider-venv) on OmniRoute combo studio-code in a git worktree ~/studio-heal;
  merges only after compile + compose/preflight of the failing video + a good video. `healcode.py --check <cid> <job>`.
- omnimap (04:40 daily): probes every free model, rebuilds combos studio-text / -fast / -vision / -code. Only FREE models
  on zai / siliconflow / huggingface: one 402 locks the whole connection (re-test re-opens: heal_connections).
- Studio's own OmniRoute key ~/.omniroute-studio.key; admin API from the server: `node ~/studio/tools/omni.mjs GET /api/combos`.
  Never change the job bot's combos (claude-free, agent-free, forms-free).
- Ship from the laptop with `.tmp\ship.ps1 "msg"` (the server commits often: always pull --rebase before push).

## Owner rules
- Rs 0. Free tools only. Never sign up or pay on his behalf. No on-screen AI label. No robotic voices.
- Do the work, don't ask: act inside the rules, verify on real frames/logs/numbers, then report. Ask only for money,
  sign-ups, deleting posted content, or his clicks. Never claim something works without checking (he caught me once on
  Stories: VAJRA already does IG Stories via a public URL).
- No self-imposed daily caps: free keys are the only limit; he brings more keys when asked.
- Fiction names: owner Mehul + friends (Raghav, Aditya, Shobhit, Shwetal, Saumya, Suhail, Jahnvi, Masood, Animesh, Jayesh,
  Aaryan, Dhruv, Mudit, Shruti), rotating. Villains always made-up names, never "Rohan", never a friend.
- Real photos/logos/faces of public figures are fine; on story pages real photos only for places/landmarks.
- DON'T BE DEFENSIVE (owner 18 Nov): real brand logos, app screens, product photos and public figures are normal on
  IG/YT/FB, so use them fully (a ChatGPT reel shows the ChatGPT logo). Read repos and files 100% (engine/learn.py deep),
  never a sample. Set up the free scrapers/crawlers that help (engine/web.py). Licence notes are a footnote, not a brake.
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
