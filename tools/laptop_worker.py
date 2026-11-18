"""Studio render worker for Mehul's laptop (Windows). Pulls render jobs from the server over ssh (no open port),
renders with HyperFrames, sends the video back. Started hidden at logon (Task Scheduler "StudioRenderWorker").
Mode (C:\\Users\\mehul\\studio-render\\mode.txt, set with tools\\studio-mode.cmd):
  auto  (default) full speed when you have not touched the keyboard/mouse for 3 min, gentle while you work
  fast  full speed always (normal priority, 6 render workers)
  quiet gentle always (below-normal priority, 3 workers: your apps stay smooth)
  off   take no jobs
On battery it takes no jobs (the server renders as before)."""
import ctypes, json, os, shutil, subprocess, sys, tarfile, time, traceback

HOST = "ubuntu@137.23.60.164"
KEY = r"C:\Users\mehul\Desktop\job\oracle.key"
HOME = r"C:\Users\mehul\studio-render"
R = "/home/ubuntu/studio-out/laptop"
SSH = ["ssh", "-i", KEY, "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=15", HOST]
SCP = ["scp", "-q", "-i", KEY, "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]
NOWIN = 0x08000000                                     # CREATE_NO_WINDOW: no console flashes
PRIO = {"fast": 0x00000020, "quiet": 0x00004000}         # NORMAL / BELOW_NORMAL priority class (Chrome inherits it)
WORKERS = {"fast": "6", "quiet": "3"}


def log(*a):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    with open(os.path.join(HOME, "worker.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    try:                                                   # keep the log small
        p = os.path.join(HOME, "worker.log")
        if os.path.getsize(p) > 2_000_000:
            os.replace(p, p + ".1")
    except OSError:
        pass


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


class POWER(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte), ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


def idle_s():
    li = LASTINPUTINFO(); li.cbSize = ctypes.sizeof(li)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
    return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000.0


def on_ac():
    p = POWER()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(p))
    return p.ACLineStatus != 0                              # 1 = plugged in, 255 = unknown (desktop): treat as plugged


def wanted():
    try:
        m = open(os.path.join(HOME, "mode.txt")).read().strip().lower()
    except OSError:
        m = "auto"
    return m if m in ("auto", "fast", "quiet", "off") else "auto"


def effective():
    m = wanted()
    if m == "auto":
        return "fast" if idle_s() > 180 else "quiet"
    return m


def run(cmd, timeout=120, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NOWIN, **kw)


def checkin(mode, ac, busy=""):
    info = json.dumps({"mode": mode, "wanted": wanted(), "ac": ac, "busy": busy, "idle": round(idle_s()), "t": time.strftime("%H:%M:%S")})
    claim = "" if busy or mode == "off" or not ac else (
        f'cd {R}/queue 2>/dev/null && for f in $(ls -tr *.json 2>/dev/null); do mv "$f" ../claimed/ 2>/dev/null && echo "JOB $f" && break; done')
    r = run(SSH + [f"mkdir -p {R}/queue {R}/claimed {R}/done; echo '{info}' > {R}/alive.json; {claim}"], timeout=40)
    for line in r.stdout.splitlines():
        if line.startswith("JOB "):
            return line[4:].strip()[:-5]                    # strip ".json"
    return None


def render(jid):
    mode = effective()
    work = os.path.join(HOME, "jobs", jid)
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    try:
        r = run(SCP + [f"{HOST}:{R}/queue/{jid}.tgz", os.path.join(work, "r.tgz")], timeout=300)
        if r.returncode:
            raise RuntimeError("download failed: " + r.stderr[-200:])
        with tarfile.open(os.path.join(work, "r.tgz")) as t:
            t.extractall(work, filter="data")
        out = os.path.join(work, "out.mp4")
        t0 = time.time()
        p = subprocess.run(["npx.cmd", "-y", "hyperframes@latest", "render", "--workers", WORKERS[mode], "--quiet", "--output", out],
                           cwd=os.path.join(work, "render"), capture_output=True, text=True, timeout=1500,
                           creationflags=NOWIN | PRIO[mode])
        if p.returncode or not os.path.exists(out):
            raise RuntimeError("render failed: " + (p.stderr or p.stdout)[-400:])
        log("rendered", jid, f"in {time.time() - t0:.0f} s, {mode} mode")
        r = run(SCP + [out, f"{HOST}:{R}/done/{jid}.mp4.part"], timeout=600)
        if r.returncode:
            raise RuntimeError("upload failed: " + r.stderr[-200:])
        run(SSH + [f"mv {R}/done/{jid}.mp4.part {R}/done/{jid}.mp4"], timeout=40)
    except Exception as e:
        log("job", jid, "failed:", str(e)[:300])
        msg = str(e)[:1500].replace("'", " ")
        run(SSH + [f"echo '{msg}' > {R}/done/{jid}.err"], timeout=40)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def measure_one(url, work):
    """Editing numbers of one competitor Short: length, cuts (scene changes), first cut, cuts per 10 s, loudness."""
    import re
    f = os.path.join(work, "v.mp4")
    r = run([sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "-q", "-f", "best[height<=720][ext=mp4]/best[height<=720]/best", "-o", f, url], timeout=240)
    if r.returncode or not os.path.exists(f):
        return {"url": url, "error": (r.stderr or "download failed")[-160:]}
    d = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], timeout=60).stdout.strip()
    dur = float(d or 0)
    s = run(["ffmpeg", "-hide_banner", "-i", f, "-vf", "scale=270:-2,select='gt(scene,0.32)',showinfo", "-an", "-f", "null", "-"], timeout=600).stderr
    cuts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", s) if float(x) > 0.15]   # frame 0 is not a cut
    l = run(["ffmpeg", "-hide_banner", "-i", f, "-af", "ebur128", "-f", "null", "-"], timeout=300).stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", l)
    os.remove(f)
    return {"url": url, "dur": round(dur, 1), "cuts": len(cuts), "first_cut": round(cuts[0], 2) if cuts else None,
            "cuts_per_10s": round(10 * len(cuts) / dur, 2) if dur else None, "lufs": float(lufs[-1]) if lufs else None,
            "cut_times": [round(c, 1) for c in cuts[:40]], "t": time.strftime("%Y-%m-%d %H:%M")}


