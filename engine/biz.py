"""Business studio: one engine that makes short videos for ANY business from that business's own media library.
Nothing business-specific lives in this file. A business is one folder:  businesses/<id>/business.json  (+ optional notes).

  python engine/biz.py <id> index                 # scan the library, describe new photos/clips once (cached)
  python engine/biz.py <id> make [--angle "..."] [--no-deliver] [--job ID] [--from plan|voice|assets|compose|render]
  python engine/biz.py <id> status                # library size, fresh media, last videos

Pipeline (each stage writes into ~/studio-out/biz/<id>/<job>/ and is skipped when its output exists):
  index   every clip/photo in the configured folders, with a one-line description (from the business's own index file,
          else Gemini looks at a frame once). Banned files (business "media.ban" regex) never enter the index.
  plan    an LLM writes the reel: 6-10 scenes, ONE spoken line each, and every scene names a media id FROM THE INDEX.
          It gets the business brief, its hard rules, its brand notes, optional context files (growth plan, angles),
          and which media is fresh (not used in "cooldown_days"). Unknown/banned ids are replaced; text goes through the
          business's own text filter (optional python hook) and the "never" regex list; a plan that still breaks a rule
          is re-asked once, then held.
  voice   Gemini TTS (Studio keys) in the business's voice; free Edge neural voice when Gemini is out. Whisper aligns
          every word (captions follow the voice).
  assets  real clips trimmed/looped to the scene length, cropped 9:16, muted; photos cropped 9:16 with camera motion.
  compose Studio's editor (engine/compose.py): word-lit captions, punch cards, end card with the handle, SFX cues.
  mix     voice + music from the business library (least recently used) + SFX, mastered to -14 LUFS.
  render  HyperFrames on THIS machine (the laptop; owner 20 Nov), or the laptop render worker when run on the server.
  qc      format, loudness, a frame sheet checked by vision against the plan, voice coverage. Fail = held, never delivered.
  deliver business "deliver": {"type": "folder", "dir": ...} or {"type": "command", "cmd": [... {mp4} {caption} {cover}
          {id} {title} {ai} {root} ...]} (the business's own intake decides approval/queue).
Media usage is remembered per business (~/studio-out/biz/<id>/usage.json) so the same clip is not reused for weeks."""
import argparse, glob, hashlib, importlib.util, json, os, random, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, sh, load, save, dur
import plan as planner, tts, align, compose

BIZ_DIR = os.path.join(ROOT, "businesses")
VID = (".mp4", ".mov", ".m4v", ".webm")
IMG = (".jpg", ".jpeg", ".png", ".webp")
W, H = 1080, 1920


# ---------------------------------------------------------------- free models off the server
def ensure_omniroute():
    """On the laptop the free model router (OmniRoute) is on the Studio server's 127.0.0.1:20128: open an SSH tunnel to it
    once (host + key from tools/laptop_worker.py, the same login the render worker uses). No-op on the server."""
    import socket
    def up():
        try:
            socket.create_connection(("127.0.0.1", 20128), 2).close(); return True
        except OSError:
            return False
    if up() or os.name != "nt":
        return
    try:
        src = open(os.path.join(ROOT, "tools", "laptop_worker.py"), encoding="utf-8").read()
        host = re.search(r'^HOST = "([^"]+)"', src, re.M).group(1); key = re.search(r'^KEY = r?"([^"]+)"', src, re.M).group(1)
    except Exception as e:
        log("biz: no ssh settings for the OmniRoute tunnel", str(e)[:80]); return
    subprocess.Popen(["ssh", "-i", key, "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30",
                      "-N", "-L", "20128:127.0.0.1:20128", host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(15):
        time.sleep(1)
        if up():
            log("biz: OmniRoute tunnel up"); return
    log("biz: OmniRoute tunnel did not come up (Gemini keys only)")


# ---------------------------------------------------------------- business + library
def business(bid):
    b = load(os.path.join(BIZ_DIR, bid, "business.json"))
    if not b:
        sys.exit(f"no businesses/{bid}/business.json")
    b["id"] = bid
    roots = [os.path.expanduser(r) for r in (b.get("library") or {}).get("roots", [])]
    b["root"] = next((r for r in roots if os.path.isdir(r)), None)
    if not b["root"]:
        sys.exit(f"{bid}: none of the library roots exists on this machine: {roots}")
    b["out"] = os.path.join(OUT, "biz", bid); os.makedirs(b["out"], exist_ok=True)
    up = (b.get("library") or {}).get("update")
    if up and not os.environ.get("BIZ_NO_UPDATE"):
        r = subprocess.run(up, cwd=b["root"], capture_output=True, text=True, timeout=600)
        log("biz library update", b["id"], "ok" if r.returncode == 0 else ("failed: " + (r.stderr or r.stdout)[-200:]))
    return b


def R(b, *p):
    return os.path.join(b["root"], *p)


def _read_rel(b, rel, limit=6000):
    for base in (b["root"], os.path.join(BIZ_DIR, b["id"])):
        f = os.path.join(base, rel)
        if os.path.exists(f):
            t = open(f, encoding="utf-8", errors="ignore").read()
            return t[:limit]
    return ""


def _probe_secs(f):
    try:
        return round(dur(f), 2)
    except Exception:
        return 0.0


def _frame(src, out, t=None):
    t = t if t is not None else min(1.0, max(0.1, _probe_secs(src) / 2))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=512:-2", out], check=False)
    return out if os.path.exists(out) else None


def _describe(b, path, kind):
    """One line about what the picture/clip shows (Gemini vision once; cached by the caller)."""
    import base64, realmedia
    tmp = os.path.join(b["out"], "desc.jpg")
    src = _frame(path, tmp) if kind == "clip" else path
    if not src:
        return ""
    try:
        if kind == "photo":
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", "scale=512:-2", tmp], check=False); src = tmp
        data = base64.b64encode(open(src, "rb").read()).decode()
        q = (f"This is media from the library of the business '{b.get('name')}' ({b.get('about', '')[:300]}). "
             "Describe what it shows in ONE factual line (max 20 words): subject, action, setting. Say if it looks AI-generated "
             "and if it shows anything the business would not want shown (dirty/damaged product, faces up close, text, logos of others). "
             'Return JSON {"desc": "...", "ai": true|false, "problem": "" or "short reason"}')
        r = realmedia._gemini([{"text": q}, {"inline_data": {"mime_type": "image/jpeg", "data": data}}]) or {}
        return r
    except Exception as e:
        log("biz describe failed", os.path.basename(path), str(e)[:100])
        return {}


SEE = """These are frames from short clips in the media library of "{name}" ({about}).
Each clip has four frames labelled like K3a, K3b, K3c, K3d (15, 40, 65, 90 % of the clip). For EVERY clip K<n> answer from what you SEE:
seen: what it really shows (max 16 words: subject, action, setting, condition of materials),
text: true if words/letters are burned into ANY of its frames (titles, captions, subtitles, stickers, logos added in editing),
ai: true if it looks AI-generated, ok: false if it is blurry, very dark, mostly black, or useless for a promo reel.
Return JSON {{"K1": {{"seen": "...", "text": false, "ai": false, "ok": true}}, ...}}"""


def _crop(path):
    """Baked-in black bars -> ffmpeg crop w:h:x:y (or "")."""
    o = subprocess.run(["ffmpeg", "-hide_banner", "-ss", "0.5", "-i", path, "-t", "4", "-vf", "cropdetect=24:2:0", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    c = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", o)
    if not c:
        return ""
    w, h, x, y = map(int, c[-1])
    try:
        W0, H0 = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip().split(",")[:2])
    except Exception:
        return ""
    return f"{w}:{h}:{x}:{y}" if (w < W0 * 0.96 or h < H0 * 0.96) and w > 100 and h > 100 else ""


def look_at_clips(b, cache, keys_paths, batch=4, limit=72):
    """Vision on 2 frames per clip, 6 clips per request; results cached (seen/text/ai/ok/crop)."""
    import base64
    todo = [(k, pth) for k, pth in keys_paths if cache.get(k, {}).get("look") != 2][:limit]
    for n in range(0, len(todo), batch):
        part, parts = todo[n:n + batch], []
        for j, (k, pth) in enumerate(part):
            c = cache.setdefault(k, {})
            if "crop" not in c:
                c["crop"] = _crop(pth)
            secs = c.get("secs") or _probe_secs(pth)
            for tag, f in (("a", 0.15), ("b", 0.4), ("c", 0.65), ("d", 0.9)):
                fr = os.path.join(b["out"], f"look{j}{tag}.jpg")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.1, secs * f):.2f}", "-i", pth, "-frames:v", "1",
                                "-vf", "scale=320:-2", "-q:v", "5", fr], check=False)
                if os.path.exists(fr):
                    parts += [{"text": f"K{j + 1}{tag}"}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(fr, "rb").read()).decode()}}]
        r = _vision([{"text": SEE.format(name=b.get("name"), about=b.get("about", "")[:300])}] + parts) or {}
        for j, (k, pth) in enumerate(part):
            v = r.get(f"K{j + 1}") or {}
            if v:
                cache[k].update(seen=str(v.get("seen", ""))[:160], text=bool(v.get("text")), ai_seen=bool(v.get("ai")), usable=v.get("ok") is not False, look=2)
        save(os.path.join(b["out"], "index.json"), cache)
        log("biz looked at clips", n + len(part), "/", len(todo))


