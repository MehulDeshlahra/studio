"""Picture smith (20 Nov, owner: "before it is made, create a detailed prompt, give sample images / references, so there
is no scope of a mistake"). Every story picture goes through four steps:

  1. bible     once per video: one fixed visual description per recurring figure and place (same words in every
               scene, so a king never turns into a monk), built from the page look and engine/iconography.py forms.
  2. prompt    a prompt-engineer call writes the scene prompt by Black Forest Labs' own rules (docs.bfl.ai prompting
               guide, github.com/black-forest-labs/skills): main subject first, then action, setting, style, lighting,
               framing; 50-90 words of prose; positive words only (FLUX has no negative prompt and draws the nouns it
               reads); jargon turned into what it looks like ("kayotsarga" -> standing, arms straight down).
  3. reference when the scene names a figure in knowledge/refs.json (real temple idols, public-domain paintings from
               Wikimedia Commons, tools/refs_build.py), the picture is drawn by FLUX.2 [klein] 9B on Cloudflare with up
               to 3 reference images ("the idol from image 1"). Tested 20 Nov: the reference gave the right standing
               Tirthankara; text alone on NVIDIA FLUX gave a seated idol with necklaces.
  4. check     Gemini Decisions API (gemini-decision-1, free 10,000 a day, ~1 s): the page's single-frame checklist
               plus general checks on the new picture, with the narration line. Any yes >= FAIL -> the prompt
               engineer is told why and the picture is drawn again (max 3 tries; the best one is kept and flagged).
"""
import base64, json, os, re, subprocess, tempfile, time, urllib.error, urllib.request
from core import ROOT, OUT, log, load
import llm

FAIL = 0.6                      # 20 Nov test: 3/3 bad frames had a yes >= 0.66, 6/6 clean frames stayed <= 0.50
TRIES = 3
REFS = os.path.join(ROOT, "knowledge", "refs.json")
REF_DIR = os.path.join(OUT, "refs")
CF_ACCOUNT = "3d44fbd85f54ea694dd4f73153843dd3"
GENERAL = {
    "split": "Is the picture split into panels, a collage, a split screen or side-by-side copies of the same scene?",
    "text": "Is there written text, letters, numbers, a caption or a watermark anywhere in the picture?",
    "body": "Does any person or figure have a clearly deformed face, extra or missing limbs, or broken, melted hands?",
}


# ---------------- Decisions API ----------------
_dead = {}


def _gkeys():
    try:
        ks = [k.strip() for k in open(os.path.expanduser("~/.studio-gemini.key")).read().split() if k.strip()]
    except OSError:
        ks = []
    day = time.strftime("%Y-%m-%d")
    return [k for k in ks if _dead.get(k) != day]


def _jpg(img):
    """The Decisions API wants a real image type; Muse gives .webp. A 768-wide JPEG copy keeps tokens low."""
    out = os.path.join(tempfile.gettempdir(), f"dec-{os.getpid()}.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", img, "-vf", "scale='min(768,iw)':-2", "-q:v", "3", out], check=True)
    return out


def decide(img, context, questions, resolution="high"):
    """questions {id: yes/no question} -> {id: probability of yes}. Raises when no key answers."""
    data = base64.b64encode(open(_jpg(img), "rb").read()).decode()
    body = {"model": "gemini-decision-1",
            "input": [{"type": "text", "text": context.strip() + "\n"},
                      {"type": "image", "data": data, "mime_type": "image/jpeg", "resolution": resolution}],
            "questions": {k: {"type": "noul", "instructions": q} for k, q in questions.items()}}
    err = "no Gemini key"
    for key in _gkeys():
        try:
            r = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/decisions", data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": key})
            d = json.load(urllib.request.urlopen(r, timeout=60))
            return {k: float(v.get("noul", 0)) for k, v in (d.get("answers") or {}).items()}
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "ignore")
            err = f"HTTP {e.code} {msg[:160]}"
            if e.code == 429:
                if "per day" in msg.lower() or "PerDay" in msg:
                    _dead[key] = time.strftime("%Y-%m-%d")
                continue
            if e.code in (401, 403):
                continue
            raise RuntimeError(err)
    raise RuntimeError(err)


def frame_checks(ch):
    """The page's checklist questions that one frame can answer (cross-scene ones go to the final review) + general."""
    src = ch.get("frame_checks") or ch.get("visual_checks") or []          # frame_checks: one thing per question
    qs = {f"p{i + 1}": q for i, q in enumerate(src) if not re.search(r"between scenes", q, re.I)}
    qs.update(GENERAL)
    return qs


def check(img, said, ch, scene_idea=""):
    ctx = (f"One picture from a short devotional / story video (page: {ch.get('name') or ch.get('id')}). "
           f"Narration over this picture: \"{said}\". The main figure is the one the narration is about."
           + (f" Planned scene: {scene_idea[:300]}" if scene_idea else ""))
    qs = frame_checks(ch)
    a = decide(img, ctx, qs)
    return {k: round(v, 2) for k, v in a.items()}, qs


