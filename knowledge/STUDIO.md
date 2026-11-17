# Studio: everything in one place (keep updated)

## Decisions
- 16 Nov: channel 1 = Hinglish "tech kaise kaam karta hai" (one curiosity question, one visual metaphor, 30-60 s).
  Based on the Instagram study (RESEARCH.md round 5). AI news only occasionally.
- 16 Nov: voice = Gemini Charon (same as VAJRA). Owner: "too good".
- 16 Nov: visuals = Muse (main) via server bridge 127.0.0.1:20240: images 40/day, videos 15/day shared with VAJRA
  (VAJRA_VIDEO_CAP 13). Muse can make the mascot speak Hindi with lip sync. Pollinations flux = free backup images.
- 16 Nov: no on-screen AI label, ever. Use Instagram's AI info toggle only when AI looks real.
- Mascot: glossy black 3D phone character, big blue eyes, blue sneakers, dark navy studio (assets: videos/tech-003/assets/mascot.webp).

## Where things are
- Repo C:\Users\mehul\Desktop\studio (public MehulDeshlahra/studio); server ~/studio, work ~/studio-work.
- Lessons: knowledge/lessons.md. Procedure: knowledge/PREFLIGHT.md. Research log: RESEARCH.md. Results: knowledge/results.md.
- Gemini key: server ~/.studio-gemini.key (never in git).

## Videos
| id | topic | length | status | owner verdict |
|---|---|---|---|---|
| tech-001 | Google AI Mode update | 43.7 s | not posted | external review 5/10 |
| tech-002 | AI Mode v2 | 22.6 s | v3 parked (old format) | revision list |
| raaz case2-p1 | Shaadi ka lifafa, Part 1 (synced captions, no double text, 35 s, countdown) | 35 s | emailed 16 Nov | awaiting |
| raaz case1-p1 | Haveli ka laal dibba, Part 1 (engine run, hand-written plan) | 72 s | sample emailed 16 Nov | owner: captions out of sync, double text, too long, boring story |
| tech upi-01 | UPI 2 second (first fully automatic run) | 48 s | QC found card overflow (fixed in engine), to re-render | awaiting |
| tech-003 | Phone ulta, screen kaise ghoomti hai | 42.6 s | pilot | good, not the best |

