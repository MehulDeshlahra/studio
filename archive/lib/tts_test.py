"""Kokoro (Apache-2.0) Hindi voice test on the server: Devanagari Hinglish vs Latin Hinglish, 4 Hindi voices."""
import os, time
import soundfile as sf
from kokoro_onnx import Kokoro

M = os.path.expanduser("~/models/kokoro")
k = Kokoro(f"{M}/kokoro-v1.0.onnx", f"{M}/voices-v1.0.bin")
print("voices:", [v for v in k.get_voices() if v.startswith("h")])
lines = {
    "deva": "गूगल ने सर्च का दिमाग ही बदल दिया। अब एक ही सवाल में तीन चीज़ें पूछो, स्पेलिंग गलत हो, तब भी जवाब मिलेगा।",
    "mixed": "गूगल ने Search का दिमाग ही बदल दिया। नाम है Gemini 4 Hydrogen।",
}
os.makedirs("/tmp/tts", exist_ok=True)
for voice in ("hm_omega", "hm_psi", "hf_alpha", "hf_beta"):
    for name, text in lines.items():
        t = time.time()
        audio, sr = k.create(text, voice=voice, speed=1.1, lang="hi")
        f = f"/tmp/tts/{voice}-{name}.wav"
        sf.write(f, audio, sr)
        print(voice, name, f"{len(audio) / sr:.1f}s audio in {time.time() - t:.1f}s", flush=True)
