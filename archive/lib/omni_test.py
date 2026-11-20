"""OmniVoice (k2-fsa, the default engine inside VoiceStudio) Hindi test on the server CPU.
Writes /tmp/omni/*.wav for the same Hinglish line in Devanagari and Latin script."""
import os, time, sys
os.makedirs("/tmp/omni", exist_ok=True)
t0 = time.time()
from omnivoice import OmniVoice  # noqa: E402
import soundfile as sf  # noqa: E402
m = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cpu")
print("load", round(time.time() - t0), "s", flush=True)
lines = {"deva": "गूगल सर्च अब पहले से कहीं ज़्यादा स्मार्ट हो गया है। एक ही सवाल में तीन चीज़ें पूछो।",
         "latin": "Google Search ab pehle se kahin zyada smart ho gaya hai. Ek hi sawaal mein teen cheezein poocho."}
for name, text in lines.items():
    for inst in ("male, young adult, indian accent", "male, middle-aged, low pitch, indian accent"):
        t = time.time()
        audio = m.generate(text=text, instruct=inst)
        a = audio[0] if isinstance(audio, (list, tuple)) else audio
        a = a.squeeze().cpu().numpy() if hasattr(a, "cpu") else a
        f = f"/tmp/omni/{name}-{inst.split(',')[1].strip().replace(' ', '')}.wav"
        sf.write(f, a, 24000)
        print(name, inst, f"{len(a) / 24000:.1f}s audio in {time.time() - t:.0f}s", flush=True)
