"""Word timings for a one-take VO, matched to the Roman script.
words_by_line(wav, texts):
  1. faster-whisper (language hi) gives every spoken word with real start/end (Devanagari spelling).
  2. Both sides are reduced to a consonant skeleton (Devanagari and Roman Hinglish become comparable), then aligned
     with a monotonic Needleman-Wunsch. Matched words take the real times; unmatched words are interpolated
     between their neighbours. -> captions and cuts follow the voice word by word.
Falls back to a pause-based estimate (old method) when whisper fails or matches too little."""
import os, re, unicodedata
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


LAST_ENGINE = [""]                          # which engine gave the timing that was used (make.py logs it)


def _groq_words(wav, lang):
    """18 Nov: Whisper large-v3 on Groq's free tier through OmniRoute (the local model is 'small' on 2 CPU cores).
    Returns [(word, start, end)] or raises."""
    import json, os, subprocess, tempfile, urllib.request, uuid
    import llm
    flac = os.path.join(tempfile.gettempdir(), f"al-{uuid.uuid4().hex[:8]}.flac")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-ac", "1", "-ar", "16000", "-c:a", "flac", flac], check=True, timeout=120)
    try:
        b = uuid.uuid4().hex
        fields = {"model": "groq/whisper-large-v3", "language": lang, "response_format": "verbose_json",
                  "timestamp_granularities[]": "word", "temperature": "0"}
        body = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields.items())
        body += (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"vo.flac\"\r\nContent-Type: audio/flac\r\n\r\n").encode()
        body += open(flac, "rb").read() + f"\r\n--{b}--\r\n".encode()
        url = llm.URL.replace("/chat/completions", "/audio/transcriptions")
        hdr = {"Authorization": "Bearer " + llm._key(), "Content-Type": f"multipart/form-data; boundary={b}"}
        for attempt in range(2):
            try:
                # 20 Nov audit: a good answer takes ~3 s; at 180 s + a 150 s wait one reel sat 7+ min here (tech 1120-1748z)
                d = json.load(urllib.request.urlopen(urllib.request.Request(url, data=body, headers=hdr), timeout=45))
                break
            except urllib.error.HTTPError as e:
                # Groq busy (the job bot shares the key): a wait of <= 150 s beats minutes of local CPU at a worse match
                wait = 0
                try:
                    wait = int(json.loads(e.read() or b"{}").get("error", {}).get("retry_after") or 0)
                except Exception:
                    pass
                if e.code != 429 or attempt or not 0 < wait <= 40:
                    raise
                import time as _t
                _t.sleep(wait + 2)
    finally:
        os.remove(flac)
    words = [(str(w.get("word", "")).strip(), float(w["start"]), float(w["end"])) for w in d.get("words") or [] if str(w.get("word", "")).strip()]
    if len(words) < 5:
        raise RuntimeError("groq whisper gave no word times")
    return words


def _laptop_words(wav, lang):
    """20 Nov audit: Groq's free whisper answered 429 for 26 of 37 reels (19-20 Nov) and the server's CPU model then took
    2-8 min on the shared 2 cores. The laptop's GPU whisper (tools/laptop_worker.py words_job) takes seconds."""
    import json, os, laptop
    if os.name == "nt" or not laptop.available():
        raise RuntimeError("laptop not available")
    d = laptop.job({"kind": "words", "path": os.path.abspath(wav), "lang": lang}, "align", wait=300)
    W = json.load(open(os.path.join(d, "words.json"), encoding="utf-8"))["words"]
    words = [(str(w[2]).strip(), float(w[0]), float(w[1])) for w in W if str(w[2]).strip()]
    if len(words) < 5:
        raise RuntimeError("laptop whisper gave no word times")
    return words


