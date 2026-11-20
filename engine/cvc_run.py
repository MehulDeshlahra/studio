"""Studio wrapper around engine/cvc (Plextrang/Claude-Video-Clipper, copied in as-is on 19 Nov).
Their engine does the cut + reframe + edit (zooms, word captions, whooshes, -14 LUFS). We only add what it has no slot
for: the opening hook line, the page logo and swear masking on screen. Called from clipcore.make_clip."""
import os, re, json, subprocess
from pathlib import Path
from cvc import cut as cvc_cut, plan as cvc_plan, edit as cvc_edit
from cvc.common import probe as cvc_probe

BRAND = {"accent": "#FFD60A", "text": "#FFFFFF", "outline": "#000000"}
MASK = re.compile(r"(?i)\b(f)u(ck\w*)|\b(s)hi(t\w*)|\b(b)itc(h\w*)|\b(m)otherf\w*|\b(c)un(t\w*)")


def _mask(t):
    return MASK.sub(lambda m: next(g for g in m.groups() if g) + "**" + (m.group(0)[-1] if len(m.group(0)) > 3 else ""), t)


def _tracked(src):
    """19 Nov: cvc holds ONE crop per camera shot, so a comedian who walks ends half out of frame. Our face tracker
    (clipcore.analyse: smoothed path, dead zone, pan limit) gives the crop centre over src time instead."""
    import clipcore
    a = clipcore.analyse(str(src))
    segs = [g for g in a["segments"] if g["layout"] == "crop"]
    # 19 Nov: the dead-zone path left the face off-centre and cvc's punch-in (zoom around the centre) pushed it out of
    # frame. Follow the face itself, smoothed over +-1 s, so it sits in the centre and every zoom keeps it in.
    fx = a.get("face_x") or []

    def x_at(t, lo=-1e9, hi=1e9):
        """Face centre at t, averaged over +-1 s but only inside [lo, hi) (one camera shot: never mixes two shots)."""
        g = next((g for g in segs if g["s"] <= t < g["e"]), None)
        if not g or any(p <= t < q for p, q in g.get("crowd") or []):
            return None
        near = [x for tt, x in fx if abs(tt - t) <= 1.0 and lo <= tt < hi]
        return sum(near) / len(near) if near else None
    return x_at


def _patch_crop(x_at, holder):
    """Wrap cvc's reframe so a 'crop' shot pans along x_at (a piecewise-linear ffmpeg expression, 0.5 s keyframes)."""
    from cvc import reframe as R
    orig_an, orig_plan, orig_sf = R.analyse_range, R.plan_shots, R.shot_filter

    def an(video, start, dur, w, h):
        holder["start"] = start
        return orig_an(video, start, dur, w, h)

    def plan(shots, w, h, min_fit=1.0):
        out = orig_plan(shots, w, h, min_fit)
        for s in out:
            if s["mode"] == "crop" and x_at(holder["start"] + (s["a"] + s["b"]) / 2) is not None:
                s["focus"][0] = R.W / 2                 # the tracker keeps the face near the centre: zoom around it
        return out

    def sf(inp, shot, w, h, label, fps=R.FPS):
        if shot["mode"] != "crop":
            return orig_sf(inp, shot, w, h, label, fps)
        cw = R.crop_width(w, h)
        t0 = holder["start"] + shot["a"]
        n = max(1, int((shot["b"] - shot["a"]) / 0.5))
        raw = []
        for k in range(n + 1):
            tt = min(shot["b"] - shot["a"], k * 0.5)
            raw.append((round(tt, 2), x_at(t0 + tt, t0, holder["start"] + shot["b"])))
        # 19 Nov frames: a moment with no face sample fell back to cvc's static x and cut the face at the edge; carry the
        # nearest known face position instead (forward, then backward); a shot with no face at all keeps cvc's x
        known = [x for _, x in raw if x is not None]
        pts, last = [], (known[0] if known else None)
        for tt, x in raw:
            last = x if x is not None else last
            pts.append((tt, shot["x0"] if last is None else int(min(max(last * w - cw / 2, 0), w - cw)) // 2 * 2))
        if len({p[1] for p in pts}) <= 1:
            return orig_sf(inp, {**shot, "x0": pts[0][1]}, w, h, label, fps)
        expr = str(pts[-1][1])
        for (ta, xa), (tb, xb) in reversed(list(zip(pts, pts[1:]))):
            expr = f"if(lt(t,{tb}),{xa}+({xb - xa})*(t-{ta})/{max(0.01, round(tb - ta, 2))},{expr})"
        trim = f"trim=start={shot['a']:.3f}:end={shot['b']:.3f},setpts=PTS-STARTPTS"
        return (f"[{inp}]{trim},crop={cw}:{h}:'{expr}':0,scale={R.W}:{R.H}:flags=lanczos,"
                f"setsar=1,fps={fps},format=yuv420p[{label}]")
    cvc_cut.analyse_range, cvc_cut.plan_shots, cvc_cut.shot_filter = an, plan, sf
    return lambda: setattr(cvc_cut, "analyse_range", orig_an) or setattr(cvc_cut, "plan_shots", orig_plan) \
        or setattr(cvc_cut, "shot_filter", orig_sf)


MODEL = Path(__file__).resolve().parent / "cvc" / "assets" / "models" / "face_detection_yunet_2023mar.onnx"
# 20 Nov: stream layout = HmdNvd/Gaming-Clipper render_clip.py "facecam split" (blurred backdrop, facecam enlarged on top,
# full 16:9 gameplay below); facecam found by nakhulgithesh/gta6-clipper facecam.py (copied as engine/cvc/gamecam.py).
# Ours on top: the small webcam inside the gameplay is blurred out (19 Nov hold: "streamer shown twice"), captions sit
# under the gameplay inside the Reels safe zone.
CAM_Y, CAM_H, GAME_Y, CAP_Y_STACK = 290, 470, 780, 1450


def _stack_cut(src, a, b, box, info, out):
    x, y, w, h = box
    sw, sh = info["width"], info["height"]
    pad = 6                                             # a little more than the face box, so the inset edge is gone
    bx, by = max(0, x - pad), max(0, y - pad)
    bw, bh = min(sw - bx, w + 2 * pad), min(sh - by, h + 2 * pad)
    fc = (f"[0:v]split=3[bg][cam][game];"
          f"[bg]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,scale=1080:1920,"
          f"eq=brightness=-0.18[bgb];"
          f"[cam]crop={w}:{h}:{x}:{y},scale=-2:{CAM_H}:flags=lanczos,unsharp=5:5:0.7:5:5:0.0[c];"
          f"[game]split=2[g0][g1];[g1]crop={bw}:{bh}:{bx}:{by},boxblur=20:4[gb];[g0][gb]overlay={bx}:{by}[gc];"
          f"[gc]scale=1080:-2:flags=lanczos[g];"
          f"[bgb][c]overlay=(W-w)/2:{CAM_Y}[t];[t][g]overlay=(W-w)/2:{GAME_Y},setsar=1,fps=30,format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src),
                    "-filter_complex", fc, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)], check=True, capture_output=True)


