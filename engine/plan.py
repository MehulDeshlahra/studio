"""Brief + shot plan for one video: the LLM writes a plan from channel rules + lessons + playbook + research,
then a second pass reviews it as a strict editor and returns the fixed plan."""
import json, os, re
from core import ROOT, read, log, dated
import llm, tts, urllib.request, urllib.error, time

GEM_TEXT = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]


def ask(prompt, max_tokens=8000):
    """Planning text: Gemini 3.8-flash on Studio's own keys first; then OmniRoute's studio-text combo (strong free models,
    ordered daily by engine/omnimap.py); flash-lite on our keys only as the last resort (18 Nov: before this, every
    afternoon all planning and repairs ran on flash-lite while the stronger OmniRoute models sat idle)."""
    usable = tts.usable(GEM_TEXT)
    r = _gem([m for m in usable if "lite" not in m], prompt, max_tokens)
    if r is not None:
        return r
    try:
        r = llm.text(prompt, json_mode=True, max_tokens=max_tokens)
        log("plan text by omniroute", llm.last_model)
        return r
    except Exception as e:
        log("plan text omniroute fail", str(e)[:160])
    r = _gem([m for m in usable if "lite" in m], prompt, max_tokens)
    if r is not None:
        return r
    raise RuntimeError("no model answered the planning request")


def _gem(models, prompt, max_tokens):
    slow_now = set()
    for m in [x for mm in models for x in (mm, mm)]:        # each model twice: malformed JSON is usually one-off
        if m in slow_now:                                    # ...but not a second 300 s wait on a model that just hung
            continue
        try:
            body = {"contents": [{"parts": [{"text": dated(prompt) + "\n\nReturn ONLY valid JSON."}]}],   # 19 Nov: today's date
                    "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens, "temperature": 0.7}}
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                       data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(m)})
            # 20 Nov audit: 6 calls hung the full 300 s on 19-20 Nov; good answers come in < 90 s
            d = json.load(urllib.request.urlopen(r, timeout=120))
            out = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
            log("plan text by", m)
            return llm.parse_json(out)
        except Exception as e:
            log("gemini text fail", m, str(e)[:120])
            if "timed out" in str(e).lower() or "503" in str(e):     # 18 Nov: a hanging model cost 2 x 300 s per plan
                tts.mark_slow(m)
                slow_now.add(m)
    return None

EXAMPLE = """Example of the voice we want (a past reel of ours, owner liked the voice and pacing):
"Phone ulta kiya... aur screen khud ghoom gayi. Par phone ko pata kaise chala? Jaadu nahi hai. Aapke phone ke andar
ek chhota sa chip hai. Naam hai... accelerometer. Is chip ke andar ek bahut hi chhota sa wazan hai, jo patli patli
springs pe latka hota hai. Jaise hi aap phone terha karte ho, gravity us wazan ko neeche kheenchti hai, aur woh
thoda sa khisak jaata hai." -> short spoken sentences, everyday words, one image per sentence, curiosity first."""

SCHEMA = """{
 "slug": "short-ascii-id",
 "title": "the curiosity question as the viewer would ask it",
 "hooks": ["hook option 1", "hook option 2", "hook option 3"], "hook_choice": 0, "hook_why": "why this one",
 "metaphor": "the ONE visual idea that explains the topic",
 "mechanism": ["for HOW/WHY topics: the 3-6 real steps of how it works, in order, from the research sources (e.g. 'message hits Meta's servers', 'webhook sends it to the business server', 'LLM reads it with the chat history', 'LLM picks a tool: calendar', 'server runs the tool', 'reply goes back'); empty for stories"],
 "cast": {"<name>": "fixed visual description reused verbatim in every prompt that shows this character"},
 "scenes": [
  {"vo": "spoken line (Roman script)", "type": "image|clip|flow|card",
   "prompt": "image prompt (image, clip, card background); for clip also what moves",
   "motion": "push|pull|pan|punch|tilt", "title": "0-4 word on-screen headline or empty",
   "nodes": ["only for flow: 2-5 short labels in order"], "big": "only for card: 1-3 words / symbol", "small": "card: <=5 words",
   "keywords": ["1-3 words from vo to highlight"],
   "real": "OPTIONAL, see REAL PICTURES: {\\"q\\": \\"search query\\", \\"kind\\": \\"logo|photo\\", \\"subject\\": \\"what it must show\\"}"}
 ],
 "music_mood": "ONE of: suspense, mystery, epic, emotional, calm, uplifting, playful, driving, dark (the feeling of the whole video)",
 "caption": "Instagram caption: 1 hook line + 1-2 lines + a question", "hashtags": ["#..."],
 "claims": [{"claim": "each factual statement", "basis": "why it is true / source"}]
}"""


PHONE = """

THIS PAGE TELLS EVERY REEL ON THE VIEWER'S OWN PHONE (owner 19 Nov: AI pictures and random logos lost relatability).
The story happens to one person (one of: Mehul, Raghav, Aditya, Shobhit, Shwetal, Saumya, Suhail, Jahnvi, Masood, Animesh,
Jayesh, Aaryan, Dhruv, Mudit, Shruti; a scammer gets a made-up name) and the viewer sees exactly what that person sees.
IGNORE the visual types above and use ONLY these scene types; never two of the same type in a row; 8-11 scenes:
  {"type":"wa","title":"<friend name>","messages":[{"from":"<friend name>","text":"<short chat line, emoji ok>"},{"from":"me","text":"..."}]}
      a WhatsApp chat (2-4 lines). The HOOK scene is usually this: the friend's problem in their own words.
  {"type":"sms","time":"10:42","messages":[{"app":"Messages","from":"VM-HDFCBK","text":"<a realistic bank SMS>"},{"app":"<app>","from":"<app>","text":"..."}]}
      lock-screen alerts (1-3): bank debit SMS, app alert, scam message. Realistic wording, exact amounts, masked account (XX4821).
  {"type":"pay","status":"failed|pending|success","value":"₹500","to":"<name>","sub":"<one short line, optional>"}
      a payment app's status screen.
  {"type":"bill","title":"<2-4 words>","sub":"<short>","rows":[{"label":"...","value":"₹..."}],"total":{"label":"...","value":"₹..."},"tone":"bad|good"}
      a receipt that does the maths line by line (2-5 rows). Every number exact; the total is the sum or result of the rows.
  {"type":"rule","title":"<who made the rule, e.g. RBI circular>","sub":"<number and date>","lines":["<rule in 4-8 words>", "..."],"stamp":"ASLI NIYAM"}
      the official rule card (2-3 lines). The ONLY place a real logo appears: add "real":{"q":"<regulator> logo","kind":"logo"}.
  {"type":"stat","value":"₹100","sub":"<what it is, 2-5 words>"}   one huge number (use once or twice)
  {"type":"compare","items":[{"label":"...","value":"...","pct":0-100},{"label":"...","value":"...","pct":0-100}]}
  {"type":"table","title":"<2-5 words>","cols":["","<option A>","<option B>","<option C>"],"rows":[{"label":"<what is compared, 1-3 words>","cells":["<A, 1-4 words>","<B>","<C>"]}],"best":<column number that wins, optional>}
      a comparison table (2-4 options, 3-6 rows). ANY comparison of 2+ options uses this, never a title.
  {"type":"list","title":"<2-5 words>","lines":["<point, under 8 words>", "..."]}   a checklist / steps card (2-5 lines)
  {"type":"title","big":"<2-4 words>","sub":"<short line>"}   for the one action to take and the ending (a title shows ONLY
      big + sub: never put lines, items or a comparison in it)
Flow of a reel: hook (wa or sms: the problem as it happens) -> what it means (pay / sms / stat) -> the real rule (rule card)
-> the maths (bill or stat) -> what to do (title or wa reply) -> "Save kijiye" + a question (title).
No "object", "image", "ui", "chart" or "clip" scenes: everything on the phone, receipt and card is drawn exactly.
The on-screen texts (chat lines, SMS, receipt rows) are part of the story, not a copy of the voice: the voice explains
what the viewer is looking at.
"""

