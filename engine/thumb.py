"""Covers / thumbnails, v2 (owner 17 Nov: "thumbnails are not up to the mark; everything top-notch").
What changed vs v1 (a blurred dark frame + the first 5 words of the title):
  hook     Gemini writes 6 cover lines from proven hook patterns (curiosity gap, specific number, myth-buster, "you"
           challenge, before/after, forbidden knowledge...), each a COMPLETE thought of 2-5 words in the video's language,
           self-scored on specificity + intrigue; never a cut-off title.
  hero     the sharpest, most striking picture of the video (scene images, a frame of the hook clip), shown SHARP and
           big, with a channel colour grade; no blur soup.
  layout   per-page design (tech = dark lab + glowing object, katha = mythic gold, stories = noir case file), huge
           headline (130-190 px) with one accent word on a highlight block, thick outline + shadow, kicker pill.
           All text inside the Instagram 3:4 grid crop (240 px off top and bottom) and mostly inside the centre square.
  judge    3 variants are rendered; Gemini looks at them the way a viewer does (full size AND tiny grid size) and picks the
           best on readability, curiosity, clarity and contrast. If the best scores < 7 it tries once more with notes.
  make(cid, job) -> cover.jpg (+ cover-variants.json)    stamp(mp4, cover, out) unchanged
  python engine/thumb.py <channel> <job>"""
import base64, glob, html, json, os, re, shutil, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log, sh

