"""Pace a one-take VO: squeeze pauses longer than MAX_PAUSE to KEEP, then time-stretch (pitch kept, ffmpeg atempo)
so the read lands at the channel's words/second target (never faster than 1.35x).
  fit(in_wav, out_wav, n_words, target_wps) -> (out_wav, factor)"""
import subprocess
import numpy as np
import soundfile as sf

MAX_PAUSE, KEEP = 0.55, 0.36          # 18 Nov owner: voice felt too fast; keep more natural breathing room


def squeeze(a, sr):
    hop = int(sr * 0.01)
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1))
    sp = rms > max(1e-4, np.percentile(rms, 95) * 0.05)
    on = np.where(sp)[0]
    if not len(on):
        return a
    keep, i = [], on[0]
    start = max(0, on[0] - 3)
    out = [a[start * hop:on[0] * hop]]
    while i <= on[-1]:
        if sp[i]:
            j = i
            while j <= on[-1] and sp[j]:
                j += 1
            out.append(a[i * hop:j * hop]); i = j
        else:
            j = i
            while j <= on[-1] and not sp[j]:
                j += 1
            gap = (j - i) * hop
            g = a[i * hop:j * hop]
            if gap / sr > MAX_PAUSE:
                k = int(KEEP * sr / 2)
                g = np.concatenate([g[:k], g[-k:]])
            out.append(g); i = j
    out.append(a[(on[-1] + 1) * hop:(on[-1] + 1) * hop + int(0.3 * sr)])
    return np.concatenate(out)


def fit(src, dst, n_words, target_wps):
    a, sr = sf.read(src, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    a = squeeze(a, sr)
    tmp = dst + ".sq.wav"
    sf.write(tmp, a, sr)
    dur = len(a) / sr
    factor = min(1.35, max(1.0, (n_words / target_wps) and dur / (n_words / target_wps)))
    if factor > 1.02:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", f"atempo={factor:.3f}", dst], check=True)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, dst], check=True)
    return dst, round(factor, 3), round(dur, 2)
