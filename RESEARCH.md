# Studio research (16 Nov 2026)

## Benchmark shorts watched (frames + transcript + loudness measured)
| | Kurzgesagt "Dust Is Not What You Think" (3M) | Fireship "Big O with a deck of cards" (1.5M) | Zack D. Films "Watermelon with floss" (14M) |
|---|---|---|---|
| Length / speech | 71 s, 208 words, 2.95 w/s | 59 s, 237 words, 4.0 w/s | 36 s, 105 words, 3.0 w/s |
| Hook (frame 0) | "What is DUST?" title + magnifier on dust, already on screen | "If you wanna get a job as a…" text over a scene | Hands already cutting the melon; first word is the action |
| Picture | Every noun is drawn the moment it is said (skin, window, sink, mites, lungs, fireplace, rain drop, Amazon, Earth) | Real stock clips + memes, one recurring Big-O chart with an arrow that moves to each curve | One continuous 3D take, camera follows the hands |
| Cuts | 7 hard cuts; the rest are continuous camera moves between worlds | a cut every 2.1 s | zero cuts |
| Text | 2-4 word follow-along captions, small, low-centre; labels with leader lines on objects ("~1%", "Mucus Membrane") | big bold 1-3 word chunks; mono labels for terms ("Linear Time: O(n)") | small 2-3 word captions |
| Colour | a new dominant hue per act | real footage colours | warm realistic |
| Ending | returns to the first scene (loop) + a twist line | punchline | absurd twist ("summon the great Watermelonus") = comments + rewatch |
| Loudness | -13.9 LUFS | -19.8 LUFS | -10.0 LUFS |

What they share: the hook is on screen at frame 0; every sentence has its own picture; one recurring element
(a chart, a set, a character) holds it together; captions are small and few words; the end loops or twists.

