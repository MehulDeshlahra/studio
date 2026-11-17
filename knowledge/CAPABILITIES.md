# What Studio can do today (the learner compares every repo / file against this list)

Pages: Kaise Tech (Hinglish tech + AI explainers, dark "lab" look), Puraan Ki Katha (mythology stories), Aage Suno
(all kinds of stories). English editions of each. Free stack only (Gemini free credits, Muse browser, Cloudflare FLUX).

## Ideas and research
- ideas.py: 10 ideas per video, scored by YouTube Shorts demand (yt-dlp search views), fit, freshness; best one made
- research.py: top Shorts on the topic are found and watched by Gemini (hook, pacing, visuals notes)
- scout.py (twice a day): AI/tech news radar (HN, GitHub trending, HF papers), watchlist channel outliers -> playbook.md
- shared brain (knowledge/brain.jsonl) + lessons from every page; owner feedback in Telegram becomes lessons

## Script and voice
- plan.py: Gemini writes a scene-by-scene plan (hook first 2 s, one idea per scene), reviewed once by a second prompt
- Gemini TTS (voice Charon), style prompt; instruction-leak cut; pace.py squeezes pauses to a target words/sec
- voice gate right after TTS: late first word, low script match, too short -> new voice before any visuals

## Visuals and edit (HyperFrames: HTML + GSAP rendered to MP4)
- classic look (compose.py): photos/clips with Ken Burns, cards, clues, choices, 3-word captions with highlight box
- lab look (compose_lab.py): object props on black, stat counters, UI panels with bars, line charts, flows, compares,
  chat bubbles streaming, terminal typing, kinetic titles with underline, panel shine, 3 rotating transitions,
  mono HUD, sentence captions with word light-up, grain + vignette, end card with handle
- images: Muse (2 accounts), Cloudflare FLUX, Pollinations; clips: Muse image-to-video
- music bed + SFX cues mixed by mix.py, loudness mastered to -14 LUFS, true peak limited
- cover/thumbnail (thumb.py): frame + big hook title + handle, stamped as first frames

## Quality
- preflight.py before render: HyperFrames layout audit + per-scene stills judged by Gemini; bad scenes rewritten
- review.py after render: start/end voice check, alignment, loudness, blank-stretch scan, vision review of frames
- doctor.py every 10 min: self-repair (failed units, timers, stuck jobs, disk, git, held videos after code fixes)

## Delivery and growth
- Telegram approvals (Studio360); optional auto-approve by score
- publish.py: Instagram Reels + Facebook Reels via Meta API, warm-up schedule; YouTube uploader not linked yet
- stats.py: IG insights into results.md + 09:00 report; dashboard (Today, Runs, Approvals, Channels, Server, Brain)

## Not built yet (good targets for learning)
- beat-synced cuts, A/B hooks or thumbnails, trend audio, comment replies, hashtag research, posting-time tuning,
  series memory (recurring characters), animated maps, 3D scenes, avatar/talking head, captions in Devanagari,
  YouTube upload, analytics-driven retention editing (where viewers drop)