CHROME = next(iter(sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux-arm64/chrome-headless-shell")))), "")
W, H = 1080, 1920
FONTS = "https://fonts.googleapis.com/css2?family=Anton&family=Montserrat:wght@800;900&family=Cinzel:wght@800;900&family=JetBrains+Mono:wght@700&display=block"
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]

STYLE = {   # per page: fonts, colours, grade and layout name
    "tech": {"layout": "lab", "font": "'Montserrat',sans-serif", "acc": "#f5c542", "acc2": "#46d1ff", "ink": "#0b0d12",
             "kicker": "KAISE TECH", "grade": "contrast(1.08) saturate(1.15)"},
    "katha": {"layout": "myth", "font": "'Cinzel',serif", "acc": "#ffb238", "acc2": "#ff7a1a", "ink": "#1a0d00",
              "kicker": "PURAAN KI KATHA", "grade": "contrast(1.12) saturate(1.2) sepia(.12)"},
    "raaz": {"layout": "noir", "font": "'Anton',sans-serif", "acc": "#ffd400", "acc2": "#e63946", "ink": "#0a0a0a",
             "kicker": "AAGE SUNO", "grade": "contrast(1.15) saturate(.85)"},
    "jain": {"layout": "myth", "font": "'Cinzel',serif", "acc": "#f2c14e", "acc2": "#e8571a", "ink": "#1a0d00",
             "kicker": "NAVKAR BHAV", "grade": "contrast(1.1) saturate(1.15) sepia(.1)"},
    "finance": {"layout": "lab", "font": "'Montserrat',sans-serif", "acc": "#33d17a", "acc2": "#f5c542", "ink": "#0b0d12",
             "kicker": "FINANCE FUEL", "grade": "contrast(1.08) saturate(1.1)"},
}

HOOKS = """Write cover lines (thumbnail text) for this vertical short video. The cover is what makes someone stop scrolling and tap.
Video title: {title}
What the video says (first lines): {lines}
Page: {page}. Cover language: {lang}.
Use DIFFERENT proven hook patterns, one per line: curiosity gap, specific number reveal, myth-buster ("X is a lie"),
"you" challenge, forbidden/insider knowledge, before/after, negative superlative, single-question interrupt, POV.
Rules: 2-5 words, a COMPLETE thought (never cut mid-phrase), simple everyday words, no hashtags, no emoji, no quotes,
true to the video (no clickbait the video does not pay off). For Hinglish write Roman letters.
Return JSON {{"hooks": [{{"text": "...", "accent": "<the ONE word to highlight, copied exactly>", "kicker": "<optional 1-3 word tag, e.g. PART 1, SACH?, AI>",
"pattern": "...", "specificity": 1-10, "intrigue": 1-10}}]}} with 6 hooks."""

JUDGE = """You are a senior thumbnail designer for top short-video channels. The image shows {n} cover variants side by side
(labelled A, B, C...), each at full size on top and at Instagram profile-grid size (3:4 crop, tiny) below it.
Video: {title}. Language: {lang}.
Score each variant 1-10 for: readable at tiny size, makes you curious to tap, clear single focal point, strong contrast,
nothing cut off or overlapping, looks premium (not cheap or cluttered). Then pick the best.
Return JSON {{"scores": {{"A": <1-10 overall>, ...}}, "best": "A", "notes": "what would make the best one even better (one sentence)"}}"""


def _gemini(parts, temp=0.6, tokens=2000):
    import tts, llm
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json", "temperature": temp, "maxOutputTokens": tokens}}
    for m in tts.usable(MODELS):
        for _ in range(2):
            try:
                r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(body).encode(),
                                           headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(m)})
                d = json.load(urllib.request.urlopen(r, timeout=180))
                return llm.parse_json("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
            except Exception as e:
                log("cover gemini fail", m, str(e)[:100])
    try:                                                   # 18 Nov: our Gemini keys out -> same question through OmniRoute
        return llm.from_parts(parts, max_tokens=tokens)
    except Exception as e:
        log("cover omniroute fail", str(e)[:120])
    return None


def hooks(plan, cid, lang):
    lines = " ".join(s.get("vo", "") for s in plan.get("scenes", [])[:4])[:500]
    r = _gemini([{"text": HOOKS.format(title=plan.get("title", ""), lines=lines, page=STYLE.get(cid, STYLE["tech"])["kicker"],
                                       lang="English" if lang == "en" else "Hinglish (Roman letters)")}], 0.9) or {}
    hs = [h for h in (r.get("hooks") or []) if isinstance(h, dict) and h.get("text") and 2 <= len(h["text"].split()) <= 6]
    for h in hs:
        h["score"] = (h.get("specificity") or 5) + (h.get("intrigue") or 5)
    hs.sort(key=lambda h: -h["score"])
    if not hs:                                        # never cut a title mid-phrase: whole short title or its first clause
        t = re.split(r"[?:!.,—-]", plan.get("title", "") or "")[0].strip()
        hs = [{"text": " ".join(t.split()[:5]), "accent": (t.split() or [""])[-1], "kicker": "", "score": 0}]
    return hs


def heroes(jd, plan, mp4):
    """Candidate hero pictures: scene images in story order (the hook scene first), plus a frame of the opening clip."""
    a = load(os.path.join(jd, "assets.json"), {}) or {}
    out = []
    for k in sorted(a, key=lambda x: int(x) if str(x).isdigit() else 99):
        img = (a[k] or {}).get("image")
        if img and os.path.exists(img):
            out.append(img)
    v0 = (a.get("0") or {}).get("video")
    if v0 and os.path.exists(v0):
        fr = os.path.join(jd, "cover-clip.jpg")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", "1.2", "-i", v0, "-frames:v", "1", "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", fr])
        if os.path.exists(fr):
            out.insert(0, fr)
    if not out and os.path.exists(mp4):               # no pictures (pure graphics video): a clean frame without captions
        fr = os.path.join(jd, "cover-frame.jpg")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", "2.5", "-i", mp4, "-frames:v", "1", "-vf", f"scale={W}:{H}", fr])
        out.append(fr)
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p); uniq.append(p)
    try:                                              # 17 Nov: the strongest picture first (engine/extras.py)
        import extras
        uniq = extras.best_image(uniq[:6], os.path.join(jd, ".bestimg"))
        import shutil; shutil.rmtree(os.path.join(jd, ".bestimg"), ignore_errors=True)
    except Exception as e:
        log("cover best-picture pick skipped", str(e)[:80])
    return uniq[:4]


def _headline(text, accent, st, size):
    words = html.escape(text.upper() if st["layout"] != "myth" else text.title()).split()
    acc = (accent or "").strip().lower().strip(".,!?")
    out = []
    for w in words:
        if acc and w.lower().strip(".,!?") == acc:
            out.append(f'<span class="hl">{w}</span>')
        else:
            out.append(w)
    return " ".join(out)