# 19 Nov (owner on the first 3 phone reels: "good now, but can be better... images/videos in background like v2, v3 of
# tech"). Added only when channel.json theme.phone_bg is on; plans made before have no "phone_bg" and stay as they are.
PHONE_BG = """
THE WORLD BEHIND THE PHONE: every scene also gets "bg_prompt": one photoreal, candid shot of the real moment around the
person, in India, that the line is about (e.g. "a young man at a busy Indian railway ticket counter at night, worried",
"hands counting rupee notes on a wooden shop counter in a small kirana store", "a crowded bank branch hall in India, people
waiting with token slips"). It is atmosphere around the phone, so: no phone or laptop screens facing the camera, no
documents, no text, no numbers, no currency symbols, no logos. Never two similar pictures in a row; together they tell the
story like a documentary. A rule scene may instead carry "bg_real": {"q": "<real building, e.g. Reserve Bank of India
headquarters Mumbai>", "kind": "photo", "subject": "the real building"} (real places only, never a person).
"""


THIS_LAB_MARK = None
LAB = """

THIS CHANNEL USES THE 'LAB' LOOK (channels/tech/style-lab.md), for Gen Z: premium, dark, minimal, our own
look (study good explainers but never copy one creator). IGNORE the visual types above and use ONLY these scene types (vary them, never 3 of a kind in a row):
  {"type":"object","prompt":"<one real object, e.g. 'a modern smartphone lying face up showing a payment confirmation glow'>","label":"<2-3 word tag>"}
  {"type":"stat","value":"<a number with unit, e.g. '2 sec' or '₹1,76,121' or '14 billion'>","sub":"<what it measures, 2-5 words>","label":"..."}
  {"type":"ui","title":"<panel title>","rows":[{"label":"...","value":"...","pct":0-100}],"label":"..."}   (2-4 rows)
  {"type":"chart","title":"...","points":[numbers...],"end_label":"<e.g. +38%>","label":"..."}
  {"type":"flow","nodes":["step 1","step 2","step 3","step 4"],"label":"..."}   (how something moves / happens, 3-5 nodes, <=14 letters each)
  {"type":"compare","items":[{"label":"...","value":"...","pct":0-100},{"label":"...","value":"...","pct":0-100}],"label":"..."}
  {"type":"title","big":"<1-3 words>","sub":"<optional short line>"}
  {"type":"clip","prompt":"<one cinematic real-world shot>","label":"..."}   (max 1 per video, for the hook)
  {"type":"chat","title":"<app name, e.g. 'ChatGPT'>","messages":[{"role":"user","text":"<short question>"},{"role":"ai","text":"<short answer, <= 14 words>"}],"label":"..."}   (for AI topics: shows a real-looking chat; the answer streams word by word)
  {"type":"code","title":"<e.g. 'terminal'>","lines":["<short command or code line>", "..."],"highlight":<index of the key line>,"label":"..."}   (2-5 lines, <= 26 characters each)
Rules: at most 4 'object' scenes (they cost image credits); every number must be true and common knowledge, or
leave numbers out (no made-up stats); labels are UPPERCASE-able tags like "NPCI SWITCH", "STEP 2", "INDIA · 2024";
no cartoons, no characters with eyes; the object prompts describe real hardware/things only.
REAL PICTURES apply here too: an 'object' scene whose line names a real brand/app/company/product/person may carry
"real": {"q": "UPI logo", "kind": "logo" or "photo", "subject": "what it must show"} (2-5 per video). When a line names 1-2 brands/apps (e.g. "Google Pay ya PhonePe"), use an 'object' scene with "real" for it, not a clip. Real logos/photos replace the
AI render; keep the object "prompt" as the fallback. Real faces of public figures are fine in a 'photo'.
EVERY SCENE HAS A PICTURE (18 Nov v2): behind each stat, ui, flow, compare, chart and title scene the video shows a full-frame
picture of what the line is about. Give each scene "bg_prompt": one photoreal shot of that exact thing (real hardware, a real
place, a person's hands using a phone, a server room...), or "real" when the line names a real brand/app/product/place
(for an app: "real": {"q": "<App> app screenshot", "kind": "photo", "subject": "the real <App> app screen"}).
Make the sequence of pictures tell the story on its own, like a documentary: never two similar pictures in a row.
REAL BRANDS ARE REQUIRED (owner): a reel about ChatGPT shows the real ChatGPT logo, a reel about UPI shows the UPI and app logos,
a reel about a phone shows the real phone. Every brand the script is about gets at least one real logo or real product photo;
a 'chat' scene's "title" is the real app name (ChatGPT, Gemini, Claude...). Big tech news: real photos of the CEO/founder are good.
SCENE 1 IS NEVER A LOGO (19 Nov: the WhatsApp agent reel opened on a white logo card; the top reels show the moment
first): the hook frame shows the situation the viewer knows (a hand holding a phone as a WhatsApp message arrives at 2 am,
a shop owner swamped with chats); the logo comes as a 1.5-3 s punctuation when the brand is first explained.
HOW-IT-WORKS SCENES: use a 'flow' (3-5 nodes) for the path the message/data takes, a 'chat' for what the user sees, a 'code'
or 'ui' only when its lines/rows say something real (never a placeholder like "sync cal"); every 'ui' row and chat bubble has
real readable words.
"""


def _strip_brand(text, cid):
    """Drop '## Page brand' sections and any line naming another page's handle / signature."""
    out, skip = [], False
    try:
        c = json.load(open(os.path.join(ROOT, "channels", cid, "channel.json"), encoding="utf-8"))
    except Exception:
        c = {}
    marks = [m.lower() for m in (c.get("handle"), c.get("handle_instagram"), (c.get("handle") or "").lstrip("@"),
                                (c.get("theme") or {}).get("signature"), (c.get("theme") or {}).get("end_line"), c.get("name")) if m]
    for line in text.splitlines():
        if line.startswith("## "):
            skip = "brand" in line.lower()
        if skip or any(m in line.lower() for m in marks):
            continue
        out.append(line)
    return "\n".join(out)


def all_lessons(own):
    """Lessons from EVERY page (owner rule 16 Nov: learning from one page applies to all).
    This page's own lessons first, then the others, each labelled with its page."""
    base = os.path.join(ROOT, "channels")
    ids = [own] + sorted(c for c in os.listdir(base) if c != own and os.path.isdir(os.path.join(base, c)))
    out = ["LESSONS FROM ALL OUR PAGES (apply every general lesson here too; format-specific ones only if they fit):"]
    for cid in ids:
        a = read(os.path.join(base, cid, "lessons.md"), 4000).strip()
        if cid != own:                       # 17 Nov: a page's BRAND rules (handle, end line, signature) never travel to other pages
            a = _strip_brand(a, cid)
        b = read(os.path.join(base, cid, "lessons-auto.md"), 2000).strip()
        if a or b:
            out.append(f"--- page '{cid}'{' (this page)' if cid == own else ''} ---")
            if a:
                out.append(a)
            if b:
                out.append("Problems the quality gate found:\n" + b)
    return "\n".join(out)


def _rules(ch):
    return "\n".join("- " + r for r in ch.get("rules", []))


