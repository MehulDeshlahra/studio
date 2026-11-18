# Clipping for pay - research (19 Nov 2026, for Cut Capsule)

## How paid clipping works
A creator or brand funds a campaign: source footage, a brief, a rate per 1,000 verified views, often a cap per clip.
Clippers cut the footage, post it on THEIR OWN accounts (Reels, Shorts, TikTok, X), submit the post link, and are paid
for the views of approved posts. No follower minimum on the big platforms.

| Platform | Rate (seen Nov 2026) | Notes | Source |
|---|---|---|---|
| Whop Content Rewards | mostly $0.20-6 per 1K, avg ~$1; gaming median $1.125 (18 campaigns, 10 Nov) | 500,000+ clippers; Whop keeps 10% of CPM payouts; per-clip caps common ($35-150) | whop.com/contentrewards, openclip.app/clipping/gta-6-clipping, clippie.ai |
| Vyro (MrBeast-backed) | $1-1.50 per 1K on 26 Sep 2026 (some guides say $3) | a post must reach 5,000 views before it earns; cash out from $10 via PayPal/Stripe | streamer.guide/guides/how-to-earn-money-vyro, vyro.com/about |
| ClipFarm, ClipAffiliates, snipr, Bully network, Discord servers | $0.50-3 per 1K; Bully: $1 per approved clip + $1/1K, cap $100 | smaller campaign lists | marketplace.kreatli.com/guides/best-clipping-platforms |
| Indian hubs on Whop | per view, UPI payouts (CliprIndia), INR | CliprIndia (Indian YouTubers' campaigns), Clipping Cafe (133 members), ClipCartel India, Clipency | whop.com/cliprindia, whop.com/clipping-cafe |
| Live campaign list (data) | rate, budget left, burn rate per campaign | Apify actor reads all Whop campaigns, no login | apify.com/datagleaner/whop-content-rewards-campaigns |

Reality check (Benzinga / Yahoo, 18 Nov 2026): influencers promise $1,000-5,000 per million GTA 6 views; a real GTA 6
campaign paid $0.70/1K capped at $35/clip, so a 1M-view clip earned $31.50 after Whop's fee. YouTube Shorts pays
~$0.03-0.10 per 1K and does not monetize reused clips without added value. Money = many clips at 20-60K views each on
campaigns with budget left, not one viral hit.

Rules that get clips rejected: breaking the brief (length, tags, sound, platforms) is the #1 reason, ahead of editing
quality (whop.com/everywhere-media). Pick campaigns by budget left + cap + hold period, not by rate.

## GTA 6 (launched 19 Nov 2026, PS5 + Xbox Series X|S; no PC date)
- Campaigns: on 14 Nov Content Rewards had ONE GTA 6 campaign (a music push, "Tokyo Girl", $0.70/1K, $35 cap, song must
  play); GTA RP campaign Lysium/Benji Ramos (NoPixel V) $1.50/1K up to $150/clip (StoryCut, 4 Nov). More will open.
- What travels: streamer reactions (a chase, a crew argument), not silent gameplay. Top GTA streamers 2026: 3mr, xQc,
  Buddha, summit1g (ontrailai/clipping PLAYBOOK).
- Rockstar policy: gameplay allowed for NON-commercial use; "advertising, sponsored and/or pay-per-view game footage" is
  presumed to violate it; spoilers (ending, cutscene compilations, big story reveals) are taken down with no end date
  (bo3.gg, tbreak.com, shiftdelete.net). So: GTA 6 clips only from a campaign/streamer that allows it, never spoilers,
  and expect takedown risk on pay-per-view GTA footage.
- YouTube now monetizes graphic GTA 6 gameplay after the first 7 s (gtaboom.com).

## Copyright
Reposting someone else's video without permission = takedown + strike; strikes add up to account removal (Meta repeat-
infringer policy). Credit is not permission. Campaign footage comes WITH permission: that is the safe lane.