## Channels
- 16 Nov LOCKED: tech page = Kaise Tech, @kaise.tech on Instagram + YouTube (owner created IG). 6 pillars in channels/tech/channel.json incl. 'Tech news, samjho'. Instagram @kaise.tech created by the owner (the empty account was his). YouTube @kaise.tech free (@kaisetech taken by 'kaise'). English: @kaisetech.en (IG + YT free). Look-alikes: none relevant (Kaiser/Kaisen accounts only). Story page name parked.
- 16 Nov FINAL: page name = Kahaniverse (owner liked it); owner picks the handle variation in the app and tells me. (Earlier draft: Kahaneo (@kahaneo, English @kahaneo.en; both free on Instagram + YouTube on 16 Nov). Broad story studio with series inside: Raaz Ka Faisla, Karma, Dil Se, Jaadu, Darr. Fallback if the app refuses the handle: Kahaanio (@kahaanio). Rejected by owner: Tum Ho Detective, Agla Kya Hoga, Kahaniverse, Kissalok, Kahani Kart (reserved), .in/.official handles, Plotlok, Mohalla TV, Suno Kahani.
- See channels/CHANNELS.md (tech, raaz, katha, game later). Each channel: channels/<id>/channel.json.
- No single mascot: tech uses the topic's own object as the character.

## Server
- Muse bridge 1: 127.0.0.1:20240 (jb-musebridge + jb-muse-browser, CDP 9444, profile ~/musebridge/profile).
- Muse bridge 2 (second account): 127.0.0.1:20241 (jb-musebridge2 + jb-muse-browser2, CDP 9445, profile ~/musebridge2/profile). LIVE 16 Nov 20:44 (second Meta account logged in by owner; test image ok; own usage.json). musebridge.js is a COPY (a symlink made node use ~/musebridge as __dirname and share usage) - copy again after bridge updates.
- Bridge code is shared (~/musebridge2/musebridge.js is a link); MUSE_BROWSER_SVC picks which browser it stops/starts.

## Facts (owner corrections)
- Oracle Always Free for this tenancy is 2 OCPU / 12 GB now (Oracle reduced it from 4). Don't suggest resizing.
- Kaggle + Cloudflare were already set up on 15 Nov: ~/videngine (cf.token, kaggle.env, vid.py, img.py). Cloudflare FLUX ~170 images/day is now the 2nd image fallback after Muse. Kaggle Wan 2.2 last run failed (KernelWorkerStatus.ERROR, 16 Nov 01:03) - fix before use.
- Studio Gemini key (~/.studio-gemini.key) is from the credits project 'My First Project V' -> TTS cap 30/day in daily.py.
- Posting (CORRECTED 17 Nov, owner): like VAJRA + MarginMart (commit 8a59377) posts are made with Mehul's 'Ads MCP' Meta login (user token, app 'Ads MCP', never expires, data access ~60 days, renews on login), so posts show 'via Ads MCP' and can be promoted as ads. Server copy: ~/.studio-meta-user.token (600). publish.py reads the Page key + linked IG id from it. FB Pages already exist: Kaise Tech 1474228909103892, Puraan Ki Katha 1453056947892202, Raaz Room 1501633449691931 (no IG linked yet on 17 Nov).

## Accounts (verified on the server 17 Nov)
- Kaise Tech: FB Page 1474228909103892 + IG @kaise.tech (17841422728593136), publish quota ok. YouTube: @kaise.tech.official (owner).
- Puraan Ki Katha: FB Page 1453056947892202 + IG @puraankikatha (17841459966207698), publish quota ok.
- Raaz Room FB Page 1501633449691931 + IG @kahanikart.official (17841413280544411) - story page; name to confirm with owner.
- Server files: ~/.studio-accounts/{tech,katha,raaz}.json (page_id only; keys come from the Ads MCP login).

## Open
- Second Muse account on the bridge (more daily clips).
- Channel accounts (Instagram + YouTube) and branding.
- Server automation of the whole pipeline.

## Story page = Aage Suno (@aagesuno), 17 Nov
- IG @aagesuno (Page still named Raaz Room, owner renames). YouTube @aagesuno to create. English page name open.
- Voice signature 'Aage suno.' once, before the twist; end line 'Kal ek nayi kahani. Follow karo.' Rules in channels/raaz/lessons.md; enforced by compose (accent + sting) and review.py.


## Dashboard + idea picking (17 Nov)
- Dashboard: https://jobbot.taildd6388.ts.net:10000 (Tailscale only). Code dashboard/ (api.py + extra.py, stdlib; app.js/app.css, no build). Unit studio-dash on 127.0.0.1:4788. Pages: Today (AI brief, needs-you, building now), Runs (+ timeline drawer), Approvals (approve/reject/feedback = same as Telegram), Channels (+ latest posts, idea ranking), Server, Connected apps, Activity, Brain, Settings (auto-approve, off by default). Ctrl+K = jump or ask (Gemini on live data).
- Design rule: neutral surfaces, colour only for meaning (green done, blue working, violet needs you, amber watch, red broken, teal approved).
- engine/ideas.py: every new video picks the best of 10 ideas (YouTube demand + fit + freshness), log in channels/<id>/ideas.json.
- tts.strip_preamble: English editions cut everything before the script's first words.


## CPU rules (17 Nov)
- Studio work is low priority (nice 15, CPUWeight 20): job bot first, Studio takes spare CPU. 100% CPU with mostly 'background' is normal.
- Render workers: 2 on a quiet server, 1 when normal-priority CPU >= 35% (make.render_workers).
- Muse browsers stay warm while Studio fetches visuals (~/musebridge*/STUDIO-AWAKE, ignored after 45 min).
- Hand-started tests: always systemd-run -p CPUWeight=20 -p Nice=15; never run Whisper at normal priority.


## Doctor (17 Nov)
- engine/doctor.py, timer studio-doctor every 10 min: clears failed units, restarts stopped timers / dashboard / Muse bridges (down 20 min), kills jobs with no progress for 60 min (lane resumes), cleans caches at 88% disk, unsticks git, trims budget.
- Telegram ONLY for owner-only items (Meta login, Gemini money/cap, disk still full), once a day each.
- Unknown repeated errors -> ~/studio-out/doctor-unknown.json: READ IT at the start of every session and fix them.


## Self-learning brain (17 Nov)
- engine/brain.py: unlimited store knowledge/brain.jsonl; each video gets the 14 most relevant items (free Gemini embeddings, 256 dims, cache ~/studio-out/brain-emb.json); items score wins/losses from first reviews; retired when they keep losing.
- engine/learn.py: GitHub links / PDFs / photos / text files posted in Studio360 -> read via GitHub API (never cloned or run) -> knowledge into the brain, code features into knowledge/build-queue.md. Weekly explore (studio-learn timer, Sun 11:00) searches GitHub for new repos.
- Kiro sessions: READ knowledge/build-queue.md and ~/studio-out/doctor-unknown.json first; build/fix the best items.


## Dashboard audit (17 Nov)
- Run python dashboard/audit.py on the server after any dashboard change: it recomputes runs, statuses, budgets, disk/memory, timers, follower counts (vs Meta), VAJRA queue and first-pass numbers from raw files and compares with /api/state (72 checks).
- Tab-by-tab review fixed: stale 92% progress, stale reviews on building videos, held-label wording, grouped issues, friendly hold reasons, brief refresh (30 min, background), brain graph ids + learned cluster, phone layout (no sideways scroll, runs as cards), VAJRA counts, settings defaults, thumbnails (cover-s.jpg).
- Housekeeping: finished videos keep video/cover/plan/timing/assets only; render/ raw.mp4 mix-tp.wav removed after a day (doctor) and raw.mp4 right after mastering. Preflight stills are deleted after the sheet is made.

