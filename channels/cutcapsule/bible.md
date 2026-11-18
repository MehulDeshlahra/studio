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

## Format (v1)
- 1080x1920, blurred fill of the same frame, the video full width in the middle, hook title (Anton, 3-7 words) on top,
  3-word captions (Montserrat ExtraBold) with the spoken word in yellow, -14 LUFS.
- Start on the hook sentence, end right after the payoff (whisper word times; never cut mid-word).
- Next: face-tracked 9:16 crop for podcasts, facecam-over-gameplay for streams.
