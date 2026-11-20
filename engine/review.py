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


PICCHK = """You check the pictures of a devotional short video before it is published. Each image is ONE scene, shown
large. Answer every question for every image strictly from what you SEE (a figure that shows it = yes). Do not excuse a
mistake as "artistic style": devotees notice every wrong detail. Each image comes with the line narrated over it: the
main figure is the one that line is about (if the line is about Yamraj, the figure must look like Yamraj, not Vishnu).
QUESTIONS:
{qs}
Return JSON {{"frames": [{{"n": <image number from 1>, "yes": [<question numbers answered yes>], "what": "<short: what is wrong>"}}]}}
(list only images with at least one yes)."""


def _confirm(model, jpg, qs, said=""):
    """One image, only the flagged questions: '' unless a model clearly sees it (and says exactly what and where).
    20 Nov: (1) the same Gemini model checking twice cleared a crowned Bahubali; (2) OmniRoute alone then cleared a
    bearded, white-robed Mahavira and a bearded saffron sage, because it was never told WHO the figure is. Now the
    narration line of that scene is given, and two different models look (OmniRoute vision + Gemini): the flag holds
    if either one sees it and names what and where."""
    import urllib.request
    try:
        raw = open(jpg, "rb").read()
    except OSError:
        return ""
    ctx = (f"The narration at this moment says: \"{said}\". The main figure in the picture is the person this line is "
           "about (the narration names him or her).\n") if said else ""
    prompt = (ctx + "Look carefully at this ONE picture. For each question answer yes ONLY if it is clearly visible, and say "
              "exactly what you see and where in the picture. Do not excuse it as an artistic or traditional choice: if the "
              "thing asked about is in the picture, the answer is yes. If it is not in the picture, answer no.\n"
              + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(qs))
              + '\nReturn JSON {"answers": [{"q": <number>, "yes": true/false, "seen": "<what and where>"}]}')

    def seen_of(a):
        if isinstance(a, str):
            a = llm.parse_json(a) or {}
        if isinstance(a, list):
            a = {"answers": a}
        if not isinstance(a, dict):
            return None
        return [str(x.get("seen") or "")[:120] for x in a.get("answers") or []
                if isinstance(x, dict) and x.get("yes") is True and len(str(x.get("seen") or "")) > 8]

    got, answered = [], 0
    try:
        r1 = seen_of(llm.vision(prompt, raw))
        if r1 is not None:
            answered += 1; got += r1
    except Exception as e:
        log("picture check confirm (omniroute) failed", str(e)[:100])
    body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(raw).decode()}}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0}}
    try:
        r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                   data=json.dumps(body).encode(),
                                   headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(model)})
        d = json.load(urllib.request.urlopen(r, timeout=120))
        r2 = seen_of(d["candidates"][0]["content"]["parts"][0]["text"])
        if r2 is not None:
            answered += 1; got += r2
    except Exception as e:
        log("picture check confirm (gemini) failed", str(e)[:100])
    if not answered:
        return "confirm step failed"                    # cannot confirm -> keep the flag (safe side)
    return "; ".join(dict.fromkeys(got))


