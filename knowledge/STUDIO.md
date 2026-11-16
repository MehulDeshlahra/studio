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

## Open
- Second Muse account on the bridge (more daily clips).
- Channel accounts (Instagram + YouTube) and branding.
- Server automation of the whole pipeline.