def index(b, describe=True):
    """All usable media of the business: [{id, kind, path, secs, desc, ai}] (cache: index.json in the business out dir)."""
    m = b.get("media") or {}
    ban = re.compile(m["ban"], re.I) if m.get("ban") else None
    cache = load(os.path.join(b["out"], "index.json"), {}) or {}
    gone = removed(b)
    items, new = [], 0
    for src in (b.get("library") or {}).get("sources", []):
        d = R(b, src["dir"])
        if not os.path.isdir(d):
            log("biz: library folder missing", d); continue
        own = load(os.path.join(d, src["index"]), {}) if src.get("index") else {}
        own = own if isinstance(own, dict) else {}
        exts = VID if src["kind"] == "clip" else IMG
        files = sorted(f for f in os.listdir(d) if f.lower().endswith(exts))
        dd = src.get("dedupe_suffix")
        for f in files:
            stem, ext = os.path.splitext(f)
            if dd and stem.endswith(dd) and (stem[: -len(dd)] + ext) in files:
                continue                                   # keep the original, skip its copy
            path = os.path.join(d, f)
            if f"{src['dir']}/{f}" in gone:                # deleted by the owner (dashboard)
                continue
            meta = own.get(f) or own.get(stem) or {}
            if meta.get("ok") is False:
                continue
            desc = str(meta.get(src.get("desc_field", "note")) or meta.get("desc") or meta.get("note") or "")
            ai = bool(meta.get(src["ai_field"])) if src.get("ai_field") and src["ai_field"] in meta else None
            key = f"{src['dir']}/{f}"
            c = cache.get(key) or {}
            st = os.stat(path)
            sig = f"{st.st_size}-{int(st.st_mtime)}"
            if c.get("sig") != sig:
                c = {"sig": sig, "secs": _probe_secs(path) if src["kind"] == "clip" else 0}
            if not desc and describe and not c.get("desc") and new < 60:
                r = _describe(b, path, src["kind"]); new += 1
                c.update(desc=(r or {}).get("desc", ""), ai=(r or {}).get("ai"), problem=(r or {}).get("problem", ""))
            cache[key] = c
            desc = desc or c.get("desc") or stem.replace("-", " ").replace("_", " ")
            if ai is None:
                ai = bool(c.get("ai")) if c.get("ai") is not None else bool(re.search(r"\b(ai|flow|generated)\b", desc, re.I))
            if ban and (ban.search(f) or ban.search(desc)):
                continue
            if c.get("problem") and m.get("skip_problem", True):
                continue
            if src["kind"] == "clip" and c.get("secs", 0) < m.get("min_clip_s", 1.5):
                continue
            items.append({"id": f"{src['kind'][0]}{len(items) + 1}", "kind": src["kind"], "path": path, "file": f, "key": key,
                          "secs": c.get("secs", 0), "desc": desc[:200], "ai": ai})
    save(os.path.join(b["out"], "index.json"), cache)
    if describe:
        look_at_clips(b, cache, [(it["key"], it["path"]) for it in items if it["kind"] == "clip"])
    out = []
    for it in items:
        c = cache.get(it["key"], {})
        if c.get("text") and m.get("skip_burned_text", True):
            continue                                       # old edited reels: their burned-in titles would double our text
        if c.get("usable") is False:
            continue
        if c.get("seen"):
            it["desc"] = f'{c["seen"]} (library note: {it["desc"][:90]})' if it["desc"] and not it["desc"].startswith(it["file"][:6]) else c["seen"]
        it["crop"] = c.get("crop", "")
        if c.get("ai_seen"):
            it["ai"] = True
        it["id"] = f'{it["kind"][0]}{len(out) + 1}'
        out.append(it)
    log("biz index", b["id"], len(out), "usable items", f"({new} newly described, {len(items) - len(out)} left out)")
    return out


