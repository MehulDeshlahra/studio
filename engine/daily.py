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
# 18 Nov owner: "never limit yourself to keep something spare; I will bring more keys". No daily caps: the keys
# themselves are the limit (KeyWatch skips a key once Google says it is out, and Telegram asks for more when all are out).
TTS_CAP = int(os.environ.get("STUDIO_TTS_CAP", "100000"))
REELS_CAP = int(os.environ.get("STUDIO_REELS_CAP", "100000"))
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


SERIAL_AHEAD = 2


def serial_blocked(cid):
    """18 Nov: Aage Suno made Parts 1-8 of one story in a day while Parts 1-5 were all held, so 8 of 10 parts were used
    up with nothing ready to post. A serial makes its next part only while fewer than SERIAL_AHEAD of its parts are held;
    the healer fixes those first (a part that is held stays the story's Part n)."""
    try:
        import serials
        ch = dict(load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}, id=cid)
        st = {d["job"]: d.get("status") for d in done_list(cid)}
        for s in serials.stories(cid):
            if s.get("closed") or not any(p["status"] == "todo" for p in s["parts"]):
                continue
            held = [n for n, j in (s.get("made_jobs") or {}).items() if st.get(j) == "held"]
            if len(held) >= SERIAL_AHEAD:
                log(f"prep lane: {cid} serial '{s['title']}' has {len(held)} held parts ({', '.join(sorted(held, key=int))}): "
                    "no new part until they are fixed")
                return True
            return False
    except Exception as e:
        log("prep lane: serial check failed", str(e)[:120])
    return False


URGENT_MIN = 2


def urgent_pages():
    """18 Nov: live pages with fewer than URGENT_MIN ready videos, emptiest first. They get the next build before the
    healer's rebuilds (engine/healer.py checks this too): from 04:35 to 10:50 only 3 new videos were started because healer
    rebuilds held the server, while Aage Suno had 1 ready video two days before launch."""
    out = []
    for cid in sorted(os.listdir(os.path.join(ROOT, "channels"))):
        c = load(os.path.join(ROOT, "channels", cid, "channel.json")) or {}
        if str(c.get("status", "")).startswith("live"):
            n = backlog(cid)
            if n < URGENT_MIN:
                out.append((n, cid))
    return [cid for n, cid in sorted(out)]


def run(args, hours=4):
    log("daily: run", " ".join(args))
    return subprocess.run([PY] + args, timeout=hours * 3600).returncode


def manual_busy():
    out = subprocess.run("systemctl list-units --state=active --no-legend 'studio-job-*' 'studio-queue*'",
                         shell=True, capture_output=True, text=True).stdout.strip()
    return bool(out)


def lane_render(dry):
    held = {(cid, d["job"]) for cid in os.listdir(os.path.join(ROOT, "channels")) for d in (done_list(cid) or [])
            if d.get("status") == "held"}
    todo = [t for t in jobs_in("prepped") if (t[0], t[1]) not in held]   # 18 Nov: a held job is the healer's, not the lane's
    if not todo:
        log("render lane: nothing prepped"); return
    # 18 Nov: with the laptop the two lanes take turns non-stop, so the healer (runs only when nothing builds) got no turn
    # from 11:07 to 15:10 with 6 videos held. Its flag now pauses the render lane too, once, until the healer has run.
    w = os.path.join(OUT, "healer-wants-turn")
    if os.path.exists(w) and time.time() - os.path.getmtime(w) < 3600 and not urgent_pages():
        log("render lane: the healer needs a turn to fix held videos, skip this round"); return
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
        # 18 Nov: Aage Suno went "live (warm-up)" on 17 Nov 01:12 and no lane built a single raaz video after that
        # (only pilot/active were built); mehul.py and stories.py already counted the live statuses.
        if c and c.get("status") in ("pilot", "active", "live", "live (warm-up)"):
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
    urgent = [cid for cid in urgent_pages() if any(cid == x and not (c.get("serial") and serial_blocked(cid)) for x, c in chans)]
    w = os.path.join(OUT, "healer-wants-turn")    # 18 Nov: held videos get fixed before more new ones are started
    if os.path.exists(w) and time.time() - os.path.getmtime(w) < 3600 and not urgent:
        log("prep lane: the healer needs a turn to fix held videos, skip this round"); return
    if urgent:
        log("prep lane: new video for", urgent[0], f"(urgent: fewer than {URGENT_MIN} ready videos on a live page)")
        if dry:
            return
        note("reels"); note("tts")
        run([os.path.join(ENGINE, "make.py"), urgent[0], "--until", "assets"])
        return
    if not muse._bridges("image"):     # 18 Nov: this stopped ALL new videos although pictures fall back to free FLUX
        log("prep lane: Muse image budget used today; pictures come from the free FLUX sources (OmniRoute, Cloudflare, Pollinations)")
    want = []
    for cid, c in chans:
        if c.get("serial") and serial_blocked(cid):
            continue
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
        # 18 Nov: while the laptop renders, the render lane only waits (no CPU here): the prep lane may build the next
        # video meanwhile. Its own lock keeps it to one prep at a time; the memory floor below still applies.
        lp = os.path.join(OUT, "laptop", "rendering")
        if lane == "prep" and os.path.exists(lp) and time.time() - os.path.getmtime(lp) < 1800:
            lk = open(os.path.join(OUT, "engine-prep.lock"), "w")
            try:
                fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                log("prep lane: a prep is already running next to the laptop render, wait"); return
            log("prep lane: the laptop is rendering, so the server builds the next video meanwhile")
        else:
            log(f"{lane} lane: the other lane is building, wait"); return
    else:                                                   # we hold engine.lock: a prep beside a laptop render may still run
        lk2 = open(os.path.join(OUT, "engine-prep.lock"), "w")
        try:
            fcntl.flock(lk2, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log(f"{lane} lane: a prep started beside a laptop render is still building, wait"); return
        if lane != "prep":                                  # the render lane holds it only for this check
            fcntl.flock(lk2, fcntl.LOCK_UN)
    if manual_busy():
        # 18 Nov (owner: "are we not using the laptop? I set fast"): a hand-started job blocked the render lane for hours
        # while the laptop sat idle in fast mode. A render on the laptop costs this server almost nothing, so the
        # render lane goes ahead when the laptop is free; the memory floor below still applies.
        lap_ok = False
        if lane == "render":
            try:
                import laptop
                lap_ok = laptop.available()
            except Exception:
                lap_ok = False
        if not lap_ok:
            log(f"{lane} lane: a manual job is running, skip"); return
        log("render lane: a manual job is running, but the laptop is free: rendering there")
    try:                                                    # 18 Nov: the job bot shares this server; never push it into swap
        avail = int(next(l for l in open("/proc/meminfo") if l.startswith("MemAvailable")).split()[1]) // 1024
        if avail < int(os.environ.get("STUDIO_MIN_FREE_MB", "1800")):
            log(f"{lane} lane: only {avail} MB memory free (the other servers need it), wait"); return
    except Exception:
        pass
    subprocess.run(["git", "-C", ROOT, "pull", "-q", "--rebase", "--autostash"], timeout=120)
    (lane_prep if lane == "prep" else lane_render)(dry)


if __name__ == "__main__":
    main()
