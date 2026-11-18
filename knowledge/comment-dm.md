# Comment-for-freebie reels + follow gate (research 19 Nov 2026)

Owner (19 Nov): reels that say "comment X, I'll DM you the link"; people follow to get it, which pulls followers. All
pages where it fits, not every reel. Set up the automation on Meta.

## Evidence (our own data, official APIs)
- Finance research (1,690 reels with captions): 10 used "comment X -> DM". Median comments per like 0.20 vs 0.007 for
  the rest; median likes 370 vs 45. Every big one offered a concrete freebie: prompts, investing guide, mutual fund ebook,
  calculators (~/studio-out/research/finance/*.json, scan .tmp/cta_scan.py).
- Tech rivals (Business Discovery, 193 posts): @trakintech "Comment Music -> APK link" 92K likes / 178K comments;
  "Comment Toolbox -> PDF editor app" 28.6K likes / 45K comments. Comment-for-DM posts 0.81 comments/like vs 0.016.
  (~/studio-out/research/cta-scan.json, .tmp/cta_scan2.py). Do NOT copy the APK idea: modded/pirated app links risk the
  page; our freebies are our own.
- Katha / raaz / jain: rival IG lists mostly wrong usernames (Business Discovery 400), no evidence yet. Fix the lists
  (knowledge/ig-accounts.json) and rescan before judging those pages.

## How it works on Meta (official docs)
- Private reply: ONE DM per comment, within 7 days, to the commenter's Inbox (followers) or Requests (others).
- Follow check: the user profile field is_user_follow_business, readable only after the person messages us or taps a
  button (comment alone = "User consent is required"). So: comment -> DM "follow karo, phir DONE likho" -> they reply ->
  check -> link, else ask again. Fail open (send the link) when Meta returns no follow status (as openreply does).
- After they reply, the normal 24 h window allows more messages.
- ACCESS: "Standard Access apps can only access data for people who have a role on the app". Messaging the public needs
  Advanced Access = App Review + Business Verification (2-4 weeks, free). Our app Planstalk Connect = Standard.
  Meta's official Ads MCP app (our posting login, token has instagram_manage_messages) serves the public, so dm.py now
  retries a refused send through it and remembers it (19 Nov). NOT yet proven: needs one real comment from an account
  that is not a role on either app.
- Free fallback: Meta Business Suite > Inbox > Automations > comment-to-message (desktop, up to 5 exact keywords, ~15 min
  delay, no follow check, set per post by the owner).
- dm.py polls every 10 min (no webhook: dev-mode webhooks reach app roles only), so the link arrives in <= 10 min.

## BUILT 19 Nov (owner: "go ahead")
- engine/offers.py: channel.json "offers": {on, every 4, kinds}. ON for finance + tech (sheet), katha + jain (wallpaper
  preferred, sheet only for a real vidhi/aarti). Raaz keeps its PART2 -> next part DM.
  decide() after the plan: design call (script + the video's research web sources) -> code drops lines with numbers not in
  script/sources -> separate check call drops unsupported lines and scores the gift; < 6/10 or "none" = normal reel (tech
  wake-word video and a recap sheet were rightly refused). Adds a closing "Comment KEYWORD" scene before the goodbye.
  build() after assets: sheet = HTML -> headless Chrome screenshot; wallpaper = video's own picture + handle; pushed to
  studio-media offers/<page>/; registry ~/studio-out/offers.json. Caption line via seo.text_for.
  Test: python engine/offers.py <cid> <job> (writes only /tmp).
- dm.py: offer keyword comment -> IG private reply asking follow + DONE (gate keyed by the IGSID Meta returns) -> any reply
  -> is_user_follow_business -> link, or "abhi follow nahi dikh raha" (max 3) -> fail open when Meta gives no answer.
  Facebook comments get the link directly. Offer posts page through all comments (500/run). Public replies vary.
  Cap 250 DMs/page/day. Mock test .tmp/gate_test.py (passes).
- Dashboard Channels page: "Offer reels" table (comments, asked, links sent, new follows).
- STILL UNPROVEN: Meta accepting DMs to strangers (see ACCESS above): first real comment from a non-team account.

## Original plan
1. Freebies made by the engine, free hosting (studio-media repo / GitHub Pages), one per offer reel, matching its topic:
   finance: checklist / calculator sheet / "documents to keep" PDF; tech: tools list, settings checklist, prompt pack;
   katha: HD deity wallpaper, aarti / vrat katha PDF, festival puja vidhi; raaz: the full story or next part early;
   jain: stotra PDF, wallpaper, festival vidhi.
2. Offer reels: about 1 in 4 per page. The plan gets an "offer" (keyword + what it is); last scene shows the keyword big
   ("Comment PDF"); caption + pinned comment repeat it. Keyword unique per reel.
3. dm.py: per-reel keyword -> offer link, follow gate (DONE reply -> is_user_follow_business), fail open, log clicks.
4. Dashboard: offers list with comments, DMs sent, follows gained.
