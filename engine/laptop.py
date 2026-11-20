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
BUSY_WAIT = 1200           # 20 Nov: a busy-but-on laptop is waited for up to 20 min before the server renders


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
        # 20 Nov audit (owner: a video should take 5-10 min): while the laptop is ON but busy with another job (a clip),
        # waiting for it beats the shared server (tech 1120-1748z: 23 min here vs 3-5 min there). Renders are claimed
        # right after Whop jobs, so the wait is one job long; after BUSY_WAIT, or if the laptop goes away, render here
        while not os.path.exists(claimed) and (time.time() - t0 < CLAIM_WAIT or (
                time.time() - t0 < BUSY_WAIT and status().get("busy") and status().get("age", 999) < 90)):
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
        while time.time() - t0 < MAX_RENDER + BUSY_WAIT:
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


def job(spec, label="", wait=2400):
    """Hand one job (spec["kind"] = info | clip) to the laptop and wait. Returns the folder with what it sent back."""
    if not available():
        raise RuntimeError("the laptop is off: clip jobs need it (YouTube blocks the server)")
    for sub in ("queue", "claimed", "done"):
        os.makedirs(os.path.join(D, sub), exist_ok=True)
    jid = time.strftime("%m%d-%H%M%S") + "-" + spec["kind"][:1]
    q = os.path.join(D, "queue", jid)
    json.dump(dict(spec, id_=jid, label=label, t=time.time()), open(q + ".json.part", "w"))
    os.replace(q + ".json.part", q + ".json")
    t0 = time.time()
    claimed = os.path.join(D, "claimed", jid + ".json")
    done, err = os.path.join(D, "done", jid + ".tgz"), os.path.join(D, "done", jid + ".err")
    try:
        while time.time() - t0 < wait:
            if os.path.exists(err):
                raise RuntimeError(f"laptop {spec['kind']} failed: " + open(err, encoding="utf-8", errors="ignore").read()[-300:])
            if os.path.exists(done):
                break
            if time.time() - t0 > CLAIM_WAIT * 2 and not os.path.exists(claimed) and os.path.exists(q + ".json"):
                # 19 Nov: the worker does one job at a time; while it is busy (a transcribe/clip job) the queue waits
                if status().get("busy") and status().get("age", 999) < 90 and time.time() - t0 < wait:
                    time.sleep(4); continue
                raise RuntimeError("the laptop did not pick the job up")
            if os.path.exists(claimed) and status().get("age", 999) > 180:
                raise RuntimeError("the laptop went away during the job")
            time.sleep(4)
        else:
            raise RuntimeError(f"laptop {spec['kind']} too slow")
        out = os.path.join(OUT, "laptop", "fetched", jid)
        os.makedirs(out, exist_ok=True)
        with tarfile.open(done) as t:
            t.extractall(out, filter="data")
        log(f"laptop: {spec['kind']} done in {time.time() - t0:.0f} s ({label})")
        return os.path.join(out, "fetch")
    finally:
        for f in (q + ".json", claimed, err, done):
            try:
                os.remove(f)
            except OSError:
                pass


def info(url, label=""):
    d = job({"kind": "info", "url": url}, label, wait=300)
    return json.load(open(os.path.join(d, "info.json")))


def fetch(url, sections, label="", wait=1800):
    """19 Nov (CutCapsule): YouTube blocks this server, so the laptop downloads the asked parts of a video.
    sections = [(start_s, end_s), ...]. Returns (info dict, [local mp4 path or None per section]); raises when the laptop
    is away or the download fails."""
    if not available():
        raise RuntimeError("the laptop is off or busy-off: YouTube downloads need it (YouTube blocks the server)")
    for sub in ("queue", "claimed", "done"):
        os.makedirs(os.path.join(D, sub), exist_ok=True)
    jid = time.strftime("%m%d-%H%M%S") + "-f"
    q = os.path.join(D, "queue", jid)
    json.dump({"id": jid, "kind": "fetch", "url": url, "sections": [[float(a), float(b)] for a, b in sections], "label": label,
               "t": time.time()}, open(q + ".json.part", "w"))
    os.replace(q + ".json.part", q + ".json")
    t0 = time.time()
    claimed = os.path.join(D, "claimed", jid + ".json")
    done, err = os.path.join(D, "done", jid + ".tgz"), os.path.join(D, "done", jid + ".err")
    try:
        while time.time() - t0 < wait:
            if os.path.exists(err):
                raise RuntimeError("laptop download failed: " + open(err, encoding="utf-8", errors="ignore").read()[-300:])
            if os.path.exists(done):
                break
            if time.time() - t0 > CLAIM_WAIT * 2 and not os.path.exists(claimed) and os.path.exists(q + ".json"):
                raise RuntimeError("the laptop did not pick the download up")
            time.sleep(4)
        else:
            raise RuntimeError("laptop download too slow")
        out = os.path.join(OUT, "laptop", "fetched", jid)
        os.makedirs(out, exist_ok=True)
        with tarfile.open(done) as t:
            t.extractall(out, filter="data")
        base = os.path.join(out, "fetch")
        info = json.load(open(os.path.join(base, "info.json"))) if os.path.exists(os.path.join(base, "info.json")) else {}
        files = [os.path.join(base, f"c{i}.mp4") if os.path.exists(os.path.join(base, f"c{i}.mp4")) else None for i in range(len(sections))]
        log(f"laptop: fetched {sum(1 for f in files if f)}/{len(files)} parts in {time.time() - t0:.0f} s ({label})")
        return info, files
    finally:
        for f in (q + ".json", claimed, err, done):
            try:
                os.remove(f)
            except OSError:
                pass


if __name__ == "__main__":
    print(json.dumps(dict(status(), available=available()), indent=1))
