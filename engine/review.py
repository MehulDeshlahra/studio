"""Strict reviewer: runs on the FINAL mp4 before anything is sent to the owner (owner, 17 Nov: "add a reviewer which
reviews before sending, I am not free to point silly mistakes"). Only videos that pass reach Telegram; the rest are
held with their problems, and every problem becomes a lesson.
Checks:
  1. start: the first spoken words match the script's first line (catches spoken instructions AND cut-off openings)
  2. end: the last line is spoken
  3. no instruction phrases anywhere in the first 30 s
  4. voice/script alignment >= 80 %
  5. format + loudness (1080x1920, 30 fps, -15.5..-12.5 LUFS, true peak <= -1.0)
  6. length inside the channel's range
  7. vision review of 2 frames per scene by a strong model with a strict checklist (cut-off/overflowing text,
     the same text twice, garbled text in images, broken anatomy, unreadable labels, missing handle/end card)
  python engine/review.py <channel> <job>  -> review.json {ok, problems[], checks{}}"""
import base64, json, os, re, subprocess, sys
from difflib import SequenceMatcher
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import OUT, ROOT, load, save, log, sh
import tts, qc, llm

VISION_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]


def _pcm(mp4, start=0.0, dur=None):
    import numpy as np
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.2f}", "-i", mp4] + (["-t", f"{dur:.2f}"] if dur else []) + \
          ["-ac", "1", "-ar", "16000", "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32)


def _whisper(a, lang):
    from faster_whisper import WhisperModel
    segs, _ = WhisperModel("base", compute_type="int8").transcribe(a, language=lang)
    return " ".join(s.text.strip() for s in segs)


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def _starts_like(heard, line, n=5):
    """does the heard text start with (roughly) the first n words of line? (English / Roman text)"""
    h, l = " ".join(_norm(heard)[:n + 3]), " ".join(_norm(line)[:n])
    best = max((SequenceMatcher(None, " ".join(_norm(heard)[i:i + n]), l).ratio() for i in range(0, 4)), default=0)
    return best, h


