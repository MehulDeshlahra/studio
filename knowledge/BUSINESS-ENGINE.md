# Business engine (any business, from its own media library)

Owner vision (20 Nov): give Studio a business name + its media library, and Studio makes professional reels for it.
Nothing business-specific in code. Owner is happy with the quality of reel-studio-1120-t5 (VAJRA).

## How it works now
- Code: `engine/biz.py`. A business = `businesses/<id>/business.json` (library roots + sources, ban regex, rules,
  never-regex, optional python text filter, voice, edit, theme, cta, caption rule, hashtags, deliver).
- `python engine/biz.py <id> index | make [--no-deliver] [--angle ".."] [--job ID] [--from plan|voice|assets|compose|render] | status`
- Steps: index (vision looks at 4 frames of every clip once: what it shows, burned-in text = left out, black bars cropped)
  -> plan from real media (fresh first, 21-day cooldown) -> rules + text filter -> voice (Gemini Charon, Edge fallback)
  -> frame check of every scene BEFORE render (swap footage, alt ids) -> Studio compose + mix -> render -> final QC
  (format, LUFS, voice, rules, frames; one repair round) -> deliver.
- VAJRA delivery: `vajra-automation/social/engine/intake.py` -> pending.json + Telegram approval card (approve = queue).
- Laptop run: keys `~/.studio-gemini.key`, `~/.omniroute-studio.key`; OmniRoute reached by an auto SSH tunnel.

## Decided next (20 Nov): run with the laptop OFF
Owner: everything must run when the laptop is off. Research done 20 Nov:

| Option | Cost | Verdict |
|---|---|---|
| Server disk (Oracle Always Free = 200 GB boot+block total; server uses 46.6 GB) | free | CHOSEN: media next to render, no new service. Owner must expand the boot volume in the Oracle console (check other instances' volumes first). |
| Immich | free | LATER only: needs 6 GB RAM min (8 recommended); server has 12 GB shared with job bot, Studio, Muse. Add when many clients want phone camera-roll upload; run with ML off. |
| Google Drive folder per business (rclone) | free 15 GB/account | optional upload route for clients |
| Telegram group per business | free | default upload route (as VAJRA) |
| Cloudflare R2 / Backblaze B2 | 10 GB free | R2 needs a card (money rule) -> no; B2 maybe as backup |

Plan:
1. Store: server `~/libraries/<business>/{clips,photos,music}` (+ library.json). Engine reads any folder already.
   VAJRA: add `assets/clips` + `assets/music` to the server clone's sparse checkout (~150 MB) of ~/vajra-automation.
2. Upload: Telegram group per business; Drive folder optional.
3. Make + render on the server on a timer when a business's queue is low (low priority; laptop render worker used when on).
4. Server delivery for VAJRA needs a GitHub push token on the server (intake.py pushes + starts approve.yml).
5. Owner-only: expand Oracle boot volume (free, ~5 min). Needs Oracle login (owner forgot it on 20 Nov).

## Status
- [x] engine + VAJRA business + intake, first reel approved for quality (20 Nov)
- [ ] server: sparse checkout clips/music, push token, timer
- [x] owner: Oracle login recovered, boot volume expanded to 200 GB (20 Nov; server / = 193 GB, 156 GB free)
- [ ] second business

## Oracle login
Details are in the local ops notes on the laptop (Vajra/.kiro/steering/vajra-ops.md), never in this public repo.
