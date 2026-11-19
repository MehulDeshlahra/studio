"""The clip renderer (19 Nov, CutCapsule). Runs on the LAPTOP (tools/laptop_worker.py "clip" jobs): YouTube blocks the
server and the laptop has 8 threads + a CUDA GPU. Pure ffmpeg / faster-whisper / OpenCV, no engine imports.
Ideas taken from the best open tools (knowledge/clipping.md):
  - cut on sentence boundaries, never mid-word (ClippyMe); remove pauses > 0.55 s inside the clip (auto-editor style)
  - layout chosen from faces: one talking head -> full 9:16 face crop, held still within each shot (ClippyMe, AutoFrame);
    a small face in a fixed corner over a game -> facecam on top + gameplay below (GTA stream clip layout);
    otherwise blurred fill with the video full width
  - hook banner from frame 1, word-by-word pop captions with the spoken word highlighted, below the mouth
make_clip(src, a, b, hook, out_dir) -> dict with final.mp4, cover.jpg, sheet.jpg, words.json, layout, duration."""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "assets", "fonts")
W, H = 1080, 1920
# 19 Nov (owner: "are you serious?"): in a full-height 9:16 crop of a wide stage shot the comedian's head sits in the top
# 15%, exactly under the hook bar, and a 1080p source gives only a 607 px slice (soft). Crop shots now use a TITLE BAND
# (the common clip-page layout): a dark band on top holds the logo + hook, the picture fills the 1080x1440 below it:
# a 3:4 crop = an 810 px slice of 1080p (1.33x, sharp), wider room for a walking speaker, and no text on any head.
# 19 Nov benchmark (same day, frame by frame vs Short Form Comedy 9.8M views on a Jo Koy clip, Don't Tell Comedy 25M):
# the winners use NO band, no boxes and no permanent hook bar: a clean full 9:16 frame, the hook big in the centre for
# the first seconds only, mid-screen captions and hard reframing on the beats. BAND = 0 turns the band off (kept for
# formats that need one).
BAND = 0
PIC_H = H - BAND
CROP_AR = W / PIC_H
BAND_COLOR = "0x0B0B10"
NOTES_ON_SCREEN = False      # the benchmark pages carry no note boxes; the edit itself is the added work
HOOK_SECONDS = 3.0           # Short Form Comedy: the hook sits mid-screen for the opening line only
NOWIN = 0x08000000 if os.name == "nt" else 0
GAP = 0.55            # a pause longer than this inside a clip is cut out
KEEP_PAD = 0.12       # silence kept on each side of a cut


_NV = [None]


def nvenc():
    """True when the GPU H.264 encoder works here (19 Nov: needs NVIDIA driver 610+; tested once per process)."""
    if _NV[0] is None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=1080x1920:d=0.5", "-c:v", "h264_nvenc",
                            "-f", "null", "-"], capture_output=True, text=True, timeout=60, creationflags=NOWIN)
        _NV[0] = r.returncode == 0
    return _NV[0]


def venc(final):
    """Video encoder args: final = the posted file (quality), else an intermediate (speed)."""
    if nvenc():
        return (["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "21", "-b:v", "0", "-maxrate", "16M",
                 "-bufsize", "32M", "-profile:v", "high", "-pix_fmt", "yuv420p"] if final else
                ["-c:v", "h264_nvenc", "-preset", "p2", "-rc", "constqp", "-qp", "16"])
    return (["-c:v", "libx264", "-preset", "fast", "-crf", "19"] if final else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "14"])


def run(cmd, timeout=1800):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NOWIN)
    if r.returncode:
        raise RuntimeError(f"{os.path.basename(cmd[0])} failed: {r.stderr[-600:]}")
    return r


def probe(f):
    r = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", f], 60)
    j = json.loads(r.stdout or "{}")
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"dur": round(float((j.get("format") or {}).get("duration") or 0), 2), "w": v.get("width"), "h": v.get("height"),
            "audio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


# ---------------- words ----------------
_MODEL = [None]
ASR = [""]                # which whisper actually ran (19 Nov: a silent CPU fallback hid for 2 days)


def fix_names(Wd, glossary):
    """19 Nov (SEGA "I AM HEISMAN" for Heismay): snap a misheard word onto a glossary name when it is close (same first
    letter, similarity >= 0.75). Briefs ask for true, correctly named captions."""
    import difflib
    names = [g for g in dict.fromkeys(glossary or []) if len(g) >= 4 and " " not in g]
    if not names:
        return Wd
    out = []
    for s, e, w in Wd:
        core = re.sub(r"\W", "", w)
        tail = w[len(w.rstrip(".,!?;:")):]
        best = max(names, key=lambda n: difflib.SequenceMatcher(None, core.lower(), n.lower()).ratio()) if core else None
        if (best and core.lower() != best.lower() and core[:1].lower() == best[:1].lower() and len(core) >= 4
                and difflib.SequenceMatcher(None, core.lower(), best.lower()).ratio() >= 0.75):
            w = best + tail
        out.append((s, e, w))
    return out


_DLLS_DONE = [False]


def _cuda_dlls():
    """19 Nov: the GPU whisper never loaded (cublas64_12.dll not found: a half-done pip uninstall had renamed nvidia/cublas/bin
    to '~in') and every clip silently used the small CPU model (misheard 'crystal gel' as 'crypto jail', garbled Hindi).
    Make the pip-installed NVIDIA runtime folders visible to CTranslate2 on Windows."""
    # 19 Nov: this ran on EVERY transcription and prepended ~10 folders each time; after enough clip jobs PATH passed
    # Windows' 8191-char cmd limit and Reel renders failed with "'npx.cmd' is not recognized". Once per process, and
    # only folders not on PATH yet.
    if os.name != "nt" or _DLLS_DONE[0]:
        return
    _DLLS_DONE[0] = True
    import glob, site
    have = set(os.environ.get("PATH", "").lower().split(os.pathsep))
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")) + [os.path.join(sp, "ctranslate2")]:
            if os.path.isdir(d):
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass
                if d.lower() not in have:
                    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", ""); have.add(d.lower())


def words(mp4, lang=None, prompt=""):
    """[(start, end, word)] + language. GPU (medium) when CUDA works, else CPU (small, int8). prompt = names to spell."""
    _cuda_dlls()
    import numpy as np
    from faster_whisper import WhisperModel
    wav = mp4 + ".wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-ac", "1", "-ar", "16000", "-f", "wav", wav], 300)
    import soundfile as sf
    a, _ = sf.read(wav, dtype="float32")
    os.remove(wav)
    if a.ndim > 1:
        a = a.mean(axis=1)
    if _MODEL[0] is None:
        for args in (("medium", "cuda", "int8_float16"), ("small", "cpu", "int8")):
            try:
                m = WhisperModel(args[0], device=args[1], compute_type=args[2])
                list(m.transcribe(np.zeros(16000, dtype="float32"))[0])          # fails here when cuDNN is missing
                _MODEL[0] = m; ASR[0] = f"{args[0]}/{args[1]}"; break
            except Exception:
                continue
    # with a script sample (Hindi page) each 30 s window must see the text before it, or the 2nd window drifts back to
    # Devanagari (19 Nov test: 82 words, the first ~30 s Roman, the rest Devanagari)
    segs, info = _MODEL[0].transcribe(a, language=lang, word_timestamps=True, beam_size=5, vad_filter=True,
                                      condition_on_previous_text=bool(prompt), initial_prompt=(prompt or None) and prompt[:400])
    return [(float(w.start), float(w.end), w.word.strip()) for s in segs for w in (s.words or []) if w.word.strip()], info.language


