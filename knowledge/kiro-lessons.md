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
- NEVER give a new niche another page's look (finance on the tech look felt "similar to tech, not catchy"). Design the look
  from how the viewer meets the topic in life (money = their phone), build it, render a test, look at the frames.
- When the owner says "I don't know what's odd", find it in the frames yourself: AI text on screens, random logos, a
  picture that doesn't match the line, nothing the viewer recognises as their own life.
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
- ALWAYS look at the pre-render check SHEET (preflight-sheet.jpg), not just its log line: it showed the repair had
  deleted the compare bars and kept a thumbnail with burnt-in text.
- A step that "decides" (visual director, creative director, repair) must decide ONCE per video and keep its choice on
  rebuilds; re-running it undid fixes. Check every new step for this.
- An automatic repair must be re-validated (lab_fix after repair) and must re-fetch what it changed (pictures).
- One blind model answer can be wrong too (read "31st day" as 30+30): two must agree before a fix changes a number.
- Facts I verify must reach the WRITER, not only the checker (a scam script missed every safety step). plan.make now
  puts the queue's verified source at the top of the research.
- A checker can only catch what is wrong, never what is MISSING: for safety/scam reels check by hand that the key
  actions are in the script.
- NEVER rename a queue topic while a build may be using it: the topic text is the key for its verified source and for
  "already made". Change the "source" field, keep the topic.
- NEVER write a script and run it in the same batch of tool calls: the run starts before the file exists (lost ~10 runs
  on 19 Nov). Write first, run in the next call.
- A reviewer that sees stills must be told what the scenes are and that items appear over time, or it holds good videos.
- NEVER run a long command in the foreground (owner: "never sleep"): systemctl start --no-block / systemd-run --no-block,
  then do other work and check back.

## Talking to the owner
- NEVER report old data: read the live server first (STATE.md + live checks).
- Say what is NOT done, plainly. Don't blame an earlier fix without checking (the 13:00 Meta errors were the cache bug).

## 19 Nov
- Judge a run by its final state, not mid-build: I called the LLP finance title "copied" while research was still running.
- A scene type can hold data its drawer never shows (phone "title" with lines/items: the LLP comparison was invisible and
  review passed 8/10). When adding a scene kind or a planner field, check on real frames that every field appears.
  Now: lab_fix turns such titles into "list"; comparisons use the "table" kind.
- Never write a script file and run it in the same parallel batch (did it again with of_live.sh; it only worked by luck).
- No inline python inside `ssh "..."` from PowerShell, ever (broke 3 times on 19 Nov): write .tmp/x.py, scp, run.
- A new tool step gets tested on the real server right away: faster-whisper with a file path fails here (PyAV), pass an
  array like align.py; a full-frame gblur on 1080p crawls on the shared CPU (blur a small copy).
- A vision check on tiny frames gives false fails (270x480: "captions unreadable", 4/10 on a 9/10 clip). Check sheets at
  >= 450x800 and judge text claims (the hook) against the transcript, not pixels.
- The laptop worker imports engine code once: after changing clipcore.py, restart the worker before testing (a run used
  the old code for clips 2-3).
- REPEATED 19 Nov (3rd time): wrote a file and ran it in the same parallel batch. HARD RULE: fs_write is always alone in
  its batch; the run is the NEXT call. Never pipe source files through PowerShell (Get-Content | python): it mangled
  every non-ASCII character in api.py (restored from git). Edit with str_replace or a Python script that opens utf-8.
- 19 Nov: .tmp\ship.ps1 only commits what is STAGED; a first ship said "no changes added" and pushed nothing. Always
  `git add <files>` first, then check the output shows the server HAS the new commit.
- 19 Nov: `systemctl is-active -q` is FALSE for a running oneshot unit ("activating"); a script took a running whopbot
  as finished and edited files under it. Test `systemctl show -p ActiveState --value` for active|activating.
- 19 Nov: switched brief reading to a fast model and it at once said "can do" for a brief that bans automation, and
  wrote an instruction as caption text. Rule: any yes/no that can cost money or an account (bans, required caption
  text) is a hard check in code after the model, tested against every stored real example before shipping.
