"""Voiceover for a Studio video: one Kokoro take per line, tightened silences, word timings, one mixed track.

  python lib/vo.py videos/<id>            -> videos/<id>/vo.wav + videos/<id>/words.json
words.json: {"lines":[{"id","start","end","cap","words":[{"w","start","end"}]}], "dur"}
Caption words (Latin Hinglish, script 'cap') get times from whisper word timings on that line's audio,
matched by position (counts differ between the Devanagari read and the Latin caption, so times are spread
over the measured speech span by character weight when whisper and caption counts differ).
"""
import json, os, re, sys
import numpy as np
import soundfile as sf

GAP = 0.32          # silence between lines (s)
LEAD = 0.15         # silence before the first line
TAIL = 0.6
SR = 24000


def trim(a, thr=0.012, pad=0.04):
    """Cut leading/trailing silence; squeeze inner pauses > 0.28 s to 0.2 s (prompt-motion audio recipe)."""
    env = np.convolve(np.abs(a), np.ones(240) / 240, "same")
    on = np.where(env > thr)[0]
    if not len(on):
        return a
    a = a[max(0, on[0] - int(pad * SR)): on[-1] + int(pad * SR)]
    env = np.convolve(np.abs(a), np.ones(240) / 240, "same") > thr
    out, i, n = [], 0, len(a)
    while i < n:
        if not env[i]:
            j = i
            while j < n and not env[j]:
                j += 1
            run = j - i
            keep = run if run < 0.28 * SR else int(0.2 * SR)
            out.append(a[i:i + keep]); i = j
        else:
            j = i
            while j < n and env[j]:
                j += 1
            out.append(a[i:j]); i = j
    return np.concatenate(out)


def main(vdir):
    from kokoro_onnx import Kokoro
    from faster_whisper import WhisperModel
    s = json.load(open(os.path.join(vdir, "script.json"), encoding="utf-8"))
    M = os.path.expanduser("~/models/kokoro")
    k = Kokoro(f"{M}/kokoro-v1.0.onnx", f"{M}/voices-v1.0.bin")
    wm = WhisperModel("small", device="cpu", compute_type="int8")
    v = s["voice"]
    gap = float(s.get("gap", GAP))
    track, t, lines = [np.zeros(int(LEAD * SR))], LEAD, []
    for ln in s["lines"]:
        a, sr = k.create(ln["tts"], voice=v["voice"], speed=v.get("speed", 1.0), lang="hi")
        assert sr == SR
        a = trim(a.astype(np.float32))
        a16 = np.interp(np.arange(0, len(a), SR / 16000), np.arange(len(a)), a).astype(np.float32)
        segs, _ = wm.transcribe(a16, language="hi", word_timestamps=True)
        ww = [w for sg in segs for w in sg.words]
        dur = len(a) / SR
        sp0 = ww[0].start if ww else 0.0
        sp1 = ww[-1].end if ww else dur
        caps = ln["cap"].split()
        if len(ww) == len(caps):
            times = [(w.start, w.end) for w in ww]
        else:                              # spread over the spoken span by character weight
            wts = np.array([len(re.sub(r"\W", "", c)) + 1 for c in caps], float)
            edges = sp0 + np.concatenate([[0], np.cumsum(wts)]) / wts.sum() * (sp1 - sp0)
            times = list(zip(edges[:-1], edges[1:]))
        lines.append({"id": ln["id"], "cap": ln["cap"], "start": round(t, 3), "end": round(t + dur, 3),
                      "heard": " ".join(w.word.strip() for w in ww),
                      "words": [{"w": c, "start": round(t + a0, 3), "end": round(t + a1, 3)} for c, (a0, a1) in zip(caps, times)]})
        track += [a, np.zeros(int(gap * SR))]
        t += dur + gap
        print(f"{ln['id']:9s} {dur:5.2f}s | heard: {lines[-1]['heard'][:90]}", flush=True)
    track.append(np.zeros(int(TAIL * SR)))
    y = np.concatenate(track)
    y = y / max(1e-6, np.abs(y).max()) * 0.89          # -1 dBFS peak before mastering
    sf.write(os.path.join(vdir, "vo.wav"), y, SR)
    json.dump({"dur": round(len(y) / SR, 3), "lines": lines}, open(os.path.join(vdir, "words.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("VO", round(len(y) / SR, 2), "s")


if __name__ == "__main__":
    main(sys.argv[1])
