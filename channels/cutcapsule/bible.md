# Cut Capsule (@cutcapsule) - clip page bible (19 Nov 2026)

What it is: an entertainment clipping page. The engine (engine/clipper.py) takes a long video, finds the best
20-59 s moments, cuts them on the hook and the payoff, and renders finished vertical clips.

## Where the money comes from (research: knowledge/clipping.md)
1. Paid clipping campaigns (Whop Content Rewards, Vyro, ClipFarm, Indian hubs like CliprIndia/Clipping Cafe): the brand
   or creator pays per 1,000 verified views of OUR posts of THEIR footage. Typical $0.50-3 per 1K, caps per clip,
   Whop takes 10%. The owner joins the campaigns (sign-up = owner); each joined campaign = an entry in sources.json.
2. Our own page growth (followers -> brand deals later). Meta/YouTube pay almost nothing for reused clips.

## Hard rules
- POST ONLY WITH PERMISSION: a source in sources.json (campaign or creator's written OK). Everything else = test, never
  posted (copyright strikes close accounts; credit is not permission).
- GTA 6: Rockstar's policy treats pay-per-view / sponsored footage as commercial use and removes story spoilers (ending,
  cutscene compilations, big reveals). Only clip GTA 6 from a campaign or a streamer who allows it, and never a spoiler.
- Follow each campaign's brief exactly (tags, length, sound, platforms): breaking the brief is the #1 rejection reason.
- Caption credits the creator. No on-screen AI label.

## Format (v2, 19 Nov; engine/clipcore.py on the laptop)
- Layout PER SHOT, joined: webcam box over a game/video -> webcam on top (1080x700) + content below (1080x1220);
  a big face -> full 9:16 face crop, held still within the shot; anything else -> blurred fill, video full width.
- Hook banner (Anton, black on white, who + action + twist, true) from frame 1: on the seam for stack, top otherwise.
- 3-word pop captions (Montserrat ExtraBold), spoken word yellow + 112%, low on the frame (off faces and mouths).
- Start on the hook sentence, end on a sentence end; 30-45 s target, 58 s cap; only really quiet gaps cut (max 25%).
- Never intros, outros, channel plugs or sponsor reads (prompt + transcript check). -14 LUFS. 8-12 hashtags.
- Speed: ~2 min per clip on the laptop CPU. The NVIDIA driver is too old for NVENC (needs 610+); a driver update would
  move encoding to the GPU (owner's choice, not needed).
