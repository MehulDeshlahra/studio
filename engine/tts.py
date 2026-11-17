"""Voice: Gemini TTS (same as VAJRA: gemini-3.8-flash-tts, Charon), the WHOLE script in one request.
Free key: ~/.studio-gemini.key (free tier ~10 TTS requests/day -> one request per reel)."""
import base64, json, os, time, urllib.error, urllib.request, wave
from core import log

MODELS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]


def _key():
    # one key per line; a random one per call spreads the free-tier quota (and a retry lands on another key)
    ks = [l.strip() for l in open(os.path.expanduser(os.environ.get("STUDIO_GEMINI_KEY_FILE", "~/.studio-gemini.key"))) if l.strip()]
    import random
    return random.choice(ks)


def speak(script, out_wav, voice="Charon", style="", lang="hi"):
    language = "Indian English" if lang == "en" else "Hinglish"
    # short "Say ...:" directive (Gemini TTS docs style); a long instruction got READ ALOUD in English (case2-p1-en).
    prompt = f"Say in {language}, {style}:\n" + script
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    errs = []
    for m in MODELS:
        for attempt in range(3):
            try:
                r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                           data=json.dumps(body).encode(),
                                           headers={"Content-Type": "application/json", "x-goog-api-key": _key()})
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
