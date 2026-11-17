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
- [ ] B1 compose.py: last scene ends where the end card starts (same as compose_lab) -> unblocks 1117-1935-type holds.
- [ ] B2 OmniRoute: own Studio API key; Studio's Gemini keys added as connections; new Studio combos ordered by
      measured success/latency (fast, strong, vision); every provider tested with a real call; the job bot's combos untouched.
- [ ] B3 lib/llm.py: Studio key, per-task combos, timeouts that fit the chain, logs which model answered.
- [ ] B4 Engine text calls: Gemini direct first while quota lasts, then OmniRoute strong combo (not flash-lite only).
- [ ] B5 engine/healer.py (every 15 min): one inbox (doctor-unknown, held videos, selfcheck could-not-fix, [mehul]
      tasks, failed units); classify (wait / retry / change input / fix code / needs owner); known-fixes file
      knowledge/fixes.json; held-video ladder (rebuild -> re-plan failing scenes with the reason -> simpler scene type ->
      code fix); every action logged and verified.
- [ ] B6 Code-fixing agent: aider (free models via OmniRoute) in a separate git worktree; checks = compile + preflight on
      the failing job + known-good jobs; merge + push only if all pass, else discard. Memory guard 2.5 GB.
- [ ] B7 Doctor: keep the cause of every failed unit in the healer inbox; a failed repair becomes a new problem;
      provider health check (error spike -> note + route around).
- [ ] B8 knowledge/STATE.md written every hour by the server (memory, running, held, errors, inbox, keys, posts).
- [ ] B9 Mehul agent: fix the ffmpeg contact-sheet failure; first real run verified.
- [ ] B10 Units created through engine/units.sh; doctor keeps the new timers on.
- [ ] B11 Final check: held videos cleared by the server itself, report.

## Log