def removed(b):
    """20 Nov: files the owner deleted from the dashboard: {library key: {"t", "trash"}}. Never used again."""
    return load(os.path.join(b["out"], "removed.json"), {}) or {}


def library(b):
    """20 Nov (owner: "where can I see the library?"): EVERY file in the business library, read-only, with what the
    engine decided about it: used / left out (why), what vision saw, last used. Nothing is described or changed here."""
    m = b.get("media") or {}
    ban = re.compile(m["ban"], re.I) if m.get("ban") else None
    cache = load(os.path.join(b["out"], "index.json"), {}) or {}
    usage, cd = _usage(b), float(m.get("cooldown_days", 21))
    gone = removed(b)
    out = []
    for src in (b.get("library") or {}).get("sources", []):
        d = R(b, src["dir"])
        if not os.path.isdir(d):
            continue
        own = load(os.path.join(d, src["index"]), {}) if src.get("index") else {}
        own = own if isinstance(own, dict) else {}
        exts = VID if src["kind"] == "clip" else IMG
        files = sorted(f for f in os.listdir(d) if f.lower().endswith(exts))
        dd = src.get("dedupe_suffix")
        for f in files:
            stem, ext = os.path.splitext(f)
            key = f"{src['dir']}/{f}"
            c = cache.get(key) or {}
            meta = own.get(f) or own.get(stem) or {}
            note = str(meta.get(src.get("desc_field", "note")) or meta.get("desc") or meta.get("note") or "")
            desc = c.get("seen") or note or c.get("desc") or ""
            why = ""
            if dd and stem.endswith(dd) and (stem[: -len(dd)] + ext) in files:
                why = "duplicate copy"
            elif meta.get("ok") is False:
                why = "marked not OK in the library notes"
            elif ban and (ban.search(f) or ban.search(desc)):
                why = "banned by the business rules"
            elif c.get("problem") and m.get("skip_problem", True):
                why = "problem: " + str(c["problem"])[:80]
            elif src["kind"] == "clip" and c.get("secs") and c["secs"] < m.get("min_clip_s", 1.5):
                why = f"too short ({c['secs']} s)"
            elif c.get("text") and m.get("skip_burned_text", True):
                why = "has burned-in text"
            elif c.get("usable") is False:
                why = "vision: not usable"
            elif key not in cache:
                why = "not looked at yet"
            if key in gone:
                why = "deleted"
            last = usage.get(f, 0)
            out.append({"key": key, "file": f, "kind": src["kind"], "secs": c.get("secs", 0), "desc": desc[:220],
                        "ai": bool(c.get("ai_seen") or c.get("ai") or meta.get(src.get("ai_field") or "_")),
                        "used": not why, "why": why, "crop": c.get("crop", ""), "last": int(last),
                        "fresh": (time.time() - last) > cd * 86400, "path": os.path.join(d, f)})
    seen = {i["key"] for i in out}
    for key, g in gone.items():                            # moved to the trash folder: still listed, can be restored
        if key not in seen and g.get("trash") and os.path.exists(g["trash"]):
            c = cache.get(key) or {}
            out.append({"key": key, "file": os.path.basename(key), "kind": "clip" if key.lower().endswith(VID) else "photo",
                        "secs": c.get("secs", 0), "desc": (c.get("seen") or c.get("desc") or "")[:220], "ai": bool(c.get("ai_seen")),
                        "used": False, "why": "deleted", "crop": "", "last": int(usage.get(os.path.basename(key), 0)), "fresh": False,
                        "path": g["trash"]})
    return out


def _usage(b):
    return load(os.path.join(b["out"], "usage.json"), {}) or {}


def _fresh(b, items):
    u, cd = _usage(b), float((b.get("media") or {}).get("cooldown_days", 21))
    now = time.time()
    for it in items:
        last = u.get(it["file"], 0)
        it["fresh"] = (now - last) > cd * 86400
        it["last"] = last
    return items