def make(ch, topic, research_text):
    # 19 Nov: per page (channel.json edit.words); finance reels win at 30-48 s, the other pages keep 95-150
    W0, W1 = [int(x) for x in ((ch.get("edit") or {}).get("words") or [95, 150])]
    # 19 Nov: the verified facts in channels/<id>/queue.json went only to the checker; the writer missed the core safety
    # facts of a scam reel (finance 1119-0028). The writer now builds the script on them.
    vf = [x for x in _fact_sources(ch, topic, "").splitlines() if x.startswith("VERIFIED")]
    if vf:
        research_text = ("VERIFIED FACTS FOR THIS VIDEO (checked by hand against official sources; build the script on these, "
                         "include every safety step they name, and claim no rule beyond them):\n" + "\n".join(vf) + "\n\n" + str(research_text))
    lessons = read(os.path.join(ROOT, "knowledge", "lessons.md"))
    # 19 Nov: the rule book distilled from every page's mistakes (engine/lessons.py); a new page starts with all of it
    learnt = read(os.path.join(ROOT, "knowledge", "lessons-learnt.md"), 7000)
    lessons = (learnt + "\n" + lessons).strip()
    ch_lessons = all_lessons(ch["id"])
    bible = read(os.path.join(ROOT, "channels", ch["id"], "bible.md"))
    owner = read(os.path.join(ROOT, "knowledge", "mehul.md"), 4000)   # how the owner thinks (engine/mehul.py)
    hooks = read(os.path.join(ROOT, "channels", ch["id"], "hooks.md"), 3500)   # engine/hookstudy.py (weekly)
    try:
        import series
        part2 = series.context(topic, ch["id"]) if str(topic).lower().startswith("part 2") else ""
        if ch.get("serial"):
            import serials
            part2 = serials.context(ch, topic) or part2
    except Exception:
        part2 = ""
    playbook = read(os.path.join(ROOT, "knowledge", "playbook.md"), 6000)
    results = (read(os.path.join(ROOT, "channels", ch["id"], "results.md"), 2500) + "\n" +
               read(os.path.join(ROOT, "knowledge", "results.md"), 2500)).strip()
    try:
        import brain
        bblock, bids = brain.prompt_block(f"{topic}. {ch.get('format', '')} {ch.get('name', '')}", 14)
    except Exception as e:
        bblock, bids = "", []; log("brain lookup failed", str(e)[:120])
    p = f"""You plan one vertical short video (Instagram Reel / YouTube Short) for the channel below. Topic: "{topic}".
{bblock}

CHANNEL: {json.dumps({k: ch[k] for k in ("id", "language", "format", "visuals", "edit") if k in ch}, ensure_ascii=False)}
CHANNEL RULES:
{_rules(ch)}
- This page is "{ch.get('name', ch['id'])}"{(' (' + ch['handle'] + ')') if ch.get('handle') else ''}. Never name, tag or mention any other page or handle.
CHANNEL BIBLE:
{bible}

{part2}
{("FIRST 2 SECONDS (what the most-viewed faceless Shorts in this niche do; scene 1 and the opening visual follow these rules; they never change this page voice style, language or the rest of the script; small sample, so use them as strong hints):" + chr(10) + hooks) if hooks else ""}
OWNER TASTE (Mehul; what he likes and dislikes, obey):
{owner}
LESSONS (hard rules learned from earlier videos and the owner; obey all):
{lessons}
{ch_lessons}

WHAT WINS ON SHORTS RIGHT NOW (scout playbook, excerpt):
{playbook}

OUR OWN RESULTS (posted videos, best first; repeat what made the top ones work, avoid what the bottom ones did):
{results or "no posts yet"}

RESEARCH ON THIS TOPIC (the best existing Shorts; beat them, do not copy them):
{research_text}

REQUIREMENTS
- 10-15 scenes; each scene = ONE spoken line of 4-16 words; total {W0}-{W1} words (about {round(W0 / 2.4)}-{round(W1 / 2.6)} s).
- Scene 1: the hook. The question or a surprising result in the first line, with the strongest visual. No intro, no greeting.
  2026 data: Shorts reach is decided by swipe-away in the first 1-2 s, so the first 4-6 spoken words already carry the
  surprise (not a setup), and the first frame already shows the subject big; never a slow build or a logo first.
- One new piece of information per scene. The same visual idea never repeats. Max 8 s per idea.
- Explain the mechanism simply with the ONE metaphor, in order, so a 14-year-old understands.
- The last scene: a short payoff + a question the viewer answers in comments.
- HOW/WHY topics (19 Nov, owner: the WhatsApp AI agent reel listed features like an advert and never showed how it works):
  fill "mechanism" first from the RESEARCH sources, then the middle of the script walks those steps IN ORDER, one scene per
  step, each with a visual that shows that exact step (the message travelling, the step lighting up in a flow, the tool
  being called). The viewer must be able to retell the steps afterwards. Feature lists, benefits and hype ("24 ghante ka
  team", "business khush") are at most ONE line, after the mechanism.
- Never speak "Follow @handle" or "follow for more": the end card shows the handle. No numbers or counts unless the
  research sources state them (if a source says 3 billion, never write 2 billion from memory).
{EXAMPLE}
- On-screen titles are for the VIEWER (e.g. "BALANCE CHECK", "2 SECOND MEIN"), never production labels
  like "ask audience", "hook", "outro". Leave most titles empty; use 3-5 titles per video.
- A flow diagram shows the WHOLE path once (3-5 nodes); do not split one path into several 2-node flows.
{EXAMPLE}
- On-screen titles are for the VIEWER (e.g. "BALANCE CHECK", "2 SECOND MEIN"), never production labels
  like "ask audience", "hook", "outro". Leave most titles empty; use 3-5 titles per video.
- A flow diagram shows the WHOLE path once (3-5 nodes); do not split one path into several 2-node flows.
- Language: {ch.get('language')}. Write vo in Roman script only (no Devanagari). Natural spoken Hinglish, short words.
  Use "..." at most twice (it makes the voice pause). Never use dashes (— or -) or slashes between words.
- Visual types: "image" (a still, animated with camera motion), "clip" (a 10 s generated video: use at most 2, for the
  hook or the key moment), "flow" (animated step diagram, for how data/money/signal moves; 2-5 nodes), "card"
  (one big word/number over an image, for the payoff).
- Prompts: describe one clear, simple 9:16 composition, subject centred, room above and below for text;
  include the channel look: {ch.get('visuals', {}).get('look', '')}. Recurring characters: paste their cast description verbatim.
  Never ask for readable text, logos or brand names inside images.
- REAL PICTURES: when the spoken line names a real, well-known thing (a brand or app logo, a product, a company, a place, a
  monument, a public figure, a real event), add "real" to that scene so the video shows the actual picture instead of an AI
  drawing: {{"q": "short web image search query", "kind": "logo" or "photo", "subject": "what the picture must show"}}.
  Use it on 2-5 scenes per video (STORY pages = mythology and case-file/mystery pages: at most 2, only for a real PLACE, temple or landmark, never for gods, heroes, victims, suspects
  or story scenes: those stay in our illustrated style; a real photo among illustrations looks wrong); only where the line is really about that thing; keep the normal "prompt" as the fallback.
  Works on image, card and object scenes (not clip or flow). "kind" may also be "clip" (a real 6 s video of a real PLACE or
  event, e.g. {{"q": "Varanasi ghat aarti", "kind": "clip"}}: use at most 1 per video, only if the line is about that place).
  For an app/product scene you may add "logo": "Google Pay logo" inside "real" (kind photo): the logo pops in first, then the photo. Query like a person would: "UPI logo", "Taj Mahal front view".
- No numbers, specs, prices or dates unless they are common, stable knowledge; list every factual statement in "claims".
- Never mention AI and never add an AI label.
Return JSON with exactly this shape:
{SCHEMA}"""
    if ch.get("theme", {}).get("style") == "lab":
        p += PHONE if ch.get("theme", {}).get("phone") else LAB      # 19 Nov: finance tells reels on the viewer's phone
        if ch.get("theme", {}).get("phone") and ch.get("theme", {}).get("phone_bg"):
            p += PHONE_BG
    plan = ask(p)
    for _ in range(2):
        words = sum(len(s.get("vo", "").split()) for s in plan.get("scenes", []))
        if W0 <= words <= W1 + 10:
            break
        log("plan has", words, "words -> asking for a fix")
        plan = ask(f"This plan has {words} spoken words; it needs {W0 + 5}-{W1 - 5}. Rewrite it to fit: add the missing "
                   f"steps of the mechanism (or cut repetition), keep the same JSON shape.\n{EXAMPLE}\n"
                   f"PLAN:\n{json.dumps(plan, ensure_ascii=False)}")
    log("plan v1", len(plan.get("scenes", [])), "scenes")
    review = f"""You are a strict senior editor of viral Indian Shorts. Review this plan against the requirements and lessons,
then return the IMPROVED plan (same JSON shape). Fix: weak hook, repeated visuals, lines over 16 words, scenes that add
no new information, unclear mechanism, prompts that would make cluttered or text-filled images, risky or unverifiable
claims (remove them), a weak ending question, stiff or bookish Hindi (make it sound like a friend talking),
production-label titles. Make the mechanism complete (no missing step). Keep 10-15 scenes and {W0}-{W1} words total.
LESSONS:
{lessons}
PLAN:
{json.dumps(plan, ensure_ascii=False)}"""
    try:
        better = ask(review)
        bw = sum(len(s.get("vo", "").split()) for s in better.get("scenes", []))
        if len(better.get("scenes", [])) >= 6 and W0 - 5 <= bw <= W1 + 15:
            plan = better
            log("plan v2 (reviewed)", len(plan["scenes"]), "scenes")
    except Exception as e:
        log("plan review failed, keeping v1:", str(e)[:120])
    try:                                           # 19 Nov: before the numbers check, so a rewritten number is checked too
        plan = fresh_fix(plan, research_text)
    except Exception as e:
        log("freshness check skipped:", str(e)[:120])
    try:
        plan = explainer_gate(ch, topic, plan, research_text, W0, W1)
    except Exception as e:
        log("explainer gate skipped:", str(e)[:120])
    if ch.get("numbers_check"):                    # 18 Nov (finance 1118-2228 said Rs 50k -> Rs 1,02,000 with Rs 5k/month paid)
        for rnd in range(3):                       # 19 Nov: 2 fix rounds (one was not enough for unsourced claims)
            probs = numbers_check(plan, _fact_sources(ch, topic, research_text), strict=bool(ch.get("facts_strict")))
            if not probs:
                log("numbers check: all calculations and rules correct" + (" after a fix" if rnd else ""))
                plan.pop("numbers_hold", None)
                break
            log("numbers check found", len(probs), "problem(s):", " | ".join(probs)[:300])
            try:                                   # 19 Nov: recorded even when the fix round repairs it (engine/lessons.py)
                from core import note_problem
                note_problem(ch["id"], str(topic)[:60], ["NUMBERS: " + x for x in probs], "numbers check")
            except Exception:
                pass
            plan["numbers_hold"] = probs
            if rnd < 2:
                try:
                    fixed = ask("Fix ONLY these factual / arithmetic errors in this Shorts plan; keep everything else the same "
                                "(same JSON shape). Change the numbers (or the scenario) so every number is exactly right, and "
                                "attribute every rule to whoever really sets it. A claim that has no official source (RBI, SEBI, "
                                "NPCI, a ministry, the I4C cyber-crime centre, a court) is REMOVED, or said without the number "
                                "('lakhs of people', 'crores of rupees'). Keep the story working after the removal."
                                "\nERRORS:\n- " + "\n- ".join(probs)
                                + "\nPLAN:\n" + json.dumps(plan, ensure_ascii=False))
                    if len(fixed.get("scenes", [])) >= 6:
                        plan = fixed
                except Exception as e:
                    log("numbers fix failed:", str(e)[:120]); break
    if ch.get("story_check"):                      # 19 Nov: jain 1119-1015 said '12 years without food, then kheer, then kevalgyan'
        try:
            plan = story_fix(ch, topic, plan, research_text)
        except Exception as e:
            log("story check skipped:", str(e)[:120])
    if ch.get("theme", {}).get("style") == "lab":
        plan = lab_fix(plan, bool(ch.get("theme", {}).get("phone")))
    out = clean(plan)
    if isinstance(out, dict) and ch.get("theme", {}).get("phone") and ch.get("theme", {}).get("phone_bg"):
        out["phone_bg"] = True                     # only plans made from now get pictures behind the phone
    if isinstance(out, dict):
        out["brain_ids"] = bids                    # which brain items this video used (scored after its review)
    return out


