# Before every video (research -> brief -> build -> review -> learn)
Write everything into videos/<id>/brief.md. Do not start building until steps 1-4 are written.

1. Read knowledge/lessons.md and knowledge/playbook.md (latest scout findings).
2. Topic research (15-20 min):
   - Search the topic on Instagram (Apify instagram-scraper / hashtag + keyword) and YouTube Shorts.
   - Pick the 5 best reels on THIS topic or format (plays, recency). Download (yt-dlp), make 16-frame sheets,
     note for each: hook line, frame 0, length, cuts, caption style, what the visual metaphor was.
   - Note what nobody has done yet (our angle) and the 3 most common comments/questions.
3. Facts: every claim gets a source in videos/<id>/sources.json. No guessed numbers, specs or prices.
4. Brief: question, one visual metaphor, 3 hook options (pick 1, say why), beat list (one new idea per 2-4 s,
   max 6-8 s per visual idea), shot list (Muse clip / Muse still / diagram / real capture), text zones, ending question.
5. Build: Gemini Charon VO (one request) -> whisper timings -> Muse assets -> HyperFrames -> mix.
6. QC gate: hyperframes check + snapshot every scene, 1080x1920 30 fps, -14 LUFS / TP <= -1.5 after muxing,
   whisper read-back, no on-screen AI label, text inside 168-1330 px band.
7. Send to owner. After feedback (and after 48 h numbers once posted): add lessons to knowledge/lessons.md
   and the result row to knowledge/results.md.