# ---------------- references ----------------
def refs_for(text, page=None, n=3):
    idx = load(REFS, {}) or {}
    t = text or ""
    out = []
    for fig, e in idx.items():
        pat = e.get("pattern") or ""
        hit = bool(pat) and re.search(pat, t, re.I)
        if not hit and fig == "Jain monk" and page == "jain":
            import iconography
            hit = bool(iconography.MONK.search(t))
        if not hit:
            continue
        for r in (e.get("refs") or [])[:1]:              # one reference per figure: the model mixes several of one figure
            f = os.path.join(REF_DIR, r["file"])
            if os.path.exists(f):
                out.append((fig, f))
    return out[:n]


def cf_klein(prompt, refs, dest, model="flux-2-klein-9b"):
    """FLUX.2 [klein] on Cloudflare Workers AI (free plan, multipart, up to 4 reference images of 512x512)."""
    try:
        tok = open(os.path.expanduser("~/videngine/cf.token")).read().strip()
        pf = dest + ".prompt.txt"
        open(pf, "w", encoding="utf-8").write(prompt)
        args = ["curl", "-s", "-m", "240", "-X", "POST",
                f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/@cf/black-forest-labs/{model}",
                "-H", "Authorization: Bearer " + tok, "-F", f"prompt=<{pf}", "-F", "width=768", "-F", "height=1344"]
        for i, (_, f) in enumerate(refs):
            args += ["-F", f"input_image_{i}=@{f}"]
        p = subprocess.run(args, capture_output=True, timeout=260)
        d = json.loads(p.stdout or b"{}")
        img = (d.get("result") or {}).get("image")
        if not img:
            log("cf klein fail", model, str(d.get("errors") or d)[:160]); return None
        open(dest, "wb").write(base64.b64decode(img))
        log("cf klein image", model, f"{len(refs)} refs", os.path.basename(dest))
        return dest
    except Exception as e:
        log("cf klein fail", model, str(e)[:120]); return None


# ---------------- prompt engineer ----------------
BIBLE = """You are the art director of a short vertical video. Before any picture is drawn, write the CHARACTER AND PLACE
BIBLE: one fixed visual description for every person, sacred figure, creature and important place that appears in the
scenes, so every picture draws them the same way.
Page look: {look}
Page cast rule: {cast}
Traditional forms that MUST be followed exactly: {forms}
Scenes (narration | planned picture):
{scenes}

For each entry write 25-45 words of concrete, visible detail only: age, build, face, hair, skin tone, clothing (colour,
cut, fabric), ornaments or their absence written positively ("bare chest", "plain bare head"), props, typical posture.
A temple idol is described as the idol (material, pose, pedestal). Use ONLY positive words (never "no", "not",
"without", "never"). Never put written words in a description.
Return JSON {{"figures": [{{"name": "...", "scenes": [<scene numbers>], "look": "..."}}], "places": [{{"name": "...", "look": "..."}}]}}"""

RULES = """You are a prompt engineer for FLUX image models. Write the picture prompt for ONE scene of a vertical video.
Rules (from Black Forest Labs' official prompting guide):
- Word order matters: start with the main subject and its fixed description from the bible (copy it), then the action
  or pose, then the setting, then the style, then the lighting, then the framing.
- 50-90 words of flowing prose, one single moment in one frame.
- Describe only what must be SEEN. Never write "no", "not", "without", "never", "avoid": say the positive form
  ("plain bare head", "clean unmarked walls", "empty sky").
- Turn every special word into what it looks like (e.g. "kayotsarga" -> "standing upright, arms hanging straight down
  by the sides, feet together"; "padmasana" -> "seated cross-legged, hands resting in the lap").
- Every surface is clean and unmarked: the picture carries no writing of any kind (do not mention text at all).
- Respectful and dignified; everyone modestly dressed in traditional attire.
- Vertical 9:16 composition, main subject in the middle third, generous calm space above and below.
{refline}
Page look (use as the style): {look}
Traditional forms that MUST be followed: {forms}
Bible: {bible}
Narration at this moment (Hindi/Hinglish): "{said}"
Planned picture from the script writer: {idea}
{feedback}
Return JSON {{"prompt": "..."}}"""

NEG = re.compile(r"\b(no|not|without|never|avoid|don'?t)\b", re.I)


def _forms(text, page):
    try:
        import iconography
        n = iconography.notes(text)
        if page == "jain" and iconography.MONK.search(text or "") and "Jain monk:" not in n:
            n = (n + "; " if n else "") + "Jain monk: " + iconography.FORMS["Jain monk"][1]
        return iconography._positive(n) or "none named"
    except Exception:
        return "none named"


