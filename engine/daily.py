"""24x7 scheduler (systemd timer studio-make, every 30 min). One job at a time on the server (lock), paced by
daily budgets so free quotas last the whole day:
  - voice: STUDIO_TTS_CAP Gemini TTS requests/day (free tier ~10; default 8, leaves room for retries)
  - reels: STUDIO_REELS_CAP new videos/day (default 6)
  - Muse: only when a bridge still has image budget (Studio uses bridge 2 first, see muse.py)
Each run picks the most useful job:
  1. English edition of a finished Hindi video (no Muse cost, 1 voice request)  [channels with "english": true]
  2. a new video for the channel with the smallest backlog (made + approved, not posted)
  python engine/daily.py [--dry]"""
import fcntl, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, PY, log, load, save
import muse

LOCK = os.path.join(OUT, "make.lock")
BUDGET = os.path.join(OUT, "budget.json")
TTS_CAP = int(os.environ.get("STUDIO_TTS_CAP", "30"))   # key is on the credits project (owner, 17 Nov)
REELS_CAP = int(os.environ.get("STUDIO_REELS_CAP", "8"))


def today():
    return load(BUDGET, {}).get(time.strftime("%Y-%m-%d"), {"tts": 0, "reels": 0})


def note(kind):
    d = load(BUDGET, {})
    day = time.strftime("%Y-%m-%d")
    d = {day: d.get(day, {"tts": 0, "reels": 0})}
    d[day][kind] = d[day].get(kind, 0) + 1
    save(BUDGET, d)


def done_list(cid):
    return load(os.path.join(ROOT, "channels", cid, "done.json"), [])


def backlog(cid):
    return sum(1 for d in done_list(cid) if d.get("status") in ("made", "approved") and not d["job"].endswith("-en"))


def run(args, hours=4):
    log("daily: run", " ".join(args))
    return subprocess.run([PY] + args, timeout=hours * 3600).returncode


def main():
    dry = "--dry" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    lk = open(LOCK, "w")
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("daily: another job is running"); return
    # never run beside a hand-started job
    busy = subprocess.run("systemctl list-units --state=active --no-legend 'studio-job-*' 'studio-queue*'",
                          shell=True, capture_output=True, text=True).stdout.strip()
    if busy:
        log("daily: a manual job is running, skip"); return
    subprocess.run(["git", "-C", ROOT, "pull", "-q", "--rebase", "--autostash"], timeout=120)
    b = today()
    if b.get("tts", 0) >= TTS_CAP:
        log("daily: voice budget used today", b); return
    chans = []
    for cid in sorted(os.listdir(os.path.join(ROOT, "channels"))):
        c = load(os.path.join(ROOT, "channels", cid, "channel.json"))
        if c and c.get("status") in ("pilot", "active"):
            chans.append((cid, c))
    # 1) English editions (cheap: no Muse)
    for cid, c in chans:
        if not c.get("english"):
            continue
        jobs = {d["job"] for d in done_list(cid)}
        for d in done_list(cid):
            j = d["job"]
            if j.endswith("-en") or (j + "-en") in jobs or d.get("status") in ("rejected", "fix"):
                continue
            if not os.path.exists(os.path.join(OUT, cid, j, "assets.json")):
                continue
            log("daily: english edition of", cid, j)
            if dry:
                return
            run([os.path.join(ROOT, "engine", "translate.py"), cid, j], 1)
            note("tts")
            run([os.path.join(ROOT, "engine", "make.py"), cid, "--lang", "en", "--job", j + "-en", "--from", "voice", "--no-send"])
            run([os.path.join(ROOT, "engine", "sync.py")], 1)
            return
    # 2) a new video
    if b.get("reels", 0) >= REELS_CAP:
        log("daily: reel budget used today", b); return
    if not muse._bridges("image"):
        log("daily: no Muse image budget left today"); return
    want = []
    for cid, c in chans:
        target = c.get("schedule", {}).get("backlog", 6)
        n = backlog(cid)
        log("daily:", cid, "backlog", n, "target", target)
        if n < target:
            want.append((n / max(1, target), cid))
    if not want:
        log("daily: every backlog is full"); return
    want.sort()
    cid = want[0][1]
    log("daily: new video for", cid)
    if dry:
        return
    note("reels"); note("tts")
    run([os.path.join(ROOT, "engine", "make.py"), cid, "--no-send"])
    run([os.path.join(ROOT, "engine", "sync.py")], 1)


if __name__ == "__main__":
    main()