# ---------------------------------------------------------------- rules
def _hook(b):
    """Optional business text filter: {"python": "path/in/library/root.py", "line": "fix_line", "caption": "fix_caption",
    "bad": "bad"} -> functions(text) -> text / bool."""
    f = b.get("text_filter") or {}
    if not f.get("python"):
        return None
    path = R(b, f["python"])
    if not os.path.exists(path):
        log("biz: text filter missing", path); return None
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("bizfilter_" + b["id"], path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def _never(b):
    return [re.compile(x, re.I) for x in b.get("never", [])]


def rule_problems(b, p):
    """Every rule the plan breaks (empty = clean)."""
    probs, nev, hk = [], _never(b), _hook(b)
    texts = [("caption", p.get("caption", ""))] + [(f"scene {i + 1}", " ".join(str(s.get(k, "")) for k in ("vo", "title", "big", "small")))
                                                    for i, s in enumerate(p.get("scenes", []))]
    for where, t in texts:
        for rx in nev:
            if rx.search(t):
                probs.append(f"{where}: breaks rule /{rx.pattern}/: {rx.search(t).group(0)!r}")
        if hk and (b.get("text_filter") or {}).get("bad") and getattr(hk, b["text_filter"]["bad"])(t):
            probs.append(f"{where}: business text filter rejects it")
    return probs


def apply_filter(b, p):
    hk, f = _hook(b), b.get("text_filter") or {}
    if not hk:
        return p
    for s in p.get("scenes", []):
        if f.get("line"):
            v = getattr(hk, f["line"])(s.get("vo", ""))
            if v != s.get("vo"):
                log("biz filter changed line:", s.get("vo", "")[:60], "->", (v or "")[:60]); s["vo"] = v
    if f.get("caption"):
        p["caption"] = getattr(hk, f["caption"])(p.get("caption", ""))
    p["scenes"] = [s for s in p["scenes"] if s.get("vo", "").strip()]
    if len(p["scenes"]) > 2:
        first = re.sub(r"[^a-z ]", "", p["scenes"][0]["vo"].lower()).strip()
        for s in p["scenes"][1:]:
            parts = re.split(r"(?<=[.?!])\s+", s["vo"].strip())
            keep = [x for x in parts if re.sub(r"[^a-z ]", "", x.lower()).strip() != first]
            if len(keep) < len(parts) and keep:
                log("biz: removed a repeat of the hook from:", s["vo"][:60]); s["vo"] = " ".join(keep)
    return p


# ---------------------------------------------------------------- plan
PLAN = """You are the editor of a top Indian short-video agency making ONE vertical reel (Instagram Reels / YouTube Shorts)
for this business, using ONLY its own real media library below.

BUSINESS: {name} ({handle})
WHAT THEY SELL / WHO BUYS: {about}
AUDIENCE: {audience}
LANGUAGE: {language}
{angle}
HARD RULES (breaking any = the reel is thrown away):
{rules}
BRAND NOTES:
{brand}
{context}
RECENT HOOKS (do not repeat or resemble): {recent}

MEDIA LIBRARY (id | kind | seconds | fresh? | what it shows). Use FRESH items first; "AI" items are AI-generated footage:
{media}

WRITE THE REEL
- {n0}-{n1} scenes, {w0}-{w1} spoken words in total (about {s0}-{s1} s). Each scene = ONE spoken line of 3-14 words + ONE media id.
- Scene 1 is the hook: the first 4-6 spoken words carry the pain or surprise; its media is the strongest, most moving clip.
  No greeting, no intro, no logo first.
- Order: hook (pain/curiosity) -> why it hurts -> the turn -> proof on real footage -> payoff -> short CTA line.
- Every spoken line must match what its media shows (never talk about something that is not on screen).
- Prefer clips over photos (at least {min_clips} clips). A media id may be used only once. Never invent ids.
- For a clip, "from" = second to start at (skip shaky starts), within its length.
- "alt": 2 other media ids that would ALSO fit the line (used if the first one turns out not to match on screen).
- "title": at most 3 scenes get a short on-screen title (2-4 words, CAPS, for the viewer). Others "".
- One "card" scene allowed (big word + small line over its media) for the payoff; others "clip" or "image".
- Natural spoken {language} in Roman script, short words, like a friend talking. No dashes or slashes. No made-up numbers.
- The last line is the CTA: {cta}
- Caption: {caption_rule}

Return JSON:
{{"title": "internal title", "hook": "first spoken line", "angle": "one line",
 "scenes": [{{"vo": "...", "media": "c3", "alt": ["c8", "p2"], "from": 0.0, "type": "clip|image|card", "title": "", "big": "", "small": "",
             "keywords": ["one", "key word"], "motion": "push|pull|pan|tilt|punch"}}],
 "caption": "...", "hashtags": ["#..."], "music_mood": "energetic|calm|serious"}}"""


def _media_table(items):
    rows = []
    for it in sorted(items, key=lambda x: (not x["fresh"], x["kind"] != "clip", x["last"])):
        rows.append(f'{it["id"]} | {it["kind"]} | {it["secs"]:.0f}s | {"fresh" if it["fresh"] else "used recently"} | '
                    f'{"AI " if it["ai"] else ""}{it["desc"]}')
    return "\n".join(rows[:140])


def _recent_hooks(b, n=12):
    done = load(os.path.join(b["out"], "done.json"), []) or []
    return " | ".join(d.get("hook", "") for d in done[-n:] if d.get("hook")) or "none yet"


def make_plan(b, items, angle=""):
    e = b.get("edit") or {}
    w0, w1 = e.get("words", [40, 70])
    n0, n1 = e.get("scenes", [6, 10])
    ctx = []
    for rel in b.get("context_files", []):
        t = _read_rel(b, rel, 3000)
        if t:
            ctx.append(f"CONTEXT ({rel}):\n{t}")
    prompt = PLAN.format(
        name=b.get("name"), handle=b.get("handle", ""), about=b.get("about", ""), audience=b.get("audience", ""),
        language=b.get("language", "Hinglish"), angle=f"ANGLE FOR THIS REEL: {angle}" if angle else "",
        rules="\n".join("- " + r for r in b.get("rules", [])), brand=_read_rel(b, b.get("brand_file", ""), 5000) if b.get("brand_file") else "",
        context="\n".join(ctx), recent=_recent_hooks(b), media=_media_table(items),
        n0=n0, n1=n1, w0=w0, w1=w1, s0=round(w0 / 2.6), s1=round(w1 / 2.4), min_clips=e.get("min_clips", 4),
        cta=b.get("cta", "a short call to action"), caption_rule=b.get("caption_rule", "3-5 short lines + hashtags"))
    p = planner.ask(prompt)
    if not isinstance(p, dict) or not p.get("scenes"):
        raise RuntimeError("planner returned no scenes")
    return p


def fix_media(b, p, items):
    """Unknown, banned or repeated media ids -> replaced by a fresh item of the same kind."""
    by = {it["id"]: it for it in items}
    used = set()
    for s in p["scenes"]:
        it = by.get(str(s.get("media", "")).strip())
        if not it or it["id"] in used:
            want = "clip" if s.get("type") in ("clip", None, "") else "photo"
            pool = [x for x in items if x["id"] not in used and x["kind"] == want] or [x for x in items if x["id"] not in used]
            pool.sort(key=lambda x: (not x["fresh"], x["last"]))
            it = pool[0] if pool else None
            log("biz: scene media", s.get("media"), "->", it and it["id"])
        if not it:
            continue
        used.add(it["id"]); s["media"] = it["id"]
        if it["kind"] == "photo" and s.get("type") == "clip":
            s["type"] = "image"
        if it["kind"] == "clip" and s.get("type") not in ("clip", "card"):
            s["type"] = "clip"
        s["from"] = max(0.0, min(float(s.get("from") or 0), max(0.0, it["secs"] - 2.0)))
    p["scenes"] = [s for s in p["scenes"] if s.get("media") in by]
    p["ai"] = any(by[s["media"]]["ai"] for s in p["scenes"])
    return p


# ---------------------------------------------------------------- voice
def voice(b, p, job):
    raw = os.path.join(job, "vo-raw.wav")
    script = "\n".join(s["vo"] for s in p["scenes"])
    v = b.get("voice") or {}
    try:
        if v.get("engine", "gemini") != "gemini":
            raise RuntimeError("business voice engine is " + v.get("engine"))
        tts.speak(script, raw, v.get("voice", "Charon"), v.get("style", ""), v.get("lang", "hi"))
        p["voice_engine"] = "gemini"
    except Exception as e:
        log("biz: Gemini voice not available -> Edge voice:", str(e)[:120])
        mp3 = raw + ".mp3"
        sh([sys.executable, "-m", "edge_tts", "--voice", v.get("edge", "hi-IN-MadhurNeural"), "--rate", v.get("edge_rate", "+6%"),
            "--text", " ".join(s["vo"].rstrip(".") + "." for s in p["scenes"]), "--write-media", mp3], timeout=180)
        sh(["ffmpeg", "-v", "error", "-y", "-i", mp3, "-ar", "24000", "-ac", "1", raw]); os.remove(mp3)
        p["voice_engine"] = "edge"
    timed, vdur, cover = align.words_by_line(raw, [s["vo"] for s in p["scenes"]], v.get("lang", "hi"))
    save(os.path.join(job, "timing.json"), {"lines": timed, "dur": vdur, "cover": cover})
    log("biz voice", p["voice_engine"], f"{vdur:.1f}s", f"matched {cover:.0%}")
    return raw


# ---------------------------------------------------------------- assets
def _prep_clip(src, start, secs, out, crop=""):
    """9:16 cover crop (after removing baked-in black bars), muted, exactly `secs` long (loops a short clip), keyframe every 0.5 s."""
    pre = f"crop={crop}," if crop else ""
    sh(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-ss", f"{start:.2f}", "-i", src, "-t", f"{secs:.2f}", "-an",
        "-vf", f"{pre}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps=30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "15", "-pix_fmt", "yuv420p", out], timeout=300)
    return out


def _prep_photo(src, out):
    sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
        "-q:v", "3", out])
    return out