LAST_MEASURE = [0.0]


def idle_work():
    """No render waiting and Mehul away (or mode fast): measure up to 4 competitor Shorts the server listed."""
    if time.time() - LAST_MEASURE[0] < 900 or effective() != "fast" or not on_ac():
        return
    LAST_MEASURE[0] = time.time()
    r = run(SSH + [f"cat {R}/measure-todo.json 2>/dev/null"], timeout=40)
    try:
        todo = json.loads(r.stdout or "[]")
    except ValueError:
        return
    done = set()
    p = os.path.join(HOME, "measured.json")
    try:
        done = {x["url"] for x in json.load(open(p))}
    except Exception:
        pass
    picks = [t for t in todo if t.get("url") not in done][:4]
    if not picks:
        return
    work = os.path.join(HOME, "jobs", "measure"); os.makedirs(work, exist_ok=True)
    res = []
    for t in picks:
        if effective() != "fast":                       # Mehul is back: stop, the rest waits for the next idle stretch
            break
        try:
            m = measure_one(t["url"], work); m.update({k: t.get(k) for k in ("page", "channel", "views", "title")}); res.append(m)
        except Exception as e:
            res.append({"url": t["url"], "error": str(e)[:160]})
    if not res:
        return
    try:
        old = json.load(open(p))
    except Exception:
        old = []
    json.dump((old + res)[-2000:], open(p, "w"))
    out = os.path.join(work, "m.json"); json.dump(res, open(out, "w"))
    run(SCP + [out, f"{HOST}:{R}/done/measure-{time.strftime('%m%d%H%M%S')}.json"], timeout=120)
    log("measured", len(res), "competitor Shorts")


def main():
    os.makedirs(os.path.join(HOME, "jobs"), exist_ok=True)
    log("worker started, mode", wanted())
    while True:
        try:
            ac = on_ac()
            jid = checkin(effective(), ac)
            if not jid:
                try:
                    idle_work()
                except Exception:
                    log("idle work error", traceback.format_exc()[-300:])
            if jid:
                log("job", jid, "claimed")
                import threading                                 # keep checking in while rendering (server sees it alive)
                stop = threading.Event()
                def beat():
                    while not stop.wait(20):
                        try:
                            checkin(effective(), on_ac(), busy=jid)
                        except Exception:
                            pass
                th = threading.Thread(target=beat, daemon=True); th.start()
                try:
                    render(jid)
                finally:
                    stop.set()
                continue
        except Exception:
            log("loop error", traceback.format_exc()[-400:])
        time.sleep(15)


if __name__ == "__main__":
    main()