def picture_check(mp4, timing, checks, max_frames=14, frame_checks=None):
    """20 Nov: the contact-sheet review passed 3 Navkar Bhav reels with a bearded saffron Mahavira, a crowned Bahubali
    and saffron monks (26 tiny frames + a 'traditional forms, never report' note). Here: ONE frame per scene at 540x960,
    only the page's checklist, any yes = a problem. Returns {"problems": [...], "frames": n}."""
    import tempfile, urllib.request
    used = [L for L in timing if L.get("end", 0) > L.get("start", 0)][:max_frames]
    pts = [round((L["start"] + L["end"]) / 2, 2) for L in used]
    said = [str(L.get("text") or "")[:200] for L in used]
    if not pts:
        return {"problems": [], "frames": 0}
    tmp = tempfile.mkdtemp()
    parts = []
    for i, t in enumerate(pts):
        f = os.path.join(tmp, f"{i}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", mp4, "-frames:v", "1", "-vf", "scale=540:960", "-q:v", "4", f],
                       capture_output=True)
        if os.path.exists(f):
            # 20 Nov: without the narration the model cannot know WHO a figure should be (missed a Vishnu-like Yamraj)
            parts.append({"text": f"Image {i + 1} (scene {i + 1}), narration: \"{said[i]}\":"})
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(f, "rb").read()).decode()}})
    # 20 Nov: Gemini Decisions API first (calibrated yes-probabilities, own free quota; on the labelled frames it caught
    # 3/3 wrong Jain pictures and passed 6/6 clean ones at 0.6). The two-model look below is the fallback.
    try:
        import picsmith
        single = {f"c{k + 1}": q for k, q in enumerate(frame_checks or checks) if not re.search(r"between scenes", q, re.I)}
        # rendered frames carry our own captions + page handle: the "text" question is asked on the raw picture only
        single.update({k: v for k, v in picsmith.GENERAL.items() if k != "text"})
        out, scores = [], []
        for i in range(len(pts)):
            fjpg = os.path.join(tmp, f"{i}.jpg")
            if not os.path.exists(fjpg):
                continue
            a = picsmith.decide(fjpg, f"One picture from a short devotional / story video. Narration over this picture: "
                                      f"\"{said[i]}\". The main figure is the one the narration is about.", single)
            bad = {k: v for k, v in a.items() if v >= picsmith.FAIL}
            scores.append(round(max(a.values() or [0]), 2))
            if bad:
                out.append(f"scene {i + 1}: " + "; ".join(f"{single[k][:110]} (yes {v:.0%})" for k, v in bad.items()))
        return {"problems": out, "frames": len(pts), "model": "gemini-decision-1", "top": scores}
    except Exception as e:
        log("picture check: Decisions API unavailable, two-model check instead:", str(e)[:120])
    qs = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(checks))
    body = {"contents": [{"parts": [{"text": PICCHK.format(qs=qs)}] + parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0}}
    for m in tts.usable(VISION_MODELS):
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                       data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(m)})
            d = json.load(urllib.request.urlopen(r, timeout=180))
            res = llm.parse_json(d["candidates"][0]["content"]["parts"][0]["text"]) or {}
            out, dropped = [], []
            for fr in res.get("frames") or []:
                ys = [int(y) for y in fr.get("yes") or [] if str(y).isdigit() and 1 <= int(y) <= len(checks)]
                n = int(fr.get("n") or 0) if str(fr.get("n") or "").isdigit() else 0
                if not ys or not 1 <= n <= len(pts):
                    continue
                # 20 Nov: flash-lite flagged "mosque domes" in a palace interior with none (Kuber). A flag holds only
                # when a second, single-image look at that frame confirms it with what it sees
                ok_ys = _confirm(m, os.path.join(tmp, f"{n - 1}.jpg"), [checks[y - 1] for y in ys], said[n - 1])
                if ok_ys:
                    out.append(f"scene {n}: {ok_ys} (checklist {', '.join(map(str, ys))})")
                else:
                    dropped.append(n)
            if dropped:
                log("picture check: not confirmed on a second look, kept:", dropped)
            return {"problems": out, "frames": len(pts), "model": m, "unconfirmed": dropped}
        except Exception as e:
            log("picture check fail", m, str(e)[:120])
    return {"problems": [], "frames": len(pts), "error": "no vision model answered"}