FRESH = """You check that a Reels script is up to date before it is published. Compare it with the dated SOURCES (the
LATEST NEWS block is newest first and is what is true now).
SOURCES:
{src}
SCRIPT (JSON):
{plan}
List every place where the script is out of date: it calls something upcoming / unreleased / rumoured that the sources
show already launched or happened; it gives an old price, rate, rule, date or holder of a post when the sources give a
newer one; or it uses a past year as if it were this year ({year}). A past year as the date of a past event is fine.
Return JSON {{"stale": ["<scene n: what is wrong -> what the sources say now>"]}} (empty list when all is current)."""


def fresh_fix(plan, src):
    """19 Nov (owner: "GTA 6 kab aayega" when GTA 6 is out; "2025" for gold on 19 Nov 2026): one check against the dated
    sources, then one rewrite of the stale lines. Runs on every plan."""
    if not src or not plan.get("scenes"):
        return plan
    year = time.localtime().tm_year
    v = ask(FRESH.format(src=src[:9000], plan=json.dumps({"title": plan.get("title"), "scenes": plan["scenes"]}, ensure_ascii=False)[:9000],
                         year=year), max_tokens=1500)
    stale = [str(x) for x in (v.get("stale") or []) if str(x).strip()][:8]
    if not stale:
        log("freshness check: current"); return plan
    log("freshness check found", len(stale), "stale line(s):", " | ".join(stale)[:300])
    fixed = ask("Rewrite this Reels plan so it is current. Fix ONLY these out-of-date points, using the sources; keep the same "
                "JSON shape, scene count and length:\n- " + "\n- ".join(stale) + "\n\nSOURCES:\n" + src[:7000]
                + "\n\nPLAN:\n" + json.dumps(plan, ensure_ascii=False))
    if isinstance(fixed, dict) and fixed.get("scenes"):
        keep = {k: plan[k] for k in ("brain_ids", "phone_bg", "numbers_hold") if k in plan}
        fixed.update(keep)
        fixed["fresh_fixed"] = stale
        return fixed
    return plan


NUMCHK = """You check the NUMBERS in this Hindi/Hinglish money-explainer script before it is published. Be exact.
1) For EVERY number in the voice-over or on screen that can be worked out from other numbers in the script (interest,
a balance after N months, totals, EMI, a percent of an amount, growth, and simple ones like "3 din late = ₹300" or
"roz ₹50 = saal mein ₹18,250"), write ONE Python arithmetic expression that computes it from the script's own numbers
exactly as the script states them. When in doubt, include it: a correct number costs nothing. Use only numbers, + - * / ** ( ) and round/min/max/abs (no names).
Example: balance after 12 months, Rs 45,000 at 42%/yr compounded monthly with Rs 5,000 paid each month:
"45000*(1+0.42/12)**12 - 5000*((1+0.42/12)**12-1)/(0.42/12)".
2) For every RULE or market fact (a rate, a limit, 'RBI says', a tax slab), judge it ONLY against the SOURCES below
(articles and official circulars found for this video). Your own memory of Indian rules is often out of date: never
mark a fact wrong from memory. "correct": true when the sources support it; false ONLY when a source clearly
contradicts it (quote that source in "why"); null when the sources say nothing about it.
A line starting "VERIFIED" was checked by hand against the official source: when an article disagrees with it, the
VERIFIED line is right and the article is wrong (never mark a fact false because of such an article).
Check WHO does what as well: a regulator (RBI, SEBI, NPCI) SETS a rule; the bank, card issuer or company PAYS or acts.
"RBI aapko ₹100 dega" is false when the sources say the bank pays.
SOURCES:
{sources}
SCRIPT (scene | voice-over | on-screen number):
{rows}
Return JSON {{"calc": [{{"scene": n, "says": <the number the script states, as a plain number>, "expr": "..."}}],
"facts": [{{"scene": n, "fact": "...", "correct": true/false/null, "why": "short, quote the source"}}]}}"""