def page(hero_path, hk, st, handle, lang, layout_hint=0):
    t = hk["text"].strip().rstrip(".")
    n = len(t)
    size = 190 if n <= 12 else 168 if n <= 18 else 146 if n <= 26 else 128
    if st["layout"] == "myth":
        size = int(size * 0.86)
    head = _headline(t, hk.get("accent"), st, size)
    kick = html.escape((hk.get("kicker") or st["kicker"]).upper())[:22]
    hero = "file://" + hero_path
    acc, acc2, ink, font = st["acc"], st["acc2"], st["ink"], st["font"]
    # text block sits in the centre-low area: inside the 3:4 grid crop (y 240..1680) and mostly inside the centre square
    top = 1010 if layout_hint % 2 == 0 else 360
    grad = ("rgba(0,0,0,.25) 0%,rgba(0,0,0,0) 30%,rgba(0,0,0,.15) 48%,rgba(0,0,0,.82) 72%,rgba(0,0,0,.92) 100%" if top > 600 else
            "rgba(0,0,0,.92) 0%,rgba(0,0,0,.8) 34%,rgba(0,0,0,.1) 58%,rgba(0,0,0,.15) 85%,rgba(0,0,0,.5) 100%")
    bg = f"""<img class="hero" src="{hero}" style="position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover;filter:{st['grade']}">
<div style="position:absolute;inset:0;background:linear-gradient(180deg,{grad})"></div>"""
    if st["layout"] == "lab":
        # full-bleed hero like the other pages, plus a faint tech glow and grid
        bg += f"""<div style="position:absolute;inset:0;background:radial-gradient(ellipse at 50% {32 if top > 600 else 72}%,transparent 40%,{acc2}1c 65%,transparent 85%);mix-blend-mode:screen"></div>
<div class="grid"></div>"""
    extra = ""
    if st["layout"] == "noir":
        extra = f'<div class="tape" style="top:{top - 120}px">CASE FILE</div>'
    if st["layout"] == "myth":
        extra = f'<div class="orn" style="top:{top - 70}px"></div>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;overflow:hidden;background:#000;position:relative}}
