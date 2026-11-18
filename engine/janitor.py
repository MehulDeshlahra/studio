"""Janitor (18 Nov, owner: "do the cleanup, keep an agent for this activity"). Daily at 03:30, and on demand.

1. Duplicates: two unposted Hindi videos with the same topic on one page -> the newest stays, the older is 'removed'
   (if one is already posted, every unposted copy goes).
2. Rejected / removed videos older than a day: video and work files deleted; plan, review, meta, feedback and the small
   cover stay, so the history line and the lessons remain.
3. Dead builds: a folder that is in no list, has no stage and was untouched for 12 h is deleted. If it was a serial
   part, that part goes back to 'todo' (18 Nov: Part 7 of Chouthi Manzil died at the voice step but was marked made, so
   the serial would have waited for it forever).
4. Serial gaps: a part marked made whose job is nowhere -> 'todo' again.
5. Pilot / test renders older than 3 days are deleted.
Never touches posted, approved, waiting or held videos' files, prepped jobs, or anything a running job uses.
  python engine/janitor.py [--now] [--dry]     (--now: 2 h instead of 12 h / 1 day, for a cleanup the owner asked for)
"""
import json, os, re, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save

DRY = "--dry" in sys.argv
NOW = "--now" in sys.argv
PAGES = ("tech", "katha", "raaz")
KEEP = re.compile(r"\.(json|md|txt)$|^cover-s\.jpg$")
report = []


def idle_h(p):
    newest = os.path.getmtime(p)
    for dp, dn, fn in os.walk(p):
        for f in fn:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(dp, f)))
            except OSError:
                pass
    return (time.time() - newest) / 3600


def mb(p):
    t = 0
    for dp, dn, fn in os.walk(p):
        for f in fn:
            try:
                t += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return t / 1048576


def norm(t):
    return re.sub(r"\W+", " ", str(t or "")).strip().lower()


def dedupe(cid, done):
    by = {}
    for d in done:
        if not d["job"].endswith("-en") and d.get("status") in ("posted", "approved", "made", "waiting", "ready", "held"):
            by.setdefault(norm(d.get("topic")), []).append(d)
    n = 0
    for t, xs in by.items():
        if len(xs) < 2 or not t:
            continue
        posted = [x for x in xs if x.get("status") == "posted"]
        keep = posted[0] if posted else sorted(xs, key=lambda x: x["job"])[-1]
        for x in xs:
            if x is not keep and x.get("status") != "posted":
                report.append(f"{cid} {x['job']}: duplicate of {keep['job']} ({t[:50]}) -> removed")
                x["status"] = "removed"; x["removed_why"] = f"duplicate of {keep['job']}"; n += 1
    return n


def prune(cid, done):
    freed = 0
    for d in done:
        if d.get("status") not in ("rejected", "removed") or d.get("pruned"):
            continue
        jd = os.path.join(OUT, cid, d["job"])
        if not os.path.isdir(jd):
            d["pruned"] = time.strftime("%Y-%m-%d"); continue
        if idle_h(jd) < (2 if NOW else 24):
            continue
        before = mb(jd)
        for f in os.listdir(jd):
            p = os.path.join(jd, f)
            if os.path.isfile(p) and KEEP.search(f):
                continue
            if not DRY:
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
        freed += before - (mb(jd) if not DRY else 0)
        d["pruned"] = time.strftime("%Y-%m-%d")
        report.append(f"{cid} {d['job']} ({d.get('status')}): video files deleted, history kept")
    return freed


def serial_fix(cid, gone_jobs):
    try:
        import serials
    except Exception:
        return
    listed = {d["job"] for d in load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []}
    for s in serials.stories(cid):
        ch = False
        for p in s["parts"]:
            j = s.get("made_jobs", {}).get(str(p["n"]))
            if p.get("status") != "made" or not j:
                continue
            alive = j in listed or (os.path.isdir(os.path.join(OUT, cid, j)) and j not in gone_jobs)
            if not alive:
                p["status"] = "todo"; s["made_jobs"].pop(str(p["n"]), None); ch = True
                report.append(f"{cid} serial '{s['title']}' Part {p['n']}: its build ({j}) died -> will be made again")
        if ch and not DRY:
            serials._save(cid, s)


def dead_builds(cid, done):
    listed = {d["job"] for d in done}
    cd = os.path.join(OUT, cid)
    gone, freed = set(), 0
    if not os.path.isdir(cd):
        return gone, freed
    for j in os.listdir(cd):
        jd = os.path.join(cd, j)
        if j in listed or not os.path.isdir(jd):
            continue
        m = load(os.path.join(jd, "meta.json"), {}) or {}
        if m.get("stage"):                                  # prepped / rendering: the lanes own it
            continue
        if idle_h(jd) < (2 if NOW else 12):
            continue
        freed += mb(jd); gone.add(j)
        report.append(f"{cid} {j}: dead build ({m.get('topic', '?')[:50]}) deleted")
        t = str(m.get("topic") or "")
        if re.match(r".+ - Part \d+:", t) and t not in {str(d.get("topic")) for d in done}:   # katha series part
            sp = os.path.join(ROOT, "channels", cid, "series-state.json")
            st = load(sp, {}) or {}
            if st and t not in (st.get("redo") or []):
                st.setdefault("redo", []).insert(0, t)
                report.append(f"{cid} series part '{t[:60]}' will be made again first")
                if not DRY:
                    save(sp, st)
        if not DRY:
            shutil.rmtree(jd, ignore_errors=True)
    return gone, freed


def pilots():
    pd, freed = os.path.join(OUT, "pilot"), 0
    if not os.path.isdir(pd):
        return 0
    for f in os.listdir(pd):
        p = os.path.join(pd, f)
        age = idle_h(p) if os.path.isdir(p) else (time.time() - os.path.getmtime(p)) / 3600
        if age < (2 if NOW else 72):
            continue
        freed += mb(p) if os.path.isdir(p) else os.path.getsize(p) / 1048576
        if not DRY:
            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
    if freed:
        report.append(f"pilot/test renders: {freed:.0f} MB deleted")
    return freed


def main():
    freed = 0
    for cid in PAGES:
        f = os.path.join(ROOT, "channels", cid, "done.json")
        done = load(f, []) or []
        dedupe(cid, done)
        freed += prune(cid, done)
        gone, fr = dead_builds(cid, done)
        freed += fr
        if not DRY:
            save(f, done)
        serial_fix(cid, gone)
    freed += pilots()
    line = f"janitor: {len(report)} actions, {freed:.0f} MB freed" + (" (dry run)" if DRY else "")
    log(line)
    for r in report:
        log("janitor:", r)
    if not DRY:
        st = load(os.path.join(OUT, "janitor.json"), {}) or {}
        st["last"] = time.strftime("%Y-%m-%d %H:%M"); st["freed_mb"] = round(freed); st["actions"] = report[-40:]
        save(os.path.join(OUT, "janitor.json"), st)
        if report and os.system(f"cd {ROOT} && git add channels/*/done.json channels/*/stories >/dev/null 2>&1 && "
                                f"git commit -qm 'janitor: {len(report)} cleanups' >/dev/null 2>&1") == 0:
            os.system(f"cd {ROOT} && git pull -q --rebase --autostash && git push -q")
    print(line); print("\n".join(report))


if __name__ == "__main__":
    main()