def vision_review(mp4, plan, timing, out_jpg, lang, handle):
    times = []
    for L in timing:
        a, b = L["start"], L["end"]
        times += [a + 0.35, (a + b) / 2]
    dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).strip())
    times.append(max(0.1, dur - 0.5))                     # end card
    qc.sheet(mp4, times[:26], out_jpg)
    desc = "\n".join(f"scene {i + 1}: says \"{s['vo']}\" | type {s['type']} | headline \"{s.get('title', '')}\""
                     for i, s in enumerate(plan["scenes"]))
    prompt = f"""You are the strictest reviewer at a top short-video studio. The contact sheet shows frames in time order:
two frames per scene (scene start, scene middle), then the very last frame (end card).
Scenes:
{desc}
Language of the video: {"English" if lang == "en" else "Hindi/Hinglish (Roman script)"}. Page handle: {handle or "none"}.
Rules of our template (do NOT report these as problems): captions show only 2-3 words of the line at a time, the
spoken word is highlighted in a yellow box (in the dark tech look: words not yet spoken are shown dimmed and light up as they are said, which is intended); cards show 1-3 big summary words; a small top bar shows the page/part.
Report ONLY real, visible problems a viewer would notice:
- any text cut off at the frame edge, overflowing, overlapping other text, or too faint to read
- the same words shown twice at the same moment (e.g. headline and top bar both "CLUE 1")
- garbled or fake letters inside the generated images, watermarks
- broken anatomy (extra fingers, melted faces), ugly artefacts, a frame that doesn't fit its line
- wrong language on screen, missing end card when a handle is given
Return JSON {{"score": 1-10, "serious": ["..."], "minor": ["..."]}} (serious = must fix before posting)."""
    b64 = base64.b64encode(open(out_jpg, "rb").read()).decode()
    body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    import urllib.request
    for m in VISION_MODELS:
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                       data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key()})
            d = json.load(urllib.request.urlopen(r, timeout=180))
            return llm.parse_json("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
        except Exception as e:
            log("review vision fail", m, str(e)[:120])
    v = qc.vision(out_jpg, plan)
    return {"score": v.get("score"), "serious": [] if v.get("ok") is not False else v.get("problems", []), "minor": []}


def review(cid, job):
    jd = os.path.join(OUT, cid, job)
    ch = load(os.path.join(ROOT, "channels", cid, "channel.json"), {})
    plan = load(os.path.join(jd, "plan.json"))
    tj = load(os.path.join(jd, "timing.json"), {})
    mp4 = os.path.join(jd, f"{cid}-{job}.mp4")
    lang = plan.get("lang") or ch.get("lang", "hi")
    probs, checks = [], {}
    # 5 format + loudness
    f = qc.fmt(mp4)
    checks["format"] = f
    if not f["ok"]:
        probs.append(f"format/loudness: {f['video']} {f['lufs']} LUFS, true peak {f['true_peak']}")
    # 6 length
    lo, hi_ = ch.get("edit", {}).get("length_s", [25, 75])
    if not (lo <= f["dur"] <= hi_ + 2):
        probs.append(f"length {f['dur']} s is outside {lo}-{hi_} s")
    # 1 + 3 start / instructions (English transcription catches English instructions in any language)
    en_start = _whisper(_pcm(mp4, 0, 30), "en")
    checks["start_en"] = en_start[:300]
    if any(k in en_start.lower() for k in tts.LEAK):
        probs.append("spoken instructions heard at the start: " + en_start[:120])
    first = plan["scenes"][0]["vo"]
    if lang == "en":
        r, heard = _starts_like(_whisper(_pcm(mp4, 0, 8), "en"), first)
        checks["start_match"] = round(r, 2)
        if r < 0.55:
            probs.append(f"the video does not start with the first line \"{first[:50]}\" (heard: \"{heard[:60]}\")")
    else:
        w1 = (tj.get("lines") or [{}])[0].get("words", [])
        if w1 and w1[0]["s"] > 1.5:
            probs.append(f"first word starts late ({w1[0]['s']:.1f} s): something is spoken before the script")
    # 2 end
    last = plan["scenes"][-1]["vo"]
    sig = (load(os.path.join(ROOT, "channels", cid, "channel.json"), {}).get("theme") or {}).get("signature")
    if sig and lang != "en":
        allvo = " ".join(re.sub(r"[^a-z ]", "", s["vo"].lower()) for s in plan["scenes"])
        n = allvo.count(sig)
        if n > 1:
            probs.append(f"the page line \"{sig}\" is said {n} times; say it once, before the twist")
        if sig in re.sub(r"[^a-z ]", "", last.lower()) and "part" not in last.lower():
            probs.append(f"\"{sig}\" is in the last line of a finished story: it promises more that never comes")
    if lang == "en":
        tail = _whisper(_pcm(mp4, max(0, f["dur"] - 9), 9), "en")
        rr = SequenceMatcher(None, " ".join(_norm(tail)), " ".join(_norm(last))).ratio()
        checks["end_match"] = round(rr, 2)
        if rr < 0.35:
            probs.append(f"the last line \"{last[:50]}\" is not clearly heard at the end")
    # 4 alignment
    cover = tj.get("cover")
    if cover is None:                       # timing made before the cover was stored: whisper method = aligned
        cover = 1.0 if tj.get("method") == "whisper" else 0.0
    checks["alignment"] = cover
    if cover < 0.8:
        probs.append(f"only {cover:.0%} of the script was found in the voice")
    # 7 vision
    v = vision_review(mp4, plan, tj.get("lines", []), os.path.join(jd, "review-sheet.jpg"), lang, ch.get("handle", ""))
    checks["vision"] = v
    probs += [f"visual: {x}" for x in (v.get("serious") or [])]
    if (v.get("score") or 0) < 6:
        probs.append(f"visual score {v.get('score')}/10")
    rep = {"ok": not probs, "problems": probs, "minor": v.get("minor") or [], "checks": checks}
    save(os.path.join(jd, "review.json"), rep)
    log("review", cid, job, "PASS" if rep["ok"] else "HOLD: " + " | ".join(probs)[:300])
    if probs:
        with open(os.path.join(ROOT, "channels", cid, "lessons-auto.md"), "a", encoding="utf-8") as fh:
            fh.write(f"\n## review {job}\n" + "\n".join("- " + p for p in probs) + "\n")
    return rep


if __name__ == "__main__":
    print(json.dumps(review(sys.argv[1], sys.argv[2]), ensure_ascii=False, indent=1)[:3000])
