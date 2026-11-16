"""Voice: Gemini TTS (same as VAJRA: gemini-3.8-flash-tts, Charon), the WHOLE script in one request.
Free key: ~/.studio-gemini.key (free tier ~10 TTS requests/day -> one request per reel)."""
import base64, json, os, time, urllib.error, urllib.request, wave
from core import log

MODELS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]


def _key():
    return open(os.path.expanduser(os.environ.get("STUDIO_GEMINI_KEY_FILE", "~/.studio-gemini.key"))).read().strip()


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


def strip_preamble(wav, first_line, lang="hi"):
    """Cut instructions the TTS model read aloud before the script (case2-p1-en read its whole style prompt).
    The instructions are English, so transcribe the first 40 s in English for every language: the last segment that
    contains an instruction phrase marks the cut. Returns (seconds_cut, leaked_text)."""
    import numpy as np, soundfile as sf
    from faster_whisper import WhisperModel
    a, sr = sf.read(wav, dtype="float32")
    mono = a if a.ndim == 1 else a.mean(axis=1)
    x = np.interp(np.arange(0, len(mono), sr / 16000), np.arange(len(mono)), mono).astype("float32")
    segs, _ = WhisperModel("base", compute_type="int8").transcribe(x[: 40 * 16000], language="en")
    segs = list(segs)
    cut, leaked = 0.0, ""
    for s in segs:
        txt = s.text.lower()
        if any(k in txt for k in LEAK):
            cut, leaked = s.end, leaked + " " + s.text.strip()
        elif cut:
            break
    if cut:
        sf.write(wav, a[int(max(0.0, cut - 0.05) * sr):], sr)
        log("tts: cut", round(cut, 2), "s of spoken instructions:", leaked[:160])
    return cut, leaked.strip()
