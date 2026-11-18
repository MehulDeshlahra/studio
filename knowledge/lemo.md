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
- First result (tech 1117-0721): old layout 3 pre-render problems, stage 1 (both share a snapshot artefact: video clips do
  not show in stills). The caption/UI-box overlap was gone.
- Turn on only after Mehul approves the side-by-side.

## Specials (after the 20 Nov launch): hand-directed in a Kiro session with the skill, posted through Studio publish
- Katha: Shadow Puppetry (close to India's leather puppet theatre). First candidate: Kartik Purnima / Dev Deepawali (24 Nov)
  or Gita Jayanti (1 Dec).
- Aage Suno: Halftone Dossier (printed case file).
- Kaise Tech: Exploded Teardown.
- One per page per week at most; a new format, never a copy of an existing video. Mehul picks the first style.
