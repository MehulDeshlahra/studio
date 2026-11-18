"""Render on Mehul's laptop when it is on (owner 18 Nov). Measured: the same video in 146 s on the laptop (i5-9300HF,
8 threads) vs 464 s here, frames identical (SSIM 0.987, grain only).
The laptop PULLS work (tools/laptop_worker.py over ssh), so it needs no open port. Nothing waits on the laptop:
  available()            the worker checked in < 60 s ago, plugged in, mode not "off"
  render(rdir, out, dur) hand the render folder over, wait; True = out written and checked, False = render here
Files: ~/studio-out/laptop/{alive.json, queue/, claimed/, done/}"""
import json, os, subprocess, sys, tarfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import OUT, log

D = os.path.join(OUT, "laptop")
CLAIM_WAIT = 75            # the worker polls every 15 s
MAX_RENDER = 1500          # a laptop render takes 2-4 min; 25 min means something is wrong -> render here


def status():
    try:
        a = json.load(open(os.path.join(D, "alive.json")))
        a["age"] = round(time.time() - os.path.getmtime(os.path.join(D, "alive.json")))
        return a
    except Exception:
        return {}


def available():
    s = status()
    return bool(s) and s["age"] < 60 and s.get("mode") != "off" and s.get("ac", True)


def _dur(f):
    try:
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                    capture_output=True, text=True, timeout=60).stdout.strip())
    except Exception:
        return 0.0


def render(rdir, out, total, label=""):
    for sub in ("queue", "claimed", "done"):
        os.makedirs(os.path.join(D, sub), exist_ok=True)
    jid = time.strftime("%m%d-%H%M%S")
    q = os.path.join(D, "queue", jid)
    with tarfile.open(q + ".tgz.part", "w:gz", compresslevel=3) as t:
        t.add(rdir, arcname="render")
    os.replace(q + ".tgz.part", q + ".tgz")
    json.dump({"id": jid, "total": total, "label": label, "t": time.time()}, open(q + ".json.part", "w"))
    os.replace(q + ".json.part", q + ".json")                 # the worker only looks at *.json: the job is complete now
    t0 = time.time()
    claimed = os.path.join(D, "claimed", jid + ".json")
    done, err = os.path.join(D, "done", jid + ".mp4"), os.path.join(D, "done", jid + ".err")
    try:
        while time.time() - t0 < CLAIM_WAIT and not os.path.exists(claimed):
            time.sleep(3)
        if not os.path.exists(claimed):
            try:
                os.remove(q + ".json")                          # take it back before the laptop can claim it
            except FileNotFoundError:
                if not os.path.exists(claimed):                 # claimed in the same second: wait for it after all
                    time.sleep(5)
            if not os.path.exists(claimed):
                log("laptop: did not pick the job up, rendering here"); return False
        log("laptop: rendering", label, "on", status().get("mode", "?"), "mode")
        open(os.path.join(D, "rendering"), "w").write(label)   # engine/daily.py: the prep lane may build meanwhile
        while time.time() - t0 < MAX_RENDER:
            if os.path.exists(err):
                log("laptop: render failed:", open(err, encoding="utf-8", errors="ignore").read()[-300:]); return False
            if os.path.exists(done):
                d = _dur(done)
                if abs(d - total) > 1.5:
                    log(f"laptop: wrong length {d:.1f} s (want {total:.1f}), rendering here"); return False
                os.replace(done, out)
                log(f"laptop: rendered in {time.time() - t0:.0f} s ({label})")
                return True
            if status().get("age", 999) > 180:
                log("laptop: went away during the render, rendering here"); return False
            time.sleep(4)
        log("laptop: too slow, rendering here"); return False
    finally:
        for f in (q + ".tgz", q + ".json", claimed, err, os.path.join(D, "rendering")):
            try:
                os.remove(f)
            except OSError:
                pass


if __name__ == "__main__":
    print(json.dumps(dict(status(), available=available()), indent=1))