def stage(b, p, items, timed, total, job):
    by = {it["id"]: it for it in items}
    adir = os.path.join(job, "assets"); os.makedirs(adir, exist_ok=True)
    out = {}
    n = len(timed)
    for i, (s, t) in enumerate(zip(p["scenes"], timed)):
        it = by[s["media"]]
        a = 0.0 if i == 0 else t["start"] - 0.08
        bb = (timed[i + 1]["start"] - 0.08) if i + 1 < n else total
        need = max(1.0, bb - a + 0.6)
        if it["kind"] == "clip":
            v = _prep_clip(it["path"], float(s.get("from") or 0), need, os.path.join(adir, f"s{i}.mp4"), it.get("crop", ""))
            f = _frame(v, os.path.join(adir, f"s{i}.jpg"), 0.2)
            out[i] = {"video": v, **({"image": f} if f else {})}
            if s.get("type") == "card":                  # a card sits on a still of its clip
                out[i] = {"image": f}
        else:
            out[i] = {"image": _prep_photo(it["path"], os.path.join(adir, f"s{i}.jpg"))}
    return out


VERIFY = """Frames from a reel for the business "{name}" ({about}).
Each frame is labelled S1, S2, ... and is the real footage shown while this line is spoken:
{lines}
Business rules that the PICTURE must not break: {rules}
For EVERY scene: does the picture really show what its line says (a viewer would agree), and does it break no rule?
Be strict. NOT ok: a line about a smooth/clean/good result over a damaged, pitted, dirty or broken picture; a blurry, very dark,
shaky or unreadable frame; a picture unrelated to the business's work (homes, families, offices, people posing) unless the line is
literally about them; a picture that shows something different from the line (cost line over a random scene).
Return JSON {{"scenes": {{"S1": {{"ok": true|false, "why": "max 12 words"}}, ...}}}}"""


def _vision(parts, tries=4):
    import realmedia
    for k in range(tries):
        r = realmedia._gemini(parts)
        if isinstance(r, dict) and r:
            return r
        time.sleep(20 * (k + 1))                         # free keys: 429 for a minute is normal
    return None


def verify(b, p, assets):
    """{scene index: why} for every scene whose picture does not match its line (None = vision unavailable)."""
    import base64
    parts, lines = [], []
    for i, s in enumerate(p["scenes"]):
        a = assets.get(i) or {}
        f = a.get("image")
        if a.get("video"):
            f = _frame(a["video"], a["video"][:-4] + "-v.jpg", min(1.2, max(0.3, _probe_secs(a["video"]) * 0.45)))
        if not f:
            continue
        sm = f[:-4] + "-s.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-vf", "scale=360:-2", "-q:v", "4", sm], check=False)
        parts += [{"text": f"S{i + 1}"}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(sm, "rb").read()).decode()}}]
        lines.append(f'S{i + 1}: "{s["vo"]}"')
    q = VERIFY.format(name=b.get("name"), about=b.get("about", "")[:300], lines="\n".join(lines), rules=" | ".join(b.get("rules", []))[:1500])
    r = _vision([{"text": q}] + parts)
    if r is None:
        return None
    sc = r.get("scenes") or {}
    return {i: (sc.get(f"S{i + 1}") or {}).get("why", "") for i in range(len(p["scenes"]))
            if (sc.get(f"S{i + 1}") or {}).get("ok") is False}


def fix_mismatch(b, p, items, timed, total, job, bad):
    """Mismatched scene: first another part of the same clip, then the best unused item of the same kind."""
    by = {it["id"]: it for it in items}
    used = {s["media"] for s in p["scenes"]}
    tried = p.setdefault("tried", {})
    for i, why in bad.items():
        s = p["scenes"][i]
        it = by[s["media"]]
        tried.setdefault(str(i), []).append(f'{s["media"]}@{s.get("from", 0)}')
        offs = [round(it["secs"] * f, 1) for f in (0.55, 0.25, 0.8)] if it["kind"] == "clip" and it["secs"] > 5 else []
        nxt = next((o for o in offs if f"{it['id']}@{o}" not in tried[str(i)]), None)
        if nxt is not None:
            s["from"] = nxt; log("biz verify: scene", i + 1, why, "-> same clip from", nxt)
            continue
        alts = [by[a] for a in (s.get("alt") or []) if a in by and a not in used]
        pool = alts or sorted([x for x in items if x["id"] not in used and x["kind"] == it["kind"]], key=lambda x: (not x["fresh"], x["last"]))
        if not pool:
            continue
        s["media"], s["from"] = pool[0]["id"], 0.0; used.add(pool[0]["id"])
        s["type"] = "clip" if pool[0]["kind"] == "clip" and s.get("type") != "card" else ("image" if pool[0]["kind"] == "photo" else s.get("type"))
        log("biz verify: scene", i + 1, why, "-> media", pool[0]["id"], pool[0]["desc"][:60])
    return stage(b, p, items, timed, total, job)


