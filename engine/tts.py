"""Voice: Gemini TTS (same as VAJRA: gemini-3.8-flash-tts, Charon), the WHOLE script in one request.
Free key: ~/.studio-gemini.key (free tier ~10 TTS requests/day -> one request per reel)."""
import base64, json, os, time, urllib.error, urllib.request, wave
from core import log

MODELS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]


KEYS_STATE = os.path.expanduser("~/studio-out/gemini-keys.json")


def _keys_all():
    return [l.strip() for l in open(os.path.expanduser(os.environ.get("STUDIO_GEMINI_KEY_FILE", "~/.studio-gemini.key"))) if l.strip()]


def _kstate():
    try:
        st = json.load(open(KEYS_STATE))
    except Exception:
        st = {}
    today = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 8 * 3600))   # Google resets daily quota at midnight Pacific
    if st.get("day") != today:
        st = {"day": today, "keys": {}, "alerted": st.get("alerted") if st.get("day") == today else None}
    return st


def _ksave(st):
    try:
        tmp = KEYS_STATE + ".tmp"; json.dump(st, open(tmp, "w")); os.replace(tmp, KEYS_STATE)
    except Exception:
        pass


def _key(model=None):
    """A random free key that is not out of daily quota today (for this model, or for every model when model is None).
    If every key is out, any key (the call then fails fast and the caller falls back)."""
    import random
    ks = _keys_all()
    st = _kstate()["keys"]
    def out(k):
        o = st.get(k[-6:], {}).get("out", [])
        return (model in o) if model else ("*" in o)
    ok = [k for k in ks if not out(k)]
    return random.choice(ok or ks)


def usable(models):
    """Models that still have quota on at least one key today (the rest are skipped instead of tried and failed).
    If none is usable, the original list comes back so callers still fail the normal way."""
    st = _kstate()["keys"]
    ks = [k[-6:] for k in _keys_all()]
    ok = [m for m in models if any(m not in st.get(k, {}).get("out", []) and "*" not in st.get(k, {}).get("out", []) for k in ks)]
    return ok or list(models)


class _KeyWatch(urllib.request.BaseHandler):
    """Counts every Gemini call per key and marks a key 'out' for the day (per model) when Google says the DAILY quota is
    used up. Installed as the global urllib opener, so every module (plan, review, thumb, brain...) is covered."""
    handler_order = 999

    def _note(self, req, code, body=""):
        if "generativelanguage.googleapis.com" not in req.full_url:
            return
        k = req.get_header("X-goog-api-key") or ""
        if not k:
            return
        m = req.full_url.split("/models/")[-1].split(":")[0] if "/models/" in req.full_url else "other"
        st = _kstate(); e = st["keys"].setdefault(k[-6:], {"ok": 0, "fail": 0, "out": [], "models": {}})
        e["models"][m] = e["models"].get(m, 0) + 1
        if code < 300:
            e["ok"] += 1
        else:
            e["fail"] += 1
            b = body.lower()
            daily = ("per day" in b or "perday" in b or "requests per day" in b or "daily" in b or "spend cap" in b
                     or ("quota" in b and "minute" not in b))
            if code in (403, 429) and daily and m not in e["out"]:
                e["out"].append(m)
                if "spend cap" in b or "permission" in b:
                    e["out"].append("*")
        _ksave(st)
        if code >= 300:
            _alert_if_all_out(st)

    def http_response(self, req, resp):
        body = ""
        if resp.status >= 300:
            try:
                raw = resp.read(); body = raw[:600].decode("utf8", "ignore")
                import io as _io
                resp.fp = _io.BytesIO(raw); resp.read = resp.fp.read
            except Exception:
                pass
        try:
            self._note(req, resp.status, body)
        except Exception:
            pass
        return resp

    https_response = http_response


def _alert_if_all_out(st):
    ks = [k[-6:] for k in _keys_all()]
    tts_out = all(any("tts" in m for m in st["keys"].get(k, {}).get("out", [])) or "*" in st["keys"].get(k, {}).get("out", []) for k in ks)
    lite_out = all(any(m.startswith("gemini-3.5-flash-lite") for m in st["keys"].get(k, {}).get("out", [])) or "*" in st["keys"].get(k, {}).get("out", []) for k in ks)
    if (tts_out or lite_out) and not st.get("alerted"):
        st["alerted"] = time.strftime("%H:%M"); _ksave(st)
        try:
            from core import telegram
            telegram(f"Studio: all {len(ks)} free Gemini keys are out of today's quota ({"voice" if tts_out else "text"}). Videos wait until the reset "
                     "(13:30 IST). Nothing to do unless this happens often; then add one more free key.")
        except Exception:
            pass


urllib.request.install_opener(urllib.request.build_opener(_KeyWatch()))


