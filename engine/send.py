"""Send a finished job to the Telegram group for approval (records the message id so replies map to the job).
  python engine/send.py <channel> <job> [<channel> <job> ...]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import OUT, load, save, telegram, log, sh


def send(cid, job):
    jd = os.path.join(OUT, cid, job)
    mp4 = os.path.join(jd, f"{cid}-{job}.mp4")
    if not os.path.exists(mp4):
        log("send: no video", cid, job); return None
    rv = load(os.path.join(jd, "review.json"))
    if not FORCE and (not rv or not rv.get("ok")):
        log("send: not sent, review missing or failed", cid, job, (rv or {}).get("problems"))
        return None
    p = load(os.path.join(jd, "plan.json"), {})
    q = load(os.path.join(jd, "qc.json"), {})
    f = q.get("format", {})
    probs = (rv or {}).get("minor", [])[:2]
    lang = "English" if p.get("lang") == "en" else "Hindi"
    txt = (f"[{cid} · {lang}] {p.get('title', job)}\n"
           f"✅ passed review · {f.get('dur')} s · {f.get('lufs')} LUFS · visual {(rv or {}).get('checks', {}).get('vision', {}).get('score')}/10\n"
           + ("Notes: " + " | ".join(str(x)[:140] for x in probs) + "\n" if probs else "")
           + f"\nCaption:\n{p.get('caption', '')}\n\nReply: ok / no / your feedback")
    if os.path.getsize(mp4) > 45 * 1024 * 1024:          # Telegram bots can send up to 50 MB
        prev = os.path.join(jd, "preview.mp4")
        if not os.path.exists(prev) or os.path.getmtime(prev) < os.path.getmtime(mp4):
            sh(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-maxrate", "5000k", "-bufsize", "10000k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", prev], timeout=1800)
        mp4 = prev
    mid = telegram(txt[:1000], video=mp4)
    if isinstance(mid, int):
        m = load(os.path.join(OUT, "tg-map.json"), {})
        m[str(mid)] = {"channel": cid, "job": job}
        save(os.path.join(OUT, "tg-map.json"), m)
        log("sent for approval", cid, job, mid)
    return mid


FORCE = "--force" in sys.argv
if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--force"]
    for i in range(0, len(a) - 1, 2):
        send(a[i], a[i + 1])