.bg{{position:absolute;inset:0}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(#ffffff08 1px,transparent 1px),linear-gradient(90deg,#ffffff08 1px,transparent 1px);background-size:60px 60px;
  -webkit-mask-image:radial-gradient(ellipse at 50% 45%,#000 30%,transparent 75%)}}
.kick{{position:absolute;left:90px;top:{top - 110}px;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:38px;letter-spacing:4px;
  color:{ink};background:{acc};padding:10px 22px;border-radius:12px}}
h1{{position:absolute;left:80px;right:80px;top:{top}px;font-family:{font};font-weight:900;font-size:{size}px;line-height:.98;letter-spacing:{'-2px' if st['layout'] != 'myth' else '1px'};
  color:#fff;-webkit-text-stroke:{'10px' if st['layout'] != 'myth' else '6px'} {ink};paint-order:stroke fill;text-shadow:0 14px 0 rgba(0,0,0,.55),0 30px 60px rgba(0,0,0,.7)}}
{"h1{background:linear-gradient(180deg,#fff6d6,#ffc75a 55%,#e88a1a);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-stroke:0;filter:drop-shadow(0 6px 0 #3a1a00) drop-shadow(0 22px 40px #000)}" if st['layout'] == 'myth' else ""}
.hl{{display:inline-block;background:{acc};color:{ink};-webkit-text-stroke:0;padding:0 .14em;border-radius:.08em;transform:rotate(-2deg);text-shadow:none;
  box-shadow:0 14px 0 rgba(0,0,0,.45)}}
{".hl{background:none;color:transparent;-webkit-text-fill-color:transparent;background:linear-gradient(180deg,#fff,#ffdf8a);-webkit-background-clip:text;background-clip:text;box-shadow:none;transform:none}" if st['layout'] == 'myth' else ""}
.tape{{position:absolute;left:80px;font-family:'Anton',sans-serif;font-size:46px;letter-spacing:8px;color:#111;background:{acc};padding:6px 26px;transform:rotate(-3deg);
  box-shadow:0 10px 30px rgba(0,0,0,.6)}}
.orn{{position:absolute;left:80px;width:260px;height:10px;border-radius:5px;background:linear-gradient(90deg,{acc},{acc2});box-shadow:0 0 30px {acc}}}
.handle{{position:absolute;left:0;right:0;top:1585px;text-align:center;font-family:'Montserrat',sans-serif;font-weight:800;font-size:40px;letter-spacing:2px;color:#fff;opacity:.9;
  text-shadow:0 4px 18px #000}}
</style></head><body>
{bg}
{extra}
{'' if st['layout'] == 'noir' else f'<div class="kick">{kick}</div>'}
<h1>{head}</h1>
<div class="handle">{html.escape(handle or '')}</div>
</body></html>"""


def render(doc, out_png, work):
    p = os.path.join(work, f"c{int(time.time() * 1000) % 10 ** 9}.html")
    open(p, "w", encoding="utf-8").write(doc)
    sh([CHROME, "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files", f"--window-size={W},{H}",
        "--virtual-time-budget=9000", f"--screenshot={out_png}", "file://" + p], timeout=120)
    os.remove(p)
    return os.path.exists(out_png)


def judge(pngs, title, lang, work):
    """One sheet: each variant at full size (top) and at grid size, 3:4 crop (bottom). Gemini picks."""
    tiles = []
    for i, p in enumerate(pngs):
        big, small = os.path.join(work, f"j{i}b.jpg"), os.path.join(work, f"j{i}s.jpg")
        sh(["ffmpeg", "-v", "error", "-y", "-i", p, "-vf", "scale=360:640,drawtext=text='" + "ABCDE"[i] + "':x=14:y=10:fontsize=54:fontcolor=yellow:box=1:boxcolor=black@0.7", big])
        sh(["ffmpeg", "-v", "error", "-y", "-i", p, "-vf", "crop=1080:1440:0:240,scale=120:160,pad=360:220:120:30:black", small])
        tiles += [big, small]
    sheet = os.path.join(work, "judge.jpg")
    ins = sum([["-i", t] for t in tiles], [])
    n = len(pngs)
    fc = "".join(f"[{2 * i}:v][{2 * i + 1}:v]vstack[c{i}];" for i in range(n)) + "".join(f"[c{i}]" for i in range(n)) + f"hstack={n}"
    sh(["ffmpeg", "-v", "error", "-y"] + ins + ["-filter_complex", fc, sheet] if n > 1 else ["ffmpeg", "-v", "error", "-y", "-i", tiles[0], "-i", tiles[1], "-filter_complex", "vstack", sheet])
    r = _gemini([{"text": JUDGE.format(n=n, title=title, lang="English" if lang == "en" else "Hinglish")},
                 {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(sheet, "rb").read()).decode()}}], 0.1, 800) or {}
    for t in tiles:
        os.remove(t)
    sc = {k.upper(): float(v) for k, v in (r.get("scores") or {}).items() if str(v).replace(".", "").isdigit()}
    best = (r.get("best") or "A").upper()[:1]
    i = "ABCDE".find(best) if best in "ABCDE"[:n] else 0
    return i, sc, r.get("notes", ""), sheet


def make(cid, job):
    jd = os.path.join(OUT, cid, job)
    mp4 = os.path.join(jd, f"{cid}-{job}.mp4")
    out = os.path.join(jd, "cover.jpg")
    work = os.path.join(jd, f".cover-{os.getpid()}"); os.makedirs(work, exist_ok=True)
    try:
        plan = load(os.path.join(jd, "plan.json"), {}) or {}
        ch = load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}
        lang = plan.get("lang") or ("en" if job.endswith("-en") else "hi")
        st = dict(STYLE.get(cid, STYLE["tech"]))
        th = ch.get("theme", {})
        if cid == "tech":
            st["acc"], st["acc2"] = th.get("accent", st["acc"]), th.get("accent2", st["acc2"])
        handle = (ch.get("handle_en") if lang == "en" else None) or ch.get("handle", "")
        hs, hero = hooks(plan, cid, lang), heroes(jd, plan, mp4)
        if not hero:
            raise RuntimeError("no picture to build a cover from")
        best, tries = None, []
        for rnd in range(2):
            pngs, meta = [], []
            for i in range(3):
                hk = hs[(i + rnd * 3) % len(hs)]
                hp = hero[(i + rnd) % len(hero)]
                png = os.path.join(work, f"v{rnd}{i}.png")
                if render(page(hp, hk, st, handle, lang, i), png, work):
                    pngs.append(png); meta.append({"hook": hk["text"], "pattern": hk.get("pattern"), "hero": os.path.basename(hp), "layout": i % 2})
            if not pngs:
                raise RuntimeError("chrome rendered nothing")
            k, sc, notes, sheet = judge(pngs, plan.get("title", ""), lang, work)
            score = sc.get("ABCDE"[k], 0)
            tries.append({"round": rnd, "variants": meta, "scores": sc, "picked": "ABCDE"[k], "notes": notes})
            if best is None or score > best[1]:
                best = (pngs[k], score, meta[k], sheet)
            if score >= 7:
                break
        sh(["ffmpeg", "-v", "error", "-y", "-i", best[0], "-q:v", "2", out])
        shutil.copy(best[3], os.path.join(jd, "cover-variants.jpg"))
        save(os.path.join(jd, "cover-variants.json"), {"picked": best[2], "score": best[1], "rounds": tries})
        log("cover made", cid, job, f"score {best[1]:.0f}/10 ·", repr(best[2]["hook"]))
        return out
    except Exception as e:
        log("cover failed", cid, job, str(e)[:200])
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)
        for x in ("cover-clip.jpg", "cover-frame.jpg", "cover-s.jpg"):
            if os.path.exists(os.path.join(jd, x)):
                os.remove(os.path.join(jd, x))


def stamp(mp4, cover, out):
    sh(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-i", cover, "-filter_complex",
        "[1:v]scale=1080:1920,format=yuv420p[c];[0:v][c]overlay=0:0:enable='lt(n,3)'[v]", "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out],
       timeout=1800)
    return out


if __name__ == "__main__":
    print(make(sys.argv[1], sys.argv[2]))