def trim(Wd, want_a, want_b):
    """Start on a sentence start near the asked start (the hook line), end on a sentence end near the asked end."""
    if not Wd:
        return want_a, want_b
    ends = {i for i, w in enumerate(Wd) if re.search(r"[.!?…]$", w[2])}
    starts = [i for i in range(len(Wd)) if i == 0 or (i - 1) in ends or Wd[i][0] - Wd[i - 1][1] > 0.6]
    a_c = [i for i in starts if want_a - 2.5 <= Wd[i][0] <= want_a + 3]
    a_i = min(a_c, key=lambda i: abs(Wd[i][0] - want_a)) if a_c else next((i for i, w in enumerate(Wd) if w[0] >= want_a - 0.3), 0)
    b_c = [i for i in ends if i > a_i and abs(Wd[i][1] - want_b) < 6]
    b_i = min(b_c, key=lambda i: abs(Wd[i][1] - want_b)) if b_c else max((i for i, w in enumerate(Wd) if w[1] <= want_b + 1.5), default=len(Wd) - 1)
    a, b = max(0.0, Wd[a_i][0] - 0.15), Wd[b_i][1] + 0.4
    if b - a < 10:
        return want_a, want_b
    if b - a > 58.5:                                    # cap: under 60 s every platform treats it as a Short / Reel
        b_i = max((i for i in ends if Wd[i][1] - a <= 58), default=None)
        b = Wd[b_i][1] + 0.4 if b_i is not None else a + 58
    return a, b


def loudness(src):
    """Audio level in dB per 50 ms (for 'is this gap really quiet?')."""
    import numpy as np, soundfile as sf
    wav = src + ".rms.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "16000", "-f", "wav", wav], 300)
    a, sr = sf.read(wav, dtype="float32")
    os.remove(wav)
    if a.ndim > 1:
        a = a.mean(axis=1)
    hop = sr // 20
    n = len(a) // hop
    r = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-10)
    return 20 * np.log10(r)


def keep_ranges(Wd, a, b, db=None, max_cut=0.25):
    """Speech ranges inside [a, b] with dead pauses removed. 19 Nov test: on a reaction video, cutting every gap between
    words removed 16 of 27 s (the laughs, the crowbar, the reactions ARE the moment). A gap is cut only when the audio in
    it is really quiet (18 dB under the clip's speech level), and at most 25% of the clip is removed."""
    import numpy as np
    ws = [w for w in Wd if w[1] > a and w[0] < b]
    if not ws:
        return [(a, b)]
    quiet = None
    if db is not None and len(db):
        sp = [db[int(w[0] * 20):max(int(w[0] * 20) + 1, int(w[1] * 20))] for w in ws]
        lvl = float(np.median(np.concatenate([x for x in sp if len(x)]))) if any(len(x) for x in sp) else -30
        quiet = lvl - 18
    gaps = []
    for p, w in zip(ws, ws[1:]):
        g = w[0] - p[1]
        if g <= GAP:
            continue
        if quiet is not None:
            seg = db[int((p[1] + KEEP_PAD) * 20):int((w[0] - KEEP_PAD) * 20)]
            if len(seg) and float(np.percentile(seg, 90)) > quiet:
                continue                                  # something is happening in this gap: keep it
        gaps.append((g - 2 * KEEP_PAD, p, w))
    budget = max_cut * (b - a)
    chosen = set()
    for g, p, w in sorted(gaps, key=lambda x: -x[0]):    # longest dead gaps first, within the budget
        if g <= budget:
            chosen.add((p, w)); budget -= g
    out = [[a, ws[0][1]]]
    for p, w in zip(ws, ws[1:]):
        if (p, w) in chosen:
            out[-1][1] = p[1] + KEEP_PAD
            out.append([max(p[1] + KEEP_PAD, w[0] - KEEP_PAD), w[1]])
        else:
            out[-1][1] = w[1]
    out[-1][1] = b
    return [(round(x, 3), round(y, 3)) for x, y in out if y - x > 0.08]


def remap(Wd, ranges):
    """Word times on the tightened timeline."""
    out, t0 = [], 0.0
    for s, e in ranges:
        for w in Wd:
            if w[0] >= s - 0.02 and w[1] <= e + 0.05:
                out.append((round(t0 + w[0] - s, 3), round(t0 + min(w[1], e) - s, 3), w[2]))
        t0 += e - s
    return out


def tighten(src, ranges, out):
    """One file of only the kept ranges (frame-accurate trim + concat), high quality for the next steps."""
    parts, fc = [], []
    for i, (s, e) in enumerate(ranges):
        fc.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}];[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.02,afade=t=out:st={max(0, e - s - 0.03):.3f}:d=0.03[a{i}]")
        parts.append(f"[v{i}][a{i}]")
    fc.append("".join(parts) + f"concat=n={len(ranges)}:v=1:a=1[v][a]")
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         ] + venc(False) + ["-r", "30", "-c:a", "aac", "-b:a", "192k", out], 1800)
    return out                                       # 19 Nov speed: an intermediate file only needs to be fast + clean


# ---------------- faces + layout ----------------
YUNET = os.path.join(ROOT, "assets", "models", "face_detection_yunet_2023mar.onnx")
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"


def _detector(w, h):
    import cv2
    if not os.path.exists(YUNET):
        import urllib.request
        os.makedirs(os.path.dirname(YUNET), exist_ok=True)
        urllib.request.urlretrieve(YUNET_URL, YUNET)
    d = cv2.FaceDetectorYN.create(YUNET, "", (w, h), 0.75, 0.3, 5000)
    return d


def _main(fs, is_cam):
    """The performer: the biggest face that is not the webcam box and not in the bottom quarter (19 Nov render 13: in
    stand-up wide shots the audience's heads at the bottom were counted, so the shot fell back to a blurred fill)."""
    c = [f for f in fs if not is_cam(f)]
    if not c:
        return None
    up = [f for f in c if f[1] < 0.75]
    return max(up or c, key=lambda q: q[2])


def _rivals(fs, is_cam):
    """Other faces that could be a second subject: above the bottom quarter and at least 60% of the performer's size."""
    m = _main(fs, is_cam)
    if not m:
        return 0
    return sum(1 for f in fs if f is not m and not is_cam(f) and f[1] < 0.75 and f[2] >= 0.6 * m[2])


