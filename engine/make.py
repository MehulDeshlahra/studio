"""Make one video for a channel, end to end:
  python engine/make.py <channel> ["topic"] [--job ID] [--from STAGE]
Stages: research -> plan -> voice -> assets -> compose -> mix -> render -> qc -> send.
Each stage writes into ~/studio-out/<channel>/<job>/ and is skipped when its output already exists (rerun-safe)."""
import argparse, json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, ASSETS, OUT, PY, log, sh, load, save, channel, telegram, dur
import research, plan as planner, tts, align, muse, compose, qc

CHROME = os.environ.get("PUPPETEER_EXECUTABLE_PATH",
                        os.path.expanduser("~/.cache/ms-playwright/chromium-1248/chrome-linux-arm64/chrome"))


def pick_topic(ch):
    done = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), [])
    used = {d["topic"].lower() for d in done}
    for t in ch.get("topics_backlog", []):
        if t.lower() not in used:
            return t
    import llm
    t = llm.text(f"Suggest ONE new topic for this channel, not in this list. Channel: {ch['format']}. "
                 f"Done: {sorted(used)}. Return JSON {{\"topic\": \"...\"}}", json_mode=True)["topic"]
    return t


def stage_assets(ch, p, job):
    look = ch.get("visuals", {}).get("look", "")
    adir = os.path.join(job, "assets"); os.makedirs(adir, exist_ok=True)
    got = load(os.path.join(job, "assets.json"), {})
    last_img = None
    for i, s in enumerate(p["scenes"]):
        k = str(i)
        if k in got and all(os.path.exists(v) for v in got[k].values()):
            last_img = got[k].get("image", last_img); continue
        a = {}
        if s.get("prompt") and s["type"] in ("image", "clip", "card", "flow", "clue", "choice"):
            prompt = s["prompt"] + (". " + look if look and look.lower()[:20] not in s["prompt"].lower() else "") + \
                ". Vertical 9:16, no text, no letters, no logos, no watermark."
            if s["type"] == "flow":
                prompt = "Soft, simple, uncluttered background for a diagram: " + prompt
            f = os.path.join(adir, f"s{i}.webp")
            img = (muse.image(prompt, f) or muse.cloudflare(prompt, os.path.join(adir, f"s{i}.jpg"))
                   or muse.pollinations(prompt, os.path.join(adir, f"s{i}p.jpg")))
            if img:
                a["image"] = img
            elif last_img:
                a["image"] = last_img; log("scene", i, "reuses the previous image")
            if s["type"] == "clip" and a.get("image"):
                v = muse.video(s["prompt"] + ". Smooth natural motion, no text, no subtitles, no speech.", a["image"],
                               os.path.join(adir, f"s{i}.mp4"))
                if v:
                    a["video"] = v
                else:
                    s["type"] = "image"; s["motion"] = "push"; log("scene", i, "clip failed -> still image")
        got[k] = a
        last_img = a.get("image", last_img)
        save(os.path.join(job, "assets.json"), got)
    save(os.path.join(job, "plan.json"), p)
    return {int(k): v for k, v in got.items()}


def _loud(f):
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", o)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", o)[-1])