## Auto-clipping tools (GitHub, free)
ygf-ui/ai-youtube-shorts-generator (Whisper + LLM highlights + auto crop), GrepCut/OpenClipper (desktop, Parakeet/Whisper,
autoreframe), Lunar0769/ClipForge (ranked clips + SEO pack), alberto2005-coder/auto-clipper-ai (faster-whisper + LLM +
ASS captions), Syechan112/cliper-tools (yt-dlp -> Whisper -> Gemini -> ffmpeg 1080x1920), niraj5511/youtube-clipper.
All use the same pipeline: download -> transcribe -> LLM picks moments -> 9:16 crop -> captions. We built our own on
the parts we already run (engine/clipper.py): Gemini watches the YouTube URL (no download to find moments), the laptop
downloads only the chosen parts (YouTube blocks the server), faster-whisper word times, ffmpeg + libass render.
Paid SaaS doing the same: OpusClip, Vizard, Klap, Submagic (not used: Rs 0 rule).

## How the best tools do it (round 2, 19 Nov) and what we took
| Idea | From | In our engine |
|---|---|---|
| Crowd signals first: YouTube "most replayed" heatmap (yt-dlp -J, 100 points), Twitch community clips, chat velocity (shift 7 s earlier), audio spikes; only the top windows are downloaded and judged | ontrailai/clipping PLAYBOOK, crestclip, yt-heatmap-clipper, AutoClipper | heatmap peaks go into the Gemini prompt; a moment near a peak gets a bonus. (New videos have no heatmap for a while.) Chat/Twitch: next |
| Score = hook + flow + value + trend (0-99) | OpusClip help center | Gemini scores the 4 parts, we rank on the mean |
| Hook banner from frame 1; formula who + action + twist, accurate; start 1-3 s before the action | ontrailai PLAYBOOK | prompt rules + the hook banner on the whole clip |
| Viral median 41 s (18% shorter than average), 30-45 s best, < 60 s | OpusClip 13.5M clips | 30-45 target, 58 s hard cap on a sentence end |
| 80% of viral clips burn captions in, 79% animate them; word-by-word with the active word highlighted | OpusClip, ontrailai | 3-word pop captions, active word yellow + 112% |
| 8-12 hashtags, niche + generic (#fyp 2.2x median views, mixed 2.5x niche-only) | OpusClip | moment tags + page tags + fyp/viral/reels/trending, max 12 |
| Clip edges on sentence boundaries and silences, never mid-word | ClippyMe | whisper word times; start on the hook sentence, end on a sentence end |
| Silence / filler removal | ClippyMe (auto-editor) | only gaps that are really quiet (18 dB under speech), max 25% of the clip. A reaction's laugh or a crowbar bang is the moment: the first version cut 16 of 27 s |
| Active-speaker 9:16 crop, camera still within each shot | ClippyMe, AutoFrame (LR-ASD) | YuNet faces at 4 fps + shot changes; one aim per shot |
| Facecam on top, gameplay below for streams | GTA clip pages, OpusClip layouts | a face fixed near an edge in half the samples = webcam box -> stack layout |
| Captions must not cover the mouth; sound mix graded like visuals; no other app's watermark; follow the brief exactly | Whop campaign pages (Creator Clips, ClipMasters, Everywhere Media) | caption position per layout, -14 LUFS, vision check before Telegram |
| Analyse once, render on demand; per-clip source slices kept | ClippyMe, AutoFrame | the laptop caches the last 3 source videos |

## Our setup (engine)
- engine/clipper.py <cid> <url> [--n 4] [--test]; dashboard "Make a video now" on Cut Capsule takes a YouTube link.
- channels/cutcapsule/sources.json = permission list (campaigns). Unknown sources = test clips, never posted.
- tools/laptop_worker.py: "fetch" job kind (yt-dlp --download-sections); engine/laptop.fetch() on the server.
