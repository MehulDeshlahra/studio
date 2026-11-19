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


def make(src, ranges, Wd, hook, out_dir, logo=None, hook_ass=None):
    """src: the downloaded window; ranges: [[a, b], ...] in src seconds; Wd: [(s, e, text)] on src.
    Returns (final_mp4, meta, plan)."""
    out_dir = Path(out_dir)
    words = [{"w": _mask(str(t)), "s": float(s), "e": float(e)} for s, e, t in Wd]
    info = cvc_probe(src)
    cutf = out_dir / "cut.mp4"
    meta = cvc_cut.build_clip(Path(src), info, {"ranges": ranges}, words, cutf)
    if not meta:
        raise RuntimeError("cvc: no words in the clip range")
    meta.update(title=hook, emphasis=[])
    plan = cvc_plan.build(meta, BRAND, {"zoom": True, "captions": True, "sfx": "auto", "uppercase": True})
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
