"""Pre-render check (owner 17 Nov: "reviewing at the end and re-rendering takes a lot of time; find an efficient way").
Runs right after compose, BEFORE the slow render (the composed page is a web page, so stills cost seconds, not minutes):
  1. hyperframes check --json: layout audit on a seek grid (text overflow, clipped, held overlaps, off-canvas), JS errors
  2. hyperframes snapshot at every scene's entrance end + middle -> one contact sheet
  3. vision review of the stills, PER SCENE, with a strict checklist (empty centre, overlap, cut text, wrong language,
     unreadable, picture does not fit the line)
Returns {"ok", "bad": {scene_index: [problems]}, "score", "layout": [...], "sheet"}. make.py repairs the bad scenes
(visual fields only; the voice stays) and runs this again, at most twice, then renders once.
  python engine/preflight.py <channel> <job>"""
import base64, glob, json, os, re, shutil, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import OUT, ROOT, load, save, log
import tts, llm

MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
LAYOUT_CODES = {"content_overlap", "text_overflow", "text_clipped", "canvas_overflow", "panel_out_of_canvas", "escaped_container",
                "occluded_text", "text_occluded"}


def _npx(args, cwd, timeout=900):
    chrome = os.environ.get("PUPPETEER_EXECUTABLE_PATH") or next(iter(sorted(glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux-arm64/chrome-headless-shell")))), "")
    env = dict(os.environ, PUPPETEER_EXECUTABLE_PATH=chrome, HYPERFRAMES_BROWSER_PATH=chrome, HYPERFRAMES_NO_TELEMETRY="1")
    r = subprocess.run(["nice", "-n", "15", "npx", "-y", "hyperframes@latest"] + args, cwd=cwd, env=env,
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def _scene_of(t, timed):
    k = 0
    for i, L in enumerate(timed):
        if L["start"] - 0.1 <= t:
            k = i
    return k


def layout(rdir, timed):
    rc, out, err = _npx(["check", "--json", "--samples", "16", "--timeout", "30000", "--no-contrast"], rdir)
    try:
        d = json.loads(out[out.index("{"):])
    except Exception:
        log("preflight: check output unreadable", (err or out)[-200:]); return [], []
    found, runtime = [], []
    for f in (d.get("layout") or {}).get("findings", []) if isinstance(d.get("layout"), dict) else (d.get("layout") or []):
        sev, code = f.get("severity"), f.get("code")
        if sev not in ("error", "warning") or code not in LAYOUT_CODES:
            continue
        sel = f.get("selector") or ""
        if re.search(r"#c\d+|\.cap|caption", sel):            # caption track: own checks
            continue
        t = f.get("time") if f.get("time") is not None else (f.get("sample") or {}).get("time", 0)
        found.append({"scene": _scene_of(float(t or 0), timed), "code": code, "selector": sel, "msg": (f.get("message") or "")[:160]})
    for f in (d.get("runtime") or {}).get("findings", []) if isinstance(d.get("runtime"), dict) else []:
        if f.get("severity") == "error":
            runtime.append((f.get("message") or "")[:160])
    return found, runtime


def stills(rdir, timed, total, out_jpg):
    ts = []
    for i, L in enumerate(timed):
        a = L["start"]; b = timed[i + 1]["start"] if i + 1 < len(timed) else total - 1.5
        ts += [round(a + min(1.1, (b - a) * 0.45), 2), round((a + b) / 2 + 0.3, 2)]
    tmp = os.path.join(rdir, ".pre")
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    rc, out, err = _npx(["snapshot", "--at", ",".join(f"{t:.2f}" for t in ts), "--no-end", "--output", tmp], rdir)
    pngs = sorted(glob.glob(os.path.join(tmp, "*.png")), key=lambda p: float((re.findall(r"(\d+(?:\.\d+)?)", os.path.basename(p)) or ["0"])[-1]))
    if len(pngs) < len(ts) // 2:
        log("preflight: snapshot gave", len(pngs), "of", len(ts), (err or out)[-200:]); return None
    for k, p in enumerate(pngs):
        shutil.copy(p, os.path.join(tmp, f"f{k:03d}.png"))
    cols = 8
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(tmp, "f%03d.png"), "-vf",
                    f"scale=300:-1,drawtext=text='%{{eif\\:n/2+1\\:d}}':x=10:y=10:fontsize=34:fontcolor=yellow:box=1:boxcolor=black@0.6,tile={cols}x{-(-len(pngs) // cols)}",
                    "-frames:v", "1", out_jpg], check=False)
    return out_jpg if os.path.exists(out_jpg) else None


def vision(sheet, plan, lang):
    desc = "\n".join(f"scene {i + 1} ({s.get('type')}): voice says \"{s.get('vo', '')}\"; on-screen fields "
                     f"{json.dumps({k: v for k, v in s.items() if k not in ('vo', 'prompt', 'keywords', 'motion')}, ensure_ascii=False)[:220]}"
                     for i, s in enumerate(plan["scenes"]))
    prompt = f"""You are the strictest finishing editor at a premium tech-explainer studio. The sheet shows two stills per scene,
in order, each labelled with its scene number (yellow). Captions at the lower third are expected and show only a PART of the spoken line (one phrase at a time), so a caption with missing words is NOT a problem; a small mono top bar
(page name left, tag right) is expected; a small yellow tag pill above the main visual is expected.
Scenes:
{desc}
On-screen language must be {"English only" if lang == "en" else "Hinglish in Roman letters (English tech words are fine)"}.
For EACH scene, report only real problems a viewer would notice:
- EMPTY: the centre of the frame has no main visual (just a dark gradient) in the middle still
- OVERLAP: text touching/covering other text or a tag, captions colliding with the visual
- CUT: text cut at the frame edge or inside its box, words missing
- READ: text too small/faint to read on a phone, or too much text
- LANG: wrong language on screen
- FIT: the visual does not match what the voice says, or looks broken/glitchy
- DUP: the same words shown twice at once
Return JSON {{"score": 1-10, "scenes": [{{"n": <scene number>, "problems": ["CODE: short description"]}}]}}
List only scenes that have problems."""
    b64 = base64.b64encode(open(sheet, "rb").read()).decode()
    body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}}
    for m in MODELS:
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key()})
            d = json.load(urllib.request.urlopen(r, timeout=180))
            return llm.parse_json("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
        except Exception as e:
            log("preflight vision fail", m, str(e)[:120])
    return None


def run(job_dir, plan, timed, total, lang):
    rdir = os.path.join(job_dir, "render")
    t0 = time.time()
    bad, lay, rt = {}, [], []
    try:
        lay, rt = layout(rdir, timed)
    except Exception as e:
        log("preflight: layout check failed", str(e)[:150])
    for f in lay:
        bad.setdefault(f["scene"], []).append(f"OVERLAP/CUT (layout audit): {f['code']} on {f['selector']}")
    sheet = None
    try:
        sheet = stills(rdir, timed, total, os.path.join(job_dir, "preflight-sheet.jpg"))
    except Exception as e:
        log("preflight: stills failed", str(e)[:150])
    v = vision(sheet, plan, lang) if sheet else None
    for s in (v or {}).get("scenes", []) or []:
        try:
            k = int(s.get("n")) - 1
        except Exception:
            continue
        if 0 <= k < len(plan["scenes"]) and s.get("problems"):
            bad.setdefault(k, []).extend(str(p)[:200] for p in s["problems"])
    res = {"ok": not bad and not rt, "bad": {str(k): v_ for k, v_ in sorted(bad.items())}, "runtime": rt,
           "score": (v or {}).get("score"), "layout": lay, "sheet": sheet, "secs": round(time.time() - t0)}
    save(os.path.join(job_dir, "preflight.json"), res)
    log("preflight", os.path.basename(job_dir), "OK" if res["ok"] else f"{len(bad)} scene(s) to fix: " +
        " | ".join(f"s{int(k) + 1}: {p[0][:70]}" for k, p in list(res["bad"].items())[:4]), f"score {res['score']}", f"({res['secs']} s)")
    return res


REPAIR = """You are fixing scenes of a planned vertical tech video that FAILED the pre-render check. The voice is already
recorded: NEVER change "vo". You may change only the visual fields of the listed scenes: type (only to a type that needs
no new image: stat, ui, chart, flow, compare, title, chat, code), title, big, sub, label, value, rows, items, nodes,
points, end_label, lines, messages. Make text SHORTER rather than smaller (titles <= 3 words, labels <= 14 letters,
row labels <= 12 letters, values <= 8 characters, max 4 rows/nodes). Keep facts true. On-screen language: {lang}.
Scenes to fix (index: current scene JSON -> problems):
{items}
Return JSON {{"scenes": {{"<index>": {{...the full fixed scene, same vo...}}}}}}"""


def repair(plan, bad, lang):
    import plan as planner
    items = "\n".join(f"{k}: {json.dumps(plan['scenes'][int(k)], ensure_ascii=False)} -> {probs}" for k, probs in bad.items())
    r = planner.ask(REPAIR.format(lang="English" if lang == "en" else "Hinglish (Roman)", items=items), max_tokens=3000) or {}
    n = 0
    for k, s in (r.get("scenes") or {}).items():
        try:
            k = int(k)
        except Exception:
            continue
        if 0 <= k < len(plan["scenes"]) and isinstance(s, dict):
            old = plan["scenes"][k]
            new = dict(old); new.update({kk: vv for kk, vv in s.items() if kk not in ("vo", "prompt")})
            if old.get("type") in ("object", "clip") and new.get("type") not in ("object", "clip"):
                pass                                        # dropping the picture is allowed; adding one is not
            elif new.get("type") in ("object", "clip") and old.get("type") not in ("object", "clip"):
                new["type"] = old["type"]
            new["vo"] = old["vo"]
            plan["scenes"][k] = new; n += 1
    return n


if __name__ == "__main__":
    cid, job = sys.argv[1], sys.argv[2]
    jd = os.path.join(OUT, cid, job)
    p = load(os.path.join(jd, "plan.json")); tj = load(os.path.join(jd, "timing.json"))
    total = tj["dur"] + 2.1
    print(json.dumps(run(jd, p, tj["lines"], total, p.get("lang", "hi")), ensure_ascii=False, indent=1))
