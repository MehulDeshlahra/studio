"""Quality gate on the FINAL mp4: format, loudness, read-back of the voice, and a vision review of one frame per scene."""
import base64, json, os, re, subprocess
from core import sh, log, dur
import llm

VISION = ["studio-vision", "gemini/gemini-3.1-flash-lite", "nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b"]   # studio-vision: engine/omnimap.py


def fmt(mp4):
    o = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height,r_frame_rate",
            "-of", "csv=p=0", mp4]).strip()
    a = sh(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", mp4]).strip()
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", mp4, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
    tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)[-1])
    c, w, h, fr = o.split(",")
    ok = c == "h264" and w == "1080" and h == "1920" and fr == "30/1" and a == "aac" and -16.0 <= lufs <= -13.0 and tp <= -1.0
    return {"ok": ok, "video": o, "audio": a, "lufs": lufs, "true_peak": tp, "dur": round(dur(mp4), 2)}


def sheet(mp4, times, out):
    frames = []
    for i, t in enumerate(times):
        f = out + f".{i}.jpg"
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-vf", "scale=270:480", f])
        frames.append(f)
    cols = min(6, len(frames))
    sh(["ffmpeg", "-v", "error", "-y"] + sum([["-i", f] for f in frames], []) +
       ["-filter_complex", "".join(f"[{i}:v]" for i in range(len(frames))) +
        f"xstack=inputs={len(frames)}:layout=" + "|".join(f"{(i % cols) * 270}_{(i // cols) * 480}" for i in range(len(frames))) +
        f":fill=black[o]", "-map", "[o]", out] if len(frames) > 1 else ["ffmpeg", "-v", "error", "-y", "-i", frames[0], out])
    for f in frames:
        os.remove(f)
    return out


def vision(sheet_path, plan):
    b64 = base64.b64encode(open(sheet_path, "rb").read()).decode()
    desc = "\n".join(f"{i + 1}. [{s['type']}] says: {s['vo']} | title: {s.get('title', '')}" for i, s in enumerate(plan["scenes"]))
    prompt = f"""This contact sheet shows one frame from each scene of a vertical short video, left to right, top to bottom.
The intended scenes:
{desc}
NOTE: the large bold words near the lower middle are word-by-word CAPTIONS that show only 2-3 words of the line at a time; that is intended, never report them as cut off or as not matching the line. Big words on a card (e.g. 'SAB KHAALI', 'BHAAV') are intended summaries of the line, not errors. Check like a strict editor: is any OTHER text (titles, cards, labels, text inside the images) cut off, overlapping, unreadable or misspelled; does any image look broken
(extra limbs, melted shapes, gibberish text, watermark); does each frame fit its line; is anything ugly or amateur?
Return JSON {{"score": 1-10, "ok": true/false (false if any serious problem), "problems": ["scene N: ..."]}}"""
    content = [{"type": "text", "text": prompt + "\nReturn ONLY JSON."},
               {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]
    for m in VISION:
        try:
            return llm.parse_json(llm._call(m, content, 2000))
        except Exception as e:
            log("vision fail", m, str(e)[:100])
    return {"score": None, "ok": None, "problems": ["vision review could not run"]}


def readback(wav, script):
    try:
        from faster_whisper import WhisperModel
        import soundfile as sf, numpy as np
        a, sr = sf.read(wav, dtype="float32")
        if a.ndim > 1:
            a = a.mean(axis=1)
        if sr != 16000:
            a = np.interp(np.arange(0, len(a), sr / 16000), np.arange(len(a)), a).astype("float32")
        segs, _ = WhisperModel("small", compute_type="int8").transcribe(a, language="hi")
        heard = " ".join(s.text for s in segs)
    except Exception as e:
        return {"ok": None, "note": f"whisper failed: {e}"}
    p = f"""Script (Roman Hinglish) and what a weak speech recognizer heard (Devanagari, often with errors on Hinglish).
Judge ONLY whether most of the script was spoken in order (the recognizer's own mistakes and repeats do not count).
Return ok=false only if whole sentences are clearly missing or the speech is mostly nonsense.
SCRIPT: {script}
HEARD: {heard}
Return JSON {{"ok": true/false, "problems": ["..."]}}"""
    try:
        r = llm.text(p, json_mode=True, max_tokens=800)
    except Exception as e:
        r = {"ok": None, "problems": [str(e)[:100]]}
    r["heard"] = heard
    return r