def _poster_under_clips(doc, assets):
    """20 Nov: the first 1-2 frames of a clip rendered black at hard cuts (video not decoded yet). Its first frame as a still
    sits under every clip for its first 0.4 s, so a cut never shows black."""
    def add(m):
        i = int(m.group(1)); img = (assets.get(i) or {}).get("image")
        if not img:
            return m.group(0)
        st = float(m.group(2))
        return (f'<img class="clip bg" src="assets/{os.path.basename(img)}" data-start="{max(0.0, st - 0.05):.3f}" data-duration="0.45" '
                f'data-track-index="3" style="z-index:0">' + m.group(0))
    return re.sub(r'<video id="v(\d+)"[^>]*?data-start="([\d.]+)"', add, doc)


def _music(b):
    d = (b.get("library") or {}).get("music_dir")
    files = sorted(glob.glob(os.path.join(R(b, d), "*.mp3"))) if d else []
    if not files:
        return None
    u = _usage(b)
    files.sort(key=lambda f: u.get("music:" + os.path.basename(f), 0))
    return files[0]


# ---------------------------------------------------------------- render + qc
def render(rdir, raw, total, label):
    if os.name != "nt":
        try:
            import laptop
            if laptop.available() and laptop.render(rdir, raw, total, label):
                return
        except Exception as e:
            log("biz laptop render skipped:", str(e)[:120])
        import make as studio_make
        env = dict(os.environ, PUPPETEER_EXECUTABLE_PATH=studio_make.CHROME) if studio_make.CHROME else None
        sh(["nice", "-n", "15", "npx", "-y", "hyperframes@latest", "render", "--workers", studio_make.render_workers(),
            "--no-low-memory-mode", "--output", raw], cwd=rdir, timeout=7200, env=env)
    else:
        sh(["npx.cmd", "-y", "hyperframes@latest", "render", "--output", raw], cwd=rdir, timeout=7200)


def loudness(f):
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    lu = re.findall(r"I:\s+(-?[\d.]+) LUFS", o); pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", o)
    return (float(lu[-1]) if lu else -99.0), (float(pk[-1]) if pk else 0.0)


def check(b, p, timed, final, job):
    import qc
    rep = {"format": qc.fmt(final)}
    lu, pk = loudness(final)
    rep["loudness"] = {"lufs": lu, "peak": pk, "ok": -18 <= lu <= -10 and pk <= -0.5}
    try:
        sheet = qc.sheet(final, [((t["start"] + t["end"]) / 2) for t in timed], os.path.join(job, "sheet.jpg"))
        shown = json.loads(json.dumps(p))               # what is really on screen: the editor hides titles that repeat the voice
        for s in shown["scenes"]:
            if s.get("title") and compose._dup(s["title"], s.get("vo")):
                s["title"] = ""
        rep["vision"] = qc.vision(sheet, shown)
    except Exception as e:
        rep["vision"] = {"ok": None, "problems": [f"vision check failed: {str(e)[:100]}"]}
    cover = (load(os.path.join(job, "timing.json"), {}) or {}).get("cover", 0)
    rep["voice"] = {"matched": cover, "ok": cover >= 0.7}
    rep["rules"] = rule_problems(b, p)
    vis_ok = rep["vision"].get("ok") is True or (rep["vision"].get("ok") is None and p.get("verified"))
    if _visual_bad(rep["vision"].get("problems") or [], len(p["scenes"])):
        vis_ok = False
    rep["ok"] = bool(rep["format"].get("ok") and rep["loudness"]["ok"] and rep["voice"]["ok"] and not rep["rules"] and vis_ok)
    save(os.path.join(job, "qc.json"), rep)
    return rep


# ---------------------------------------------------------------- deliver
def _visual_bad(problems, n):
    """{scene index: problem} for problems about the PICTURE not supporting the line (caption wording nits are ignored)."""
    bad = {}
    for x in problems:
        x = str(x)
        m = re.match(r"\s*scene\s+(\d+)", x, re.I)
        if m and 0 < int(m.group(1)) <= n and re.search(r"frame shows|visual|picture|footage|contradict|does not (clearly )?(show|read|match)|blurry|dark|ambiguous", x, re.I) \
                and not re.search(r"^\s*scene\s+\d+:\s*the caption", x, re.I):
            bad[int(m.group(1)) - 1] = x[:140]
    return bad


def deliver(b, job_id, final, p, cover):
    """business "deliver" = one target or a list (first usable one wins: a git_drop whose clone is missing is skipped)."""
    ds = b.get("deliver") or {"type": "folder", "dir": os.path.join(b["out"], "ready")}
    for d in (ds if isinstance(ds, list) else [ds]):
        if d["type"] == "git_drop" and not os.path.isdir(os.path.join(os.path.expanduser(d["dir"]), ".git")):
            continue
        if d["type"] == "command" and d.get("only_if_exists") and not os.path.exists(os.path.expanduser(d["only_if_exists"])):
            continue
        return _deliver_one(b, d, job_id, final, p, cover)
    log("biz: no usable deliver target"); return False


def _deliver_one(b, d, job_id, final, p, cover):
    cap = os.path.join(os.path.dirname(final), "caption.txt")
    open(cap, "w", encoding="utf-8").write(p["caption"].strip() + "\n")
    vals = {"mp4": final, "caption": cap, "cover": cover or "", "id": job_id, "title": p.get("title", ""),
            "ai": "1" if p.get("ai") else "0", "root": b["root"], "hook": p.get("hook", "")}
    if d["type"] == "folder":
        dst = os.path.expanduser(d["dir"]); os.makedirs(dst, exist_ok=True)
        for f in (final, cap, cover):
            if f:
                shutil.copy(f, os.path.join(dst, f"{job_id}-" + os.path.basename(f)))
        log("biz delivered to folder", dst)
        return True
    if d["type"] == "git_drop":
        # the reel goes into a git repo folder (e.g. a drop repo the business's own automation imports from)
        repo = os.path.expanduser(d["dir"]); sub = os.path.join(repo, d.get("path", "drop"), f"{b['id']}-{job_id}")
        g = lambda *x: subprocess.run(["git", "-C", repo, *x], capture_output=True, text=True, timeout=300)
        g("pull", "-q", "--rebase")
        os.makedirs(sub, exist_ok=True)
        shutil.copy(final, os.path.join(sub, "reel.mp4")); shutil.copy(cap, os.path.join(sub, "caption.txt"))
        if cover and os.path.exists(cover):
            shutil.copy(cover, os.path.join(sub, "cover.jpg"))
        save(os.path.join(sub, "meta.json"), {"business": b["id"], "job": job_id, "title": p.get("title", ""), "ai": bool(p.get("ai")),
                                              "hook": p.get("hook", ""), "made": time.strftime("%Y-%m-%d %H:%M")})
        keep = float(d.get("keep_days", 5)) * 86400          # old drops leave the repo (the importer has them by then)
        base = os.path.join(repo, d.get("path", "drop"))
        for x in os.listdir(base):
            px = os.path.join(base, x)
            if os.path.isdir(px) and x != os.path.basename(sub) and time.time() - os.path.getmtime(px) > keep:
                shutil.rmtree(px)
        g("add", "-A", d.get("path", "drop"))
        g("commit", "-qm", f"studio drop {b['id']}-{job_id}")
        for _ in range(3):
            if g("push", "-q").returncode == 0:
                log("biz delivered to git drop", f"{d.get('path', 'drop')}/{b['id']}-{job_id}"); return True
            g("pull", "-q", "--rebase"); time.sleep(5)
        log("biz: git drop push failed"); return False
    if d["type"] == "command":
        cmd = [str(x).format(**vals) for x in d["cmd"]]
        cmd = [sys.executable if x == "{python}" else x for x in cmd]
        r = subprocess.run(cmd, cwd=b["root"], capture_output=True, text=True, timeout=900)
        log("biz deliver command", r.returncode, (r.stdout + r.stderr)[-400:].replace("\n", " | "))
        return r.returncode == 0
    raise SystemExit("unknown deliver type " + d["type"])