def analyse(mp4, fps=4):
    """Faces sampled at 4 fps (640 px wide) + shot changes. Returns the layout and, per shot, where to aim."""
    import cv2, numpy as np
    cap = cv2.VideoCapture(mp4)
    sw, sh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    vfps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(vfps / fps)))
    sc = 640 / max(1, sw)
    dw, dh = 640, int(sh * sc)
    det = _detector(dw, dh)
    samples, prev, cuts, i = [], None, [0.0], 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, fr = cap.retrieve()
            if not ok:
                break
            t = i / vfps
            sm = cv2.resize(fr, (dw, dh))
            hist = cv2.calcHist([cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            # 19 Nov render 13: 0.42 missed a crowd -> stage cut (the stage half became a blurred fill); 0.32
            if prev is not None and cv2.compareHist(prev, hist, cv2.HISTCMP_BHATTACHARYYA) > 0.32 and t - cuts[-1] > 0.6:
                cuts.append(round(t, 2))
            prev = hist
            _, f = det.detect(sm)
            faces = [] if f is None else [(float(x[0] + x[2] / 2) / dw, float(x[1] + x[3] / 2) / dh, float(x[3]) / dh, float(x[14]))
                                          for x in f if x[14] > 0.75]
            samples.append((t, faces))
        i += 1
    cap.release()
    dur = i / vfps
    n = max(1, len(samples))
    with_face = [s for s in samples if s[1]]
    big = [max(s[1], key=lambda f: f[2]) for s in with_face]
    share = len(with_face) / n
    med_h = float(np.median([f[2] for f in big])) if big else 0
    info = {"src": [sw, sh], "dur": round(dur, 2), "face_share": round(share, 2), "face_h": round(med_h, 3), "cuts": cuts}
    # 19 Nov tests (a reaction video): one layout for a whole clip failed both ways: the face crop cut the reactor's webcam
    # box in half, and a clip that switches between the reactor full screen and webcam-over-skit needs both layouts.
    # 1) find the webcam box: a face that stays in one spot near an edge in >= 20% of all samples;
    # 2) decide the layout PER SHOT: webcam seen -> stack, a big face -> face crop aimed at it, else blurred fill;
    # 3) merge neighbouring shots with the same layout; a shot under 0.8 s joins the one before (no flicker).
    cam = None
    allf = [(t, f) for t, fs in samples for f in fs]
    best = 0
    for t0, f0 in allf:
        # 19 Nov test (stand-up on a fixed stage camera): a static face high in the CENTRE was taken for a webcam box and
        # the comedian was shown twice. A webcam overlay sits beside the content, i.e. horizontally off-centre (a corner).
        if not (f0[2] < 0.35 and (f0[0] < 0.33 or f0[0] > 0.67)):
            continue
        near = {t for t, f in allf if abs(f[0] - f0[0]) < 0.04 and abs(f[1] - f0[1]) < 0.05 and abs(f[2] - f0[2]) < 0.06}
        # 19 Nov render 9 (stand-up): an audience member's face in ONE crowd shot was taken for a webcam box. A webcam
        # overlay stays put while the content under it cuts: it must show in 2+ shots (or half the clip with no cuts)
        in_shots = {sum(1 for c in cuts if c <= t) for t in near}
        if not (len(in_shots) >= 2 or (len(cuts) <= 1 and len(near) / n >= 0.5)):
            continue
        if len(near) / n >= 0.2 and len(near) > best:
            pts = [f for t, f in allf if abs(f[0] - f0[0]) < 0.04 and abs(f[1] - f0[1]) < 0.05]
            cam, best = [round(float(np.median([p[i] for p in pts])), 3) for i in range(3)], len(near)
    is_cam = lambda f: cam and abs(f[0] - cam[0]) < 0.05 and abs(f[1] - cam[1]) < 0.06
    shots = cuts + [dur]
    segs = []
    for s, e in zip(shots, shots[1:]):
        ss = [fs for t, fs in samples if s <= t < e]
        k = max(1, len(ss))
        cam_share = sum(1 for fs in ss if any(is_cam(f) for f in fs)) / k
        other = [_main(fs, is_cam) for fs in ss if any(not is_cam(f) for f in fs)]
        crowd = False
        if cam and cam_share >= 0.5:
            lay, aim = "stack", None
        elif len(other) / k >= 0.6 and float(np.median([f[2] for f in other])) >= 0.16:
            lay, aim = "crop", round(float(np.median([f[0] for f in other])), 3)
        elif (len(other) / k >= 0.6 and sw >= 1280 and
              sum(1 for t, fs in samples if s <= t < e and _rivals(fs, is_cam) > 0) <= 0.2 * k and
              float(np.std([f[0] for f in other])) < 0.25):     # 19 Nov: the crop follows a walking speaker now (was 0.12)
            # 19 Nov test (Jo Koy wide stage shot): ONE person, small in a wide HD frame, stays roughly in one place ->
            # crop on him (a 9:16 slice of a 1080p frame) instead of a tiny figure on a blurred copy of the same frame
            lay, aim = "crop", round(float(np.median([f[0] for f in other])), 3)
        elif sw >= 1280 and sum(1 for fs in ss if len([f for f in fs if not is_cam(f)]) >= 3) >= 0.5 * k:
            # 19 Nov benchmark: a crowd / audience-reaction shot is a plain centre crop on the winning page, not a tiny
            # picture on a blurred copy (fill stays for shots with no people: slides, text, b-roll)
            lay, aim, crowd = "crop", 0.5, True
        else:
            lay, aim = "fill", None
        if crowd:
            path = [[round(s, 2), 0.5, 0]]              # crowd: a still centre crop, no tracking of random faces
        elif lay == "crop":
            path = _track([(t, _main(fs, is_cam)[0]) for t, fs in samples if s <= t < e and any(not is_cam(f) for f in fs)],
                          s, aim, sw, sh)
        else:
            path = []
        # where the face sits vertically (a punch-in centres on it and never cuts the head off)
        fy = round(float(np.median([f[1] for f in other])), 3) if other else 0.38
        fh = round(float(np.median([f[2] for f in other])), 3) if other else 0.2
        if segs and (e - s < 0.8 or segs[-1]["layout"] == lay):
            segs[-1]["e"] = round(e, 2)
            if segs[-1]["layout"] == "crop" and lay == "crop" and e - s >= 0.8:
                segs[-1]["aims"] += path
                if crowd:
                    segs[-1].setdefault("crowd", []).append([round(s, 2), round(e, 2)])
            continue
        segs.append({"s": round(s, 2), "e": round(e, 2), "layout": lay, "aims": path, "fy": fy, "fh": fh,
                     "crowd": [[round(s, 2), round(e, 2)]] if crowd else []})
    info["cam"] = cam
    info["segments"] = segs
    info["lost"] = subject_lost(samples, segs, is_cam, sw, sh)
    # 19 Nov frames: a note sat on the comedian's face. Where the main face is on the OUTPUT frame (px, top..bottom with
    # hair and chin), per sample, so ass() can move a note off it.
    fy = []
    fh_out = W * sh / max(1, sw)                       # fill: the frame scaled to full width, centred +40
    for t, fs in samples:
        g = next((g for g in segs if g["s"] <= t < g["e"]), None)
        fx = [f for f in fs if not is_cam(f)]
        if not g or not fx or g["layout"] == "stack":
            continue
        f = _main(fx, lambda q: False)
        if g["layout"] == "crop":
            # the box runs from the top of the head (a face box stops at the brow; 19 Nov a note sat on a bald head)
            top, bot = BAND + (f[1] - 1.1 * f[2]) * PIC_H, BAND + (f[1] + 0.65 * f[2]) * PIC_H
        else:
            y0 = (H - fh_out) / 2 + 40
            top, bot = y0 + (f[1] - 0.75 * f[2]) * fh_out, y0 + (f[1] + 0.65 * f[2]) * fh_out
        fy.append((round(t, 2), int(top), int(bot)))
    info["face_y"] = fy
    # 19 Nov render 12: during a 1.3x punch-in the window is ~23% narrower than the tracked crop and a face moving fast
    # left it (half a face on screen while 'lost' said 0). The raw face x per sample lets the zoomed window keep it in.
    raw = [(t, _main(fs, is_cam)[0]) for t, fs in samples if any(not is_cam(f) for f in fs)]
    info["face_x"] = [(round(t, 2), round(float(np.median([x for _, x in raw[max(0, i - 1):i + 2]])), 4))
                      for i, (t, _) in enumerate(raw)]
    rawy = [(t, _main(fs, is_cam)) for t, fs in samples if any(not is_cam(f) for f in fs)]
    info["face_yh"] = [(round(t, 2), float(np.median([f[1] for _, f in rawy[max(0, i - 1):i + 2]])),
                        float(np.median([f[2] for _, f in rawy[max(0, i - 1):i + 2]]))) for i, (t, _) in enumerate(rawy)]
    lays = {g["layout"] for g in segs}
    info["layout"] = lays.pop() if len(lays) == 1 else "mixed:" + "+".join(sorted({g["layout"] for g in segs}))
    return info


def _track(pts, s, aim, sw, sh):
    """19 Nov frames (Jo Koy walking the stage): one fixed aim per shot lost him (empty stage at 13 s). Follow him like a
    camera operator: smooth the face path, keep him inside the middle 40% of the crop (no pan while he stays there),
    pan at most 0.7 crop widths a second, keyframes >= 0.5 s apart. Returns [[t, x, glide]]; glide 0 = a hard cut."""
    import numpy as np
    if not pts:
        return [[round(s, 2), aim, 0]]
    cwf = (sh * CROP_AR) / max(1, sw)
    xs = [p[1] for p in pts]
    sm = [float(np.median(xs[max(0, i - 2):i + 3])) for i in range(len(xs))]
    dead, vmax = 0.2 * cwf, 0.7 * cwf
    cam, out, last_t = sm[0], [[round(s, 2), round(sm[0], 4), 0]], s
    prev_t = pts[0][0]
    for (t, _), x in zip(pts, sm):
        step = vmax * max(0.0, t - prev_t)
        prev_t = t
        want = x - dead if x > cam + dead else x + dead if x < cam - dead else cam
        cam += max(-step, min(step, want - cam))
        if t - last_t >= 0.5 and abs(cam - out[-1][1]) > 0.004:
            out.append([round(t, 2), round(cam, 4), 1]); last_t = t
    return out[:80]


def _x_at(aims, t):
    """Crop centre (0-1) at time t, the same path _crop_x_expr gives ffmpeg."""
    x = aims[0][1]
    for (t0, x0, *_), (t1, x1, *g) in zip(aims, aims[1:]):
        if t < t1:
            return x0 + (x1 - x0) * (t - t0) / max(0.01, t1 - t0) if (g and g[0]) else x0
        x = x1
    return x


def subject_lost(samples, segs, is_cam, sw, sh):
    """19 Nov: the vision check scored a clip 10 with an empty stage on screen. Code check: share of crop-time samples
    whose speaker's face is outside the crop window (a face seen in the frame but not on screen)."""
    hw = (sh * CROP_AR) / max(1, sw) / 2
    n = lost = 0
    for g in segs:
        if g["layout"] != "crop" or not g["aims"]:
            continue
        for t, fs in samples:
            if g["s"] <= t < g["e"] and not any(a <= t < b for a, b in g.get("crowd") or []):
                fx = [f for f in fs if not is_cam(f)]
                if not fx:
                    continue
                n += 1
                f = _main(fx, lambda q: False)
                if abs(f[0] - _x_at(g["aims"], t)) > hw * 0.85:
                    lost += 1
    return round(lost / n, 3) if n else 0.0


# ---------------- the edit: camera rhythm (19 Nov research) ----------------
# A static crop for the whole clip reads as a re-upload (openshorts punch_in.py); edited clips change the framing on
# the speech's beats. Recipe from Plextrang/Claude-Video-Clipper plan.py (tested short-form engine): open on a quick
# zoom-out snap, alternate wide <-> punched-in on sentence ends >= 2.8 s apart (a hard cut, like a 2-camera shoot),
# always change framing on a camera cut, a slow +3% push inside each beat so the frame never sits dead, and ONE eased
# snap zoom near the payoff. Punch <= 1.18 (openshorts: past ~15% heads get cut and upscaling shows); never zoom a slice
# narrower than 540 source px (soft), never let the face fill more than 55% of the height.
# 19 Nov benchmark: the winning clip page punches much harder (wide stage -> face close-up); the resolution guard below
# keeps a 1080p source near 1.12 and lets a 1440p/4K source go up to 1.35
WIDE_Z, PUNCH_Z = [1.0, 1.03], [1.28, 1.35, 1.22]
DRIFT, OPEN_Z, OPEN_S, SNAP_S = 0.03, 1.18, 0.3, 0.27


def _ease_out(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def zoom_plan(Wt, dur, cuts):
    """Beats [{a, b, z, kind: open|cut|snap}] over the clip (seconds on the final timeline)."""
    must = sorted({round(c, 2) for c in cuts if 0.3 < c < dur - 1.0})
    soft = [round(Wt[i + 1][0] - 0.03, 2) for i in range(len(Wt) - 1)
            if re.search(r"[.?!]$", str(Wt[i][2])) or Wt[i + 1][0] - Wt[i][1] > 0.45]
    bounds, last = [], 0.0
    for c in sorted(set(must) | set(soft)):
        if c >= dur - 1.2:
            break
        if c in must:
            if c - last >= 0.5:
                bounds.append(c); last = c
        elif c - last >= 2.8 and all(m <= c or m - c >= 1.5 for m in must):
            bounds.append(c); last = c
        elif c - last > 6.0:
            bounds.append(c); last = c
    beats = list(zip([0.0] + bounds, bounds + [dur]))
    plan = []
    for i, (a, b) in enumerate(beats):
        z = PUNCH_Z[(i // 2) % len(PUNCH_Z)] if i % 2 else WIDE_Z[(i // 2) % len(WIDE_Z)]
        plan.append({"a": round(a, 2), "b": round(b, 2), "z": z, "kind": "open" if i == 0 else "cut"})
    late = [p for p in plan[1:] if p["z"] > 1.05 and p["a"] >= 0.55 * dur and not any(abs(p["a"] - m) < 0.05 for m in must)]
    if late:
        late[0]["kind"] = "snap"                      # the payoff gets the one eased zoom (and a whoosh)
    return plan


def z_at(plan, t):
    for i, p in enumerate(plan):
        if p["a"] <= t < p["b"] or i == len(plan) - 1:
            zb = p["z"] + DRIFT * min(1.0, (t - p["a"]) / max(0.1, p["b"] - p["a"]))
            if p["kind"] == "open" and t - p["a"] < OPEN_S:
                return OPEN_Z + (zb - OPEN_Z) * _ease_out((t - p["a"]) / OPEN_S)
            if p["kind"] == "snap" and i and t - p["a"] < SNAP_S:
                zp = plan[i - 1]["z"] + DRIFT
                return zp + (zb - zp) * _ease_out((t - p["a"]) / SNAP_S)
            return zb
    return 1.0


def _face_x_at(fx, t, gap=0.6):
    """The face centre (0-1) at t, interpolated between samples; None when no sample is within `gap` s."""
    if not fx:
        return None
    for (t0, x0), (t1, x1) in zip(fx, fx[1:]):
        if t0 <= t <= t1:
            if t1 - t0 > 2 * gap:
                return x0 if t - t0 < t1 - t else x1
            return x0 + (x1 - x0) * (t - t0) / max(0.01, t1 - t0)
    near = min(fx, key=lambda p: abs(p[0] - t))
    return near[1] if abs(near[0] - t) <= gap else None


def _crop_cmds(seg, info, zp, path, fps=30):
    """sendcmd file for one crop segment: per-frame crop w/h/x/y (pan from the tracker + zoom from the plan), only the
    frames where something changes (openshorts sendcmd_lines). Times relative to the segment start."""
    sw, sh = info["src"]
    cw0 = min(sw, int(sh * CROP_AR)) // 2 * 2
    zmax = min(max(PUNCH_Z) + DRIFT, cw0 / 540.0, 0.55 / max(0.05, seg.get("fh") or 0.2))
    fy, fh = seg.get("fy") or 0.38, seg.get("fh") or 0.2
    lines, prev = [], None
    stats = info.setdefault("zlost", [0, 0])            # [frames with a face, frames with it at/out of the window edge]
    n = int(round((seg["e"] - seg["s"]) * fps))
    for f in range(n + 1):
        t = seg["s"] + f / fps
        z = max(1.0, min(zmax, z_at(zp, t))) if zp else 1.0
        w, h = int(cw0 / z) // 2 * 2, int(sh / z) // 2 * 2
        cx = (_x_at(seg["aims"], t) if seg["aims"] else 0.5) * sw
        in_crowd = any(a <= t < b for a, b in seg.get("crowd") or [])
        fx = None if in_crowd else _face_x_at(info.get("face_x") or [], t)
        if fx is not None and z > 1.02:
            # keep the real face inside the middle 60% of the zoomed window (shift only as much as needed)
            fx *= sw
            lim = 0.30 * w
            if fx > cx + lim:
                cx = fx - lim
            elif fx < cx - lim:
                cx = fx + lim
        x = int(max(0, min(sw - w, cx - w / 2))) // 2 * 2
        if fx is not None:
            fpx = fx if fx > 1.5 else fx * sw
            stats[0] += 1
            stats[1] += not (x + 0.08 * w <= fpx <= x + 0.92 * w)    # the face centre near / past the window edge
        head_top = (fy - 1.1 * fh) * sh                 # hair / a cap above the face box (19 Nov: a cap was cut)
        # 19 Nov render: at 40% down a tight punch put the mid-screen caption on her mouth; at 33% the chin clears it
        y = fy * sh - 0.33 * h
        y = min(y, head_top - 0.03 * h)                 # never cut the top of the head
        y = int(max(0, min(sh - h, y))) // 2 * 2
        near = [] if in_crowd else [p for p in info.get("face_yh") or [] if abs(p[0] - t) <= 0.3]
        if near:                                         # where the face is ON SCREEN now (captions keep off it)
            _, cy, chh = min(near, key=lambda p: abs(p[0] - t))
            top_o = ((cy - 1.1 * chh) * sh - y) / h * H
            bot_o = ((cy + 0.65 * chh) * sh - y) / h * H
            info.setdefault("face_out", []).append((round(t, 3), int(top_o), int(bot_o)))
        box = (w, h, x, y)
        if box != prev:
            tt = f / fps
            lines.append(f"{tt:.4f} crop@c w {w}, crop@c h {h}, crop@c x {x}, crop@c y {y};")
            prev = box
    open(path, "w").write("\n".join(lines) + "\n")
    return cw0


def _crop_x_expr(aims, sw, sh):
    """Crop x over time: a jump at a hard cut (glide 0), a straight pan between keyframes of one shot (glide 1)."""
    cw = min(sw, int(sh * CROP_AR)) // 2 * 2
    pts = [(a[0], max(0, min(sw - cw, int(a[1] * sw - cw / 2))), a[2] if len(a) > 2 else 0) for a in aims]
    expr = str(pts[-1][1])
    for (t0, x0, _), (t1, x1, g1) in reversed(list(zip(pts, pts[1:]))):
        piece = f"({x0}+({x1 - x0})*(t-{t0})/{max(0.01, round(t1 - t0, 3))})" if g1 and x1 != x0 else str(x0)
        expr = f"if(lt(t,{t1}),{piece},{expr})"
    return cw, expr


# ---------------- captions ----------------
def _ts(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


HOOK_Y = {"stack": 700, "crop": 402, "fill": 400}     # crop: inside the title band (BAND 480), under the logo     # 19 Nov frames: the stack hook sat on the reactor's eyes -> the seam
# 19 Nov research (ai-reels-editor-skill layout.md, the Reels safe zone shared by IG/TikTok/Shorts): nothing in the top
# 220 px, nothing below y 1470 (username, caption, audio row). Captions at 1450/1560 ran into it; crop captions sit in
# the chest band (Claude-Video-Clipper: ~2/3 down), the fill ones just under the picture.
# 19 Nov benchmark: Short Form Comedy and Don't Tell Comedy put captions mid-screen (~52% down): on the chest in a
# close-up, by the mic in a wide shot
CAP_Y = {"stack": 1400, "crop": 1000, "fill": 1400}


def place_notes(notes, Wt, dur):
    """19 Nov (originality, golden rule): the page's own notes on the clip ({"after": "<words from the transcript>",
    "text": "<our note>", "kind": "react"|"context"}). Each starts when its anchor words are spoken (found in the
    tightened word list, so cuts don't shift it) and stays ~3 s; no two overlap. A note whose anchor is not found is
    dropped (never shown at a wrong moment), except "context" notes with no anchor, which open at 0.6 s."""
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", str(s).lower()).split()
    ws = [norm(w[2]) for w in Wt]
    flat = [(i, x) for i, xs in enumerate(ws) for x in xs]
    out = []
    for n in notes or []:
        txt = str(n.get("text") or "").strip()
        if not txt:
            continue
        anchor = norm(n.get("after") or "")
        st = None
        if anchor:
            # 19 Nov test: the moment-picker quotes the speech a little differently from whisper (word order, spelling):
            # best window of k+2 words where most anchor words appear (exact or near-spelled), at least 60% and 2 words
            import difflib
            seq = [x for _, x in flat]
            k = len(anchor)
            near = lambda a, b: a == b or (len(a) > 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)
            best, best_j = 0, None
            for j in range(0, max(1, len(seq) - k + 1)):
                win = seq[j:j + k + 2]
                hit = sum(1 for a in anchor if any(near(a, b) for b in win))
                if hit > best:
                    best, best_j = hit, j
            if best_j is not None and best >= max(2 if k >= 2 else 1, int(0.6 * k + 0.5)):
                win = seq[best_j:best_j + k + 2]
                last = max(i for i, b in enumerate(win) if any(near(a, b) for a in anchor))
                st = Wt[flat[min(len(flat) - 1, best_j + last)][0]][1]          # right after the last matching word
        elif n.get("kind") == "context":
            st = 0.6
        if st is None or st > dur - 1.2:
            continue
        en = min(dur - 0.2, st + max(2.4, min(4.0, 0.33 * len(txt.split()) + 1.4)))
        if out and st < out[-1][1] + 0.3:
            ps, pe, pt, pk = out[-1]
            if st - 0.25 - ps >= 1.8:                 # the earlier note has been read: shorten it, keep the new one
                out[-1] = (ps, round(st - 0.25, 2), pt, pk)
            else:
                continue
        if len(txt.split()) > 11 or len(txt) > 64:        # a note is a glance, never a paragraph (never cut mid-word)
            continue
        out.append((round(st, 2), round(en, 2), txt, n.get("kind") or "react"))
    return out


def ass(path, hook, Wd, dur, segs, accent="&H0030D8FF&", brand="", notes=None, face_y=None):
    """Hook banner (frame 1 to the end) + 3-word pop captions; the spoken word in the accent colour, a touch larger.
    Positions follow the layout on screen at that moment (segs from analyse())."""
    esc = lambda s: str(s).replace("{", "(").replace("}", ")").replace("\\", "/").replace("\n", " ")
    segs = segs or [{"s": 0, "e": dur, "layout": "fill"}]
    lay_at = lambda t: next((g["layout"] for g in segs if g["s"] <= t < g["e"]), segs[-1]["layout"])
    L = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
         "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
         "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
         # 19 Nov: in the title band the hook can be bigger (it read small); wraps inside 70 px margins
         "Style: HookT,Montserrat Thin,82,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,13,7,5,90,90,0,1",
         "Style: Hook,Anton,100,&H00111111,&H00111111,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,1,0,3,22,0,5,70,70,0,1",
         # 19 Nov research (OpenClipper "beast"/"hustle" presets, the MrBeast caption look): heavy black outline
         # (~0.17 em) and a HARD opaque drop shadow, not a thin outline with a soft grey one
         "Style: Cap,Montserrat Thin,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,12,6,5,60,60,0,1",
         "Style: Brand,Montserrat Thin,40,&H50FFFFFF,&H50FFFFFF,&H70000000,&H00000000,0,0,0,0,100,100,2,0,1,3,0,5,40,40,0,1",
         # the page's own voice (notes): brand-yellow box, black bold text, smaller than the hook
         # font family inside assets/fonts/Montserrat-ExtraBold.ttf is "Montserrat Thin" (style ExtraBold): "Montserrat
         # ExtraBold" matched nothing and fell back to a thin system font (19 Nov test frames)
         "Style: Note,Montserrat Thin,60,&H00111111,&H00111111,&H0030D8FF,&H0030D8FF,-1,0,0,0,100,100,0,0,3,20,0,5,80,80,0,1",
         "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    if brand:
        # 19 Nov (owner: "did you add our branding?"): a small, see-through handle the whole clip, under the captions and
        # out of the safe area for the Reels buttons. Campaigns that forbid watermarks turn it off (sources.json).
        L.append(f"Dialogue: 0,{_ts(0)},{_ts(dur)},Brand,,0,0,0,,{{\\pos({W // 2},1640)}}{esc(brand)}")
    if hook and not BAND:
        # 19 Nov benchmark (Short Form Comedy, 9.8M): the hook is a big caption-style line in the middle for the opening
        # seconds, its last words in the accent colour, then the clean frame; no permanent bar
        hw = esc(hook.upper()).split()
        k = max(1, len(hw) - 2)
        txt = " ".join(hw[:k]) + " {\\c" + accent + "}" + " ".join(hw[k:])
        en = min(dur, HOOK_SECONDS)
        y = CAP_Y[lay_at(0.1)] + 250                 # two lines under the captions with a clear gap (19 Nov frames)
        L.append(f"Dialogue: 2,{_ts(0)},{_ts(en)},HookT,,0,0,0,,{{\\pos({W // 2},{y})\\fscx70\\fscy70"
                 f"\\t(0,140,\\fscx100\\fscy100)\\fad(0,160)}}{txt}")
    elif hook:
        for gi, g in enumerate(segs):
            e = dur if gi == len(segs) - 1 else g["e"]
            fs = max(72, min(100, int(100 * 34 / max(34, len(hook)))))    # one line in the band (Anton ~0.27 em/char)
            L.append(f"Dialogue: 2,{_ts(g['s'])},{_ts(e)},Hook,,0,0,0,,{{\\pos({W // 2},{HOOK_Y[g['layout']]})\\fs{fs}}}{esc(hook.upper())}")
    for st, en, txt, kind in (notes if NOTES_ON_SCREEN else []) or []:
        # 19 Nov test: the layout (and so the hook) can change while a note is up: sit below the LOWEST hook in its span
        lays = {g["layout"] for g in segs if g["s"] < en and g["e"] > st} or {lay_at(st)}
        y = max(HOOK_Y[l] for l in lays) + (170 if hook else 0)
        # 19 Nov frames: the note covered the speaker's face. Over a face for >25% of its time -> the low band above the
        # captions, whichever band covers the face less
        span = [(a, b) for t, a, b in (face_y or []) if st <= t <= en]
        if span:
            over = lambda yy: sum(1 for a, b in span if a < yy + 120 and b > yy - 120) / len(span)
            low = min(CAP_Y[l] for l in lays) - 230
            if over(y) > 0.15 and over(low) < over(y):
                y = low
        L.append(f"Dialogue: 3,{_ts(st)},{_ts(en)},Note,,0,0,0,,{{\\pos({W // 2},{y})\\fscx80\\fscy80\\t(0,120,\\fscx100\\fscy100)"
                 f"\\fad(80,120)}}{esc(txt)}")
    # 19 Nov test: "WHERE THE FUCK DID YOU LOSE IT" on screen. The audio stays original; the on-screen words are masked
    mask = lambda s: re.sub(r"(?i)\b(f)u(ck\w*)|\b(s)hi(t\w*)|\b(b)itc(h\w*)|\b(m)otherf\w*|\b(c)un(t\w*)",
                            lambda m: next(g for g in m.groups() if g) + "**" + (m.group(0)[-1] if len(m.group(0)) > 3 else ""), s)
    Wd = [(a, b, mask(t)) for a, b, t in Wd]
    groups, cur = [], []
    for w in Wd:
        cur.append(w)
        if len(cur) == 3 or re.search(r"[.!?,…]$", w[2]):
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)
    # 19 Nov render: in a tight punch-in the mid-screen caption sat on her mouth. A caption group whose time has the
    # face (on-screen box, after zoom) over the caption line moves down to the low line (still inside the safe zone);
    # never during the opening hook (the hook sits there)
    gy = []
    for gi, g in enumerate(groups):
        lay = lay_at(g[0][0])
        y = CAP_Y[lay]
        span = [(a, b) for t, a, b in (face_y or []) if g[0][0] - 0.05 <= t <= g[-1][1] + 0.05]
        if span and g[0][0] >= HOOK_SECONDS and sum(1 for a, b in span if a < y + 60 and b > y - 60) / len(span) > 0.3:
            y = min(1340, y + 330)
        gy.append(y)
    for gi, g in enumerate(groups):
        g_end = groups[gi + 1][0][0] if gi + 1 < len(groups) else min(dur, g[-1][1] + 0.5)
        for k, w in enumerate(g):
            st, en = w[0], (g[k + 1][0] if k + 1 < len(g) else g_end)
            if en - st < 0.03:
                continue
            pop = "\\fscx86\\fscy86\\t(0,90,\\fscx100\\fscy100)" if k == 0 else ""
            # 19 Nov research (OpenClipper "beast" preset): the spoken word yellow, 1.15x and tilted 2 degrees
            txt = " ".join((f"{{\\c{accent}\\fscx115\\fscy115\\frz2}}{esc(x[2]).upper()}{{\\c&H00FFFFFF&\\fscx100\\fscy100\\frz0}}" if j == k
                            else esc(x[2]).upper()) for j, x in enumerate(g))
            L.append(f"Dialogue: 1,{_ts(st)},{_ts(en)},Cap,,0,0,0,,{{\\pos({W // 2},{gy[gi]}){pop}}}{txt}")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


# ---------------- render ----------------
def _ff(p):
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _layout_vf(lay, info, seg, sub):
    """The filter for one layout; times inside a crop aim are relative to the segment start."""
    sw, sh = info["src"]
    tail = (("," + sub) if sub else "") + ",format=yuv420p[v]"
    if lay == "crop" and info.get("zoom") is not None and info.get("work"):
        p = os.path.join(info["work"], f"crop_{int(seg['s'] * 100)}.cmd")
        cw = _crop_cmds(seg, info, info["zoom"], p)
        pad = f",pad={W}:{H}:0:{BAND}:color={BAND_COLOR}" if BAND else ""
        return (f"[0:v]sendcmd=f='{_ff(p)}',crop@c={cw}:{sh}:0:0,scale={W}:{PIC_H}:flags=lanczos,setsar=1{pad}{tail}")
    if lay == "crop":
        aims = [[round(a[0] - seg["s"], 2)] + list(a[1:]) for a in seg["aims"]]
        cw, xe = _crop_x_expr(aims, sw, sh)
        pad = f",pad={W}:{H}:0:{BAND}:color={BAND_COLOR}" if BAND else ""
        return f"[0:v]crop={cw}:{sh}:'{xe}':0,scale={W}:{PIC_H}:flags=lanczos{pad}{tail}"
    if lay == "stack":
        fx, fy, fh = info["cam"]
        bw, bh = int(fh * sh * 3.3), int(fh * sh * 3.3 * 700 / W)
        bw, bh = min(bw, sw) // 2 * 2, min(bh, sh) // 2 * 2
        bx = max(0, min(sw - bw, int(fx * sw - bw / 2)))
        by = max(0, min(sh - bh, int(fy * sh - bh * 0.42)))
        gw = min(int(sh * W / 1220) // 2 * 2, sw)
        gx = (sw - gw) // 2
        return (f"[0:v]split=2[c][g];[c]crop={bw}:{bh}:{bx}:{by},scale={W}:700:flags=lanczos[cam];"
                f"[g]crop={gw}:{sh}:{gx}:0,scale={W}:1220:flags=lanczos[game];[cam][game]vstack{tail}")
    return (f"[0:v]split=2[bg][fg];[bg]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,gblur=sigma=7,"
            f"eq=brightness=-0.18:saturation=0.85,scale={W}:{H}:flags=bilinear[bgb];[fg]scale={W}:-2:flags=lanczos[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2+40{tail}")


LOGO = os.path.join(ROOT, "assets", "brand", "cutcapsule-logo.png")
# top-left, below the 220 px Reels header (19 Nov: it sat at y 150, inside it), above the hook (crop hook now at 370)
LOGO_W, LOGO_X, LOGO_Y, LOGO_A = 140, 40, 236, 0.92     # small, top-left (Don't Tell Comedy); None = centred (band)


def _logo_tail(pre, logo):
    """Filter text that puts the logo (input 1) over [pre] and outputs [v]."""
    if not logo:
        return f"[{pre}]format=yuv420p[v]"
    # 19 Nov frames: the white wordmark got lost on bright backgrounds -> a soft dark shadow under it
    return (f"[1:v]scale={LOGO_W}:-1,format=rgba,pad=iw+24:ih+24:12:12:color=black@0,split[lg0][sh0];"
            f"[lg0]colorchannelmixer=aa={LOGO_A}[lg];"
            f"[sh0]colorchannelmixer=rr=0:gg=0:bb=0:aa=0.75,boxblur=7:2[sh];" +
            (f"[{pre}][sh]overlay={LOGO_X - 10}:{LOGO_Y - 10}[p2];[p2][lg]overlay={LOGO_X - 12}:{LOGO_Y - 12},format=yuv420p[v]"
             if LOGO_X is not None else
             f"[{pre}][sh]overlay=(W-w)/2+2:{LOGO_Y - 10}[p2];[p2][lg]overlay=(W-w)/2:{LOGO_Y - 12},format=yuv420p[v]"))


SFX = os.path.join(ROOT, "assets", "audio", "sfx")


def _audio(info, first_idx):
    """Extra inputs + the audio graph: the voice lightly cleaned (highpass, gentle compression: Claude-Video-Clipper
    mix_audio), at most 2 whooshes UNDER it (the opening snap, the payoff snap; ai-reels-editor: SFX at ~0.7 of base,
    never above the voice), then -14 LUFS. Returns (inputs, filter, label)."""
    cues = []
    zp = info.get("zoom") or []
    if zp:
        cues.append(("whoosh-cine.mp3", 0.0, 0.22))
        snap = next((p for p in zp if p["kind"] == "snap"), None)
        if snap:
            cues.append(("whoosh-fast.mp3", max(0.0, snap["a"] - 0.12), 0.18))
    cues = [c for c in cues if os.path.exists(os.path.join(SFX, c[0]))]
    ins, chains, labels = [], ["[0:a]highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2[vo]"], ["[vo]"]
    for k, (f, at, vol) in enumerate(cues):
        ins += ["-i", os.path.join(SFX, f)]
        d = int(at * 1000)
        chains.append(f"[{first_idx + k}:a]aformat=channel_layouts=stereo,aresample=48000,volume={vol},adelay={d}|{d}[s{k}]")
        labels.append(f"[s{k}]")
    mix = (f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first," if len(labels) > 1 else "[vo]")
    chains.append(f"{mix}loudnorm=I=-14:TP=-1.5:LRA=11[a]" if len(labels) > 1 else "[vo]loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    return ins, ";".join(chains), "[a]"


def render(src, info, assf, out, logo=None):
    """One segment: layout + captions in a single pass. Several layouts: each segment framed on its own (no captions),
    joined, then captions + loudness in one pass over the joined video so they run across the joins."""
    sub = f"ass='{_ff(assf)}':fontsdir='{_ff(FONTS)}'"
    segs = info["segments"]
    has_audio = bool(probe(src).get("audio"))
    # 19 Nov speed: "fast" is ~2x "medium" for the same look at CRF 19 (platforms re-encode every upload anyway)
    enc = venc(True) + ["-r", "30", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    li = ["-i", logo] if logo else []
    if len(segs) == 1:
        vf = _layout_vf(segs[0]["layout"], info, segs[0], sub).replace(",format=yuv420p[v]", "[pre]") + ";" + _logo_tail("pre", logo)
        if has_audio:
            ins, af, al = _audio(info, 1 + len(li) // 2)
            run(["ffmpeg", "-v", "error", "-y", "-i", src] + li + ins + ["-filter_complex", vf + ";" + af,
                 "-map", "[v]", "-map", al] + enc + ["-movflags", "+faststart", out], 2400)
        else:
            run(["ffmpeg", "-v", "error", "-y", "-i", src] + li + ["-filter_complex", vf, "-map", "[v]"] + enc
                + ["-movflags", "+faststart", out], 2400)
        return out
    work = os.path.dirname(out)
    parts = [os.path.join(work, f"seg{i}.mp4") for i in range(len(segs))]
    from concurrent.futures import ThreadPoolExecutor             # 19 Nov speed: segments framed in parallel
    def one(i):
        g = segs[i]
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{g['s']:.3f}", "-to", f"{g['e']:.3f}", "-i", src, "-filter_complex",
             _layout_vf(g["layout"], info, g, None), "-map", "[v]", "-map", "0:a?"] + venc(False)
            + ["-threads", "3", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", parts[i]], 1800)
    with ThreadPoolExecutor(2 if nvenc() else 3) as ex:   # a GTX 1650 runs 2-3 NVENC sessions at once
        list(ex.map(one, range(len(segs))))
    lst = os.path.join(work, "segs.txt")
    open(lst, "w").write("".join(f"file '{os.path.basename(p)}'\n" for p in parts))
    joined = os.path.join(work, "joined.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], 600)
    vf = f"[0:v]{sub}[pre];" + _logo_tail("pre", logo)
    if has_audio:
        ins, af, al = _audio(info, 1 + len(li) // 2)
        run(["ffmpeg", "-v", "error", "-y", "-i", joined] + li + ins + ["-filter_complex", vf + ";" + af,
             "-map", "[v]", "-map", al] + enc + ["-movflags", "+faststart", out], 2400)
    else:
        run(["ffmpeg", "-v", "error", "-y", "-i", joined] + li + ["-filter_complex", vf, "-map", "[v]"] + enc
            + ["-movflags", "+faststart", out], 2400)
    for p in parts + [lst, joined]:
        os.remove(p)
    return out


def lufs(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True,
                       timeout=300, creationflags=NOWIN)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


# 19 Nov (owner: "just copy paste what is on github"): the cut + reframe + edit is Plextrang/Claude-Video-Clipper's
# engine, copied into engine/cvc and used as-is (engine/cvc_run.py). "own" = the hand-built path below (kept as a fallback).
ENGINE = "cvc"


def _make_cvc(src, Wd, a2, b2, ranges, hook, out_dir, lang, brand, notes):
    import cvc_run
    rs = [[round(s, 3), round(e, 3)] for s, e in ranges] if 1 <= len(ranges) <= 6 else [[a2, b2]]
    hook_ass = None
    if hook:
        hook_ass = os.path.join(out_dir, "hook.ass")
        hw = str(hook).upper().replace("{", "(").replace("}", ")").split()
        k = max(1, len(hw) - 2)
        txt = " ".join(hw[:k]) + " {\\c&H000AD6FF&}" + " ".join(hw[k:])
        open(hook_ass, "w", encoding="utf-8").write("\n".join([
            "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
            "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: HookT,Montserrat Thin,82,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,13,7,5,90,90,0,1",
            "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            # cvc captions sit at y 1270: the hook goes above them, in the chest band, for the opening line only
            f"Dialogue: 2,{_ts(0)},{_ts(HOOK_SECONDS)},HookT,,0,0,0,,{{\\pos({W // 2},1010)\\fscx70\\fscy70"
            f"\\t(0,140,\\fscx100\\fscy100)\\fad(0,160)}}{txt}"]) + "\n")
    logo = LOGO if (brand and os.path.exists(LOGO)) else None
    final, meta, plan = cvc_run.make(src, rs, Wd, hook, out_dir, logo, hook_ass)
    q = probe(final); q["lufs"] = lufs(final)
    d = max(1.0, q["dur"])
    run(["ffmpeg", "-v", "error", "-y", "-i", final, "-vf", f"fps={6 / d},scale=450:800,tile=6x1", "-frames:v", "1", "-q:v", "3",
         os.path.join(out_dir, "sheet.jpg")], 120)
    run(["ffmpeg", "-v", "error", "-y", "-ss", "0.8", "-i", final, "-frames:v", "1", "-q:v", "2", os.path.join(out_dir, "cover.jpg")], 60)
    Wt = [(w["s"], w["e"], w["w"]) for w in meta["words"]]
    modes = sorted({s["mode"] for s in meta["shots"]})
    res = {"layout": modes[0] if len(modes) == 1 else "mixed:" + "+".join(modes),
           "segments": [{"s": s["t0"], "e": s["t1"], "layout": s["mode"]} for s in meta["shots"]],
           "faces": {}, "shots": len(meta["shots"]), "lost": 0.0, "engine": "cvc (Claude-Video-Clipper)",
           "cut": [round(a2, 2), round(b2, 2)], "kept": meta["parts"], "removed_s": 0, "lang": lang, "words": len(Wt),
           "format": q, "text": " ".join(w[2] for w in Wt), "notes": [], "notes_asked": len(notes or []), "asr": ASR[0],
           "beats": len(plan.get("transitions") or []), "notes_on_screen": False}
    json.dump({"words": Wt, **res}, open(os.path.join(out_dir, "clip.json"), "w"), ensure_ascii=False)
    return res


def make_clip(src, a, b, hook, out_dir, lang=None, brand="", glossary=None, notes=None, wprompt=""):
    """src = a downloaded window of the video; a, b = the asked moment inside it (seconds in src).
    wprompt: a sample in the wanted script (19 Nov Hindi page: whisper wrote garbled Devanagari; a Roman Hinglish sample
    as initial_prompt makes it write Latin, which our captions and the note anchors need)."""
    os.makedirs(out_dir, exist_ok=True)
    Wd, lang = words(src, lang, " ".join(x for x in (wprompt, ", ".join(glossary or [])) if x))
    Wd = fix_names(Wd, glossary)
    a2, b2 = trim(Wd, a, b)
    ranges = keep_ranges(Wd, a2, b2, loudness(src))
    if ENGINE == "cvc":
        # 19 Nov: cvc has crop / fit only. A streamer's webcam box over gameplay needs our stack layout (cam on top,
        # game below), so those clips keep the own engine; everything else uses cvc
        try:
            cam = analyse(src).get("cam")
        except Exception:
            cam = None
        if not cam:
            return _make_cvc(src, Wd, a2, b2, ranges, hook, out_dir, lang, brand, notes)
        log_ = "clipcore: webcam box found, own engine (stack layout)"
        print(log_)
    tight = tighten(src, ranges, os.path.join(out_dir, "tight.mp4"))
    Wt = remap(Wd, ranges)
    info = analyse(tight)
    info["work"] = out_dir
    # 19 Nov research: the camera rhythm (zoom_plan) on every crop shot
    info["zoom"] = zoom_plan(Wt, info["dur"], info["cuts"]) if any(g["layout"] == "crop" for g in info["segments"]) else None
    if info["zoom"] is not None:                      # the camera first, so captions know where the face is on screen
        for g in info["segments"]:
            if g["layout"] == "crop":
                _crop_cmds(g, info, info["zoom"], os.path.join(out_dir, f"crop_{int(g['s'] * 100)}.cmd"))
    assf = os.path.join(out_dir, "captions.ass")
    logo = LOGO if (brand and os.path.exists(LOGO)) else None      # 19 Nov: the page's real logo; text handle only without it
    placed = place_notes(notes, Wt, info["dur"])
    ass(assf, hook, Wt, info["dur"], info["segments"], brand="" if logo else brand, notes=placed,
        face_y=info.get("face_out") or info.get("face_y"))
    final = render(tight, info, assf, os.path.join(out_dir, "final.mp4"), logo)
    q = probe(final); q["lufs"] = lufs(final)
    d = max(1.0, q["dur"])
    # 19 Nov: at 270x480 the checker called readable captions "unreadable"; 6 frames at 450x800 (2700x800)
    run(["ffmpeg", "-v", "error", "-y", "-i", final, "-vf", f"fps={6 / d},scale=450:800,tile=6x1", "-frames:v", "1", "-q:v", "3",
         os.path.join(out_dir, "sheet.jpg")], 120)
    run(["ffmpeg", "-v", "error", "-y", "-ss", "0.8", "-i", final, "-frames:v", "1", "-q:v", "2", os.path.join(out_dir, "cover.jpg")], 60)
    os.remove(tight)
    res = {"layout": info["layout"], "segments": info["segments"],
           "faces": {k: info.get(k) for k in ("face_share", "face_h", "cam")}, "shots": len(info["cuts"]),
           "lost": max(info.get("lost", 0), round(info["zlost"][1] / info["zlost"][0], 3) if info.get("zlost") and info["zlost"][0] else 0),
           "cut": [round(a2, 2), round(b2, 2)], "kept": ranges, "removed_s": round((b2 - a2) - sum(e - s for s, e in ranges), 2),
           "lang": lang, "words": len(Wt), "format": q, "text": " ".join(w[2] for w in Wt),
           "notes": [{"s": s, "e": e, "text": t, "kind": k} for s, e, t, k in placed], "notes_asked": len(notes or []),
           "asr": ASR[0], "beats": len(info.get("zoom") or []), "notes_on_screen": NOTES_ON_SCREEN}
    json.dump({"words": Wt, **res}, open(os.path.join(out_dir, "clip.json"), "w"), ensure_ascii=False)
    return res


if __name__ == "__main__":       # python engine/clipcore.py <src.mp4> <a> <b> "<hook>" <out_dir>
    print(json.dumps(make_clip(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]), indent=1))
