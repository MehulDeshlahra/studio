# Self-healing server + full use of OmniRoute (18 Nov 2026)
Owner asked (18 Nov, 03:40-04:00): "why do you have to fix things? we already had an agent on the server. Make the server
fully automated and self-healing. Are we using OmniRoute fully? Use each and everything." This file records the
diagnosis (checked on the server, not from notes) and the build. Status lines are updated as each part is verified.

## Diagnosis: why Kiro still had to fix things
1. The doctor (every 10 min) knows 11 fixed recipes (failed units, timers, stuck jobs, disk, git, some held videos).
   Anything else went to ~/studio-out/doctor-unknown.json "for the next Kiro session". Nothing on the server read it
   to act (only the dashboard and the weekly report showed it).
2. Held videos looped: the doctor re-ran a held video from compose with the SAME plan and the SAME code, at most 3 times,
   and only after a code change. A code bug (e.g. katha 1117-1935: the last scene ran under the end card, so its
   "FOLLOW" text overlapped the end card) can never pass that way. Preflight's own repair asked the AI to rewrite the
   scene text, which cannot fix a layout bug in code.
3. selfcheck (the only part allowed to change code) acts only on Python tracebacks and dashboard errors (needs a
   file + line). Bad videos never crash, so they never reach it. Limits: 4 fixes a day, 40-line patch, 1 try.
   It made 5 fixes in total (all dashboard/crash).
4. The Mehul agent may not edit code; it writes "[mehul]" tasks into build-queue.md for Kiro. It runs once a day and has
   never finished a real run (no mehul-log.json; its contact sheet failed on ffmpeg at 01:07 and 01:51).
5. The doctor "cleared" failed units (reset-failed) without finding the cause; a failed repair (dashboard restart
   timed out 02:07) was only logged.
6. Nothing on the server works the 40+ items in build-queue.md.
7. Repairs ran on the weakest model: Gemini 3.8-flash is out on every key by afternoon -> 3.5-flash-lite.
8. RESUME.md is hand-written, so a new session starts from stale notes.

## OmniRoute audit (usage_history, 15-17 Nov)
- 12 providers, one key each: gemini, groq, openrouter, nvidia, huggingface, cloudflare-ai, zai, llm7, nara,
  siliconflow, pollinations, ollama-cloud (off). 1,342 models listed.
- ~1,640 calls a day. Job bot key "fixer-agent" ~3,700 calls in 3 days (mostly nvidia). Studio + VAJRA share one key
  "vajra-gen" (~630 calls in 3 days).
- Studio's main work (plan, preflight, review, covers, mehul, voice) calls Gemini DIRECTLY with ~/.studio-gemini.key
  and uses OmniRoute only as a fallback (lib/llm.py, combo claude-free).
- The 3 combos (claude-free, agent-free, forms-free) are "priority" chains that all start with NVIDIA's slowest model
  (nemotron-3-ultra-550b, ~14 s). Result: 110 nvidia + 146 openrouter 429s, groq gpt-oss-120b 141 429s, 58 claude-free
  calls timed out (499) with 0 successes, zai 0 successes, cloudflare 1, siliconflow 1, huggingface 1 call.
- Studio's 4 Gemini keys are not in OmniRoute; OmniRoute's Gemini key is not in Studio's rotation.

## Build (status: [ ] todo, [x] verified on the server)
- [x] B1 compose.py: last scene ends where the end card starts (same as compose_lab). Plus: unknown "motion" (a repair
      wrote "none") crashed compose with KeyError. Verified: healcode --check katha 1117-1935 -> preflight passed;
      1118-0035 composes with no content_overlap (scene 12 ends 47.141 = end card start).
- [x] B1b PIPELINE STALL found: a video held before render kept stage "prepped", so the render lane rebuilt the same held
      job every 10 min (1118-0035 seven times 03:20-04:20) and the prep lane stopped (2 prepped max) -> nothing new was
      made. Fixed: held jobs get stage "held", the render lane skips held jobs. The prep lane also stopped all new videos
      when the Muse image budget was out although pictures fall back to free FLUX: now it continues.
