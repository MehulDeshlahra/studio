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
| tech-003 | Phone ulta, screen kaise ghoomti hai | 42.6 s | pilot | good, not the best |

## Channels
- See channels/CHANNELS.md (tech, raaz, katha, game later). Each channel: channels/<id>/channel.json.
- No single mascot: tech uses the topic's own object as the character.

## Server
- Muse bridge 1: 127.0.0.1:20240 (jb-musebridge + jb-muse-browser, CDP 9444, profile ~/musebridge/profile).
- Muse bridge 2 (second account): 127.0.0.1:20241 (jb-musebridge2 + jb-muse-browser2, CDP 9445, profile ~/musebridge2/profile). Installed 16 Nov, NOT started: waits for the owner's login.
- Bridge code is shared (~/musebridge2/musebridge.js is a link); MUSE_BROWSER_SVC picks which browser it stops/starts.

## Open
- Second Muse account on the bridge (more daily clips).
- Channel accounts (Instagram + YouTube) and branding.
- Server automation of the whole pipeline.