# ---------------------------------------------------------------- make
def make(b, angle="", job_id=None, frm="", send=True):
    import qc, make as studio_make
    job_id = job_id or time.strftime("%m%d-%H%M")
    job = os.path.join(b["out"], job_id); os.makedirs(job, exist_ok=True)
    order = ["plan", "voice", "assets", "compose", "render"]
    redo = set(order[order.index(frm):]) if frm in order else set()
    items = _fresh(b, index(b))
    if len([x for x in items if x["kind"] == "clip"]) < 3:
        raise SystemExit(f"{b['id']}: fewer than 3 usable clips in the library")
    pp = os.path.join(job, "plan.json")
    if "plan" in redo or not os.path.exists(pp):
        p = None
        for attempt in range(2):
            p = fix_media(b, apply_filter(b, make_plan(b, items, angle)), items)
            probs = rule_problems(b, p)
            if not probs:
                break
            log("biz plan breaks rules, asking again:", "; ".join(probs)[:300])
            angle = (angle + " | AVOID: " + "; ".join(probs))[:900]
        cap = p.get("caption", "").rstrip()
        if not re.search(r"#\w", cap):
            cap += "\n\n" + " ".join(p.get("hashtags") or b.get("hashtags", []))
        p["caption"] = re.sub(r"[ \t]*(#\w+(?:\s+#\w+)+)\s*$", r"\n\n\1", cap).strip()      # hashtags on their own line
        save(pp, p)
        redo |= {"voice", "assets", "compose", "render"}
    p = load(pp)
    rule_hold = rule_problems(b, p)
    if rule_hold:
        save(os.path.join(job, "qc.json"), {"ok": False, "rules": rule_hold}); log("biz HELD before voice:", rule_hold)
        return {"ok": False, "job": job, "held": rule_hold}
    vo = os.path.join(job, "vo-raw.wav")
    if "voice" in redo or not os.path.exists(vo):
        voice(b, p, job); save(pp, p); redo |= {"assets", "compose", "render"}
    tj = load(os.path.join(job, "timing.json"))
    timed, vdur = tj["lines"], tj["dur"]
    theme = dict(b.get("theme") or {}); theme.setdefault("handle", b.get("handle", "")); theme["lang"] = (b.get("voice") or {}).get("lang", "hi")
    total = round(vdur + 0.7 + (1.4 if theme.get("handle") else 0.0), 3)
    if "assets" in redo or not os.path.exists(os.path.join(job, "assets.json")):
        assets = stage(b, p, items, timed, total, job)
        # every scene's real frames vs its spoken line + the business rules, BEFORE render (library notes can be wrong)
        for rnd in range(3):
            bad = verify(b, p, assets)
            if bad is None:
                save(os.path.join(job, "qc.json"), {"ok": False, "why": "frame check could not run (vision unavailable)"})
                log("biz HELD: frame check could not run; no reel is delivered unchecked")
                return {"ok": False, "job": job, "held": ["vision unavailable"]}
            if not bad:
                log("biz verify: all", len(p["scenes"]), "scenes match their lines"); break
            if rnd == 2:
                save(os.path.join(job, "qc.json"), {"ok": False, "why": "scenes still mismatch", "bad": bad})
                log("biz HELD: scenes still mismatch after 2 repairs", bad); return {"ok": False, "job": job, "held": list(bad.values())}
            assets = fix_mismatch(b, p, items, timed, total, job, bad); save(pp, p)
        p["verified"] = True; save(pp, p)
        save(os.path.join(job, "assets.json"), {str(k): v for k, v in assets.items()}); redo |= {"compose", "render"}
    assets = {int(k): v for k, v in load(os.path.join(job, "assets.json")).items()}
    rdir = os.path.join(job, "render")
    if "compose" in redo or not os.path.exists(os.path.join(rdir, "index.html")):
        if os.path.isdir(rdir):
            shutil.rmtree(rdir)
        os.makedirs(os.path.join(rdir, "assets"))
        doc, cues = compose.page(p, timed, total, theme, assets)
        doc = _poster_under_clips(doc, assets)
        open(os.path.join(rdir, "index.html"), "w", encoding="utf-8").write(doc)
        for v in assets.values():
            for f in v.values():
                shutil.copy(f, os.path.join(rdir, "assets", os.path.basename(f)))
        mus = _music(b)
        save(os.path.join(job, "cues.json"), {"lufs": -14, "sfx": cues,
             **({"music": {"file": mus, "offset": 0.0, "gain_db": float((b.get("edit") or {}).get("music_db", -21)), "fade_out": 1.2}} if mus else {})})
        p["music"] = os.path.basename(mus) if mus else ""; save(pp, p)
        sh(["ffmpeg", "-v", "error", "-y", "-i", vo, "-ar", "48000", os.path.join(job, "vo.wav")])
        audio_dir = next((d for d in (os.path.join(os.environ.get("STUDIO_ASSETS", os.path.expanduser("~/studio-assets")), "audio"),
                                      os.path.join(ROOT, "assets", "audio")) if os.path.isdir(os.path.join(d, "sfx"))), os.path.join(ROOT, "assets", "audio"))
        sh([sys.executable, os.path.join(ROOT, "lib", "mix.py"), job, audio_dir])
        shutil.copy(os.path.join(job, "mix.wav"), os.path.join(rdir, "assets", "mix.wav"))
        redo.add("render")
    final = os.path.join(job, f"{b['id']}-{job_id}.mp4")
    if "render" in redo or not os.path.exists(final):
        raw = os.path.join(job, "raw.mp4"); t0 = time.time()
        render(rdir, raw, total, f"{b['id']} {job_id}")
        studio_make.remux(raw, os.path.join(job, "mix.wav"), total, final)
        os.remove(raw); log("biz rendered in", round(time.time() - t0), "s")
    rep = check(b, p, timed, final, job)
    # one repair round: scenes the final frame check rejects get other footage, then one more render
    bad = _visual_bad((rep.get("vision") or {}).get("problems") or [], len(p["scenes"]))
    if not rep["ok"] and bad and not rep["rules"] and not p.get("final_repair"):
        p["final_repair"] = True
        log("biz final check rejected", len(bad), "scene(s) -> new footage + one more render:", bad)
        assets = fix_mismatch(b, p, items, timed, total, job, bad); save(pp, p)
        save(os.path.join(job, "assets.json"), {str(k): v for k, v in assets.items()})
        return make(b, angle, job_id, "compose", send)
    cover = os.path.join(job, "cover.jpg")
    _frame(final, cover, 0.6)
    if cover and os.path.exists(cover):
        sh(["ffmpeg", "-v", "error", "-y", "-ss", "0.6", "-i", final, "-frames:v", "1", "-q:v", "2", cover])
    done = load(os.path.join(b["out"], "done.json"), []) or []
    row = {"job": job_id, "title": p.get("title"), "hook": p.get("hook") or p["scenes"][0]["vo"], "ok": rep["ok"],
           "made": time.strftime("%Y-%m-%d %H:%M"), "ai": p.get("ai"), "media": [s["media"] for s in p["scenes"]]}
    done = [d for d in done if d["job"] != job_id] + [row]
    log("biz qc", "OK" if rep["ok"] else "HELD", json.dumps({k: rep[k] for k in ("format", "loudness", "voice")})[:300],
        "rules:", rep["rules"], "vision:", (rep.get("vision") or {}).get("problems"))
    if rep["ok"]:
        u = _usage(b)
        by = {it["id"]: it for it in items}
        for s in p["scenes"]:
            u[by[s["media"]]["file"]] = time.time()
        if p.get("music"):
            u["music:" + p["music"]] = time.time()
        save(os.path.join(b["out"], "usage.json"), u)
        if send:
            row["delivered"] = deliver(b, job_id, final, p, cover)
    save(os.path.join(b["out"], "done.json"), done)
    return {"ok": rep["ok"], "final": final, "job": job, "qc": rep}


