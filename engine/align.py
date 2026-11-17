"""Word timings for a one-take VO, matched to the Roman script.
words_by_line(wav, texts):
  1. faster-whisper (language hi) gives every spoken word with real start/end (Devanagari spelling).
  2. Both sides are reduced to a consonant skeleton (Devanagari and Roman Hinglish become comparable), then aligned
     with a monotonic Needleman-Wunsch. Matched words take the real times; unmatched words are interpolated
     between their neighbours. -> captions and cuts follow the voice word by word.
Falls back to a pause-based estimate (old method) when whisper fails or matches too little."""
import re, unicodedata
from difflib import SequenceMatcher
import numpy as np
import soundfile as sf

DEV = {"क": "k", "ख": "k", "ग": "g", "घ": "g", "च": "C", "छ": "C", "ज": "j", "झ": "j", "ट": "t", "ठ": "t", "ड": "d",
       "ढ": "d", "ण": "n", "त": "t", "थ": "t", "द": "d", "ध": "d", "न": "n", "प": "p", "फ": "p", "ब": "b", "भ": "b",
       "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "s", "ष": "s", "स": "s", "ह": "h", "ळ": "l",
       "ऑ": "", "ऍ": ""}
DROP = set("yh")


def skel_dev(w):
    w = unicodedata.normalize("NFC", w)
    return "".join(DEV.get(c, "") for c in w if DEV.get(c, "") not in DROP and c in DEV)


def skel_lat(w):
    w = re.sub(r"[^a-z]", "", w.lower())
    for a, b in (("chh", "C"), ("ch", "C"), ("kh", "k"), ("gh", "g"), ("jh", "j"), ("th", "t"), ("dh", "d"), ("ph", "p"),
                 ("bh", "b"), ("sh", "s"), ("ng", "n"), ("ck", "k")):
        w = w.replace(a, b)
    w = w.replace("w", "v").replace("z", "j").replace("f", "p").replace("q", "k").replace("x", "ks").replace("c", "k")
    return "".join(c for c in w if c not in "aeiouyh")


def _sim(a, b):
    if not a and not b:
        return 0.35
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _whisper(wav, lang="hi", prompt=None):
    from faster_whisper import WhisperModel
    a, sr = sf.read(wav, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != 16000:
        a = np.interp(np.arange(0, len(a), sr / 16000), np.arange(len(a)), a).astype("float32")
    # 17 Nov: Hinglish matched only 62-84% (Devanagari output vs our Latin script). The script as initial_prompt makes
    # Whisper write the same Latin spellings, so the words line up (English editions already match ~95%).
    segs, _ = WhisperModel("small", compute_type="int8").transcribe(a, language=lang, word_timestamps=True, beam_size=5,
                                                                    initial_prompt=(prompt or None) and prompt[:600])
    out = [(w.word.strip(), float(w.start), float(w.end)) for s in segs for w in s.words if w.word.strip()]
    # speech end by energy (drops hallucinated words in a silent tail)
    hop = 160
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1))
    on = np.where(rms > max(1e-4, np.percentile(rms, 95) * 0.05))[0]
    end = (on[-1] + 1) * hop / 16000 if len(on) else len(a) / 16000
    return [w for w in out if w[1] < end + 0.1], len(a) / 16000, (on[0] * hop / 16000 if len(on) else 0.0), end


