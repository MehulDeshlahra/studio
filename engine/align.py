"""Line timings for a one-take VO: find the pauses between sentences (language-free), match them to the
expected line boundaries (by character share), then spread each line's words by length.
lines(wav, texts) -> [{"text","start","end","words":[{"w","s","e"}]}]"""
import numpy as np
import soundfile as sf


def _speech(a, sr):
    hop = int(sr * 0.01)
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1))
    thr = max(1e-4, np.percentile(rms, 95) * 0.06)
    return rms > thr, hop / sr


def lines(wav, texts, min_pause=0.16):
    """Pieces split at "..." are aligned separately (the reader pauses there) and merged back."""
    parts, owner = [], []
    for k, t in enumerate(texts):
        for p in [x.strip() for x in t.split("...") if x.strip()] or [t]:
            parts.append(p); owner.append(k)
    got, total = _lines(wav, parts, min_pause)
    out = []
    for k, t in enumerate(texts):
        g = [x for x, o in zip(got, owner) if o == k]
        ws = []
        for x in g:
            ws += x["words"]
        out.append({"text": t, "start": g[0]["start"], "end": g[-1]["end"], "words": ws})
    return out, total


def _lines(wav, texts, min_pause=0.16):
    a, sr = sf.read(wav, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    sp, step = _speech(a, sr)
    on = np.where(sp)[0]
    t0, t1 = on[0] * step, (on[-1] + 1) * step
    # silent runs inside the speech
    runs, i = [], on[0]
    while i < on[-1]:
        if not sp[i]:
            j = i
            while j < len(sp) and not sp[j]:
                j += 1
            if (j - i) * step >= min_pause:
                runs.append((i * step, j * step))
            i = j
        else:
            i += 1
    w = [max(1, len(t)) for t in texts]
    cum = np.cumsum(w)[:-1] / sum(w)
    exp = t0 + cum * (t1 - t0)
    bounds, last = [], t0
    for k, e in enumerate(exp):
        left = len(exp) - k - 1                              # boundaries still needed after this one
        cands = [r for r in runs if r[0] > last + 0.4]
        cands = cands[: len(cands) - left] if left and len(cands) > left else cands
        if cands:
            r = min(cands, key=lambda r: abs((r[0] + r[1]) / 2 - e) - 0.8 * (r[1] - r[0]))
            if abs((r[0] + r[1]) / 2 - e) < 2.5:
                bounds.append(r); last = r[1]; continue
        bounds.append((e - 0.05, e + 0.05)); last = e + 0.05
    out, s = [], t0
    for k, t in enumerate(texts):
        e = bounds[k][0] if k < len(bounds) else t1
        words = t.split()
        lens = [len(x) + 2 for x in words]
        tot, c, ws = sum(lens), s, []
        for x, l in zip(words, lens):
            d = (e - s) * l / tot
            ws.append({"w": x, "s": round(c, 3), "e": round(c + d, 3)}); c += d
        out.append({"text": t, "start": round(s, 3), "end": round(e, 3), "words": ws})
        s = bounds[k][1] if k < len(bounds) else e
    return out, round(len(a) / sr, 3)
