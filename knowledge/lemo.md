# Lemo-Opuscar in Studio (18 Nov)

Library: github.com/lemomo-ai/lemo-opuscar, laptop copy `C:\Users\mehul\lemo-opuscar`, Kiro skill `lemo-opuscar`
(`~/.kiro/skills/lemo-opuscar`). 99 film styles; every demo film is hand-written code for one story (Shadow Puppetry =
1,689 lines of puppets for one myth), so it cannot run inside the 24x7 engine as is.

## Licence rules (keep them)
- Code (`core/`, `tools/`, demo code): MIT. Free to reuse; keep the notice in the file we copy.
- Docs (`STYLE.md`, `DEMO.md`, guides, image prompts): CC BY-NC 4.0 + a permission to follow/adapt them to make our own
  films (commercial ok). Not allowed: copying them into a product/service or sharing them. **This repo is public: never
  paste STYLE.md text or prompts into it.** Ideas rewritten in our own words are fine.
- Films we make with it are ours, no credit needed. Third-party material inside demos keeps its own licence.

## Used in the daily engine (pilots, all behind switches, off by default)
- Tech `stage` layout (`engine/compose_lab.py`, theme `"stage": true` or `STUDIO_LAB_STAGE=1`): main visual 15% bigger and
  110 px lower, caption as a dark pill with an accent dot at y 1395, no caption over a big-number screen, hairline grid
  instead of film grain. Keynote grammar.
- Katha `lamp` texture and raaz `print` texture (`engine/compose.py` `_texture`, theme `"texture"` or `STUDIO_TEXTURE`).
- Pilot runner: `~/studio-out/pilot.py <tech job>`, `~/studio-out/pilot2.py <cid> <job> <texture>`; results in
  `~/studio-out/pilot/*-result.json` + `preflight-sheet.jpg` per variant. Nothing is rendered or posted.
- Results (18 Nov, Studio's own pre-render check): tech 1117-0721 old 2 real problems (caption over the UI box, caption
  mismatch) -> stage 0; tech 1117-0729 old 1 (flow node cut) -> stage 0, score 8 -> 9. (An "EMPTY scene 1" in all four
  was the pilot's fault: its copy skipped the clip videos.) Side by side: Desktop\studio-tech-old-vs-stage.jpg.
- Turn the stage layout on only after Mehul approves (theme "stage": true in channels/tech/channel.json).
- REJECTED, do not switch on: `lamp` (katha) is invisible on the already warm golden paintings; `print` (raaz) turned the
  cream suspect cards nearly black and the layout audit reported text_occluded (it would hold videos). Textured looks
  need the hand-made specials, not an overlay.

## Specials (after the 20 Nov launch): hand-directed in a Kiro session with the skill, posted through Studio publish
- Katha: Shadow Puppetry (close to India's leather puppet theatre). APPROVED by Mehul 18 Nov: first special =
  Dev Deepawali (24 Nov), made on the laptop (WebGL/GPU) in a Kiro session with the lemo-opuscar skill; ready by 23 Nov.
- Aage Suno: Halftone Dossier (printed case file).
- Kaise Tech: Exploded Teardown.
- One per page per week at most; a new format, never a copy of an existing video. Mehul picks the first style.

## Creative system in the daily engine (18 Nov, owner: "learn from the library, use your brain, mix and match styles")
- Looks (engine/compose_lab.py SKINS, grammar learnt from Lemo styles, in our own words): keynote (real world, products,
  apps), blueprint (how it works inside), hologram (AI / invisible / future), terminal (hacking, code, data, privacy).
  Add a look = one SKINS entry (use, picture style) + its CSS in skin_css(); everything else follows.
- make.py, per video: (1) visual director: which scenes get a REAL logo / app screen / product photo, from
  channels/tech/visual-rules.md (learnt from 14 IG reels: big creators + hashtag pages); a brand's logo always once, at the
  reveal (scene 3+). (2) creative director: a look PER SCENE, in runs of 2+, max 3 looks, REAL scenes keynote, varied
  against the last videos. Pictures are made in each scene's look; the layout/captions are scoped per look; a change of
  look enters with a zoom-through.
- Hand-made Lemo specials (full films, laptop GPU) stay separate: Dev Deepawali shadow puppetry approved for 24 Nov.

## 18 Nov evening: mixed-look pilot (tech 1117-0729 "Hey Google"), fixes from its frames
- Looks chosen: 1-3 keynote, 4-5 blueprint, 6 keynote, 7 blueprint, 8-10 keynote. Side by side: Desktop\kaise-tech-OLD-vs-MIX.mp4.
- Fixed: real logos/photos were shown as blended props (lighten + feathered mask): the white Google card turned grey at
  the corners. Now realmedia lab layout = the card/photo itself, compose_lab `.prop.real` = clean rounded card.
- Fixed: a real app screen behind a diagram (ui/flow) was hidden under the panel. Now establish-then-overlay: the real
  screen plays alone for 1.0-1.8 s, then the card arrives and the picture dims + blurs (real bg = s<i>rb.jpg).
- Watermark filter: makeuseofimages (MUO mark) and Freepik premium previews are skipped.
- Story pages (katha, raaz): per-scene picture looks in channel.json "looks" (first = base = the page's current style),
  make._pick_story_looks + _look_prompt. katha: painting / puppet (shadow-puppet theatre) / pattachitra; raaz: film /
  cctv / memory / evidence. Base keeps >= 60% of scenes, scene 1 + last always base, cutaways of 1-3 scenes, max 2 extra
  looks. OFF ("looks_on": false) until the picture pilot (~/studio-out/pilot/looks-*/pair*.jpg) passes.
