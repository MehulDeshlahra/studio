"""Brief + shot plan for one video: the LLM writes a plan from channel rules + lessons + playbook + research,
then a second pass reviews it as a strict editor and returns the fixed plan."""
import json, os, re
from core import ROOT, read, log
import llm

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
   "keywords": ["1-3 words from vo to highlight"]}
 ],
 "caption": "Instagram caption: 1 hook line + 1-2 lines + a question", "hashtags": ["#..."],
 "claims": [{"claim": "each factual statement", "basis": "why it is true / source"}]
}"""


def _rules(ch):
    return "\n".join("- " + r for r in ch.get("rules", []))


def make(ch, topic, research_text):
    lessons = read(os.path.join(ROOT, "knowledge", "lessons.md"))
    ch_lessons = read(os.path.join(ROOT, "channels", ch["id"], "lessons.md"))
    bible = read(os.path.join(ROOT, "channels", ch["id"], "bible.md"))
    playbook = read(os.path.join(ROOT, "knowledge", "playbook.md"), 6000)
    p = f"""You plan one vertical short video (Instagram Reel / YouTube Short) for the channel below. Topic: "{topic}".

CHANNEL: {json.dumps({k: ch[k] for k in ("id", "language", "format", "visuals", "edit") if k in ch}, ensure_ascii=False)}
CHANNEL RULES:
{_rules(ch)}
CHANNEL BIBLE:
{bible}

LESSONS (hard rules learned from earlier videos and the owner; obey all):
{lessons}
{ch_lessons}

WHAT WINS ON SHORTS RIGHT NOW (scout playbook, excerpt):
{playbook}

RESEARCH ON THIS TOPIC (the best existing Shorts; beat them, do not copy them):
{research_text}

REQUIREMENTS
- 10-15 scenes; each scene = ONE spoken line of 4-16 words; total 95-150 words (about 40-55 s).
- Scene 1: the hook. The question or a surprising result in the first line, with the strongest visual. No intro, no greeting.
- One new piece of information per scene. The same visual idea never repeats. Max 8 s per idea.
- Explain the mechanism simply with the ONE metaphor, in order, so a 14-year-old understands.
- The last scene: a short payoff + a question the viewer answers in comments.
- Language: {ch.get('language')}. Write vo in Roman script only (no Devanagari). Natural spoken Hinglish, short words.
  Use "..." at most twice (it makes the voice pause).
- Visual types: "image" (a still, animated with camera motion), "clip" (a 10 s generated video: use at most 2, for the
  hook or the key moment), "flow" (animated step diagram, for how data/money/signal moves; 2-5 nodes), "card"
  (one big word/number over an image, for the payoff).
- Prompts: describe one clear, simple 9:16 composition, subject centred, room above and below for text;
  include the channel look: {ch.get('visuals', {}).get('look', '')}. Recurring characters: paste their cast description verbatim.
  Never ask for readable text, logos or brand names inside images.
- No numbers, specs, prices or dates unless they are common, stable knowledge; list every factual statement in "claims".
- Never mention AI and never add an AI label.
Return JSON with exactly this shape:
{SCHEMA}"""
    plan = llm.text(p, json_mode=True, max_tokens=6000)
    log("plan v1", len(plan.get("scenes", [])), "scenes")
    review = f"""You are a strict senior editor of viral Indian Shorts. Review this plan against the requirements and lessons,
then return the IMPROVED plan (same JSON shape). Fix: weak hook, repeated visuals, lines over 16 words, scenes that add
no new information, unclear mechanism, prompts that would make cluttered or text-filled images, risky or unverifiable
claims (remove them), a weak ending question. Keep 10-15 scenes and 95-150 words total.
LESSONS:
{lessons}
PLAN:
{json.dumps(plan, ensure_ascii=False)}"""
    try:
        better = llm.text(review, json_mode=True, max_tokens=6000)
        if len(better.get("scenes", [])) >= 6:
            plan = better
            log("plan v2 (reviewed)", len(plan["scenes"]), "scenes")
    except Exception as e:
        log("plan review failed, keeping v1:", str(e)[:120])
    return clean(plan)


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
