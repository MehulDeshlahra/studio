# Studio

Automated faceless Shorts studio (₹0, free AI stack, runs on an Oracle server).

- `scout/` the scout agent: studies what is working on Shorts right now and what is new in AI/tech
  (`scout.py`, watchlist in `watchlist.json`). Read-only, free models only.
- `knowledge/` what the scout learned: `playbook.md` (editing that wins / flops, with video ids),
  `topics.json` (ranked story ideas), `videos/` (one analysis per watched Short), `shorts.json` (view snapshots).
- `lib/llm.py` OmniRoute client (text, and Gemini watching a YouTube URL).
- `RESEARCH.md` the hand research behind the first playbook.

Secrets never live here: keys stay as files on the server.