def _whisper(wav, lang="hi", prompt=None, engine="local"):
    a, sr = sf.read(wav, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != 16000:
        a = np.interp(np.arange(0, len(a), sr / 16000), np.arange(len(a)), a).astype("float32")
    if engine == "groq":
        out = _groq_words(wav, lang)
    elif engine == "laptop":
        out = _laptop_words(wav, lang)
    else:
        from faster_whisper import WhisperModel
        # 17 Nov: Hinglish matched only 62-84% (Devanagari output vs our Latin script). The script as initial_prompt makes
        # Whisper write the same Latin spellings, so the words line up (English editions already match ~95%).
        # 20 Nov: device "auto" picked CUDA on the Windows laptop without cuBLAS -> crash; Studio runs Whisper on CPU everywhere
        segs, _ = WhisperModel("small", device=os.environ.get("STUDIO_WHISPER_DEVICE", "cpu"), compute_type="int8").transcribe(a, language=lang, word_timestamps=True, beam_size=5,
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


def _implausible(W):
    """19 Nov (tech 1118-1845, 'WhatsApp pe AI agent'): Whisper sometimes gives timestamps that cannot be real: a run of
    words 0.06 s long (13 words squeezed into 1.5 s) or one word lasting 5 s. The match took those times as they were, so the
    captions flashed past, then one word ('Ek') hung on screen for 5 s over an empty box, and the 83 % match score still passed.
    Indexes of Whisper words whose times must not be trusted: > 1.8 s, or part of a run of >= 3 words shorter than 0.11 s
    (plus a neighbour that is shorter than 0.16 s, it was squeezed by the same glitch)."""
    n = len(W)
    d = [b - a for _w, a, b in W]
    bad = {j for j in range(n) if d[j] > 1.8}
    j = 0
    while j < n:
        if d[j] < 0.11:
            k = j
            while k < n and d[k] < 0.11:
                k += 1
            if k - j >= 3:
                bad.update(range(j, k))
                for x in (j - 1, k):
                    if 0 <= x < n and d[x] < 0.16:
                        bad.add(x)
            j = k
        else:
            j += 1
    return bad


def sync_problems(lines):
    """Caption timing that a viewer would see as broken: too many words in too little time, a word that hangs for seconds,
    a line that starts before the previous one ended. [] when fine. Used by make.py (voice gate) and review.py."""
    probs, prev_end = [], 0.0
    for k, L in enumerate(lines or []):
        ws = L.get("words") or []
        if not ws:
            continue
        dur = max(0.01, float(L["end"]) - float(L["start"]))
        ws_ = [float(w["e"]) - float(w["s"]) for w in ws]
        if len(ws) >= 5 and len(ws) / dur > 6.5:
            probs.append(f"captions out of sync: line {k + 1} has {len(ws)} words in {dur:.1f} s")
        if max(ws_) > 2.2:
            probs.append(f"captions out of sync: a word in line {k + 1} stays {max(ws_):.1f} s")
        if float(L["start"]) < prev_end - 0.35:
            probs.append(f"captions out of sync: line {k + 1} starts {prev_end - float(L['start']):.1f} s before line {k} ends")
        prev_end = max(prev_end, float(L["end"]))
    return probs


def words_by_line(wav, texts, lang="hi"):
    toks, line_of = [], []
    for k, t in enumerate(texts):
        for w in t.split():
            if re.search(r"[A-Za-z0-9]", w):
                toks.append(w); line_of.append(k)
    sk = [skel_lat(w) for w in toks]
    can = [i for i, x in enumerate(sk) if len(x) >= 1]

    def match(W):
        heard = [skel_lat(w[0]) if lang == "en" else (skel_dev(w[0]) or skel_lat(w[0])) for w in W]
        pairs = _nw(sk, heard)
        # 17 Nov: words like "hai ka ho ki" have an EMPTY consonant skeleton and can never match, so a perfect Hinglish
        # voice scored only 58-79%. Coverage counts only words that can be matched (a missing sentence still shows up).
        return pairs, sum(1 for i in can if i in pairs) / max(1, len(can))
    # 18 Nov: Groq Whisper large-v3 (free, via OmniRoute) first; the local 'small' model runs too when Groq is busy or
    # matches less than 90%, and the better match wins.
    best = None
    for eng in ("groq", "laptop", "local"):
        try:
            W_, total_, t0_, t1_ = _whisper(wav, lang, engine=eng)   # 17 Nov: no script as initial_prompt (made Whisper loop)
        except Exception as e:
            if eng == "local" and best is None:
                raise
            continue
        pairs_, cover_ = match(W_)
        if best is None or cover_ > best[1]:
            best = (pairs_, cover_, W_, total_, t0_, t1_, eng)
        # 20 Nov: the local 'small' model also ran whenever Groq matched under 90% (2.5-3 min on 2 CPU cores per reel)
        # and only won by a few points (85% -> 88%). Groq at 75%+ (the voice gate's own bar) is used as it is.
        if best[1] >= 0.75:
            break
    pairs, cover, W, total, t0, t1, engine_used = best
    LAST_ENGINE[0] = engine_used
    if cover < 0.5:
        raise RuntimeError(f"alignment matched only {cover:.0%} of the words")
    s = [None] * len(toks); e = [None] * len(toks)
    bad = _implausible(W)                                # times that cannot be real are interpolated instead
    for i, j in pairs.items():
        if j in bad:
            continue
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