def need(b):
    """(should_make, why). business "auto": {"min_pending": 3, "max_per_day": 2, "max_waiting": 3, "hours": [7, 22],
    "pending": {"file": "social/queue.json", "list": "posts", "done_field": "posted", "require": "video"},
    "queue_id": "reel-studio-{business}-{job}"}"""
    a = b.get("auto") or {}
    if not a:
        return False, "no auto settings"
    h = int(time.strftime("%H"))
    lo, hi = a.get("hours", [0, 24])
    if not lo <= h < hi:
        return False, f"outside hours {lo}-{hi}"
    done = load(os.path.join(b["out"], "done.json"), []) or []
    today = time.strftime("%Y-%m-%d")
    made_today = [d for d in done if str(d.get("made", "")).startswith(today) and d.get("ok")]
    if len(made_today) >= a.get("max_per_day", 2):
        return False, f"{len(made_today)} made today"
    pend, ids = 0, set()
    pc = a.get("pending") or {}
    if pc.get("file"):
        q = load(R(b, pc["file"]), {}) or {}
        lst = q.get(pc.get("list", "posts"), []) if isinstance(q, dict) else q
        for it in lst:
            if isinstance(it, dict):
                ids.add(str(it.get("id")))
                if not it.get(pc.get("done_field", "posted")) and (not pc.get("require") or it.get(pc["require"])):
                    pend += 1
    qid = a.get("queue_id", "{business}-{job}")
    waiting = [d for d in done if d.get("delivered") and qid.format(business=b["id"], job=d["job"]) not in ids
               and time.time() - time.mktime(time.strptime(d["made"], "%Y-%m-%d %H:%M")) < 3 * 86400]
    if len(waiting) >= a.get("max_waiting", 3):
        return False, f"{len(waiting)} delivered reels not in the queue yet"
    if pend + len(waiting) >= a.get("min_pending", 3):
        return False, f"{pend} pending + {len(waiting)} on the way"
    return True, f"only {pend} pending + {len(waiting)} on the way"


def status(b):
    items = _fresh(b, index(b, describe=False))
    clips = [x for x in items if x["kind"] == "clip"]
    print(json.dumps({"business": b["name"], "root": b["root"], "clips": len(clips), "photos": len(items) - len(clips),
                      "fresh_clips": sum(x["fresh"] for x in clips), "done": (load(os.path.join(b["out"], "done.json"), []) or [])[-5:]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("business"); ap.add_argument("cmd", choices=["index", "make", "status", "auto"])
    ap.add_argument("--angle", default=""); ap.add_argument("--job"); ap.add_argument("--from", dest="frm", default="")
    ap.add_argument("--no-deliver", action="store_true")
    a = ap.parse_args()
    B = business(a.business)
    ensure_omniroute()
    if a.cmd == "index":
        it = index(B)
        print(json.dumps([{k: x[k] for k in ("id", "kind", "secs", "ai", "desc")} for x in it], ensure_ascii=False, indent=0)[:6000])
    elif a.cmd == "status":
        status(B)
    elif a.cmd == "auto":
        go, why = need(B)
        log("biz auto", B["id"], "MAKE" if go else "skip", "-", why)
        if go:
            r = make(B, a.angle, a.job, a.frm, not a.no_deliver)
            if not r.get("ok"):                            # held -> one more try with a fresh plan (new job)
                log("biz auto: held, trying a new reel once")
                r = make(B, a.angle, time.strftime("%m%d-%H%M") + "r", "", not a.no_deliver)
            print(json.dumps({k: v for k, v in r.items() if k != "qc"}, ensure_ascii=False))
    else:
        print(json.dumps({k: v for k, v in make(B, a.angle, a.job, a.frm, not a.no_deliver).items() if k != "qc"}, ensure_ascii=False))
