"""Re-voice videos whose lines speak to the viewer informally (owner 20 Nov: "never say tu, always a request").
For each <page>/<job>: hold it (so the old voice cannot post), rewrite every viewer-facing line with engine/respect.py
(text model rewrite, word fix as fallback), make a new voice and rebuild. A video the owner had approved keeps its
approval if it passes the review again (make.py keep_approval). One video at a time.
  python tools/revoice.py finance/1119-0005 raaz/case2-p1 ..."""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "engine")); sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import respect
from core import ROOT, OUT, load, save, log, telegram

PY = sys.executable
for arg in sys.argv[1:]:
    cid, job = arg.split("/", 1)
    jd = os.path.join(OUT, cid, job)
    dp = os.path.join(ROOT, "channels", cid, "done.json")
    done = load(dp, []) or []
    row = next((d for d in done if d["job"] == job), None)
    if not row:
        log("revoice: not in done.json", arg); continue
    p = load(os.path.join(jd, "plan.json"), {}) or {}
    probs = respect.problems(p)
    if not probs:
        log("revoice: already clean", arg); continue
    was = row.get("status")
    row["status"] = "held"
    row["review"] = probs[:6] + (["owner-approved before the re-voice"] if was == "approved" else [])
    save(dp, done)
    n = respect.fix_plan(p)
    save(os.path.join(jd, "plan.json"), p)
    left = respect.problems(p)
    for f in ("vo-raw.wav", "vo-paced.wav", "timing.json"):
        if os.path.exists(os.path.join(jd, f)):
            os.remove(os.path.join(jd, f))
    if was == "approved":
        m = load(os.path.join(jd, "meta.json"), {}) or {}
        m["keep_approval"] = True; save(os.path.join(jd, "meta.json"), m)
    log("revoice:", arg, n, "lines rewritten", ("still informal: " + left[0][:100]) if left else "clean", "| new voice")
    t0 = time.time()
    r = subprocess.run([PY, os.path.join(ROOT, "engine", "make.py"), cid, "--job", job, "--from", "voice"], cwd=ROOT)
    st = next((d.get("status") for d in load(dp, []) if d["job"] == job), None)
    log("revoice:", arg, "done in", int(time.time() - t0), "s, status", st)
    try:
        telegram(f"🗣 {cid} {job} re-voiced to 'aap' wording: {st}")
    except Exception:
        pass