def ensure_bible(p, ch):
    if p.get("bible"):
        return p["bible"]
    sc = p.get("scenes") or []
    lines = "\n".join(f"{i + 1}. {s.get('vo', '')} | {str(s.get('prompt') or '')[:220]}" for i, s in enumerate(sc))
    allt = " ".join(str(s.get("vo", "")) + " " + str(s.get("prompt", "")) for s in sc)
    vis = ch.get("visuals") or {}
    try:
        b = llm.text(BIBLE.format(look=vis.get("look", ""), cast=vis.get("cast", ""), forms=_forms(allt, ch.get("id")), scenes=lines),
                     json_mode=True, max_tokens=3000)
        if isinstance(b, dict) and b.get("figures") is not None:
            p["bible"] = b
            log("picsmith bible:", ", ".join(f["name"] for f in b.get("figures", [])[:8]))
    except Exception as e:
        log("picsmith bible failed", str(e)[:120])
    return p.get("bible") or {}


def _bible_for(bible, i):
    figs = [f for f in bible.get("figures") or [] if (i + 1) in (f.get("scenes") or [])] or (bible.get("figures") or [])[:3]
    out = [f"{f['name']}: {f['look']}" for f in figs]
    out += [f"{x['name']}: {x['look']}" for x in (bible.get("places") or [])[:3]]
    return " | ".join(out)


def write_prompt(ch, s, i, bible, refs, feedback=""):
    said = str(s.get("vo") or "")
    idea = str(s.get("prompt") or "")
    vis = ch.get("visuals") or {}
    refline = ("- Reference images are attached: " + "; ".join(f"image {k + 1} shows {fig}" for k, (fig, _) in enumerate(refs))
               + ". Name them in the prompt (\"the idol from image 1\") and keep exactly their form, face, pose and dress; "
               "take nothing else from them (their background, railings, people or colours stay out).") if refs else ""
    msg = RULES.format(refline=refline, look=vis.get("look", ""), forms=_forms(said + " " + idea, ch.get("id")),
                       bible=_bible_for(bible, i) or "none", said=said, idea=idea,
                       feedback=("The previous picture for this scene was REJECTED: " + feedback +
                                 " Rewrite the prompt so that this cannot happen again.") if feedback else "")
    for _ in range(2):
        try:
            r = llm.text(msg, json_mode=True, max_tokens=1200)
            pr = str((r or {}).get("prompt") or "").strip()
        except Exception as e:
            log("picsmith prompt failed", str(e)[:100]); pr = ""
        if pr and not NEG.search(pr):
            return pr
        if pr:                                    # one negative clause slipped in: drop that clause
            pr2 = ", ".join(c for c in re.split(r",\s*", pr) if not NEG.search(c))
            if len(pr2.split()) >= 30:
                return pr2
        msg += "\nYour last answer used a negative word. Positive words only."
    return ""


# ---------------- one scene ----------------
def on(ch, theme_style=None):
    return ch.get("picsmith", True) is not False and theme_style != "lab"


def scene_picture(ch, p, s, i, base_prompt, adir, chain):
    """chain(prompt, n) -> image path or None (the page's normal sources). Returns the image path or None.
    Records s['pic'] = {prompt, refs, tries: [{file, fails}]}."""
    bible = ensure_bible(p, ch)
    said = str(s.get("vo") or "")
    refs = refs_for(said + " " + str(s.get("prompt") or "") + " " + _bible_for(bible, i), ch.get("id"))
    tries, feedback, best = [], "", None
    for n in range(TRIES):
        prompt = write_prompt(ch, s, i, bible, refs, feedback) or base_prompt
        img = cf_klein(prompt, refs, os.path.join(adir, f"s{i}k{n}.jpg")) if refs else None
        img = img or chain(prompt, n)
        if not img:
            continue
        try:
            a, qs = check(img, said, ch, str(s.get("prompt") or ""))
        except Exception as e:
            log("picsmith check unavailable, picture kept unchecked:", str(e)[:120])
            tries.append({"file": os.path.basename(img), "prompt": prompt, "fails": {}, "unchecked": True})
            best = img
            break
        fails = {k: v for k, v in a.items() if v >= FAIL}
        tries.append({"file": os.path.basename(img), "prompt": prompt, "fails": fails, "top": max(a.values() or [0])})
        log(f"picsmith scene {i + 1} try {n + 1}:", "OK" if not fails else "REDRAW " + ", ".join(f"{k}={v}" for k, v in fails.items()),
            f"({len(refs)} refs)")
        if not fails:
            best = img
            break
        feedback = "; ".join(f"{qs[k]} (yes, {v:.0%})" for k, v in fails.items())
    if best is None and tries:                   # every try failed: keep the least bad one, the review will hold it
        t = min(tries, key=lambda t: t.get("top", 1))
        best = os.path.join(adir, t["file"])
        log(f"picsmith scene {i + 1}: all {len(tries)} tries failed, kept the least bad ({t.get('top')})")
    s["pic"] = {"refs": [f for f, _ in refs], "tries": tries}
    return best
