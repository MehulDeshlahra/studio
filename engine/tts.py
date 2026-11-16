"""Voice: Gemini TTS (same as VAJRA: gemini-3.8-flash-tts, Charon), the WHOLE script in one request.
Free key: ~/.studio-gemini.key (free tier ~10 TTS requests/day -> one request per reel)."""
import base64, json, os, time, urllib.error, urllib.request, wave
from core import log

MODELS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]


def _key():
    return open(os.path.expanduser(os.environ.get("STUDIO_GEMINI_KEY_FILE", "~/.studio-gemini.key"))).read().strip()


def speak(script, out_wav, voice="Charon", style=""):
    prompt = (f"Read this in natural spoken Hinglish/Hindi as {style}. Start instantly, no intro. "
              "Pause briefly between sentences. Read exactly these words:\n\n" + script)
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