def _safe_eval(expr):
    """Arithmetic only: numbers, + - * / ** %, round/min/max/abs, and sum(... for k in range(n)) with n <= 1000 (a
    month-by-month balance). Names other than those functions and the loop variables are refused; no attributes."""
    import ast as _ast
    tree = _ast.parse(str(expr), mode="eval")
    funcs = ("round", "min", "max", "abs", "sum", "range")
    loopvars = {t.id for n in _ast.walk(tree) if isinstance(n, _ast.comprehension) for t in _ast.walk(n.target)
                if isinstance(t, _ast.Name)}
    ok = (_ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Constant, _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.Pow,
          _ast.USub, _ast.UAdd, _ast.Mod, _ast.FloorDiv, _ast.Call, _ast.Name, _ast.Load, _ast.Store,
          _ast.GeneratorExp, _ast.ListComp, _ast.comprehension)
    for n in _ast.walk(tree):
        if not isinstance(n, ok):
            raise ValueError("not allowed: " + type(n).__name__)
        if isinstance(n, _ast.Name) and n.id not in funcs and n.id not in loopvars:
            raise ValueError("not allowed name: " + n.id)
        if isinstance(n, _ast.Call) and not (isinstance(n.func, _ast.Name) and n.func.id in funcs):
            raise ValueError("only round/min/max/abs/sum/range calls")
        if isinstance(n, _ast.Constant) and not isinstance(n.value, (int, float)):
            raise ValueError("not a number")
        if isinstance(n, _ast.Constant) and isinstance(n.value, (int, float)) and abs(n.value) > 1e12:
            raise ValueError("number too big")

    # 18 Nov: evaluated by this small interpreter, not eval(): '9**9**9**9' hung eval for ever. Every power is capped.
    import operator as _op
    BIN = {_ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul, _ast.Div: _op.truediv, _ast.Mod: _op.mod,
           _ast.FloorDiv: _op.floordiv}

    def ev(n, env):
        if isinstance(n, _ast.Expression):
            return ev(n.body, env)
        if isinstance(n, _ast.Constant):
            return float(n.value)
        if isinstance(n, _ast.Name):
            if n.id in env:
                return env[n.id]
            raise ValueError("unknown name " + n.id)
        if isinstance(n, _ast.UnaryOp):
            v = ev(n.operand, env)
            return -v if isinstance(n.op, _ast.USub) else v
        if isinstance(n, _ast.BinOp):
            a, b = ev(n.left, env), ev(n.right, env)
            if isinstance(n.op, _ast.Pow):
                if abs(b) > 10000 or abs(a) > 1e9:
                    raise ValueError("power too big")
                r = float(a) ** float(b)
            else:
                r = BIN[type(n.op)](a, b)
            if isinstance(r, complex) or abs(r) > 1e15:
                raise ValueError("result out of range")
            return r
        if isinstance(n, _ast.Call):
            f = n.func.id
            if f == "sum" and len(n.args) == 1 and isinstance(n.args[0], (_ast.GeneratorExp, _ast.ListComp)):
                g = n.args[0]
                if len(g.generators) != 1 or g.generators[0].ifs or not isinstance(g.generators[0].target, _ast.Name):
                    raise ValueError("one simple loop only")
                it = g.generators[0].iter
                if not (isinstance(it, _ast.Call) and isinstance(it.func, _ast.Name) and it.func.id == "range"):
                    raise ValueError("loops only over range()")
                bounds = [int(ev(x, env)) for x in it.args]
                rg = range(*bounds)
                if len(rg) > 1000:
                    raise ValueError("range too long")
                var = g.generators[0].target.id
                return sum(ev(g.elt, dict(env, **{var: float(k)})) for k in rg)
            args = [ev(x, env) for x in n.args]
            if f in ("round", "min", "max", "abs"):
                return {"round": lambda *x: round(x[0], int(x[1]) if len(x) > 1 else None),
                        "min": min, "max": max, "abs": abs}[f](*args)
            raise ValueError("call not allowed: " + f)
        raise ValueError("not allowed: " + type(n).__name__)
    return ev(tree, {})



def _fact_sources(ch, topic, research_text):
    """19 Nov: what the numbers check may judge facts against: the verified source written for this topic in
    channels/<id>/queue.json (checked by hand in the deep dive) + this video's research (web articles)."""
    out = []
    try:
        q = json.load(open(os.path.join(ROOT, "channels", ch["id"], "queue.json"), encoding="utf-8"))
        it = next((x for x in q if isinstance(x, dict) and str(x.get("topic", "")).strip().lower() == str(topic).strip().lower()), None)
        if it and it.get("source"):
            out.append("VERIFIED (checked against the official circular and 2+ news sources): " + it["source"])
    except Exception:
        pass
    if research_text:
        out.append(str(research_text))
    return "\n".join(out)


def _mask(text, value):
    """Hide every way the script writes this number (5000, 5,000, ₹5,000, 5 hazaar for round thousands) as X."""
    v = int(value) if float(value).is_integer() else value
    forms = {str(v)}
    if isinstance(v, int):
        forms.add(f"{v:,}")
        s = str(v)
        if len(s) > 3:                                  # Indian grouping 1,02,000
            head, tail = s[:-3], s[-3:]
            head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
            forms.add(head + "," + tail)
        if v % 1000 == 0 and v < 100000:
            forms.add(f"{v // 1000} hazaar"); forms.add(f"{v // 1000} hazar")
        if v % 100000 == 0:
            forms.add(f"{v // 100000} lakh")
    out, n = text, 0
    for fm in sorted(forms, key=len, reverse=True):
        out, k = re.subn(rf"(?<![\d,.])(?:₹\s?)?{re.escape(fm)}(?![\d,])", "X", out, flags=re.I)
        n += k
    return out, n

