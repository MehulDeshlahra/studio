"""Final mix: VO + music bed + SFX cues -> mix.wav, mastered (default -12 LUFS, -1 dBTP).

  python lib/mix.py videos/<id> [assets_dir]
videos/<id>/cues.json:
 {"music": {"file": "music/x.mp3", "offset": 8.0, "gain_db": -20, "fade_out": 1.5, "drops": [[37.95, 38.45]]},
  "lufs": -12,
  "sfx": [{"t": 2.33, "file": "sfx/whoosh-fast.mp3", "gain_db": -16, "align": "peak"|"onset", "dur": 1.8}]}
'peak' puts the loudest moment of the file on t (whooshes, impacts); 'onset' starts it at t (clicks, typing).
"""
import json, os, re, subprocess, sys
import numpy as np

SR = 48000


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def peak_s(path):
    a = decode(path)
    env = np.convolve(np.abs(a), np.ones(480) / 480, "same")
    return float(np.argmax(env)) / SR


def first_sound_s(path, thr=0.02):
    a = decode(path)
    idx = np.where(np.abs(a) > thr * max(1e-6, np.abs(a).max()))[0]
    return float(idx[0]) / SR if len(idx) else 0.0


def main(vdir, adir):
    c = json.load(open(os.path.join(vdir, "cues.json"), encoding="utf-8"))
    vo = os.path.join(vdir, "vo.wav")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vo],
                               capture_output=True, text=True).stdout)
    ins, filt, labels = ["-i", vo], ["[0:a]aresample=48000,aformat=channel_layouts=stereo[vo]"], ["[vo]"]
    m = c.get("music")
    if m:
        ins += ["-ss", str(m.get("offset", 0)), "-i", os.path.join(adir, m["file"])]
        vol = f"{10 ** (m.get('gain_db', -20) / 20):.4f}"
        # silence drops before big reveals: volume 0 inside each window, 60 ms ramps
        expr = "1"
        for a, b in m.get("drops", []):
            expr = f"{expr}*(1-clip((t-{a})/0.06,0,1)*clip(({b}-t)/0.06,0,1))"
        fo = m.get("fade_out", 1.5)
        filt.append(f"[1:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur},afade=t=in:d=0.4,"
                    f"afade=t=out:st={dur - fo}:d={fo},volume={vol},volume='{expr}':eval=frame[mus]")
        labels.append("[mus]")
    for i, s in enumerate(c.get("sfx", [])):
        f = os.path.join(adir, s["file"])
        lead = peak_s(f) if s.get("align") == "peak" else first_sound_s(f)
        start = max(0.0, s["t"] - lead)
        n = len(ins) // 2 if False else None
        ins += ["-i", f]
        k = sum(1 for x in ins if x == "-i") - 1
        trim = f",atrim=0:{s['dur']},afade=t=out:st={max(0, s['dur'] - 0.15)}:d=0.15" if s.get("dur") else ""
        filt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo{trim},volume={10 ** (s.get('gain_db', -18) / 20):.4f},"
                    f"adelay={int(start * 1000)}|{int(start * 1000)}[s{i}]")
        labels.append(f"[s{i}]")
    lufs = c.get("lufs", -12)
    filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,"
                f"loudnorm=I={lufs}:TP=-1.0:LRA=11[out]")
    out = os.path.join(vdir, "mix.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(filt), "-map", "[out]",
                    "-ar", str(SR), out], check=True)
    ld = subprocess.run(["ffmpeg", "-i", out, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", ld)[-1]
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", ld)
    print(f"mix.wav {dur:.2f}s  {I} LUFS  true peak {tp[-1] if tp else '?'} dBFS  ({len(c.get('sfx', []))} sfx)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "audio"))
