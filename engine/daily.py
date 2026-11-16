"""Scheduler (systemd timer studio-make, every 2 h): for each active channel, keep a backlog of made-but-not-posted
videos; when it is below the target and Muse has budget, make ONE video (one job at a time on the whole server).
  python engine/daily.py [--dry]"""
import fcntl, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, PY, log, load
import muse

LOCK = os.path.join(OUT, "make.lock")


def backlog(cid):
    done = load(os.path.join(ROOT, "channels", cid, "done.json"), [])
    return sum(1 for d in done if d.get("status") in ("made", "approved"))


def main():
    dry = "--dry" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    lk = open(LOCK, "w")
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("daily: another job is running"); return
    subprocess.run(["git", "-C", ROOT, "pull", "-q", "--rebase", "--autostash"], timeout=120)
    if not muse._bridges("image"):
        log("daily: no Muse image budget left today"); return
    chans = []
    for cid in sorted(os.listdir(os.path.join(ROOT, "channels"))):
        c = load(os.path.join(ROOT, "channels", cid, "channel.json"))
        if not c or c.get("status") not in ("pilot", "active"):
            continue
        target = c.get("schedule", {}).get("backlog", 4)
        b = backlog(cid)
        log("daily:", cid, "backlog", b, "target", target)
        if b < target:
            chans.append((b / max(1, target), cid))
    if not chans:
        return
    chans.sort()
    cid = chans[0][1]
    log("daily: making one video for", cid)
    if not dry:
        r = subprocess.run([PY, os.path.join(ROOT, "engine", "make.py"), cid], timeout=4 * 3600)
        subprocess.run([PY, os.path.join(ROOT, "engine", "sync.py")], timeout=300)


if __name__ == "__main__":
    main()