def _nw(S, W):
    n, m = len(S), len(W)
    sim = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            sim[i, j] = _sim(S[i], W[j])
    GAP = -0.6
    D = np.zeros((n + 1, m + 1))
    D[:, 0] = np.arange(n + 1) * GAP
    D[0, :] = np.arange(m + 1) * GAP
    B = np.zeros((n + 1, m + 1), dtype=int)
    B[1:, 0] = 1
    B[0, 1:] = 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d = D[i - 1, j - 1] + (3 * sim[i - 1, j - 1] - 1)
            u = D[i - 1, j] + GAP
            l = D[i, j - 1] + GAP
            D[i, j] = max(d, u, l)
            B[i, j] = 0 if D[i, j] == d else (1 if D[i, j] == u else 2)
    i, j, pairs = n, m, {}
    while i > 0 or j > 0:
        if i > 0 and j > 0 and B[i, j] == 0:
            if sim[i - 1, j - 1] >= 0.5:
                pairs[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif i > 0 and (j == 0 or B[i, j] == 1):
            i -= 1
        else:
            j -= 1
    return pairs


def words_by_line(wav, texts, lang="hi"):
    toks, line_of = [], []
    for k, t in enumerate(texts):
        for w in t.split():
            if re.search(r"[A-Za-z0-9]", w):
                toks.append(w); line_of.append(k)
    W, total, t0, t1 = _whisper(wav, lang)   # 17 Nov: the script as initial_prompt made Whisper loop on garbage ("Ṭ Ṭ Ṭ") and run 3x slower; keep plain
    heard = [skel_lat(w[0]) if lang == "en" else (skel_dev(w[0]) or skel_lat(w[0])) for w in W]
    sk = [skel_lat(w) for w in toks]
    pairs = _nw(sk, heard)
    # 17 Nov: words like "hai ka ho ki" have an EMPTY consonant skeleton and can never match, so a perfect Hinglish voice
    # scored only 58-79%. Coverage counts only words that can be matched (a missing sentence still shows up here).
    can = [i for i, x in enumerate(sk) if len(x) >= 1]
    cover = sum(1 for i in can if i in pairs) / max(1, len(can))
    if cover < 0.5:
        raise RuntimeError(f"alignment matched only {cover:.0%} of the words")
    s = [None] * len(toks); e = [None] * len(toks)
    for i, j in pairs.items():
        s[i], e[i] = W[j][1], W[j][2]
    # interpolate unmatched words between anchors, weighted by length
    i = 0
    while i < len(toks):
        if s[i] is not None:
            i += 1; continue
        j = i
        while j < len(toks) and s[j] is None:
            j += 1
        a = e[i - 1] if i > 0 else t0
        b = s[j] if j < len(toks) else t1
        b = max(b, a + 0.08 * (j - i))
        lens = [len(toks[k]) + 1 for k in range(i, j)]
        c = a
        for k, l in zip(range(i, j), lens):
            d = (b - a) * l / sum(lens)
            s[k], e[k] = c, c + d
            c += d
        i = j
    for k in range(len(toks) - 1):                       # a word never runs into the next one
        e[k] = min(max(e[k], s[k] + 0.06), max(s[k + 1], s[k] + 0.06))
    lines = []
    for k, t in enumerate(texts):
        idx = [x for x, o in enumerate(line_of) if o == k]
        if not idx:
            lines.append({"text": t, "start": lines[-1]["end"] if lines else 0.0, "end": lines[-1]["end"] if lines else 0.0, "words": []})
            continue
        ws = [{"w": toks[x], "s": round(s[x], 3), "e": round(e[x], 3)} for x in idx]
        lines.append({"text": t, "start": ws[0]["s"], "end": ws[-1]["e"], "words": ws})
    return lines, round(total, 3), cover


# ---- fallback (pause based, used only when whisper is unavailable) ----
def _speech(a, sr):
    hop = int(sr * 0.01)
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1))
    return rms > max(1e-4, np.percentile(rms, 95) * 0.06), hop / sr


def lines(wav, texts, min_pause=0.16):
    a, sr = sf.read(wav, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    sp, step = _speech(a, sr)
    on = np.where(sp)[0]
    t0, t1 = on[0] * step, (on[-1] + 1) * step
    w = [max(1, len(t)) for t in texts]
    cum = np.concatenate([[0], np.cumsum(w) / sum(w)])
    out = []
    for k, t in enumerate(texts):
        a0, a1 = t0 + cum[k] * (t1 - t0), t0 + cum[k + 1] * (t1 - t0)
        words = t.split()
        lens = [len(x) + 2 for x in words]
        c, ws = a0, []
        for x, l in zip(words, lens):
            d = (a1 - a0) * l / sum(lens)
            ws.append({"w": x, "s": round(c, 3), "e": round(c + d, 3)}); c += d
        out.append({"text": t, "start": round(a0, 3), "end": round(a1, 3), "words": ws})
    return out, round(len(a) / sr, 3)
