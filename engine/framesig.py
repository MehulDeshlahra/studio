"""21 Nov (owner deleted 3 Gaming clips: the same SEGA ad posted 4 times with new captions). Picture fingerprint of a
clip: 8 frames spread over its length, each shrunk to 16x28 grey and turned into bits (brighter / darker than the
frame's mean). Two clips are the same video when most frames of one have a near-identical frame in the other (order
does not matter: a re-cut of the same ad still matches). Cached by file path + size + mtime in ~/studio-out/framesig.json.
  same(mp4_a, mp4_b) -> share of matching frames (0..1); >= 0.75 = the same clip
  python engine/framesig.py a.mp4 b.mp4"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import OUT, load, save

CACHE = os.path.join(OUT, "framesig.json")
W, H, N = 16, 28, 8
_mem = {}


def _key(mp4):
    st = os.stat(mp4)
    return f"{mp4}|{st.st_size}|{int(st.st_mtime)}"


def sig(mp4):
    """[bit string per frame] or [] when the file cannot be read."""
    if not os.path.exists(mp4):
        return []
    k = _key(mp4)
    if not _mem:
        _mem.update(load(CACHE, {}) or {})
    if k in _mem:
        return _mem[k]
    try:
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                                 capture_output=True, text=True, timeout=60).stdout.strip() or 0)
    except Exception:
        d = 0
    out = []
    for i in range(N if d > 0 else 0):
        try:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{d * (i + 0.5) / N:.2f}", "-i", mp4, "-frames:v", "1",
                                  "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True, timeout=60).stdout
        except Exception:
            continue
        if len(raw) == W * H:
            m = sum(raw) / len(raw)
            out.append("".join("1" if b > m else "0" for b in raw))
    _mem[k] = out
    try:
        save(CACHE, dict(list(_mem.items())[-3000:]))
    except Exception:
        pass
    return out


def _near(a, b):
    return sum(x != y for x, y in zip(a, b)) / len(a) < 0.12


def same(a_mp4, b_mp4):
    A, B = sig(a_mp4), sig(b_mp4)
    if not A or not B:
        return 0.0
    f = lambda X, Y: sum(1 for x in X if any(_near(x, y) for y in Y)) / len(X)
    return max(f(A, B), f(B, A))


if __name__ == "__main__":
    print(round(same(sys.argv[1], sys.argv[2]), 2))
