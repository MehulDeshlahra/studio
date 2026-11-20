import os, soundfile as sf
from kokoro_onnx import Kokoro
M = os.path.expanduser("~/models/kokoro")
k = Kokoro(f"{M}/kokoro-v1.0.onnx", f"{M}/voices-v1.0.bin")
os.makedirs("/tmp/fix", exist_ok=True)
for i, t in enumerate(["बदल दिया", "बदल्‌ दिया", "बद-ल दिया", "badal diya", "बदलाव", "पूरा बदल गया"]):
    try:
        a, sr = k.create(t, voice="hm_psi", speed=1.1, lang="hi")
        sf.write(f"/tmp/fix/{i}.wav", a, sr)
        print(i, t, k.tokenizer.phonemize(t, "hi") if hasattr(k, "tokenizer") else "")
    except Exception as e:
        print(i, t, "ERR", e)
