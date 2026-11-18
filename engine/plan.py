"""Brief + shot plan for one video: the LLM writes a plan from channel rules + lessons + playbook + research,
then a second pass reviews it as a strict editor and returns the fixed plan."""
import json, os, re
from core import ROOT, read, log
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
            body = {"contents": [{"parts": [{"text": prompt + "\n\nReturn ONLY valid JSON."}]}],
                    "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens, "temperature": 0.7}}
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                       data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(m)})
            d = json.load(urllib.request.urlopen(r, timeout=300))
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
    lessons = read(os.path.join(ROOT, "knowledge", "lessons.md"))
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
        p += LAB
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
    if ch.get("numbers_check"):                    # 18 Nov (finance 1118-2228 said Rs 50k -> Rs 1,02,000 with Rs 5k/month paid)
        for rnd in range(3):                       # 19 Nov: 2 fix rounds (one was not enough for unsourced claims)
            probs = numbers_check(plan, _fact_sources(ch, topic, research_text))
            if not probs:
                log("numbers check: all calculations and rules correct" + (" after a fix" if rnd else ""))
                plan.pop("numbers_hold", None)
                break
            log("numbers check found", len(probs), "problem(s):", " | ".join(probs)[:300])
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
    out = clean(plan)
    if isinstance(out, dict):
        out["brain_ids"] = bids                    # which brain items this video used (scored after its review)
    return out


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

def numbers_check(plan, sources=""):
    """Problems with the plan's numbers ([] = fine). Arithmetic is computed by Python, not judged by the model."""
    rows = "\n".join(f"{i + 1} | {s.get('vo', '')} | {s.get('value') or s.get('big') or s.get('end_label') or ''}"
                     for i, s in enumerate(plan.get("scenes", [])))
    try:
        r = ask(NUMCHK.format(rows=rows, sources=(sources or "(none found: mark facts null, never false)")[:9000]), max_tokens=2500) or {}
    except Exception as e:
        log("numbers check failed to run:", str(e)[:120]); return []
    probs = []
    # 19 Nov: the model "proved" '3 x 100 = 500' with the expression "500". A formula with no arithmetic, or that
    # contains its own answer, proves nothing: ask again for those, built only from the script's other numbers.
    def _lazy(c):
        e = re.sub(r"\s", "", str(c.get("expr") or ""))
        s = re.sub(r"[^\d.]", "", str(c.get("says") or ""))
        return not re.search(r"[-+*/%]", e.lstrip("-")) or (s and re.search(rf"(?<![\d.]){re.escape(s.rstrip('0').rstrip('.') or s)}(?:\.0+)?(?![\d.])", e))
    lazy = [c for c in (r.get("calc") or []) if _lazy(c)]
    if lazy:
        ask_rows = "\n".join(f"scene {c.get('scene')}: the script says {c.get('says')}" for c in lazy)
        try:
            r2 = ask("For each number below, write the Python arithmetic expression that computes it ONLY from the OTHER "
                     "numbers in the script (never write the answer itself). If the number is a plain input (a rule, a price, "
                     "a date) and not calculated from others, set \"input\": true.\nSCRIPT:\n" + rows + "\nNUMBERS:\n" + ask_rows +
                     '\nReturn JSON {"calc": [{"scene": n, "says": <number>, "expr": "...", "input": false}]}', max_tokens=1500) or {}
            redo = [c for c in (r2.get("calc") or []) if not c.get("input")]
            r["calc"] = [c for c in (r.get("calc") or []) if not _lazy(c)] + redo
            for c in redo:
                if _lazy(c):
                    probs.append(f"scene {c.get('scene')}: {c.get('says')} is said as a result but no formula reaches it from the script's numbers")
        except Exception as e:
            log("numbers check re-ask failed:", str(e)[:80])
    for c in r.get("calc") or []:
        if _lazy(c):
            continue
        try:
            got, says = float(_safe_eval(c.get("expr"))), float(str(c.get("says")).replace(",", ""))
            tol = max(0.05 * abs(says), 0.5 if abs(says) < 100 else 0)     # spoken rounding: "3 percent" for 3.04
            if says and abs(got - says) > tol:
                probs.append(f"scene {c.get('scene')}: says {says:,.2f} but the script's own scenario gives {got:,.2f} ({c.get('expr')})")
        except Exception as e:
            log("numbers check: skipped one expression", str(c.get("expr"))[:80], str(e)[:60])
    for f in r.get("facts") or []:
        if f.get("correct") is False:
            probs.append(f"scene {f.get('scene')}: '{str(f.get('fact'))[:100]}' is wrong: {str(f.get('why'))[:120]}")
    return probs


def clean(plan):
    clips = 0
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
    plan["scenes"] = [s for s in plan["scenes"] if s["vo"]]
    return plan
