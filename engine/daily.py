"""24x7 scheduler, two lanes so network waits and CPU work overlap (2-core server):
  prep lane   (timer studio-prep,  every 10 min): research -> plan -> voice -> Muse images/clips  (mostly waiting on APIs)
  render lane (timer studio-make,  every 10 min): compose -> render -> mix -> QC -> send to Telegram  (CPU)
While one video renders, the next one's images are being made. Each lane has its own lock (one job per lane).
Daily budgets keep free quotas for the whole day:
  STUDIO_TTS_CAP voice requests/day (30), STUDIO_REELS_CAP new videos/day (8), Muse image budget (bridge 2 first).
Prep picks, in order: English edition of a finished Hindi video (no Muse cost) -> new video for the page with the
smallest backlog. At most STUDIO_PREPPED_MAX (2) prepped jobs wait for the render lane.
  python engine/daily.py --lane prep|render [--dry]"""
import fcntl, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, PY, log, load, save
import muse

BUDGET = os.path.join(OUT, "budget.json")
def _nkeys():
    try:
        return max(1, sum(1 for l in open(os.path.expanduser("~/.studio-gemini.key")) if l.strip()))
    except Exception:
        return 1
# 17 Nov (owner: "the server should always be making something"): ~10 free voice requests per key per day; keep 1 per key
# spare for re-voices. Reels per day follow the voice budget.
TTS_CAP = int(os.environ.get("STUDIO_TTS_CAP", str(9 * _nkeys())))
REELS_CAP = int(os.environ.get("STUDIO_REELS_CAP", str(7 * _nkeys())))
PREPPED_MAX = int(os.environ.get("STUDIO_PREPPED_MAX", "2"))
ENGINE = os.path.join(ROOT, "engine")


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


def jobs_in(stage):
    out = []
    for cid in sorted(os.listdir(OUT)):
        cd = os.path.join(OUT, cid)
        if not os.path.isdir(cd):
            continue
        for j in sorted(os.listdir(cd)):
            m = load(os.path.join(cd, j, "meta.json"), {})
            if m.get("stage") == stage:
                out.append((m.get("prepped_at", ""), cid, j, m))
    return [x[1:] for x in sorted(out)]


def backlog(cid):
    n = sum(1 for d in done_list(cid) if d.get("status") in ("made", "approved") and not d["job"].endswith("-en"))
    return n + sum(1 for c, j, m in jobs_in("prepped") if c == cid and not j.endswith("-en"))


def run(args, hours=4):
    log("daily: run", " ".join(args))
    return subprocess.run([PY] + args, timeout=hours * 3600).returncode


def manual_busy():
    out = subprocess.run("systemctl list-units --state=active --no-legend 'studio-job-*' 'studio-queue*'",
                         shell=True, capture_output=True, text=True).stdout.strip()
    return bool(out)


def lane_render(dry):
    todo = jobs_in("prepped")
    if not todo:
        log("render lane: nothing prepped"); return
    cid, j, m = todo[0]
    log("render lane:", cid, j)
    if dry:
        return
    args = [os.path.join(ENGINE, "make.py"), cid, "--job", j, "--from", "compose"]
    if m.get("lang") == "en":
        args += ["--lang", "en"]
    run(args)
    run([os.path.join(ENGINE, "sync.py")], 1)


def lane_prep(dry):
    if len(jobs_in("prepped")) >= PREPPED_MAX:
        log("prep lane: enough prepped jobs waiting for the render lane"); return
    b = today()
    if b.get("tts", 0) >= TTS_CAP:
        log("prep lane: voice budget used today", b); return
    chans = []
    for cid in sorted(os.listdir(os.path.join(ROOT, "channels"))):
        c = load(os.path.join(ROOT, "channels", cid, "channel.json"))
        if c and c.get("status") in ("pilot", "active"):
            chans.append((cid, c))
    # 1) English editions (no Muse cost)
    for cid, c in chans:
        if not c.get("english"):
            continue
        have = {d["job"] for d in done_list(cid)} | {j for cc, j, m in jobs_in("prepped") if cc == cid}
        for d in done_list(cid):
            j = d["job"]
            if j.endswith("-en") or (j + "-en") in have or d.get("status") in ("rejected", "fix"):
                continue
            if not os.path.exists(os.path.join(OUT, cid, j, "assets.json")):
                continue
            log("prep lane: english edition of", cid, j)
            if dry:
                return
            if run([os.path.join(ENGINE, "translate.py"), cid, j], 1) == 0:
                note("tts")
                run([os.path.join(ENGINE, "make.py"), cid, "--lang", "en", "--job", j + "-en", "--from", "voice", "--until", "assets"])
            return
    # 2) a new video
    if b.get("reels", 0) >= REELS_CAP:
        log("prep lane: reel budget used today", b); return
    if not muse._bridges("image"):
        log("prep lane: no Muse image budget left today"); return
    want = []
    for cid, c in chans:
        target = c.get("schedule", {}).get("backlog", 6)
        n = backlog(cid)
        log("prep lane:", cid, "backlog", n, "target", target)
        if n < target:
            want.append((n / max(1, target), cid))
    if not want:
        log("prep lane: every backlog is full"); return
    want.sort()
    cid = want[0][1]
    log("prep lane: new video for", cid)
    if dry:
        return
    note("reels"); note("tts")
    run([os.path.join(ENGINE, "make.py"), cid, "--until", "assets"])


def main():
    dry = "--dry" in sys.argv
    lane = sys.argv[sys.argv.index("--lane") + 1] if "--lane" in sys.argv else "render"
    os.makedirs(OUT, exist_ok=True)
    lk = open(os.path.join(OUT, "engine.lock"), "w")          # ONE lock for both lanes: one build at a time on 2 cores
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log(f"{lane} lane: the other lane is building, wait"); return
    if manual_busy():
        log(f"{lane} lane: a manual job is running, skip"); return
    subprocess.run(["git", "-C", ROOT, "pull", "-q", "--rebase", "--autostash"], timeout=120)
    (lane_prep if lane == "prep" else lane_render)(dry)


if __name__ == "__main__":
    main()