## Skills cloned and read (C:\Users\mehul\Desktop\studio\ref)
| Repo | Licence | What we take |
|---|---|---|
| heygen-com/hyperframes (latest, incl. new motion-doctrine, cut-the-curve, seam-craft) | Apache-2.0 | engine; vector law at seams (exit direction = entry direction, cut mid-motion), one "current" direction, no idle wobble, stillness 0.3-0.75 s before a payoff, seam-gate verifier |
| joodic/reel-craft (410k-view trial reel) | none stated: ideas only | script shape (hook that doesn't explain itself, wrong guess kept open, new loop right after the payoff, callback), nothing appears before its word, new picture every ~2 s, sound at 7-8/10 (40-60 events per 90 s, ambience bed, 2-4 silence drops), -14 LUFS, anti-slop list |
| Tejashmakwana/motionmaxxing | Apache-2.0 | measured motion (median move 0.33 s, land decelerates, arrive from oversize), "never ship" list (HUD labels, deck layouts, stat slides, slogan copy, logo end card > 1.4 s), scripted render gates look.py / lint.mjs |
| iart-ai/tiktok-video-skills | MIT | retention arc, pattern interrupt every 2-4 s with uneven intervals, 9:16 safe box 900x1400, loop seam check |
| bestagentkits/motion-video-skill | MIT | measurable finish: cuts on beats +-2 ms, music 4-6 dB under voice, -14 LUFS, true peak <= -1 dBFS |
| Vincentwei1021/video-shotcraft | Apache-2.0 | 124 camera/shot recipe cards; real captures over mock UI |
| Vincentwei1021/video-talkcraft | PolyForm NONCOMMERCIAL: principles only, no code | word-level timestamps drive everything; tag each sentence with what it does (data / compare / quote...) and pick the visual card from that; real screenshots for evidence, never mock UI; layout rotation (same card not 3 shots in a row) |
| LottieFiles/motion-design-skill | MIT | Disney principles, spring damping rules |
| alchaincyf/huashu-art-motion | MIT | 35 art styles for variety between episodes |
| feitangyuan/onetake | NONCOMMERCIAL: skip | — |
| OpenMontage, oliverhees/hermes-motion-pack | AGPL: ideas only | pipeline shape, self-critique step; Kokoro / Piper as $0 voices |
| 2boysfromtown/hyperframes-motion | MIT | basic templates (emoji products, glitch): below our bar, not used |
| social-media-skills/skills | MIT | hook-writer, reels-script checks |

## Research tool
Agent Reach 1.6.1 installed on the laptop (MIT, read-only; github, youtube, web, reddit, v2ex work without login).
YouTube subtitles defaulted to Chinese and hit a 429; local whisper on downloaded files worked instead.
Use for the idea step: GitHub trending/releases, Reddit threads, YouTube search. No logins on main accounts.

## Round 2: recent winners (Oct-Nov 2026), measured
| Short | Views | Length | Cuts / avg shot | Words/s | LUFS | What makes it work |
|---|---|---|---|---|---|---|
| Dhruv Rathee "Don't buy the new iPhone Duo" (Hindi) | 23M | 77 s | 13 / 5.5 s | 2.8 | -10.8 | split screen: graphics top, him bottom; prices STACK up item by item ("x3", AC, TV, fridge...) until the total hits; relatable Indian swap (buffaloes, e-rickshaw) |
| Cleo Abram "Something in King Tut's tomb" | 3.4M | 52 s | 19 / 2.6 s | 3.8 | -17.7 | "Everybody stop." hook; one 3D model of the tomb is the home set and returns 8+ times, each time with a new arrow / ? / pixel reveal; neon-green labels; numbered list that grows (1. radar, 2. gravity); real footage in between |
| Varun Mayya "Jensen Huang just resigned" | 959k | 77 s | 42 / 1.8 s | 3.5 | -12.9 | evidence editing: real article screenshots (CNBC, NYT, TechCrunch, CNN) with the exact phrase highlighted as it is spoken, real photos of every person named, a cut every 1.8 s, presenter only at the end |
| Aevy TV "Coolest thing anyone's done with Claude" | 1M | 111 s | 39 / 2.8 s | 3.6 | -18.9 | "Wait, somebody just..." hook; story of one real person; real screens |
| ByteByteGo "REST API in 30 s" | 455k | 32 s | 0 / one diagram | 2.6 | -14.1 | one diagram that grows |
| MKBHD "iPhone Duo animation" | 7.4M | 20 s | 0 | - | -30 | pure product animation, no edit needed |

Patterns that are new vs round 1:
1. Evidence editing (Varun): real headline/post screenshots, highlighter lands on the word as it is spoken. Best fit for an AI/tech news channel and fully faceless-friendly.
2. A recurring home object (Cleo's 3D tomb, Kurzgesagt's window): the video keeps returning to it, each return adds one new mark.
3. Stacking numbers (Dhruv): items pile up with prices until a total; Indian everyday swaps make tech numbers feel real.
4. Pace of the winners: a new picture every 1.8-2.8 s, 3.5-3.8 words/s.
5. Loudness: the Indian winners are LOUD (-10.8 / -12.9 LUFS). Target about -12 LUFS, true peak -1, not -14.
6. Hooks are 2-4 words of interruption: "Everybody stop." / "Breaking news," / "Wait, somebody just...".
Instagram reels themselves need a logged-in account to download (Agent Reach marks them login-only); YouTube Shorts used as the proxy.

## Round 3: prompt-motion.com (gallery of 240 Claude-made motion videos with their prompts; read 16 Nov)
Licence/robots: Content-Signal use=reference, ai-train=no, AI crawlers and /api/ disallowed. Read as reference only;
the server scout must NOT crawl it.
- One 26-word prompt copied 33 times: results from 0 to 17,023 likes, median 5. Vague briefs scatter.
  Prompts over 100 words: median 56 likes vs 5 for short ones.
- The five parts of the best prompts: ONE concept ("one shape, never cut"; "the orange dot connects every scene"),
  a BANNED list, timing to a beat grid ("120 BPM, 7 bars, something on every beat"), a BUILD method
  (one HTML file, every frame a pure function of t in seek(t), Playwright capture, 4-8 subframes blended for
  motion blur), and a REVIEW step.
- Banned list that works (from the top entries): glows/neon, particle bursts, crossfades, bouncy easing,
  text/labels in the corners, gradients on UI chrome, stock footage, dead time >1 s, Math.random,
  "motion that isn't connected to an element already on screen", "anything that looks like a template".
- Explainers: give a PROCESS with a start and an end (empty glass -> finished Negroni, 1,028 likes), or a fixed
  scene list. None of 27 explainer prompts asked for fact checks: we must.
- Plan -> check -> fix loop: 3 different ideas with 1 still each, asset list, beat table (time, on screen, what
  moves, WHY the beat exists); contact sheet of one still per beat (focal element >= half the width, text >= 32 px
  at 1080p, nothing in corners, new layout every frame); every-frame strip from 0.3 s before to 0.3 s after each
  transition; scan for single-frame pops; fix ONE thing at a time and prove it with frames.
- Fix requests that work: "focal element spans >= 60% width, crop rather than shrink"; "exits before entries";
  "at [t], [element] leaves A, travels into B and becomes its role there"; "durations vary, never equal
  staggers"; "nothing simply appears: grows, slides from an edge or is revealed by a mask".
- Audio recipe from the Ora 2 film: shorten pauses >0.28 s to 0.2 s; level phrases toward the median; word timings
  by splitting at 100 ms pauses and transcribing each piece (one Whisper pass can be 0.5 s late); voice ~9 dB
  above music in 300 Hz-4 kHz; one SFX per event placed by its measured peak; -14 LUFS.
- Claude can't judge sound or "feel" (moderate agreement with a motion designer on 13 videos): keep the human
  Telegram approval for the first posts of each channel; measure everything else.

## Round 4: prompt-motion.com videos watched (12 entries: video + prompt + contact sheet, studio\watch\pm\)
- Most-liked showreel (stephanlivera, 15 s): flat FULL-FRAME colour fields (tomato red, cobalt, cream, black, acid
  yellow), giant heavy grotesk words filling 70-90% of the width (CLAUDE / EASE / NEVER / LINEAR), one mark (an
  asterisk) that grows, spins and returns on the end card, colour-flood cuts, truchet pattern, dot-grid 3D torus.
  Every frame is one bold idea. -13.1 LUFS.
- Ora 2 launch (22 s, white canvas): words typed in time with the voice, ONE gradient word, real images in a ring
  -> grid -> burst, liquid-glass controls with sliders that move as named, camera push 1.00->1.04 per scene.
  -14.2 LUFS.
- Jake's "agent session story" (53 s): ONE fixed illustrated home set (desk, monitor, window, guitar) with a cute
  box mascot; day turns to night through the window; notes fly in, the mascot reacts (eyes, bandage, bow);
  screen changes state (code -> check). Made with heygen-com/hyperframes-community-skills (session-story skill).
  -> best model for our channel mascot + home set.
- Steam news recap (60 s, Japanese): dark cards + bullet lists, the same layout every item = the "slide" look
  to AVOID; it's what a vague prompt gives.
- Pattern across the good ones: one concept, one recurring carrier (dot / asterisk / mascot / shape), real assets,
  voice-timed text, measured loudness (-13 to -14 LUFS).

## Round 5: Instagram study (57 reels, 16 Nov)
Source: Apify IG scrapers + yt-dlp, metrics in watch/ig/metrics.json, 16-frame sheets in watch/ig/sheets/.

Numbers
- Loudness: almost all at -14.1 LUFS (Instagram normalises). Target -14, not -12.
- Winners (>=1M plays, n=26): median 58.5 s, first word at 0.0 s, ~3 words/s. Flops median 126 s.
- Cut count does not decide: winners range from 0 cuts (one continuous shot) to 30.
- Same story reposted by ezexplains: 592k / 48k / 5k. Hook and first frame matter more than topic.

What the winners look like
- ONE question, ONE visual metaphor for the whole reel:
  - snapstudy0571 13.3M: "how does the bike gear change?" 3D macro renders, no face, 28 s.
  - sparethoughtstudios 9.3M: "how do shop gates know you didn't pay?" dark 3D product renders, keyword caption on top, real data (0.025 mm, patent no., 58 kHz graph).
  - rajat_bytes 4.7M: "count to 1,023 on fingers" 3D hand + Hinglish captions + binary boxes.
  - madebysajjan 3.1M: 32 vs 64 bit as a stick figure + highway lanes, Hinglish.
  - sochozara_ai 4.1M: Veo 3D cartoon characters, Hinglish dialogue (talking-object format).
- Face-led winners: presenter in bottom half + real evidence on top (screen recording, article cards, numbered steps with red arrows): tech_spert 7.3M, digibott 7.1M, mrtechpedia 6.1M, cactuss.ai 4.9M, ezexplains 4.1M.
- GitHub/tool lists: rajenlabs 830k (face + repo card "replaces X" overlay, "Comment REPO" CTA), stewieaiguy 676k (cartoon character + gameplay bg + big 3-word captions).
- samjho.exe: the most polished faceless motion graphics in the set (dark gold UI cards, numbers) but 117-163 s long: 9k-160k plays. Polish alone does not win.

Lesson for Studio
- tech-001/002 were "news of a feature" with UI cards = the samjho.exe lane. The winning lane is a curiosity question ("X kaise kaam karta hai?") answered with one simple, physical visual metaphor in 30-60 s.
- Faceless is fine when the visual is a character or object (3D hand, stick figure, talking object, 3D product render).
