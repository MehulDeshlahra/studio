# Kiro lessons: mistakes made in sessions and the rule that stops each one (read at the start of every session)
Owner 19 Nov: "you are learning from mistakes right? it should decrease and tend to very less... auto think, I will not
be there every time." Add a line here the same day a mistake happens. engine/lessons.py also folds these into
knowledge/lessons-learnt.md for the engine.

## Checking
- NEVER trust a model's memory for a rule or a fact (the checker said RBI's ₹100/day rule "does not exist"). Judge facts
  only against fetched sources; verify the key rule yourself with a web search before a video is built on it.
- NEVER let a model check a number while it sees the answer: it bends the maths to fit (wrote "3*100 + 100*(3 - round(3/3))"
  to reach 500). Hide the number, recompute blind, compare in Python.
- ALWAYS read every new script line by line before the first videos of a new page (found "RBI pays you" and a missing
  condition that the checks passed).
- ALWAYS test a new check on a known-bad and a known-good example before trusting it (both directions).
- ALWAYS look at real frames, not logs, before saying a video works.

## New page / new niche
- ALWAYS run knowledge/new-page.md fully (rivals, trends, format, money, ship) before the first post; set
  schedule.manual_first so the owner sees the first videos.
- ALWAYS check the niche's legal rules first (finance: SEBI; mythology: respect; fiction: no real victims).
- NEVER hard-code the page list: core.pages(). A new page appears everywhere (dashboard brain was CHANNELS[:3]).
- ALWAYS give a new page its own length / word range from what wins in its niche (edit.length_s, edit.words).

## Engine changes
- NEVER let an automatic agent change caches, rate limits, timeouts or back-offs (selfcheck set the Meta cache to 0 and
  locked the whole Meta app for hours). Guarded in selfcheck.py.
- ALWAYS merge shared state files under a lock (done.json: stale copies undid the owner's "removed").
- NEVER block the render lane on a manual job when the laptop is free (the laptop sat idle for hours).
- ALWAYS compile every changed file before shipping (an edit added 4 spaces to line 1 of api.py: caught by compileall).
- When a fix applies only to future builds, say so and rebuild the affected video instead of leaving it.
- NEVER trust the planner's scene types: it wrote 'info'/'image' and empty panels on a lab page ('None' on screen).
  plan.lab_fix() now repairs them; a new look or page needs the same type check.
- NEVER run a long command in the foreground (owner: "never sleep"): systemctl start --no-block / systemd-run --no-block,
  then do other work and check back.

## Talking to the owner
- NEVER report old data: read the live server first (STATE.md + live checks).
- Say what is NOT done, plainly. Don't blame an earlier fix without checking (the 13:00 Meta errors were the cache bug).
