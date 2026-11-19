# Rules learnt from mistakes (engine/lessons.py, daily; every script prompt reads this)
Updated 2026-11-19 03:57 from 636 recorded problems on 5 pages.

- ALWAYS write on-screen text as the exact words of its spoken line or a 1-4 word tag of it; never a different phrase (seen 50+ times: tech, katha, jain)
- ALWAYS put titles, numbers and labels on a clear dark area of the picture; never text over a busy or bright part (seen 20+ times: tech, katha)
- ALWAYS give every scene one clear main visual in the centre; a scene with only a dark gradient or empty frame is a hold (seen 12+ times: tech, katha)
- NEVER repeat the same text twice in one scene (title and tag saying the same thing) (seen 5+ times: tech)
- ALWAYS end with the page's own end line and handle; never another page's handle or end line (seen 10+ times: tech, katha)
- ALWAYS start the first spoken line with the hook itself in the first 4-6 words; no greeting, no intro (seen 6 times: katha, tech)
- ALWAYS keep the script inside the page's word range (channel.json edit.words); too long is cut, too short is held (seen 6 times: raaz, tech)
- ALWAYS keep each recurring character's description word for word in every image prompt that shows them (seen 2 times: katha)
- ALWAYS draw a deity in their traditional form, dignified and fully dressed; never count faces or arms (seen 8 times: katha)
- NEVER put English articles (THE, A) or Devanagari in on-screen text; Hinglish in Roman letters only (seen 8 times: katha, tech)
- NEVER ask an image model for readable text, numbers or logos inside a picture; real logos come from the 'real' field (seen 10+ times: tech)
- ALWAYS use a scene type the page's look can draw, with its data (stat needs a number in 'value', compare needs 2+ items, flow needs 2+ nodes, ui needs rows) (seen 4 times: finance, tech)
- ALWAYS show a real logo on its own card scene, once, at the brand's reveal; never as a full-screen background behind text (seen 3 times: finance, tech)
- NEVER use a YouTube thumbnail, a stock-site preview or any picture with burnt-in text as a real picture (seen 3 times: finance, tech)
- ALWAYS say who does what: a regulator (RBI, SEBI, NPCI) SETS a rule; the bank or company PAYS or acts (seen 1 time: finance)
- ALWAYS say a rule with its exact condition and the day it starts (for each day of delay AFTER T+1, from the 31st day, only if nothing is outstanding, 7 WORKING days) (seen 3 times: finance)
- ALWAYS show who set a rule and when on screen (a source card: RBI circular · 20 Sep 2019) and in the caption (seen 2 times: finance)
- NEVER state a loss figure, a percentage or a 'most / majority' claim without an official source; without one, say it without the number (seen 3 times: finance)
- ALWAYS make every calculated number come out of the script's own numbers exactly (₹45,000 at 42% with ₹5,000 a month paid is paid off in a year; it never grows to ₹1,02,000) (seen 2 times: finance)
- NEVER mix two rules' numbers (₹500/day is card closure; ₹5,000/day is property papers; ₹100/day is failed payments) (seen 2 times: finance)
- NEVER give investment advice: no stock, fund or coin picks, no return claims, no market prices from the last 3 months (SEBI) (finance rule)
- ALWAYS end a finance reel with one action the viewer can do today and 'Save karo' (finance format, from 30 watched rival reels)
- ALWAYS keep fiction serial parts in order, each ending on its own cliffhanger; never a real victim or a friend as the villain (raaz rules)
- ALWAYS ensure the first spoken line starts within 4-6 seconds of the video start; no delay (seen 6 times: katha, tech)
- ALWAYS ensure the script matches the spoken lines; no missing or extra parts (seen 26 times: katha, tech)
- ALWAYS review the video for visual quality and consistency; no missing or low-quality visuals (seen 18 times: katha, raaz, tech)
- ALWAYS ensure the video length is within the allowed range (25-55 seconds); no too short or too long videos (seen 3 times: raaz, tech)

## GOLDEN RULE (19 Nov, owner, after a low-effort Finance Fuel Story went live)
OUR CONTENT SHOULD NEVER BE LOW EFFORT. Money comes after hard work. Before doing anything: research what the best do
and what NOT to do, think it through, ask "is this good?" and if it is only good, discard it and make it better. Ship
only the best of the best. Every format, feature and post has research behind it (written down) and its real output
is looked at before it goes live.

## 19 Nov: the Stories that went live (Finance Fuel "myth", 2 frames)
Plain text on black, no brand or picture, "DM karo" instead of a sticker, the answer frame posted together with the
question (no suspense), and the answer did not answer the question (asked "send unknown money back?", answered "PIN is
never needed to receive"). Rules: a question and its answer are checked against each other; a reveal is never posted
in the same minute as the question; no format ships without a researched design and frames checked by eye. The API
cannot add poll / quiz / link stickers, so automated "quiz" Stories can never be interactive.

## 19 Nov audit (golden rule): a 9-10 vision score meant nothing
Frame-by-frame audit of everything queued: 8 of 30 approved reels were not postable although the final review gave
them 9-10/10: all 6 Navkar Bhav (Mughal onion domes, blue/green-skinned Tirthankara and Bahubali, saffron-robed Jain
monks, a female Hindu-style Dharanendra, a king who changes face, one story needing a source check), Puraan Ki Katha
"Brahma's fifth head" with a one-headed Brahma, Finance Fuel gold/silver (investment advice, unsourced numbers).
Fix: every page has channel.json "visual_checks", a must-answer checklist the reviewer answers per frame; any yes is
serious and caps the score at 5 (tested: the same 3 reels went 9-10 -> 4). Positive iconography text was not enough
for the image model: write the NEVER list too (iconography.JAIN_NEVER). Order matters: a page's first posts are its
strongest, not its oldest (katha: Ujjain/Greenwich first).

## 19 Nov: true before pretty (story pages + clips)
- Scripture pages had no fact check: a jain Reel said Mahavira went 12 years without food then ate kheer and got
  kevalgyan (false: ~325 meal days in 4545; kevalgyan during a 2-day fast); a katha Reel mixed two Mahakal stories.
  Fix: channel.json "story_check" (plan.story_fix): every event and history claim judged against web sources and the
  named scriptures, 2 rewrites, then held before voice. Overclaims ("whole world", "first ever") count as false.
- Clip context notes invented a special and a year. Fix: notes get the video's own facts (title, channel, date,
  description); a name or number not in them or the transcript is rejected in code, asked again once, then dropped.
- The vision check scored a clip 10 with an empty stage (the comedian walked out of a fixed crop). Fix: the crop
  follows the speaker (smoothed path, dead zone, pan limit) and code measures time out of crop (>10% = held).