def numbers_check(plan, sources="", strict=False):
    """Problems with the plan's numbers ([] = fine). Arithmetic is computed by Python, not judged by the model."""
    def _screen(s):                                   # 19 Nov: phone scenes carry numbers on screen (receipt rows, SMS)
        out = [str(s.get("value") or s.get("big") or s.get("end_label") or "")]
        out += [f'{r.get("label")} {r.get("value")}' for r in (s.get("rows") or []) if isinstance(r, dict)]
        if isinstance(s.get("total"), dict):
            out.append(f'{s["total"].get("label")} = {s["total"].get("value")}')
        out += [str(m.get("text")) for m in (s.get("messages") or []) if isinstance(m, dict)]
        out += [str(x) for x in (s.get("lines") or [])]
        return " ; ".join(x for x in out if x and x != "None")
    rows = "\n".join(f"{i + 1} | {s.get('vo', '')} | {_screen(s)}" for i, s in enumerate(plan.get("scenes", [])))
    try:
        r = ask(NUMCHK.format(rows=rows, sources=(sources or "(none found: mark facts null, never false)")[:9000]), max_tokens=2500) or {}
    except Exception as e:
        log("numbers check failed to run:", str(e)[:120]); return []
    probs = []
    # 19 Nov: shown its answer, the model bends the maths to fit it ('3 x 100 = 500' became "500", then
    # "3*100 + 100*(3 - round(3/3))"). So the first answer only says WHICH numbers are results; each one is then worked
    # out BLIND: hidden as X in the script, a fresh call writes the formula from the words, Python computes it.
    for c in (r.get("calc") or [])[:8]:
        try:
            says = float(str(c.get("says")).replace(",", ""))
        except Exception:
            continue
        if not says:
            continue
        masked, hits = _mask(rows, says)
        if not hits:
            continue
        try:
            b2 = ask("In this short money-explainer script one number is hidden as X. Work X out from the OTHER numbers and "
                     "the words exactly as the script describes the situation (what is paid, for how long, at what rate). "
                     "Write ONE Python arithmetic expression for X using only numbers and + - * / ** ( ), round, min, max, "
                     "abs, sum(... for k in range(n)). If X is a plain input (a rule, a price, a date) that cannot be worked "
                     "out from other numbers, set \"input\": true.\nSCRIPT:\n" + masked +
                     '\nReturn JSON {"expr": "...", "input": false, "how": "short"}', max_tokens=800) or {}
        except Exception as e:
            log("numbers check: blind ask failed", str(e)[:80]); continue
        if b2.get("input") or not b2.get("expr"):
            continue
        # 19 Nov: a model 'worked out' ₹5,000/day as 500 from its memory of another rule (credit cards). A formula may
        # only use numbers that are in the (masked) script, plus everyday constants; otherwise it is outside knowledge.
        known = {float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", masked)}
        CONST = {0, 1, 2, 3, 4, 7, 10, 12, 24, 30, 52, 60, 100, 365, 1000, 100000}
        lits = [float(x) for x in re.findall(r"\d+\.?\d*", str(b2["expr"]))]
        if any(v not in known and v not in CONST and round(v * 100, 6) not in known and round(v / 100, 6) not in known and round((v - 1) * 100, 6) not in known and round((1 - v) * 100, 6) not in known for v in lits):   # 1.12 = +12%   # 3% = 0.03
            log("numbers check: formula uses a number not in the script, ignored:", b2["expr"]); continue
        try:
            got = float(_safe_eval(b2["expr"]))
        except Exception as e:
            log("numbers check: skipped one expression", str(b2.get("expr"))[:80], str(e)[:60]); continue
        tol = (1.0 if abs(says) >= 100 else 0.5) if strict else max(0.05 * abs(says), 0.5 if abs(says) < 100 else 0)
        if abs(got - says) > tol:
            # 19 Nov: one blind answer can be wrong too ("31st day" read as 30+30 = 60). A second blind answer must agree
            # before the number counts as wrong, else the fix round would change a correct number.
            try:
                b3 = ask("A careful second opinion. In this script one number is hidden as X. What is X, worked out ONLY from "
                         "the other numbers and the words? Watch for counting days (the 31st day after a 30-day limit is 31), "
                         "per-day vs total, and rates. Write ONE Python arithmetic expression. If X is a plain input that "
                         "cannot be worked out, set \"input\": true.\nSCRIPT:\n" + masked +
                         '\nReturn JSON {"expr": "...", "input": false}', max_tokens=600) or {}
                got2 = None if b3.get("input") or not b3.get("expr") else float(_safe_eval(b3["expr"]))
            except Exception:
                got2 = None
            if got2 is None or abs(got2 - says) <= tol or abs(got2 - got) > max(tol, 0.01 * abs(got)):
                log("numbers check: blind answers disagree or confirm the script, not a problem:", c.get("scene"), says, got, got2)
                continue
            probs.append(f"scene {c.get('scene')}: says {says:,.2f} but worked out from the script it is {got:,.2f} "
                         f"({b2['expr']}; {str(b2.get('how', ''))[:80]})")
    for f in r.get("facts") or []:
        if strict and f.get("correct") is None:
            probs.append(f"scene {f.get('scene')}: '{str(f.get('fact'))[:100]}' is not in the sources: remove it or say only what the sources say")
        if f.get("correct") is False:
            probs.append(f"scene {f.get('scene')}: '{str(f.get('fact'))[:100]}' is wrong: {str(f.get('why'))[:120]}")
    return probs


STORYCHK = """You check a short scripture-story Reel ({page}) against its SOURCES before it is published. Devotees know these
stories well: one wrong event loses their trust for ever.
List EVERY story claim in the voice-over and on-screen text: who did what, to whom, where, when, how long, in what
order, what caused what, who gave what (a meal, a boon, a curse), numbers (years, days, heads, arms), AND every claim
about history, science, places or today ("the whole world kept time by Ujjain before Greenwich" is false: Ujjain was
the prime meridian of Indian astronomy only). Overclaims ("whole world", "first ever", "only") are false unless sourced.
Judge each claim:
- "false": a SOURCE contradicts it (quote the source in "why"), OR it contradicts the standard account of the
  tradition's own scriptures ({texts}) and you are sure (name the text and say what it really says). Mixing in another
  tradition's version (a Hindu or Buddhist telling inside a Jain story, or the reverse) is false.
- "invented": a specific detail (a person, a meal, a number, a cause, an order of events) that neither the sources nor
  the scriptures give: the script made it up to sound vivid.
- "ok": supported, or a plain moral / feeling line that claims no event.
A moral, a question to the viewer or a call to comment is never a claim.
SOURCES:
{sources}
SCRIPT (scene | voice-over | on-screen):
{rows}
Return JSON {{"claims": [{{"scene": n, "claim": "...", "verdict": "ok|false|invented", "why": "short, quote or name the source",
"truth": "what the sources / scriptures really say (empty when unknown)"}}]}}"""
def story_check(ch, plan, sources):
    """19 Nov: problems with a story page's events ([] = fine): false or invented events, judged against the sources."""
    rows = "\n".join(f"{i + 1} | {s.get('vo', '')} | {s.get('text') or s.get('headline') or ''}"
                     for i, s in enumerate(plan.get("scenes", [])))
    r = ask(STORYCHK.format(page=ch.get("name", ch["id"]), texts=ch.get("story_texts", "the tradition's scriptures"),
                            sources=(sources or "(no sources found: judge from the scriptures only when sure)")[:12000],
                            rows=rows), max_tokens=3000) or {}
    flagged = [c for c in r.get("claims") or [] if str(c.get("verdict", "")).lower() in ("false", "invented")]
    if not flagged:
        return []
    # 19 Nov: with no sources the checker judged from memory and was itself wrong once ("Bhagavata: Satyabhama killed
    # Narakasura"; in Bhagavata 10.59 Krishna does). A flag counts only when a SECOND, independent model agrees.
    try:
        conf = llm.text(STORY2.format(page=ch.get("name", ch["id"]), texts=ch.get("story_texts", "the scriptures"),
                                      sources=(sources or "(none)")[:8000],
                                      claims="\n".join(f"{i + 1}. scene {c.get('scene')}: {c.get('claim')}" for i, c in enumerate(flagged))),
                        json_mode=True, max_tokens=2000) or {}
        second = {int(x.get("n", 0)): x for x in conf.get("claims") or [] if str(x.get("n", "")).isdigit()}
    except Exception as e:
        log("story check: second opinion failed, keeping only source-quoted flags", str(e)[:100])
        second = None
    out = []
    for i, c in enumerate(flagged):
        v = str(c.get("verdict")).lower()
        if second is None:
            if not sources or len(sources) < 500:
                continue                                   # no sources and no second opinion: not enough to change a story
            x = {"verdict": v, "really": ""}
        else:
            x = second.get(i + 1) or {}
            if str(x.get("verdict", "")).lower() not in ("false", "invented"):
                log("story check: second opinion disagrees, kept:", str(c.get("claim"))[:90], "->", x.get("verdict"))
                continue
        t1, t2 = str(c.get("truth") or "").strip(), str(x.get("really") or "").strip()
        t = f" (really: {t1[:140]})" if t1 and (not t2 or t2[:25].lower() in t1.lower() or t1[:25].lower() in t2.lower()) else \
            (f" (the two checks disagree on what really happened: REMOVE this detail, do not replace it)" if t1 or t2 else "")
        out.append(f"STORY scene {c.get('scene')}: {v}: '{str(c.get('claim'))[:110]}': {str(c.get('why'))[:120]}{t}")
    return out
STORY2 = """A second, independent check of claims another checker flagged in a scripture-story Reel ({page}). Judge each claim
yourself against the SOURCES and the standard account of {texts}. Be careful: popular retellings, TV serials and regional
folk versions often differ from the scripture; name the text and chapter you rely on. If you are not sure, say "unsure".
SOURCES:
{sources}
CLAIMS:
{claims}
Return JSON {{"claims": [{{"n": <number>, "verdict": "false|invented|ok|unsure", "text": "scripture + chapter", "really": "what it says"}}]}}"""
def story_fix(ch, topic, plan, research_text):
    """Story check + up to 2 rewrites; a plan still wrong after them carries numbers_hold (held before any voice)."""
    src = _fact_sources(ch, topic, research_text)
    try:                                           # scripture-specific evidence on top of the topic research
        import web
        # 19 Nov: the whole scripture list in the query found nothing; a short page word ("Jain", "Purana") finds sources
        q = " ".join(re.sub(r"[^\w\s']", " ", str(topic)).split()[:8])   # a whole-sentence topic found 0 sources
        extra = web.facts(f"{q} {ch.get('story_query', '')}".strip(), n=3, per=3000)
        if extra:
            src = (src + "\n\n" + extra).strip()
    except Exception as e:
        log("story check: web sources failed", str(e)[:100])
    for rnd in range(3):
        probs = story_check(ch, plan, src)
        if not probs:
            log("story check: every event matches the sources" + (" after a fix" if rnd else ""))
            plan.pop("numbers_hold", None)
            return plan
        log("story check found", len(probs), "problem(s):", " | ".join(probs)[:400])
        try:
            from core import note_problem
            note_problem(ch["id"], str(topic)[:60], probs, "story check")
        except Exception:
            pass
        plan["numbers_hold"] = probs
        if rnd == 2:
            break
        try:
            fixed = ask("Fix ONLY these story errors in this Shorts plan; keep everything else the same (same JSON shape). "
                        "Tell each event exactly as the sources / scriptures do (use the 'really' part). An invented detail is "
                        "REMOVED, not replaced by another invention. If the title or hook rests on a false event, rewrite the "
                        "title and hook around what really happened. Keep the story moving after the change."
                        "\nERRORS:\n- " + "\n- ".join(probs) + "\nSOURCES:\n" + src[:6000]
                        + "\nPLAN:\n" + json.dumps(plan, ensure_ascii=False))
            if len(fixed.get("scenes", [])) >= 6:
                keep = {k: plan[k] for k in ("numbers_hold",) if k in plan}
                plan = fixed; plan.update(keep)
        except Exception as e:
            log("story fix failed:", str(e)[:120]); break
    return plan
ART = re.compile(r"(?:(?<=\s)|^)the\s+|^an?\s+", re.I)


def _no_article(s):
    """19 Nov: the vision check held pages for an English article on screen ("THE" in a Hinglish title). On-screen
    text is short and Hinglish: drop "the" and a leading "a/an" (never when it would leave the field empty)."""
    if not isinstance(s, str):
        return s
    out = ART.sub("", s.strip()).strip()
    return out if out else s


LAB_TYPES = ("object", "stat", "ui", "chart", "flow", "compare", "title", "clip", "chat", "code", "wa", "sms", "pay", "bill", "rule",
             "table", "list")
PHONE_TYPES = ("wa", "sms", "pay", "bill", "rule", "stat", "compare", "title", "flow", "table", "list")
FRIENDS = ["Mehul", "Raghav", "Aditya", "Shobhit", "Shwetal", "Saumya", "Suhail", "Jahnvi", "Masood", "Animesh", "Jayesh",
           "Aaryan", "Dhruv", "Mudit", "Shruti"]
NOT_NAMES = {"me", "friend", "dost", "bhai", "mummy", "papa", "bank", "messages", "save kijiye", "save karo", ""}


def _friend_names(plan):
    """19 Nov (finance 1119-0351 used 'Rahul'): the chat person must be one of the owner's friends. A chat name that is not
    one is replaced everywhere in the plan (voice, chats, titles) by an unused friend."""
    used = set()
    for s in plan.get("scenes", []):
        if s.get("type") != "wa":
            continue
        for m in s.get("messages") or []:
            if isinstance(m, dict):
                used.add(str(m.get("from") or "").strip())
        used.add(str(s.get("title") or "").strip())
    free = [f for f in FRIENDS if f not in used]
    for n in sorted(used, key=len, reverse=True):
        if not n or n.lower() in NOT_NAMES or n in FRIENDS or not re.fullmatch(r"[A-Z][a-z]{2,12}", n) or not free:
            continue
        new = free.pop(0)
        blob = re.sub(rf"\b{re.escape(n)}\b", new, json.dumps(plan, ensure_ascii=False))
        plan.clear(); plan.update(json.loads(blob))
        log("lab fix: chat name", n, "->", new, "(owner's friends only)")
    return plan


def lab_fix(plan, phone=False):
    """19 Nov (finance 1118-2334 held: the planner wrote 'info' and 'image' scenes and a 'ui' with no rows on a lab page;
    the screen showed 'None' and a bare logo). Every lab scene gets a type the lab compositor draws, with its data;
    a scene that cannot be drawn becomes a 'title' (big words over its full-frame picture)."""
    def words(s):
        t = s.get("big") or s.get("title") or s.get("label") or " ".join(str(s.get("vo", "")).split()[:3])
        return " ".join(str(t).split()[:4]).upper()
    for s in plan.get("scenes", []):
        t = s.get("type")
        ok = {
            "stat": bool(re.search(r"\d", str(s.get("value") or s.get("big") or ""))),
            "ui": len(s.get("rows") or []) >= 1,
            "chart": len(s.get("points") or []) >= 2,
            "flow": len(s.get("nodes") or []) >= 2,
            "compare": len(s.get("items") or []) >= 2,
            "chat": len(s.get("messages") or []) >= 1,
            "code": len(s.get("lines") or []) >= 1,
            "object": bool(s.get("prompt") or (isinstance(s.get("real"), dict) and s["real"].get("q"))),
            "clip": bool(s.get("prompt")),
            "title": True,
            "wa": len(s.get("messages") or []) >= 1, "sms": len(s.get("messages") or []) >= 1,
            "pay": bool(s.get("value") or s.get("big")), "bill": len(s.get("rows") or []) >= 1,
            "rule": len(s.get("lines") or []) >= 1,
            "table": len(s.get("cols") or []) >= 2 and len(s.get("rows") or []) >= 1,
            "list": len(s.get("lines") or []) >= 2,
        }
        if phone and t == "title" and (len(s.get("lines") or []) >= 2 or len(s.get("items") or []) >= 2):
            # 19 Nov (finance 1119-0351, owner: "still confused about the difference"): 7 title scenes held the comparison
            # in lines/items, and a title draws only its heading, so the whole comparison was invisible. Keep the data.
            if not s.get("lines"):
                s["lines"] = [f"{x.get('label', '')}: {x.get('value', '')}".strip(": ") for x in s["items"] if isinstance(x, dict)]
            s["title"] = s.get("title") or s.get("big")
            s["type"] = t = "list"; ok["list"] = len(s["lines"]) >= 2
            log("lab fix (phone): title holding", len(s["lines"]), "lines -> list card")
        if phone and t not in PHONE_TYPES:
            # 19 Nov: a phone page draws everything; a picture scene becomes the drawn scene its data allows, else a title
            if t == "chat" and ok["chat"]:
                s["type"] = t = "wa"
            elif t == "ui" and ok["ui"]:
                s["type"] = t = "bill"
            else:
                s["type"] = t = "title"; s["big"] = words(s)
            s.pop("prompt", None)                 # bg_prompt stays: phone_bg plans paint it behind the phone
            log("lab fix (phone): scene ->", t)
        if t in LAB_TYPES and not ok.get(t, False):
            # 19 Nov: the pre-render repair wrote a 'ui' holding compare items and a 'chart' holding flow nodes (both drew
            # nothing). Use the type whose data the scene really has.
            for t2, k2 in (("compare", "items"), ("flow", "nodes"), ("ui", "rows"), ("chart", "points"), ("chat", "messages"), ("code", "lines")):
                if ok[t2]:
                    if t2 == "compare":
                        for j, it in enumerate(s["items"]):
                            it.setdefault("pct", 40 + 50 * j // max(1, len(s["items"]) - 1))
                    log("lab fix: scene type", t, "->", t2, "(it holds", k2 + ")")
                    s["type"] = t = t2
                    break
        if t == "stat" and ok["stat"] and not s.get("value"):
            s["value"] = s.get("big")
        r_ = s.get("real") if isinstance(s.get("real"), dict) else {}
        if phone and t != "rule":
            s.pop("real", None); r_ = {}          # a phone page shows a real logo only on its rule card
        if str(r_.get("kind", "")).lower() == "logo" and t not in ("object", "chat", "rule"):
            # 19 Nov: a real logo as a full-frame background is a white card behind white text (finance 1118-2334 s2).
            # A logo is shown on its own card: an object scene; the words go in the label.
            s["type"] = "object"; s["prompt"] = s.get("prompt") or r_.get("subject") or r_["q"]
            s["label"] = s.get("label") or s.get("title") or s.get("big")
            log("lab fix: logo scene -> object card", r_.get("q"))
            continue
        if t in ("image", "card", "info") and (s.get("prompt") or (isinstance(s.get("real"), dict) and s["real"].get("q"))) \
                and not s.get("big"):
            s["type"] = "object"; continue
        if t not in LAB_TYPES or not ok.get(t, False):
            s["type"] = "title"; s["big"] = words(s)
            log("lab fix: scene type", t, "-> title", repr(s["big"]))
    if phone:
        _friend_names(plan)
    return plan


CTA_RX = re.compile(r"^\s*(follow|subscribe)\b[^.?!]*(@\w|for more)[^.?!]*[.!]?\s*$", re.I)   # a whole line that is only a follow ask
HOWWHY_RX = re.compile(r"\b(kaise|kyun|kyon|kya hota|how|why|samjho|explained|matlab kya)\b", re.I)


def _grade(plan, topic, research_text):
    lines = "\n".join(f"{i + 1}. {s.get('vo', '')}" for i, s in enumerate(plan.get("scenes", [])))
    g = ask(f"""You are a viewer who knows nothing about "{plan.get('title') or topic}". Read this 45 s reel script (Hinglish).
SCRIPT:
{lines}
SOURCES (what is true):
{str(research_text)[:5000]}
Answer as JSON: {{"answers_title": true/false (after watching, can you explain HOW it works, not just WHAT it does?),
"steps_learned": ["each concrete step of the mechanism the script actually explains, in order"],
"missing_steps": ["the important steps a 14-year-old would still not understand, from the sources"],
"filler": [line numbers that add no new information: hype, benefits list, repeated idea, 'follow' lines; the hook (line 1)
and the final question are NOT filler],
"unsourced": ["numbers or claims not in the sources or out of date"],
"jargon": ["technical words used without an everyday comparison (e.g. webhook, LLM, API, function calling)"],
"stiff": [line numbers that sound bookish or like a manual instead of a friend talking ('ka upyog karke', 'execute karta')],
"score": 1-10 (10 = a top Hindi tech creator would post it as is)}}""", max_tokens=1500) or {}
    g["ok"] = bool(g.get("answers_title") and len(g.get("steps_learned") or []) >= 3 and not g.get("unsourced")
                   and len(g.get("filler") or []) <= 1 and len(g.get("jargon") or []) <= 1 and len(g.get("stiff") or []) <= 1
                   and (g.get("score") or 0) >= 8)
    return g


def explainer_gate(ch, topic, plan, research_text, W0, W1, rounds=2):
    """19 Nov (owner: the WhatsApp AI agent reel 'is not top notch', the reviewer gave it 10/10). The editor pass fixes form
    (hook, line length); nothing checked that a 'kaise kaam karta hai' reel actually EXPLAINS. This gate grades the script
    as a viewer would (answers the title? which real steps are learned? filler? unsourced numbers?), rewrites it with that
    feedback, grades again, up to `rounds` times, and keeps the best-graded plan. Story pages are skipped."""
    title = f"{plan.get('title', '')} {topic}"
    if (ch.get("serial") or ch.get("id") in ("katha", "jain", "raaz")) or not (HOWWHY_RX.search(title) or (ch.get("theme") or {}).get("style") == "lab"):
        return plan
    g = _grade(plan, topic, research_text)
    best, best_g = plan, g
    for rnd in range(rounds + 1):
        log(f"explainer gate round {rnd}:", "pass" if g["ok"] else "fail", "score", g.get("score"), "steps", len(g.get("steps_learned") or []),
            "filler", g.get("filler"), "unsourced", (g.get("unsourced") or [])[:3])
        if (g.get("score") or 0) > (best_g.get("score") or 0) or (g["ok"] and not best_g["ok"]):
            best, best_g = plan, g
        if g["ok"] or rnd == rounds:
            break
        fixed = ask(f"""Rewrite this reel plan so it truly EXPLAINS "{plan.get('title') or topic}". A test viewer said:
- steps they learned: {json.dumps(g.get('steps_learned') or [], ensure_ascii=False)}
- steps still missing: {json.dumps(g.get('missing_steps') or [], ensure_ascii=False)}
- filler lines (cut or replace with a mechanism step): {g.get('filler')}
- numbers/claims with no source or out of date (fix from the SOURCES or remove): {json.dumps(g.get('unsourced') or [], ensure_ascii=False)}
- jargon left unexplained: {json.dumps(g.get('jargon') or [], ensure_ascii=False)}; stiff, bookish lines: {g.get('stiff')}
Rules: 10-14 scenes, each ONE spoken line of 5-14 words, natural Hinglish like a friend explaining at a chai stall (short
words, "sochiye", "matlab", "bas"); nobody is ever spoken to as "tu" (no "tu", "tera", "tujhe", no bare "bata" / "kar"): "tum" or "aap" only (owner rule); every technical word gets an everyday comparison the first time (webhook = "ek doorbell jo
business ke server ko jagaati hai"); keep the hook idea and the JSON shape; fill "mechanism" with 3-6 real steps from the sources and walk them in order,
one scene per step, each scene's visual showing that step (a flow node lighting up, the message moving, the tool card);
at most one benefits line; no spoken 'follow' line; end with a payoff + an easy comment question; {W0}-{W1} words total;
same channel look and scene types; every number must appear in the SOURCES.
SOURCES:
{str(research_text)[:5000]}
PLAN:
{json.dumps(plan, ensure_ascii=False)}""")
        sc = (fixed or {}).get("scenes") or []
        words = sum(len(s.get("vo", "").split()) for s in sc)
        if not (len(sc) >= 8 and W0 - 10 <= words <= W1 + 15):
            log("explainer gate: rewrite unusable (", len(sc), "scenes,", words, "words)")
            break
        plan = fixed
        g = _grade(plan, topic, research_text)
    best["explainer"] = {k: best_g.get(k) for k in ("score", "ok", "steps_learned", "missing_steps", "unsourced")}
    log("explainer gate: kept the plan with score", best_g.get("score"), "(pass)" if best_g["ok"] else "(best available)")
    return best


def _roman(plan):
    """20 Nov: nemotron wrote a whole Jain script in Devanagari; clean() then deleted every Devanagari letter, the lines
    became ",", "24", "?" and the voice model invented its own story (alignment 0%). Lines in Devanagari are now
    rewritten in Roman Hinglish (one text call) before anything else touches them."""
    dev = [i for i, s in enumerate(plan.get("scenes") or []) if re.search(r"[\u0900-\u097F]", s.get("vo", ""))]
    keys = [k for k in ("title", "caption") if re.search(r"[\u0900-\u097F]", str(plan.get(k) or ""))]
    if not dev and not keys:
        return 0
    import llm
    src = {f"s{i}": plan["scenes"][i]["vo"] for i in dev}
    src.update({k: plan[k] for k in keys})
    for i, s in enumerate(plan.get("scenes") or []):
        for k in ("title", "big", "small"):
            if re.search(r"[\u0900-\u097F]", str(s.get(k) or "")):
                src[f"{k}{i}"] = s[k]
    try:
        r = llm.text("Rewrite each value below in natural Roman-letter Hinglish exactly as an Indian reel narrator would type it "
                     "(e.g. 'Raja Shrenik narak mein hain, phir bhi agle kaal ke pehle Tirthankar kaise?'). Same meaning, same "
                     "names, no Devanagari letters, no English translation. Return JSON with the same keys.\n"
                     + json.dumps(src, ensure_ascii=False), json_mode=True, max_tokens=3000) or {}
    except Exception as e:
        log("roman rewrite failed:", str(e)[:120]); r = {}
    n = 0
    for k, v in src.items():
        new = str(r.get(k) or "").strip()
        if not new or re.search(r"[\u0900-\u097F]", new):
            continue
        if k.startswith("s") and k[1:].isdigit():
            plan["scenes"][int(k[1:])]["vo"] = new
        elif k in ("title", "caption"):
            plan[k] = new
        else:
            kk = re.match(r"(title|big|small)(\d+)", k)
            plan["scenes"][int(kk.group(2))][kk.group(1)] = new
        n += 1
    log("plan: Devanagari rewritten in Roman letters:", n, "of", len(src), "values")
    return n


def clean(plan):
    clips = 0
    _roman(plan)
    for s in plan["scenes"]:
        s["vo"] = re.sub(r"[\u0900-\u097F]+", "", s.get("vo", "")).strip()
        t = s.get("type", "image")
        if t == "clip":
            clips += 1
            if clips > 2:
                t = "image"
        if t == "flow" and len(s.get("nodes") or []) < 2:
            t = "image"
        if t == "card" and not s.get("big"):
            t = "image"
        s["type"] = t
        s["motion"] = s.get("motion") if s.get("motion") in ("push", "pull", "pan", "punch", "tilt") else "push"
        s["title"] = " ".join((s.get("title") or "").split()[:4])
        for k in ("title", "big", "small", "sub", "label"):
            s[k] = _no_article(s[k]) if s.get(k) else s.get(k)
        for k in ("title", "big", "small", "sub", "label"):
            if s.get(k):
                s[k] = _no_article(s[k])
    # 19 Nov: the planner wrote "Follow @KaiseTech for more" (wrong handle, real one is @kaise.tech) as a spoken last scene
    # on top of the end card. A CTA scene goes; the end card already shows the page's own handle.
    if len(plan["scenes"]) > 6:
        plan["scenes"] = [s for s in plan["scenes"] if not CTA_RX.search(s.get("vo", ""))]
    plan["scenes"] = [s for s in plan["scenes"] if s["vo"]]
    return plan
