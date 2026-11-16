# Studio lessons (read before EVERY video; add to it after every review)
Each lesson: what went wrong or right -> the rule. Newest at the top. Owner feedback beats measurements.

## Hard rules from the owner
- NEVER put an "AI visuals" (or any AI) label ON SCREEN. Disclose only with Instagram's own "AI info" toggle,
  and only when the AI content looks or sounds real (cartoon mascot = no toggle needed; realistic people/places = toggle).
- Voice = Gemini TTS (gemini-3.8-flash-tts, Charon, style prompt), whole script in ONE request. Never Kokoro/Edge
  ("robotic"). Key: server ~/.studio-gemini.key (free tier, ~10 TTS requests/day).
- Videos must be truly professional: editing, motion graphics, voice, SFX, hook. Research before every video (PREFLIGHT.md).
- Only free tools. Ask before spending money.

## tech-003 (16 Nov, pilot "Phone ulta karte hi screen kaise ghoom jaati hai?") - owner: "good, not the best"
- OK: Muse 3D mascot + Charon voice + one visual metaphor + word captions = the right direction.
- Diagram section ran ~19 s with the same tilt shown twice -> max 6-8 s per visual idea; each beat must show NEW information.
- Captions hid unspoken words with opacity 0 -> text looked off-centre. Show the whole chunk, light the spoken word.
- HyperFrames render lowered the audio to -17 LUFS -> always re-mux the mastered mix.wav into the final mp4 and
  true-peak limit after AAC (target -14 LUFS, TP <= -1.5).
- Muse clips are 704x1248 -> soft at 1080x1920. Use Muse clips for short moments; stills (1152x2048) for holds.
- A whole scene layout that zoomed the SVG cut the subject off -> snapshot every scene before render.
- Hook text and caption overlapped the mascot's face -> plan text zones per shot (face free).

## tech-001 / tech-002 (Nov) - external review 5/10
See lessons-tech-001.md (frame 0 must say what + why-for-me, quick proof, one headline per section, real things,
length follows information, short question ending, one colour identity, no effects to cover editorial problems).
- tech-002: the "AI news with UI cards" format is the samjho.exe lane: polished but low reach. Switched format.

## Engine lessons (16 Nov, first automatic runs: tech upi-01, raaz case1-p1)
- A render started with nohup from an ssh session dies when the session ends ("render_cancelled_parent_exited"). On the server always start long jobs with `sudo systemd-run --unit=studio-job-<name> --uid=ubuntu ...` (the timers already use systemd).
- Gemini TTS reads ~2.3 words/s for suspense (163 words = 72 s). Plan raaz parts at 120-140 words for ~60 s.
- Big card words must be auto-sized (14 chars at 190 px overflowed). Captions at 45% opacity were hard to read: use 80%.
- True peak after AAC overshoots the limiter: master with two-pass loudnorm (I=-14, TP=-2, linear) and mux; re-measure the final mp4.
- QC vision model flagged intended 3-word captions as "cut off": QC prompt now says captions are word-by-word. Read-back with whisper small is weak on Hinglish: only fail on whole missing sentences.
- Muse puts printed text on some images (e.g. "BATCH SETTLEMENT VIA RBI" on a door): prompts say no text, but check; cover text with a card or regenerate.
- Two simultaneous jobs on the 2-CPU server make renders 2x slower; the scheduler runs one job at a time.
