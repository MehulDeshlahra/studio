"""CutCapsule: long video -> the best short moments -> finished vertical clips (owner 19 Nov: "just provide a YT link,
it sees the best moments, suggests clips and auto-creates them"). Research: knowledge/clipping.md.

  python engine/clipper.py <cid> <youtube url> [--n 4] [--test] [--campaign KEY]

1 moments   Gemini watches the YouTube URL (no download) and returns the N best standalone moments (20-59 s) with a hook
            title, why it works and a score.
2 fetch     the laptop downloads only those parts (YouTube blocks this server): engine/laptop.fetch, 4 s padding.
3 cut       faster-whisper word times: start on the first word of a sentence, end on a sentence end (no cut mid-word).
4 render    ffmpeg 1080x1920: blurred fill of the same frame, the video full width in the middle, hook title on top,
            3-word captions with the spoken word highlighted, -14 LUFS.
5 hand-off  each clip = its own job (plan.json, review.json, cover.jpg, done.json row "made") -> Telegram for approval.

PERMISSION GATE: clips are posted only from sources the page may use: channels/<cid>/sources.json (a paid clipping
campaign or a creator who allows clipping). Anything else runs only with --test (made, never posted): reposting other
people's videos without permission gets copyright strikes and can close the account."""
import argparse, json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, ASSETS, log, load, save, channel, telegram, note_problem
import llm

FONTS = os.path.join(ASSETS, "fonts")
W, H = 1080, 1920

MOMENTS = """You are the best short-form video clipper in the world. Watch this whole video and pick the {n} best moments to
post as standalone Reels / Shorts for the page "{page}" ({about}).
A great moment: hooks in its first 2 seconds (a bold claim, a shocking line, a laugh, a fight, a reveal, a question),
makes sense with no context, has ONE clear payoff, and ends right after it. Prefer moments where someone reacts or says
something quotable over quiet stretches. Each moment is 20 to 59 seconds long. Moments must not overlap.
{rules}
Return JSON:
{{"video": {{"title": "<video title>", "speaker": "<who is talking / the creator>", "language": "<main spoken language>"}},
 "moments": [{{"start": "<MM:SS or HH:MM:SS where the hook begins>", "end": "<MM:SS where the payoff ends>",
   "hook": "<on-screen title, 3-7 words, the curiosity or the claim, in the video's language (Hinglish in Roman script for Hindi)>",
   "why": "<why people will watch to the end, one line>", "score": <1-10 viral potential>,
   "caption": "<Instagram caption, one or two short lines, no hashtags>", "tags": ["<3-5 hashtags without #>"]}}]}}"""


def ts(x):
    """'1:02:03' / '02:03' / 123 -> seconds."""
    if isinstance(x, (int, float)):
        return float(x)
    parts = [float(p) for p in re.findall(r"\d+(?:\.\d+)?", str(x))][-3:]
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def permitted(cid, url, campaign=None):
    """The source entry that allows this URL (campaign or creator permission), else None."""
    src = load(os.path.join(ROOT, "channels", cid, "sources.json"), {}) or {}
    for key, s in (src.get("sources") or {}).items():
        if campaign and key != campaign:
            continue
        if not s.get("active", True):
            continue
        pats = s.get("match") or []
        if any(p and p.lower() in url.lower() for p in pats) or (campaign and key == campaign):
            return dict(s, key=key)
    return None


def find_moments(ch, url, n, source=None):
    rules = ""
    if source:
        rules = "CAMPAIGN RULES (every clip must follow them):\n- " + "\n- ".join(source.get("rules") or []) + "\n"
    rules += "- " + "\n- ".join((ch.get("clip") or {}).get("rules") or [])
    p = MOMENTS.format(n=n + 2, page=ch.get("name", ch["id"]), about=ch.get("format", ""), rules=rules)
    d = llm.watch(url, p, max_tokens=4000)
    ms = []
    for m in d.get("moments") or []:
        try:
            a, b = ts(m["start"]), ts(m["end"])
        except Exception:
            continue
        if b - a < 12:
            b = a + 30
        if b - a > 62:
            b = a + 58
        if any(not (b <= x["a"] or a >= x["b"]) for x in ms):
            continue
        ms.append({"a": a, "b": b, "hook": str(m.get("hook") or "")[:60], "why": str(m.get("why") or "")[:200],
                   "score": float(m.get("score") or 5), "caption": str(m.get("caption") or "")[:300],
                   "tags": [re.sub(r"[^\w]", "", str(t)) for t in (m.get("tags") or [])][:5]})
    ms.sort(key=lambda m: -m["score"])
    return d.get("video") or {}, ms[:n]


def words(mp4, lang=None):
    """faster-whisper words [(start, end, text)] of a clip (CPU int8, small model; ~1 min of audio in ~1 min)."""
    from faster_whisper import WhisperModel
    wav = mp4 + ".wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-ac", "1", "-ar", "16000", wav], check=True, timeout=300)
    segs, info = WhisperModel("small", compute_type="int8").transcribe(wav, language=lang, word_timestamps=True, beam_size=4,
                                                                     vad_filter=True)
    out = [(w.start, w.end, w.word.strip()) for s in segs for w in (s.words or []) if w.word.strip()]
    os.remove(wav)
    return out, info.language