def vision_review(mp4, plan, timing, out_jpg, lang, handle, checks=None):
    times = []
    for L in timing:
        a, b = L["start"], L["end"]
        times += [a + 0.35, (a + b) / 2]
    dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).strip())
    times.append(max(0.1, dur - 0.5))                     # end card
    qc.sheet(mp4, times[:26], out_jpg)
    from compose import _dup
    forms = ""
    try:                                          # 18 Nov: same deity reference as the picture prompts (engine/iconography.py)
        import iconography
        n = iconography.notes(" ".join(s.get("vo", "") + " " + s.get("prompt", "") for s in plan["scenes"]))
        if n:
            forms = "\nTraditional forms (correct, never report them as a mistake): " + n + "." + iconography.NO_COUNT
    except Exception:
        pass
    desc = "\n".join(f"scene {i + 1}: says \"{s['vo']}\" | type {s['type']}"
                     + ("" if (not s.get("title") or _dup(s["title"], s.get("vo"))) else f" | headline \"{s['title']}\"")
                     + (f" | CARD words shown on screen (intended, do not flag them): \"{s.get('big', '')}\" / \"{s.get('small', '')}\"" if s.get("type") == "card" else "")
                     for i, s in enumerate(plan["scenes"]))
    prompt = f"""You are the strictest reviewer at a top short-video studio. The contact sheet shows frames in time order:
two frames per scene (scene start, scene middle), then the very last frame (end card).
Scenes:
{desc}{forms}
Language of the video: {"English" if lang == "en" else "Hindi/Hinglish (Roman script)"}. Page handle: {handle or "none"}.
Rules of our template (do NOT report these as problems): captions show only 2-3 words of the line at a time, the
spoken word is highlighted in a yellow box (in the dark tech look: words not yet spoken are shown dimmed and light up as they are said, which is intended); PHONE PAGES (finance): scenes are drawn phone screens on purpose: a WhatsApp chat, a lock screen with bank SMS, a payment status screen, a paper receipt, a white official rule card with a stamp. Items in them appear one by one with the voice, so a still may show only the first bubbles or rows, or a bar not yet grown: never report that as missing, cut off or misaligned. Captions are a few words at a time and words not yet spoken are dimmed; never report a caption as cut off unless letters are really outside the frame. cards show 1-3 big summary words; a small top bar shows the page/part.
Report ONLY real, visible problems a viewer would notice:
- any text cut off at the frame edge, overflowing, overlapping other text, or too faint to read
- the same words shown twice at the same moment (e.g. headline and top bar both "CLUE 1")
- garbled or fake letters inside the generated images, watermarks
- broken anatomy (extra fingers, melted faces), ugly artefacts, a frame that doesn't fit its line
- wrong language on screen, missing end card when a handle is given
- 19 Nov (owner: the WhatsApp AI agent reel got 10/10 here and was "not top notch"): judge the CONTENT too, as a top
  creator would before posting:
  * a frame that does not SHOW what its line says (line about a calendar check, frame shows a blank terminal; line about
    languages, frame shows fireworks) = serious when it happens in 2+ scenes
  * an empty or near-empty UI card, chat bubble or box (a panel with no text, a bubble with a grey bar, a big empty caption
    box with one word) = serious
  * a caption that shows a single word for a long stretch, or words that clearly lag or run ahead of the scene = serious
  * a "how it works" video whose frames never show the mechanism (only logos, icons and feature words) = serious
  * the same picture or layout repeated across 3+ scenes = minor
- a god, goddess or sacred figure shown wrongly or disrespectfully (wrong gender or form, revealing clothes, mocking), or a
  split / collage picture where one scene was meant (18 Nov: a generated Kartikeya came out as a woman)
Return JSON {{"score": 1-10, "serious": ["..."], "minor": ["..."]}} (serious = must fix before posting)."""
    if checks:
        # 19 Nov audit: 6 of 6 Navkar Bhav reels scored 9-10 here with Mughal domes, blue/green-skinned Tirthankaras and
        # saffron-robed Jain monks: the page's own must-answer checklist; any "yes" is serious
        prompt += ("\nPAGE CHECKLIST: look at EVERY frame and answer each question honestly (a frame that shows it = yes):\n"
                   + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(checks))
                   + '\nAdd to the JSON: "checklist": [{"q": <number>, "yes": true/false, "where": "<scene / frame if yes>"}]. '
                     "Every yes is a serious problem: list it in serious too.")
    b64 = base64.b64encode(open(out_jpg, "rb").read()).decode()
    body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    import urllib.request
    for m in tts.usable(VISION_MODELS):
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                       data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(m)})
            d = json.load(urllib.request.urlopen(r, timeout=180))
            res = llm.parse_json("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
            if checks and isinstance(res, dict):
                hits = [c for c in res.get("checklist") or [] if isinstance(c, dict) and c.get("yes")]
                for c in hits:
                    try:
                        q = checks[int(c.get("q")) - 1]
                    except Exception:
                        q = str(c.get("q"))
                    res.setdefault("serious", []).append(f"checklist: {q} -> {c.get('where') or 'yes'}")
                if hits:
                    res["score"] = min(int(res.get("score") or 10), 5)
            return res
        except Exception as e:
            log("review vision fail", m, str(e)[:120])
            if "timed out" in str(e).lower():
                tts.mark_slow(m)
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
    try:                                    # 19 Nov: 83 % matched but the captions were visibly out of sync (WhatsApp reel)
        import align
        probs += align.sync_problems(tj.get("lines") or [])[:2]
    except Exception as e:
        log("review: sync check skipped", str(e)[:100])
    # 6b blank stretch (17 Nov: a clip ended early and left ~1 s of empty frame; the 2-frames-per-scene sheet missed it):
    #    every 0.25 s, look at the picture area above the captions; nearly flat for 0.75 s+ = blank
    try:
        import numpy as np
        w_, h_ = 54, 96
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"fps=4,scale={w_}:{h_},format=gray", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, h_, w_)[:, int(h_ * 0.16):int(h_ * 0.6), :].astype(np.float32)
        flat = (fr.std(axis=(1, 2)) < 6) & (fr.max(axis=(1, 2)) < 70)
        run_, start_ = 0, 0
        for k, fl in enumerate(list(flat) + [False]):
            if fl:
                run_ += 1; start_ = start_ if run_ > 1 else k
            else:
                if run_ >= 3 and start_ / 4 < (f.get("dur") or 999) - 2.5:      # end card excluded
                    probs.append(f"blank frame from {start_ / 4:.1f} s to {(start_ + run_) / 4:.1f} s (nothing in the picture area)")
                run_ = 0
        checks["blank_frames"] = int(flat.sum())
    except Exception as e:
        log("review blank check failed", str(e)[:120])
    # 7 vision
    v = vision_review(mp4, plan, tj.get("lines", []), os.path.join(jd, "review-sheet.jpg"), lang, ch.get("handle", ""),
                      checks=ch.get("visual_checks") or [])
    checks["vision"] = v
    probs += [f"visual: {x}" for x in (v.get("serious") or [])]
    if ch.get("visual_checks"):
        pc = picture_check(mp4, tj.get("lines", []), ch["visual_checks"], frame_checks=ch.get("frame_checks"))
        checks["picture_check"] = pc
        probs += [f"picture check: {x}" for x in pc.get("problems") or []]
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