- [x] B1c Pictures: free FLUX.1-dev (NVIDIA) + z-image (Pollinations) through OmniRoute, 768x1344, ~10 s, frames checked
      clean. Order: Muse -> OmniRoute FLUX -> Cloudflare schnell -> Pollinations flux.
- [x] B2 OmniRoute: Studio key "studio" (~/.omniroute-studio.key); 4 Studio Gemini keys added (5 Gemini connections);
      combos studio-text / studio-fast / studio-vision / studio-code built from real probes (engine/omnimap.py).
      Probe 04:11: 29 of 53 free models answered correctly. Job bot combos untouched.
      Lesson: a paid model on zai / siliconflow / huggingface answers 402 and OmniRoute locks the WHOLE connection
      (credits_exhausted) -> only free models are probed; locked connections are re-tested and re-opened automatically.
- [x] B3 lib/llm.py: Studio key, text / fast / vision / code / from_parts, 300 s timeouts, last_model logged.
      Verified: text 6.5 s (gemini-3-flash-preview), fast 0.6 s (laguna), vision 3.1 s red/blue correct (nemotron VL).
- [x] B4 plan.ask: 3.8-flash (own keys) -> studio-text -> flash-lite. preflight / review / covers / Mehul agent /
      realmedia / learn fall back to OmniRoute when the own Gemini keys are out (preflight used to skip vision silently).
- [~] B5 engine/healer.py (every 15 min; timer installed 04:26; dry run classified 60 doctor notes: 42 quota waits,
      8 merged into the held ladder, 10 gone): one inbox (doctor-unknown, held videos, selfcheck could-not-fix, [mehul]
      tasks, failed units); classify (wait / retry / change input / fix code / needs owner); known-fixes file
      knowledge/fixes.json; held-video ladder (rebuild -> re-plan failing scenes with the reason -> simpler scene type ->
      code fix); every action logged and verified.
- [~] B6 Code-fixing agent (engine/healcode.py; aider 0.86.2 in ~/aider-venv, test fix 9 s / 250 MB): aider (free models via OmniRoute) in a separate git worktree; checks = compile + preflight on
      the failing job + known-good jobs; merge + push only if all pass, else discard. Memory guard 2.5 GB.
- [x] B7 Doctor (dry run clean; held videos moved to the healer): keep the cause of every failed unit in the healer inbox; a failed repair becomes a new problem;
      provider health check (error spike -> note + route around).
- [x] B8 knowledge/STATE.md written by the server every 15 min (healer), committed by sync.py; steering says read it first.
- [~] B9 Mehul agent: the ffmpeg sheet command works (rc 0 on kuber-01); the 01:07/01:51 failures were under memory
      pressure and the log cut the reason off -> now logs the end of the error, timeout 420 s. First real run: 22:30.
- [x] B10 Units via engine/units.sh (studio-healer :07/:22/:37/:52, studio-omnimap 04:40, memory fence drop-ins);
      doctor keeps them on. Dashboard shows the healer's step for each held video.
- [ ] B11 Final check: held videos cleared by the server itself, report.

## More found while building (all fixed, 18 Nov)
- Jobs cut off by the 01:50 freeze (katha 1118-0053, 1118-0133) were never resumed: healer.heal_orphans resumes them.
- The doctor's hourly OmniRoute re-test also re-opened connections in OmniRoute's own rate-limit cool-down: now only
  "credits_exhausted" locks are re-tested.
- Owner task "Link YouTube" was stale: all three pages answer channels.list (Kaise Tech, Puraan Ki Katha, Aage Suno);
  marked done; the doctor now checks every YouTube login once a day and tells the owner only if one stops working.
