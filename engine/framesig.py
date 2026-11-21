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


def audio(mp4):
    """Loudness curve (log RMS per 100 ms, normalised). 21 Nov: one SEGA ad came as a 30 s 16:9 cut, a 15 s cut and a
    9:16 version: the pictures differ (crop / layout) but the soundtrack is the same. Test: every SEGA version scored
    1.00-1.13 against the others, every different clip 0.40 or less."""
    if not os.path.exists(mp4):
        return []
    k = "A|" + _key(mp4)
    if not _mem:
        _mem.update(load(CACHE, {}) or {})
    if k in _mem:
        return _mem[k]
    import numpy as np
    try:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                             capture_output=True, timeout=120).stdout
    except Exception:
        raw = b""
    a = np.frombuffer(raw, np.int16).astype(float)
    out = []
    if len(a) >= 8000:
        e = np.log(np.sqrt(np.mean(a[: len(a) // 800 * 800].reshape(-1, 800) ** 2, axis=1) + 1))
        if e.std() > 0.05:                                # a silent clip has no usable curve
            out = [round(float(x), 3) for x in (e - e.mean()) / e.std()]
    _mem[k] = out
    try:
        save(CACHE, dict(list(_mem.items())[-3000:]))
    except Exception:
        pass
    return out


def same_audio(a_mp4, b_mp4):
    """Best match of the shorter loudness curve slid over the longer one (a 15 s cut inside the 30 s ad matches)."""
    import numpy as np
    A, B = np.array(audio(a_mp4)), np.array(audio(b_mp4))
    if len(A) < 30 or len(B) < 30:
        return 0.0
    if len(A) > len(B):
        A, B = B, A
    best = max(float(np.mean(A * B[s:s + len(A)])) for s in range(len(B) - len(A) + 1))
    for s in range(1, min(30, len(A) // 3)):               # small shifts both ways (a cut that starts later)
        best = max(best, float(np.mean(A[s:] * B[:len(A) - s])), float(np.mean(B[s:len(A)] * A[:len(A) - s])))
    return best


def repeat(a_mp4, b_mp4):
    """True when b shows the same video as a: same pictures, or the same soundtrack (another cut / crop of one ad)."""
    return same(a_mp4, b_mp4) >= 0.75 or same_audio(a_mp4, b_mp4) >= 0.8


def _near(a, b):
    return sum(x != y for x, y in zip(a, b)) / len(a) < 0.12


def same(a_mp4, b_mp4):
    A, B = sig(a_mp4), sig(b_mp4)
    if not A or not B:
        return 0.0
    f = lambda X, Y: sum(1 for x in X if any(_near(x, y) for y in Y)) / len(X)
    return max(f(A, B), f(B, A))


if __name__ == "__main__":
    print("pictures", round(same(sys.argv[1], sys.argv[2]), 2), "audio", round(same_audio(sys.argv[1], sys.argv[2]), 2),
          "REPEAT" if repeat(sys.argv[1], sys.argv[2]) else "different")