def remux(raw, mix, total, out):
    """Master to -14 LUFS with true peak <= -1.5 AFTER the AAC encode (the encoder adds 2-3 dB overshoot):
    gain + brickwall limiter at -4.4 dBFS, measured on the encoded file, corrected once."""
    lim = mix.replace(".wav", "-tp.wav")
    L0, _ = _loud(mix)
    gain = -14 - L0 + 2.8
    for _ in range(3):
        sh(["ffmpeg", "-v", "error", "-y", "-i", mix, "-af",
            f"apad=whole_dur={total:.3f},volume={gain:.2f}dB,alimiter=limit=0.6:level=false:attack=1:release=40,aresample=48000",
            "-c:a", "pcm_s16le", lim])
        sh(["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", lim, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", "-movflags", "+faststart", out])
        L, tp = _loud(out)
        log("master", f"gain {gain:+.1f} dB -> {L} LUFS, TP {tp}")
        if abs(L + 14) <= 0.6 and tp <= -1.5:
            break
        gain += (-14 - L) if tp <= -1.5 else -1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel"); ap.add_argument("topic", nargs="?")
    ap.add_argument("--job"); ap.add_argument("--from", dest="frm", default="")
    ap.add_argument("--no-send", action="store_true")
    ap.add_argument("--lang", default="", help="en = English page version (voice, captions, handle_en)")
    a = ap.parse_args()
    ch = channel(a.channel)
    if a.lang == "en":
        ch["lang"] = "en"
        ch["handle"] = ch.get("handle_en", "")
        ch["voice"] = dict(ch["voice"], style=ch["voice"].get("style_en", ch["voice"].get("style", "")))
    theme = dict(ch.get("theme", {}))
    theme["lang"] = ch.get("lang", "hi")
    if ch.get("handle") and not ch["handle"].startswith("TBD"):
        theme["handle"] = ch["handle"]
    job_id = a.job or time.strftime("%m%d-%H%M")
    job = os.path.join(OUT, ch["id"], job_id); os.makedirs(job, exist_ok=True)
    order = ["research", "plan", "voice", "assets", "compose", "mix", "render", "qc", "send"]
    redo = set(order[order.index(a.frm):]) if a.frm in order else set()
    meta = load(os.path.join(job, "meta.json"), {})
    topic = a.topic or meta.get("topic") or pick_topic(ch)
    meta.update({"channel": ch["id"], "job": job_id, "topic": topic}); save(os.path.join(job, "meta.json"), meta)
    log("job", ch["id"], job_id, topic)

    # 1 research
    rp = os.path.join(job, "research.json")
    if "research" in redo or not os.path.exists(rp):
        qs = [topic, topic + " shorts", topic + " explained"]
        r = research.run(topic, qs, job)
    r = load(rp)
    rtext = research.summary(r)
    # 2 plan
    pp = os.path.join(job, "plan.json")
    if "plan" in redo or not os.path.exists(pp):
        p = planner.make(ch, topic, rtext); save(pp, p)
    p = load(pp)
    # 3 voice (one request)
    vo = os.path.join(job, "vo-raw.wav")
    if "voice" in redo or not os.path.exists(vo):
        script = "\n".join(s["vo"] for s in p["scenes"])
        tts.speak(script, vo, ch["voice"].get("voice", "Charon"), ch["voice"].get("style", ""), p.get("lang") or ch.get("lang", "hi"))
    import pace
    paced = os.path.join(job, "vo-paced.wav")
    if "voice" in redo or not os.path.exists(paced):
        nw = sum(len(s["vo"].split()) for s in p["scenes"])
        _, f, d0 = pace.fit(vo, paced, nw, ch.get("edit", {}).get("wps", 2.6))
        log("paced voice: pauses squeezed, speed x", f, "from", d0, "s")
        redo.add("voice")
    vo = paced
    tp = os.path.join(job, "timing.json")
    if "voice" in redo or not os.path.exists(tp) or load(tp, {}).get("method") != "whisper":
        cover = 0.0
        try:
            timed, vdur, cover = align.words_by_line(vo, [s["vo"] for s in p["scenes"]], p.get("lang") or ch.get("lang", "hi"))
            method = "whisper"; log("aligned words with whisper, matched", f"{cover:.0%}")
        except Exception as e:
            log("whisper alignment failed, pause estimate:", str(e)[:150])
            timed, vdur = align.lines(vo, [s["vo"] for s in p["scenes"]]); method = "pauses"
        save(tp, {"method": method, "dur": vdur, "lines": timed, "cover": cover if method == "whisper" else 0.0})
    tj = load(tp)
    timed, vdur = tj["lines"], tj["dur"]
    # holds: silence after a line (e.g. a countdown before the answer); words after it move later
    vo_use = vo
    holds = [(i, float(s["hold"])) for i, s in enumerate(p["scenes"]) if s.get("hold")]
    if holds:
        import numpy as np, soundfile as sf
        a_, sr = sf.read(vo, dtype="float32")
        shift, pieces, last = 0.0, [], 0
        for i, h in holds:
            if i + 1 >= len(timed):
                continue
            cut = (timed[i]["end"] + timed[i + 1]["start"]) / 2
            pieces += [a_[last:int(cut * sr)], np.zeros(int(h * sr), dtype="float32")]
            last = int(cut * sr)
            for L in timed[i + 1:]:
                L["start"] += h; L["end"] += h
                for w in L["words"]:
                    w["s"] += h; w["e"] += h
            shift += h
        pieces.append(a_[last:])
        vo_use = os.path.join(job, "vo-held.wav")
        sf.write(vo_use, np.concatenate(pieces), sr)
        vdur += shift
    total = round(vdur + 0.7 + (1.4 if theme.get("handle") else 0.0), 3)
    # 4 assets
    assets = stage_assets(ch, p, job)
    # 5 compose
    rdir = os.path.join(job, "render")
    if "compose" in redo or not os.path.exists(os.path.join(rdir, "index.html")):
        os.makedirs(os.path.join(rdir, "assets"), exist_ok=True)
        doc, cues = compose.page(p, timed, total, theme, assets)
        open(os.path.join(rdir, "index.html"), "w", encoding="utf-8").write(doc)
        for v in assets.values():
            for f in v.values():
                shutil.copy(f, os.path.join(rdir, "assets", os.path.basename(f)))
        save(os.path.join(job, "cues.json"), {"lufs": -14, "music": {"file": theme.get("music", "music/digital-clouds.mp3"),
              "offset": theme.get("music_offset", 8.0), "gain_db": -22, "fade_out": 1.5}, "sfx": cues})
        redo.add("mix")
    # 6 mix
    mix = os.path.join(job, "mix.wav")
    if "mix" in redo or not os.path.exists(mix):
        sh(["ffmpeg", "-v", "error", "-y", "-i", vo_use, "-ar", "48000", os.path.join(job, "vo.wav")])
        sh([PY, os.path.join(ROOT, "lib", "mix.py"), job, os.path.join(ASSETS, "audio")])
        shutil.copy(mix, os.path.join(rdir, "assets", "mix.wav"))
        redo.add("render")
    # 7 render
    raw, final = os.path.join(job, "raw.mp4"), os.path.join(job, f"{ch['id']}-{job_id}.mp4")
    if "render" in redo or not os.path.exists(final):
        env = dict(os.environ, PUPPETEER_EXECUTABLE_PATH=CHROME)
        t0 = time.time()
        sh(["nice", "-n", "15", "npx", "-y", "hyperframes@latest", "render", "--workers", "1", "--output", raw],
           env=env, timeout=7200, cwd=rdir) if os.name != "nt" else sh(["npx.cmd", "-y", "hyperframes@latest", "render", "--output", raw], cwd=rdir)
        log("rendered in", round(time.time() - t0), "s")
        remux(raw, mix, total, final)
    # 8 qc
    rep = {"topic": topic, "title": p.get("title"), "format": qc.fmt(final)}
    mids = [((t["start"] + t["end"]) / 2) for t in timed]
    sheet = qc.sheet(final, mids, os.path.join(job, "sheet.jpg"))
    rep["vision"] = qc.vision(sheet, p)
    tj2 = load(os.path.join(job, "timing.json"), {})
    words = [w for L in tj2.get("lines", []) for w in L.get("words", [])]
    cover = tj2.get("cover")
    if cover is None and tj2.get("method") == "whisper":
        cover = 1.0
    rep["voice"] = {"ok": (cover or 0) >= 0.7, "method": tj2.get("method"), "matched": cover, "words": len(words),
                    "problems": [] if (cover or 0) >= 0.7 else [f"only {cover or 0:.0%} of the script was found in the voice"]}
    rep["ok"] = bool(rep["format"]["ok"] and rep["vision"].get("ok") is not False and rep["voice"].get("ok") is not False)
    save(os.path.join(job, "qc.json"), rep)
    # auto-lessons: every problem the gate found is kept for the next plans
    probs = (rep["vision"].get("problems") or []) + (rep["voice"].get("problems") or [])
    if probs:
        with open(os.path.join(ROOT, "channels", ch["id"], "lessons-auto.md"), "a", encoding="utf-8") as f:
            f.write(f"\n## {job_id} {topic}\n" + "\n".join("- " + str(x) for x in probs) + "\n")
    log("qc", "OK" if rep["ok"] else "PROBLEMS", json.dumps(rep["format"]), rep["vision"].get("score"))
    # 9 send for approval + remember
    done = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), [])
    if not any(d["job"] == job_id for d in done):
        done.append({"job": job_id, "topic": topic, "title": p.get("title"), "qc_ok": rep["ok"], "status": "made"})
        save(os.path.join(ROOT, "channels", ch["id"], "done.json"), done)
    if not a.no_send:
        txt = (f"[{ch['id']}] {p.get('title')}\n{'✅ QC ok' if rep['ok'] else '⚠️ QC: ' + '; '.join(map(str, probs))[:600]}\n"
               f"{rep['format']['dur']} s, {rep['format']['lufs']} LUFS, vision {rep['vision'].get('score')}/10\n\n{p.get('caption', '')}")
        mid = telegram(txt, video=final)
        if isinstance(mid, int):
            m = load(os.path.join(OUT, "tg-map.json"), {})
            m[str(mid)] = {"channel": ch["id"], "job": job_id}
            save(os.path.join(OUT, "tg-map.json"), m)
    print(json.dumps({"final": final, "ok": rep["ok"]}))


if __name__ == "__main__":
    main()