def speak(script, out_wav, voice="Charon", style="", lang="hi"):
    language = "Indian English" if lang == "en" else "Hinglish"
    # short "Say ...:" directive (Gemini TTS docs style); a long instruction got READ ALOUD in English (case2-p1-en).
    # 17 Nov: the "Say in ...:" line was READ ALOUD on every voice (7-9 s cut each time; when the cut missed, the video
    # was held: top hold reason #3). A bracket style tag is not read (tested: speech starts at 0.0 s with the script).
    prompt = f"[{language}, {style.strip().rstrip('.')}] " + script
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    errs = []
    for m in MODELS:
        for attempt in range(3):
            try:
                r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                           data=json.dumps(body).encode(),
                                           headers={"Content-Type": "application/json", "x-goog-api-key": _key(m)})
                d = json.load(urllib.request.urlopen(r, timeout=300))
                pcm = base64.b64decode(d["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
                w = wave.open(out_wav, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(pcm); w.close()
                log("tts", m, voice, f"{len(pcm) / 48000:.1f}s")
                return out_wav
            except urllib.error.HTTPError as e:
                msg = e.read()[:200].decode("utf-8", "ignore")
                errs.append(f"{m} {e.code} {msg}")
                if e.code in (400, 403, 404):
                    break
                time.sleep(20 if e.code == 429 else 5)
            except Exception as e:
                errs.append(f"{m} {str(e)[:100]}")
                time.sleep(5)
    raise RuntimeError("tts failed: " + " | ".join(errs))


LEAK = ("read this", "start instantly", "no intro", "pause briefly", "read exactly", "words per second", "narrator", "say in")


def strip_preamble(wav, first_line, lang="hi", style=""):
    """Cut instructions the TTS model read aloud before the script. Word-level: the cut lands on the first word AFTER
    the last instruction phrase, so the script's first line is kept (16 Nov the segment-level cut also removed
    "You are the detective..."). Instructions are English, so transcribe the first 40 s in English. Returns (cut_s, text)."""
    import re as _re
    import numpy as np, soundfile as sf
    from faster_whisper import WhisperModel
    a, sr = sf.read(wav, dtype="float32")
    mono = a if a.ndim == 1 else a.mean(axis=1)
    x = np.interp(np.arange(0, len(mono), sr / 16000), np.arange(len(mono)), mono).astype("float32")
    segs, _ = WhisperModel("base", compute_type="int8").transcribe(x[: 40 * 16000], language="en", word_timestamps=True)
    words = [(w.word.strip(), w.start, w.end) for s in segs for w in s.words if w.word.strip()]
    norm = [_re.sub(r"[^a-z]", "", w[0].lower()) for w in words]
    # 0) the exact instruction we sent ("Say in Hinglish, a calm low narrator...:"). 17 Nov: the Hindi edition still
    #    started with "Say in English, curious, warm, energetic..." because only the phrase "say in" was cut.
    language = "Indian English" if lang == "en" else "Hinglish"
    pre = set(t for t in (_re.sub(r"[^a-z ]", " ", f"say in {language} {style} indian english hinglish read aloud".lower()).split()) if len(t) > 1)
    k, hits, last_pre = 0, 0, -1
    for k, nw in enumerate(norm[:80]):
        if not nw:
            continue
        if last_pre >= 0 and words[k][1] - words[last_pre][2] > 1.2:   # a gap = the instruction ended (Whisper skipped the Hindi after it)
            break
        if nw in pre:
            hits += 1; last_pre = k
        elif k - last_pre > 3:                     # 4 words in a row that are not instruction words: the script began
            break
    if last_pre >= 1 and words[0][1] < 2.0 and any(n in pre for n in norm[:3]) and hits >= 0.6 * (last_pre + 1):
        # 17 Nov katha: English Whisper stopped after "...turning point." (the Hindi script was not transcribed), so
        # there was no "next word"; cut just after the last instruction word then
        cut = max(0.0, min(words[last_pre + 1][1] - 0.08, words[last_pre][2] + 0.3)) if last_pre + 1 < len(words) else words[last_pre][2] + 0.15
        said = " ".join(w[0] for w in words[: last_pre + 1])
        sf.write(wav, a[int(cut * sr):], sr)
        log("tts: cut", round(cut, 2), "s of the spoken instruction:", said[:160])
        return cut, said
    # 1) best: find where the script's first words start and cut everything before them (17 Nov: "Say in" was cut but
    #    "Indian English, curious warm energetic young Indian" stayed in the English edition)
    fl = [_re.sub(r"[^a-z]", "", t.lower()) for t in first_line.split()][:4]
    fl = [t for t in fl if t]
    if len(fl) >= 2 and lang == "en":
        for i2 in range(1, min(len(norm), 80)):
            hit = sum(1 for k, t in enumerate(fl[:3]) if i2 + k < len(norm) and norm[i2 + k] == t)
            if hit >= 2 and words[i2][1] > 0.3:
                pre = " ".join(w[0] for w in words[:i2])
                if any(k in pre.lower() for k in ("say", "indian", "english", "hinglish", "voice", "tone", "warm", "energetic", "curious", "calm")):
                    cut = max(0.0, words[i2][1] - 0.08)
                    sf.write(wav, a[int(cut * sr):], sr)
                    log("tts: cut", round(cut, 2), "s before the first line:", pre[:160])
                    return cut, pre
                break
    last = -1
    for k in LEAK + ("these words", "exactly these", "the final question", "accent"):
        kw = k.split()
        for i2 in range(len(norm) - len(kw) + 1):
            # 17 Nov: a match deep inside the story cut half a Katha voice (159 words left as 40 s). Only the opening counts.
            if norm[i2:i2 + len(kw)] == kw and words[i2][1] < 10 and i2 < 30:
                last = max(last, i2 + len(kw) - 1)
    if last < 0 or last + 1 >= len(words):
        return 0.0, ""
    cut = max(0.0, words[last + 1][1] - 0.08)
    leaked = " ".join(w[0] for w in words[: last + 1])
    sf.write(wav, a[int(cut * sr):], sr)
    log("tts: cut", round(cut, 2), "s of spoken instructions:", leaked[:160])
    return cut, leaked
