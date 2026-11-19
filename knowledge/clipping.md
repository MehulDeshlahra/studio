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

## Where the money is paid: viewer country (19 Nov, read from the joined briefs)
- CoD MW4 DMZ (Clipping Culture): views from India, Pakistan, Bangladesh are NOT PAID; other countries $2/1K (TikTok),
  $1.50/1K Instagram; caption must have #Ad/#Advertisement/#Sponsored and @callofduty. Footage is in a Google Doc under
  "Reference materials" (tools/whop.py brief now opens those).
- Jo Koy (Eclipse): Instagram Reels only, 70%+ of views from the US, caption names "Blue in the Face, on Netflix".
- So Cut Capsule must grow a US/UK/global audience, not an Indian one: English captions and hooks, post at US evening
  time, US-relevant topics. Every source entry keeps "not_paid_countries" and "audience_rule" (engine/whopbot.py).
- publish.py posts a campaign clip only to the platforms its source allows (Jo Koy: IG only).
- Footage hosts seen: Google Drive folders (gdown list + download, Jo Koy 13 files, Daise 235 incl. photos and muted
  copies), Frame.io share pages (SEGA: 4 trailers; tools/grab.py saves each asset's HLS master at 1080p with audio),
  MediaSilo (CoD: link dead, "could not be found" -> official YouTube upload is the fallback).
- Eneba BroPacks bans automated clipping (needs own reaction/voice-over): skipped. Most briefs ban AI voice-overs and
  added music (CoD), want #Ad as the first hashtag on its own line and at most 3 more hashtags: clipper.py does that
  for every campaign source.

## Market map + strategy (19 Nov, from all 120 live Content Rewards campaigns + web research)
- Content Rewards money by category (budget left): entertainment $284K (31), business $155K (8, mostly Boxabl $0.50-1),
  personal-brand $58K (19), gaming $50K (11) + streamer $29K (8) + twitch/roblox $14K, technology $42K (7),
  music $19K (18 small sound campaigns), comedy $1K (2), anime 0, Hindi/India 0. Median rate $1/1K, max $6.
- Types: clipping 111, ugc-faceless 14, reposting 11, sound 10, ugc-with-face 10, slideshows 10, logo 4.
- Platforms: TikTok 118 (banned in India: we skip it), Instagram 106, YouTube 75, X 20, Facebook 10.
- Our watcher read page 1 only (120); the listing has a nextCursor: there are more pages. TODO: read every page.
- India views are not paid on most global campaigns (CoD, SEGA list India/Pakistan/Bangladesh as unpaid; several need
  50-70% US). India-first platforms pay India views in rupees: ClipConnect (Rs 10-100/1K, 10% fee each side, UPI from
  Rs 500), Dashrize (weekly UPI, IG/YT/FB/X), INDclipping (Rs 30-100/1K), Klipp.in (18K clippers), Vyuzz (city-level
  campaigns, UPI), Halchal app (regional languages). Global others: Vyro (MrBeast-backed, TikTok/Reels/Shorts/X,
  $1K+ campaigns), Clipping.net (up to $3), Promote.fun ($0.20-2.25), ClipAffiliates, Ssemble (must edit in their app).
- Decision basis: one page = one audience. Cut Capsule = English, US/global. Hindi clips (Indian platforms) need a
  separate Hindi page, never mixed (the US share is a payout rule; a mixed audience fails it).
- Never: betting/1win/casino, TikTok via VPN, AI voice-over where banned, music where banned, footage outside the
  official folder, reposting without a campaign, fake views/engagement, deleting a submitted post before 30 days.
- clippingalpha.com (19 Nov 04:02 UTC): 974 live campaigns on 6 clipping platforms, $2.4M left (631 clipping, 143 UGC,
  39 logo, 161 music); CPM: 337 at $1-1.99, 130 at $2-2.99, 55 at $3+. We read 120 of them. It ranks campaigns and
  shows "$ paid in the last 24 h": use it as the cross-platform campaign source (public pages).
- Betting/casino (owner asked "why not", 19 Nov research): India's Promotion and Regulation of Online Gaming Act 2025,
  in force with its Rules from 1 May 2026, makes ADVERTISING online money games a crime: up to 2 years and/or Rs 50 lakh
  (PIB). The owner lives in India, so posting 1win/Stake clips is personal criminal risk, whatever country views come
  from. Instagram/Facebook also restrict gambling promotion. Abroad people do it (Stake $10 CPM; UK OSINT report found
  44 clipper/tipster accounts pushing unregulated sites). Rule stays: never.
- TikTok from India (19 Nov): banned since 2020 (IT Act 69A blocking of the app). A VPN alone fails in 2026: TikTok reads
  the SIM country code, device region and datacenter-IP lists; reports of 0 views / views stuck in the home country.
  What works for others: a real foreign SIM + residential IP + phone set to that region (paid). Posting automation:
  the official Content Posting API makes unaudited apps post PRIVATE only; other GitHub uploaders use browser
  automation (against TikTok's terms). Our server is in Mumbai (Oracle AS31898, IN). Parked: costs money, low
  reliability, account risk. Re-check if the owner has someone abroad or the ban changes.
- 19 Nov 10:44: engine/campaigns.py reads Content Rewards' own JSON API (/api/campaign/campaigns/discover, public,
  cursor pages): 733 live campaigns, $1.64M left (was 120 from the page scrape). 93 score >= 60, 45 >= 75. Country-priced
  campaigns (geoPriced, SEGA) carry the rate in cpmMaxRateCents. Blocked now too: AI-girlfriend / NSFW chat apps
  (Candy.AI), poker / rummy / teen patti / fantasy-cash, regional-only campaigns ([NORDICS], [FRANCE]...).
- First 9 campaign clips (19 Nov 08:05-10:10): CoD 2, SEGA 3, Jo Koy 4; vision 10/10 but hooks were word salad and a
  subtitle said HEISMAN (Heismay). Fixed: brief names glossary (whisper initial_prompt + fuzzy snap, clipcore.fix_names),
  natural-hook rules with bad examples, captions name the product, required lines never repeated, YouTube title = the
  caption sentence. FaZe (ClippedIn) needs an application + their logo overlay: whopbot keeps "apply_later".
- Indian platforms (19 Nov): no paid campaigns (ClipConnect 1 XP challenge, Vyuzz 0, Dashrize samples only).
  engine/indiawatch.py checks daily and pings when one appears.
- Post capacity is now the bottleneck, not campaigns: 1 post/day in warm-up (to 27 Nov), 2/day after, while there are
  45 campaigns >= 75. More English clip accounts = more paid posts (each campaign accepts every account we connect).
- Vyro (19 Nov 13:40, logged in, 4 accounts connected): only 9 campaigns in its whole catalog; almost all carry a
  "location" restriction and /eligibility returns eligibleAccounts [] for an India-based clipper (no Join button).
  The rest are TikTok-only. The API needs DPoP-bound tokens (can't be replayed outside the page), so any future use =
  drive the page + read its responses (tools/whop.py browser). Parked: re-check weekly; never change the profile
  country (KYC). Content Rewards is the platform that works for us.
- Content Rewards accounts 19 Nov: @cut.capsule YT, @cutcapsule IG/FB/X, @cutcapsule.gaming IG/FB, @cutcapsule.tv IG/FB
  all Connected (FB verified by a code Reel posted through the API).

## What winning clip pages add (19 Nov study: top YouTube clip Shorts of the last 30 days, Gemini watched each)
Data: 149 Shorts found in 10 niche searches; 16 watched; clip pages among them, views in 30 days:
- Btalk Radar 17.3M, 15 s: STORY told by its own overlays ("Rashmika was waiting for Vijay to offer the bottle...",
  then "her teary eyes says it all"), red circle on the person, zoom, sad music. The page invents the narrative.
- Abuzar Core 13.6M, 19 s (MC Stan, India's Got Latent): hook "MC Stan ne show pe kya nikal diya?" + a REACTION overlay
  "Bhai ye kya hai?" for the rest. Single moment, loops.
- Kohsa Edit 12.1M, 22 s: one framing line "SAMAY WAS RICH", a reaction cut to the judges, sticker, remix song.
- theRawTRex 9.2M, 18 s (CoD MW4): split screen "IN GAME" vs "IN REAL", a comparison the original never had.
- Stunt Master 22.8M, 15 s: GTA 6 "30fps vs 60fps" labels over gameplay: the debate is the hook.
- stand-up pages: 75-178 s single bits with split screen comedian / audience reactions also win (long is fine there).
Rules we took (engine/clipper.py + clipcore.py, shipped 19 Nov):
1. Our own text layer on every clip ("notes": 1 context + 2 reactions tied to the exact spoken words), held if fewer
   than 2 land (originality: Instagram/YouTube stop recommending re-uploads without material edits).
2. Length by type: reaction / one moment 15-25 s ending on the payoff (loops); stories / stand-up 30-55 s.
3. Hook text stays on screen for the whole clip (all winners keep the framing line up).
Next ideas (not built yet): comparison formats for gaming (game vs real, old vs new), a reaction cut-in when the
footage has audience/judge shots, a punch-in zoom on the payoff word, brand-allowed music only.
Brand safety: no astrology / tantra / remedy clips (Tarun Sharma Show paused 19 Nov); reposting campaigns score 0.