- 19 Nov: the robot's browser profile (whop-profile) opens in ONE window at a time; a laptop job and the owner's window
  collided ("profile already in use"). whop.py now waits for it. Vyro/ClipConnect logins are SESSION cookies (lost on
  close): whop.py saves all cookies on close and restores them. Before opening a window for the owner, no robot job runs.
- 19 Nov: auto-approved campaign clips went out with word-salad hooks and a misheard name; look at a frame sheet + the
  final post captions (seo.text_for) of the first clips of every new source before the first slot.
- 19 Nov (4th time): ran a ship+run in the SAME batch as the edits it needed; the run used the old units.sh. The rule
  stands: edits first (one batch), compile + ship + run in the NEXT call. Also no inline python inside ssh "..."
  (PowerShell broke it again): write .tmp/x.py, scp, run.
- 19 Nov: a 10/10 review and an 83 % voice match hid a reel the owner called "not top notch" (WhatsApp AI agent): the
  checks only hunted defects. Before calling a video good, look at full-size frames at 6+ moments and read the script as a
  viewer: does it TEACH the title question, do the frames show what the line says, do captions follow the voice. The
  engine now has the same three checks (plan.explainer_gate, review content rules, align.sync_problems).- 19 Nov: told the owner "nothing has posted yet" from done.json alone; Finance Fuel had 2 Stories live and every FB
  page had public profile/cover "updated" posts plus verification Reels. RULE: before saying what is or is not posted,
  read the LIVE accounts (IG media + stories, FB posts/reels/stories via the Graph API: .tmp/live_check.py,
  .tmp/fb_posts.py). Never infer the live state from our own files.

## 19 Nov: the Stories that went live (Finance Fuel "myth", 2 frames)
Plain text on black, no brand or picture, "DM karo" instead of a sticker, the answer frame posted together with the
question (no suspense), and the answer did not answer the question (asked "send unknown money back?", answered "PIN is
never needed to receive"). Rules: a question and its answer are checked against each other; a reveal is never posted
in the same minute as the question; no format ships without a researched design and frames checked by eye. The API
cannot add poll / quiz / link stickers, so automated "quiz" Stories can never be interactive.

## 19 Nov audit (golden rule): a 9-10 vision score meant nothing
Frame-by-frame audit of everything queued: 8 of 30 approved reels were not postable although the final review gave
them 9-10/10: all 6 Navkar Bhav (Mughal onion domes, blue/green-skinned Tirthankara and Bahubali, saffron-robed Jain
monks, a female Hindu-style Dharanendra, a king who changes face, one story needing a source check), Puraan Ki Katha
"Brahma's fifth head" with a one-headed Brahma, Finance Fuel gold/silver (investment advice, unsourced numbers).
Fix: every page has channel.json "visual_checks", a must-answer checklist the reviewer answers per frame; any yes is
serious and caps the score at 5 (tested: the same 3 reels went 9-10 -> 4). Positive iconography text was not enough
for the image model: write the NEVER list too (iconography.JAIN_NEVER). Order matters: a page's first posts are its
strongest, not its oldest (katha: Ujjain/Greenwich first).
- 19 Nov: "whisper on the GPU" (said on 18-19 Nov) was never true in the worker: cublas64_12.dll failed to load (a half-done
  pip uninstall left nvidia/cublas/bin renamed to '~in') and clipcore silently fell back to the small CPU model. RULE: a
  fallback must LOG which path ran; verify a speed/quality claim in the real process (worker), not in a test shell.
- 19 Nov: I picked katha 1118-1015 (Ujjain/Greenwich) as the page's FIRST post from its look, never checked its story:
  it said the whole world kept Ujjain time, mixed two Shiva Purana episodes, and had a trishul where the text says a
  hunkara. Jain 1119-1015 (12 years without food) passed every check too. RULE: on a scripture page, a Reel is judged
  on its events against the text (plan.story_check) before its looks; "strongest first" means strongest AND true.
- 19 Nov: the clip context note said "Ali Wong, Baby Cobra 2016" on a Jo Koy clip: the prompt had no video facts so the
  model guessed. RULE: a model may only state facts it was GIVEN; check names/numbers in code (clipper.ungrounded).
