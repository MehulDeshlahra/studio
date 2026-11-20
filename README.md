# studio

Free, self-running short-video factory (story pages, paid clipping campaigns, business reels) on one shared Oracle
server plus the owner's laptop for renders.

## Where the truth is (read in this order)
1. `knowledge/STATE.md` on the server (`cat ~/studio/knowledge/STATE.md`): written every 15 min by engine/state.py from
   the live server (memory, jobs, held videos, healer, models, free quotas, owner tasks). The live truth.
2. `.kiro/steering/studio-ops.md`: the operating rules.
3. `knowledge/mehul.md`: the owner's decisions and quality bar.
4. `knowledge/MONEY.md`: the money plan and checklist.
5. `knowledge/AUDIT-2026-11.md`: how every flow works today, the measured losses and what was changed (20 Nov 2026).
6. `knowledge/selfheal.md`, `knowledge/kiro-lessons.md`, `knowledge/lessons-learnt.md`: how the server heals itself
   and the rules learned from mistakes.
7. `knowledge/build-queue.md`: open owner-agent tasks and recent verified work (small, live).

## History (kept for reference, not current)
- `knowledge/STUDIO.md`, `knowledge/RESUME.md`, `RESEARCH.md`: decisions and research from 16-19 Nov.
- `knowledge/archive/`: the old 5,607-line build queue. `archive/`: retired scripts.

## Code
- `engine/`: the pipeline (daily lanes -> make -> review -> publish; clipwatch -> clipper; biz.py for businesses).
  Timers are created by `engine/units.sh`.
- `lib/llm.py`: model calls through OmniRoute (combos rebuilt daily by engine/omnimap.py).
- `dashboard/`: the owner's dashboard (api.py + app.js); `dashboard/audit.py` checks it against the raw files.
- `tools/`: laptop worker, login helpers, Whop browser robot.