def trim(W_, want_a, want_b, pad):
    """Start on a sentence start at/after the asked start (within 3 s), end on a sentence end near the asked end."""
    if not W_:
        return want_a, want_b
    ends = {i for i, w in enumerate(W_) if re.search(r"[.!?…]$", w[2])}
    a_i = next((i for i, w in enumerate(W_) if w[0] >= want_a - 0.6 and (i == 0 or (i - 1) in ends or W_[i][0] - W_[i - 1][1] > 0.6)), None)
    if a_i is None or W_[a_i][0] > want_a + 3:
        a_i = next((i for i, w in enumerate(W_) if w[0] >= want_a - 0.3), 0)
    b_cands = [i for i in ends if i > a_i and abs(W_[i][1] - want_b) < 6]
    b_i = min(b_cands, key=lambda i: abs(W_[i][1] - want_b)) if b_cands else max(
        (i for i, w in enumerate(W_) if w[1] <= want_b + 1.5), default=len(W_) - 1)
    a = max(0.0, W_[a_i][0] - 0.12)
    b = W_[b_i][1] + 0.35
    if b - a < 10:
        a, b = want_a, want_b
    return a, b


def _ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass(path, hook, W_, a, b, accent="&H0030D8FF&"):
    """Hook title on top (whole clip) + 3-word caption groups below the video, the spoken word in the accent colour."""
    esc = lambda s: str(s).replace("{", "(").replace("}", ")").replace("\n", " ")
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
             "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             "Style: Hook,Anton,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,3,18,0,5,70,70,0,1",
             # the ExtraBold file (fontsource mirror) names its family "Montserrat Thin"; its weight is ExtraBold (205)
             "Style: Cap,Montserrat Thin,76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1",
             "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    dur = b - a
    if hook:
        lines.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(dur)},Hook,,0,0,0,,{{\\pos({W // 2},400)\\fad(120,0)}}{esc(hook.upper())}")
    ws = [(max(0, s - a), max(0, e - a), t) for s, e, t in W_ if e > a and s < b]
    groups, cur = [], []
    for w in ws:
        cur.append(w)
        if len(cur) == 3 or re.search(r"[.!?,…]$", w[2]):
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)
    for gi, g in enumerate(groups):
        g_end = groups[gi + 1][0][0] if gi + 1 < len(groups) else min(dur, g[-1][1] + 0.4)
        for k, w in enumerate(g):
            st = w[0]
            en = g[k + 1][0] if k + 1 < len(g) else g_end
            if en <= st:
                continue
            txt = " ".join((f"{{\\c{accent}}}{esc(x[2]).upper()}{{\\c&H00FFFFFF&}}" if j == k else esc(x[2]).upper())
                           for j, x in enumerate(g))
            lines.append(f"Dialogue: 0,{_ass_time(st)},{_ass_time(en)},Cap,,0,0,0,,{{\\pos({W // 2},1440)}}{txt}")
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def render(src, a, b, assf, out):
    """Blurred cover background + the video full width in the middle + captions; loudness -14 LUFS."""
    d = b - a
    fs = FONTS.replace("\\", "/").replace(":", "\\:")
    af = assf.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    vf = (f"[0:v]split=2[bg][fg];"
          f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=28,eq=brightness=-0.18:saturation=0.85[bgb];"
          f"[fg]scale={W}:-2:flags=lanczos[fgs];"
          f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2+40,ass='{af}':fontsdir='{fs}',format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", src, "-filter_complex", vf,
                    "-map", "[v]", "-map", "0:a?", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "20", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", out],
                   check=True, timeout=1800)
    return out


def probe(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", f],
                       capture_output=True, text=True, timeout=60)
    j = json.loads(r.stdout or "{}")
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"dur": round(float((j.get("format") or {}).get("duration") or 0), 2), "w": v.get("width"), "h": v.get("height"),
            "audio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


def lufs(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def make(cid, url, n=4, test=False, campaign=None):
    ch = channel(cid)
    if not ch:
        raise SystemExit(f"no page {cid}")
    src = permitted(cid, url, campaign)
    if not src and not test:
        msg = (f"{cid}: {url} is not in channels/{cid}/sources.json (no clipping campaign or creator permission). "
               "Made as a TEST only: it will not be posted.")
        log(msg); test = True
    base = time.strftime("%m%d-%H%M")
    sdir = os.path.join(OUT, cid, "sources", base)
    os.makedirs(sdir, exist_ok=True)
    log("clipper:", cid, url, "n", n, "test" if test else f"source {src['key']}")
    video, ms = find_moments(ch, url, n, src)
    save(os.path.join(sdir, "moments.json"), {"url": url, "video": video, "moments": ms, "source": src, "test": test})
    if not ms:
        raise RuntimeError("no moments found")
    log("clipper: moments", [(round(m["a"]), round(m["b"]), m["hook"], m["score"]) for m in ms])
    PAD = 4.0
    import laptop
    info, files = laptop.fetch(url, [(max(0, m["a"] - PAD), m["b"] + PAD) for m in ms], label=f"{cid} {base}")
    save(os.path.join(sdir, "info.json"), info)
    done_p = os.path.join(ROOT, "channels", cid, "done.json")
    made = []
    for i, (m, f) in enumerate(zip(ms, files)):
        if not f:
            continue
        jid = f"{base}-c{i + 1}"
        jd = os.path.join(OUT, cid, jid)
        os.makedirs(jd, exist_ok=True)
        raw = os.path.join(jd, "source.mp4")
        shutil.move(f, raw)
        off = max(0, m["a"] - PAD)
        try:
            W_, lang = words(raw)
        except Exception as e:
            log("clipper: whisper failed", str(e)[:120]); W_, lang = [], None
        a, b = trim(W_, m["a"] - off, m["b"] - off, PAD)
        assf = os.path.join(jd, "captions.ass")
        ass(assf, m["hook"], W_, a, b)
        out = os.path.join(jd, f"{cid}-{jid}.mp4")
        render(raw, a, b, assf, out)
        q = probe(out)
        q["lufs"] = lufs(out)
        probs = []
        if not (12 <= q["dur"] <= 62):
            probs.append(f"length {q['dur']} s")
        if (q["w"], q["h"]) != (W, H):
            probs.append(f"size {q['w']}x{q['h']}")
        if not q["audio"]:
            probs.append("no audio")
        if len(W_) < 15:
            probs.append("almost no speech found (captions empty)")
        sheet = os.path.join(jd, "sheet.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", f"fps={6 / max(1, q['dur'])},scale=270:480,tile=6x1", "-frames:v", "1", sheet],
                       timeout=120)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.2", "-i", out, "-frames:v", "1", "-q:v", "2", os.path.join(jd, "cover.jpg")], timeout=60)
        who = info.get("channel") or info.get("uploader") or video.get("speaker") or ""
        credit = f"🎥 Credit: {who}" + (f" ({info.get('webpage_url') or url})" if not src or src.get("credit_link", True) else "")
        req = (src or {}).get("caption_add") or ""
        tags = list(dict.fromkeys([t for t in m["tags"] if t] + [t.lstrip("#") for t in (ch.get("hashtags_base") or [])]))[:6]
        caption = "\n\n".join(x for x in [m["caption"], req, credit] if x)
        plan = {"title": m["hook"], "topic": m["hook"], "caption": caption, "hashtags": ["#" + t for t in tags], "lang": lang or "",
                "clip": {"url": url, "start": round(off + a, 2), "end": round(off + b, 2), "why": m["why"], "score": m["score"],
                         "source": (src or {}).get("key"), "test": test, "video": video, "info": info},
                "seo": {"ig": {"caption": caption, "hashtags": ["#" + t for t in tags]},
                        "fb": {"caption": caption, "hashtags": ["#" + t for t in tags]},
                        "yt": {"title": m["hook"][:90], "description": caption, "tags": tags}},
                "scenes": []}
        save(os.path.join(jd, "plan.json"), plan)
        save(os.path.join(jd, "qc.json"), {"format": q, "ok": not probs})
        rv = {"ok": not probs and not test, "problems": probs + (["TEST: no clipping permission for this source, never post"] if test else []),
              "minor": [], "checks": {"format": q, "vision": {"score": None}}}
        save(os.path.join(jd, "review.json"), rv)
        save(os.path.join(jd, "meta.json"), {"channel": cid, "job": jid, "topic": m["hook"], "stage": "done", "source_url": url,
                                             "kind": "clip", "test": test})
        done = load(done_p, []) or []
        if not any(d["job"] == jid for d in done):
            done.append({"job": jid, "topic": m["hook"], "title": m["hook"], "status": "held" if (probs or test) else "made",
                         "review": rv["problems"][:4], "clip": {"url": url, "start": plan["clip"]["start"], "end": plan["clip"]["end"]}})
            save(done_p, done)
        if probs:
            note_problem(cid, jid, probs, "clipper")
        made.append((jid, q, probs))
        log("clipper: made", jid, q, probs or "ok")
        if rv["ok"]:
            import send
            send.send(cid, jid)
    if test and made:
        telegram(f"✂️ {cid} TEST clips made from {url} (not for posting: no permission entry): " + ", ".join(j for j, _, _ in made))
    for f in files:                                   # the laptop's download folder (parts already moved into the jobs)
        if f:
            shutil.rmtree(os.path.dirname(os.path.dirname(f)), ignore_errors=True); break
    return made


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cid"); ap.add_argument("url")
    ap.add_argument("--n", type=int, default=4); ap.add_argument("--test", action="store_true"); ap.add_argument("--campaign")
    a = ap.parse_args()
    r = make(a.cid, a.url, a.n, a.test, a.campaign)
    print(json.dumps([{"job": j, "format": q, "problems": p} for j, q, p in r]))
