"""Brief + shot plan for one video: the LLM writes a plan from channel rules + lessons + playbook + research,
then a second pass reviews it as a strict editor and returns the fixed plan."""
import json, os, re
from core import ROOT, read, log
import llm, tts, urllib.request, urllib.error, time

GEM_TEXT = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]


def ask(prompt, max_tokens=8000):
    """Planning text: Gemini (Studio free key) first, OmniRoute free chain as fallback."""
    for m in [x for mm in GEM_TEXT for x in (mm, mm)]:        # each model twice: malformed JSON is usually one-off
        try:
            body = {"contents": [{"parts": [{"text": prompt + "\n\nReturn ONLY valid JSON."}]}],
                    "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens, "temperature": 0.7}}
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                       data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key()})
            d = json.load(urllib.request.urlopen(r, timeout=300))
            out = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
            log("plan text by", m)
            return llm.parse_json(out)
        except Exception as e:
            log("gemini text fail", m, str(e)[:120])
    return llm.text(prompt, json_mode=True, max_tokens=max_tokens)

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
"""


def all_lessons(own):
    """Lessons from EVERY page (owner rule 16 Nov: learning from one page applies to all).
    This page's own lessons first, then the others, each labelled with its page."""
    base = os.path.join(ROOT, "channels")
    ids = [own] + sorted(c for c in os.listdir(base) if c != own and os.path.isdir(os.path.join(base, c)))
    out = ["LESSONS FROM ALL OUR PAGES (apply every general lesson here too; format-specific ones only if they fit):"]
    for cid in ids:
        a = read(os.path.join(base, cid, "lessons.md"), 4000).strip()
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
    lessons = read(os.path.join(ROOT, "knowledge", "lessons.md"))
    ch_lessons = all_lessons(ch["id"])
    bible = read(os.path.join(ROOT, "channels", ch["id"], "bible.md"))
    hooks = read(os.path.join(ROOT, "channels", ch["id"], "hooks.md"), 3500)   # engine/hookstudy.py (weekly)
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
CHANNEL BIBLE:
{bible}

{("FIRST 2 SECONDS (what the most-viewed faceless Shorts in this niche do; scene 1 must follow these rules):" + chr(10) + hooks) if hooks else ""}
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
- 10-15 scenes; each scene = ONE spoken line of 4-16 words; total 95-150 words (about 40-55 s).
- Scene 1: the hook. The question or a surprising result in the first line, with the strongest visual. No intro, no greeting.
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
  Use it on 2-5 scenes per video (MYTHOLOGY pages: at most 2, only for a real PLACE or temple, never for gods, heroes
  or story scenes: those stay in our painted style; a real photo among paintings looks wrong); only where the line is really about that thing; keep the normal "prompt" as the fallback.
  Works on image, card and object scenes (not clip or flow). Query like a person would: "UPI logo", "Taj Mahal front view".
- No numbers, specs, prices or dates unless they are common, stable knowledge; list every factual statement in "claims".
- Never mention AI and never add an AI label.
Return JSON with exactly this shape:
{SCHEMA}"""
    if ch.get("theme", {}).get("style") == "lab":
        p += LAB
    plan = ask(p)
    for _ in range(2):
        words = sum(len(s.get("vo", "").split()) for s in plan.get("scenes", []))
        if 95 <= words <= 160:
            break
        log("plan has", words, "words -> asking for a fix")
        plan = ask(f"This plan has {words} spoken words; it needs 100-145 (40-55 s). Rewrite it to fit: add the missing "
                   f"steps of the mechanism (or cut repetition), keep the same JSON shape.\n{EXAMPLE}\n"
                   f"PLAN:\n{json.dumps(plan, ensure_ascii=False)}")
    log("plan v1", len(plan.get("scenes", [])), "scenes")
    review = f"""You are a strict senior editor of viral Indian Shorts. Review this plan against the requirements and lessons,
then return the IMPROVED plan (same JSON shape). Fix: weak hook, repeated visuals, lines over 16 words, scenes that add
no new information, unclear mechanism, prompts that would make cluttered or text-filled images, risky or unverifiable
claims (remove them), a weak ending question, stiff or bookish Hindi (make it sound like a friend talking),
production-label titles. Make the mechanism complete (no missing step). Keep 10-15 scenes and 95-150 words total.
LESSONS:
{lessons}
PLAN:
{json.dumps(plan, ensure_ascii=False)}"""
    try:
        better = ask(review)
        bw = sum(len(s.get("vo", "").split()) for s in better.get("scenes", []))
        if len(better.get("scenes", [])) >= 6 and 90 <= bw <= 165:
            plan = better
            log("plan v2 (reviewed)", len(plan["scenes"]), "scenes")
    except Exception as e:
        log("plan review failed, keeping v1:", str(e)[:120])
    out = clean(plan)
    if isinstance(out, dict):
        out["brain_ids"] = bids                    # which brain items this video used (scored after its review)
    return out


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