def facecam(src):
    try:
        from cvc import gamecam
        return gamecam.facecam_box(str(src), str(MODEL), samples=12)
    except Exception as e:
        print("cvc_run: facecam check failed", str(e)[:120]); return None


def make(src, ranges, Wd, hook, out_dir, logo=None, hook_ass=None):
    """src: the downloaded window; ranges: [[a, b], ...] in src seconds; Wd: [(s, e, text)] on src.
    Returns (final_mp4, meta, plan)."""
    out_dir = Path(out_dir)
    words = [{"w": _mask(str(t)), "s": float(s), "e": float(e)} for s, e, t in Wd]
    info = cvc_probe(src)
    cutf = out_dir / "cut.mp4"
    box = facecam(src)
    if box:
        a, b = float(ranges[0][0]), float(ranges[-1][1])        # one range: reactions keep their pauses
        _stack_cut(src, a, b, box, info, cutf)
        meta = {"fps": 30, "parts": [[a, b]], "duration": round(b - a, 3), "splices": [],
                "shots": [{"t0": 0.0, "t1": round(b - a, 3), "mode": "stack", "focus": [540, 960]}],
                "words": [{**w, "s": round(w["s"] - a, 3), "e": round(w["e"] - a, 3)} for w in words if a <= w["s"] < b],
                "title": hook, "emphasis": [], "facecam": list(box)}
        plan = cvc_plan.build(meta, BRAND, {"zoom": False, "captions": True, "sfx": "light", "uppercase": True,
                                            "caption_y": CAP_Y_STACK})
        return _finish(cutf, meta, plan, out_dir, logo, hook_ass, hook_y=CAM_Y + CAM_H - 70)
    try:
        undo = _patch_crop(_tracked(src), {"start": 0.0})
    except Exception as e:                              # tracking is a bonus: their static crop still works
        print("cvc_run: tracker unavailable, static crops:", str(e)[:120]); undo = lambda: None
    try:
        meta = cvc_cut.build_clip(Path(src), info, {"ranges": ranges}, words, cutf)
    finally:
        undo()
    if not meta:
        raise RuntimeError("cvc: no words in the clip range")
    meta.update(title=hook, emphasis=[])
    plan = cvc_plan.build(meta, BRAND, {"zoom": True, "captions": True, "sfx": "auto", "uppercase": True})
    return _finish(cutf, meta, plan, out_dir, logo, hook_ass)


def _finish(cutf, meta, plan, out_dir, logo, hook_ass, hook_y=None):
    """cvc's mix + caption render, then our hook (moved to hook_y when given) + logo."""
    if hook_ass and hook_y:
        t = open(hook_ass, encoding="utf-8").read()
        open(hook_ass, "w", encoding="utf-8").write(re.sub(r"\\pos\(540,\d+\)", f"\\\\pos(540,{hook_y})", t))
    wav = out_dir / "mix.wav"
    cvc_edit.mix_audio(cutf, plan["sfx"], wav, plan["duration"])
    edited = out_dir / "edited.mp4"
    cvc_edit.render_python(cutf, plan, wav, edited, out_dir)
    final = out_dir / "final.mp4"
    # our layer: the hook for the opening seconds + the logo, one pass, audio copied
    vf, ins = [], ["-i", str(edited)]
    if hook_ass:
        ff = lambda p: str(p).replace("\\", "/").replace(":", "\\:")
        fonts = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
        vf.append(f"[0:v]ass='{ff(hook_ass)}':fontsdir='{ff(fonts)}'[h]")
    else:
        vf.append("[0:v]null[h]")
    if logo:
        ins += ["-i", logo]
        vf.append("[1:v]scale=140:-1,format=rgba,colorchannelmixer=aa=0.92[lg];[h][lg]overlay=40:236,format=yuv420p[v]")
    else:
        vf.append("[h]format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(vf), "-map", "[v]", "-map", "0:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy", "-movflags", "+faststart", str(final)],
                   check=True, capture_output=True)
    for p in (cutf, wav, edited):
        try:
            os.remove(p)
        except OSError:
            pass
    return str(final), meta, plan