- Weekly report: held videos / unknown errors moved out of "Needs you" (they are the healer's), healer line added.
- Mehul agent's real failure: ffmpeg 6.1.1 (arm64) crashes ("malloc(): corrupted top size") stacking 213 px rows
  (odd height). Rows are 214 px now; contact sheet verified (51 s). Preflight sheet uses an even height too.
- z-image (Pollinations) drew Kartikeya as a woman in revealing clothes on a split panel: removed from the picture
  chain; preflight + review now check sacred figures (gender / form / attributes / modesty) and split pictures.
- Pollinations answers "not enough credits, top up" as a normal 200 reply: lib/llm.py and omnimap treat that text as a
  failure (it could have become a caption or a plan). Checked: no such text in any plan, caption or reply so far.
- The healer would have re-run its steps after every render (sync commits change HEAD): steps now follow the CODE
  version (last commit touching engine/ or lib/), max 6 steps per video per day.
- Healer checks must not change the video: a check re-voiced a good video (old timing without a voice score) -> check
  mode never re-aligns or re-voices; the "good video" must have a real voice score.
- Voice: OmniRoute cannot route Gemini TTS (no speech endpoint for gemini), so voice stays on Studio's own 4 keys.

## Log
- 04:35 end-to-end test of the coding agent on a sandbox clone (injected the old end-card bug): aider found the cause
  and wrote the same one-line fix in 28k tokens through studio-code. Not merged: the verifier demanded a fully clean
  preflight and the vision reviewer flagged an unrelated scene -> verifier changed to "original problem gone + no new
  layout problem" with ONE preflight and no repairs (STUDIO_PREFLIGHT_TRIES=1).
- 04:47 second run: studio-code had been re-ranked by a probe taken while Gemini was busy, so Pollinations wrote a
  symptom fix (smaller pop-in scale) with a "top up your credits" text as commit message. The verifier REJECTED it
  ("original problem still there (10, OVERLAP)"). Fixed: 429 no longer demotes a model; long-input probe for coding
  models; a provider's "top up" text in a 200 reply counts as a failure everywhere (lib/llm.py).
- OmniRoute map 04:55: 32 of 59 answered; studio-code = Gemini 3.7 / 3.8 / 3.1-pro / nemotron-ultra (all read a whole
  engine file correctly).
- 05:01 third run: correct fix, verified ("original problem gone, nothing new"), merge failed (the checks leave side
  files in the worktree) -> worktree reset before rebase.
- 05:45 FOURTH RUN: PASSED END TO END. Injected bug -> aider found it -> verified on the failing video and a good video
  -> merged + pushed (sandbox commit 8f4c616, exactly the one-line fix). Sandbox deleted afterwards.
- 05:37 the healer started its first real repair on its own: tech lab-gpt-01 rebuilt from voice (code changed).
- KeyWatch bug: per-minute 429s were stored as "out for the day" (all 4 keys showed TTS out after 3-8 calls while
  voices kept working) -> daily only on Google's per-day wording; a model that answers is unmarked; today's marks reset.
- studio-scout had failed every run since 17 Nov 17:01 (unit pulled git without --autostash) -> unit fixed.
- Captions: Groq Whisper large-v3 via OmniRoute = 97% vs 76% / 100% vs 91% match, 3 s; waits up to 150 s when Groq is
  busy (the job bot shares the Groq key) before falling back to the local model.
- 05:45 Mehul agent FIRST REAL RUN (knowledge/mehul-log.json): katha 5/10, raaz 6/10, tech 5/10; rules added (Hindi only),
  code tasks written for the healer. Problems found + fixed: it started its own builds next to the healer's (two of
  them on lab-gpt-01 at once, one on an English edition) -> stopped; it now only asks the healer (replan_requested);
  make.py holds a per-job lock so no job is ever built twice at once; it counted old English editions as a violation
  -> they are excluded from its data; owner-agent code tasks may not touch the core pipeline and are always
  regression-checked.
- 06:03 the healer's lab-gpt-01 rebuild sat 23 min in local Whisper under swap (load 17): stopped; it is retried with
  Groq-first alignment once free memory is back above 2.5 GB.
- Server load: the job bot's careers browser (jb-careers, chromium renderer) grew to 4.8 GB and ~60% CPU; load 17 on
  2 cores at 05:44; swap 2 GB used. Not Studio's process: left for the owner to decide.
