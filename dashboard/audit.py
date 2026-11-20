"""Dashboard audit (like the job dashboard's audit.js): recompute every figure from the raw files, independently of
api.py, and compare with /api/state. Exit 1 and print the mismatches. Run after any dashboard change:
  python dashboard/audit.py"""
import glob, json, os, re, subprocess, sys, time, urllib.request

HOME = os.path.expanduser("~"); ROOT = os.path.join(HOME, "studio"); OUT = os.path.join(HOME, "studio-out")

def _pages():
    """Studio pages from channels/ (18 Nov: was hard-coded)."""
    sys.path.insert(0, os.path.join(ROOT, "engine"))
    import core
    return core.pages()

S = json.load(urllib.request.urlopen("http://127.0.0.1:4788/api/state", timeout=90))
bad, ok = [], 0


def check(name, shown, truth, tol=0):
    global ok
    if (isinstance(shown, (int, float)) and isinstance(truth, (int, float)) and abs(shown - truth) <= tol) or shown == truth:
        ok += 1
    else:
        bad.append(f"{name}: dashboard {shown!r} vs raw {truth!r}")


def jl(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


# 1 runs: one per job folder of the 3 studio pages
folders = [(c, j) for c in _pages() for j in os.listdir(os.path.join(OUT, c)) if os.path.isdir(os.path.join(OUT, c, j)) and os.path.exists(os.path.join(OUT, c, j, "plan.json"))]
shown = {(j["cid"], j["job"]) for j in S["jobs"]}
CAP = 40                                   # 20 Nov: /api/state sends the newest 40 runs on purpose (Cut Capsule alone has 70+)
if len(shown) >= CAP:                      # the window is by job_state "updated", not folder mtime: check only shown runs exist
    folders = [k for k in folders if k in shown]
check("runs: videos with a plan", len(shown & set(folders)), len(folders))
for k in set(folders) - shown:
    bad.append(f"runs: {k} exists on disk but is not shown")
# 2 status of each run vs done.json
for j in S["jobs"]:
    d = {x["job"]: x for x in (jl(os.path.join(ROOT, "channels", j["cid"], "done.json"), []) or [])}.get(j["job"])
    st = (d or {}).get("status")
    if j["active"]:
        continue
    if st in ("approved", "posted", "rejected") and j["status"] != st:
        bad.append(f"status {j['cid']}/{j['job']}: shown {j['status']} vs done.json {st}")
    elif st == "held" and j["status"] not in ("held", "building"):
        bad.append(f"status {j['cid']}/{j['job']}: shown {j['status']} vs done.json held")
    else:
        ok += 1
# 3 progress: a finished video (mp4 + review) must show 100% and all steps done
for j in S["jobs"]:
    jd = os.path.join(OUT, j["cid"], j["job"])
    if os.path.exists(os.path.join(jd, f"{j['cid']}-{j['job']}.mp4")) and os.path.exists(os.path.join(jd, "review.json")) and not j["active"]:
        if j["pct"] < 0.999:
            bad.append(f"progress {j['cid']}/{j['job']}: finished video shows {j['pct']:.0%}")
        else:
            ok += 1
# 4 budgets
b = (jl(os.path.join(OUT, "budget.json"), {}) or {}).get(time.strftime("%Y-%m-%d"), {})
sb = {x["name"]: x["used"] for x in S["budgets"]}
check("budget voice", sb.get("Voice (Gemini TTS)"), b.get("tts", 0)); check("budget videos", sb.get("New videos today"), b.get("reels", 0))
# 5 server
du = os.statvfs("/"); disk = 100 * (1 - du.f_bavail / du.f_blocks)
check("disk %", S["server"]["disk_pct"], round(disk, 1), 1.5)
mem = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}
check("memory %", S["server"]["mem_pct"], round(100 * (1 - mem["MemAvailable"] / mem["MemTotal"]), 1), 3)
check("load", S["server"]["load"][0], round(os.getloadavg()[0], 2), 4)
up = float(open("/proc/uptime").read().split()[0]) / 3600
check("uptime h", S["server"]["uptime_h"], round(up, 1), 0.2)
# 6 timers: dashboard schedule vs systemd
out = subprocess.run("systemctl list-timers --all --no-legend 'studio*' | awk '{print $NF}'", shell=True, capture_output=True, text=True).stdout.split()
names = {t["unit"] for t in S["schedule"]}
for n in out:
    check(f"timer {n} listed", n.replace(".timer", "") in names or n.replace(".service", "") in names, True)
# 7 channels: followers vs Meta (cached 30 min: allow small drift)
ut = open(os.path.join(HOME, ".studio-meta-user.token")).read().strip()
d = json.load(urllib.request.urlopen(f"https://graph.facebook.com/v23.0/me/accounts?fields=name,followers_count,fan_count,instagram_business_account{{username,followers_count,media_count}}&limit=50&access_token={ut}", timeout=60))
meta = {(p.get("instagram_business_account") or {}).get("username"): p for p in d["data"]}
for c in S["channels"]:
    p = meta.get(c["ig"])
    if not p:
        bad.append(f"channel {c['name']}: @{c['ig']} not found in Meta"); continue
    ig = p["instagram_business_account"]
    check(f"{c['name']} IG followers", c["igF"], ig.get("followers_count", 0), 5)
    check(f"{c['name']} IG posts", c["posts"], ig.get("media_count", 0), 1)
    check(f"{c['name']} FB followers", c["fb"], p.get("followers_count", p.get("fan_count", 0)) or 0, 5)
# 8 VAJRA pipeline counts
q = jl(os.path.join(HOME, "vajra-automation", "social", "queue.json"), {}) or {}
vc = next((c for c in S["channels"] if c["id"] == "vajra"), None)
if vc:
    posts = q.get("posts", [])
    pend = [x for x in posts if not x.get("posted") and not x.get("hold")]
    check("VAJRA queued", vc["counts"].get("queued"), len(pend))
    check("VAJRA on hold", vc["counts"].get("on_hold"), len(q.get("hold", [])))
# 9 quality numbers vs a fresh parse
first = {}
rx = re.compile(r"^(\d{4}-\d\d-\d\d) [\d:]+ review (\w+) (\S+) (PASS|HOLD)")
for line in open(os.path.join(OUT, "engine.log"), encoding="utf-8", errors="ignore"):
    m = rx.match(line)
    if m and (m.group(2), m.group(3)) not in first:
        first[(m.group(2), m.group(3))] = (m.group(1), m.group(4) == "PASS")
since = S["quality"]["days"][0]["day"]
vs = [v for v in first.values() if v[0] >= since]
check("first-pass videos (7 d)", S["quality"]["videos7"], len(vs)); check("first-pass passed", sum(1 for v in vs if v[1]), round(S["quality"]["rate7"] * len(vs) / 100) if vs else 0, 1)
# 10 approvals list = waiting/ready only
need = [j for j in S["jobs"] if j["status"] in ("waiting", "ready")]
check("needs-you approvals", len([n for n in S["needs"] if n["kind"] == "approve"]), len(need))
# 11 stale data
check("state fresh (s)", int(time.time()) - S["now"] < 120, True)
if S["server"]["hist"]:
    check("server chart fresh", time.time() - S["server"]["hist"][-1]["t"] < 30, True)
# 12 doctor ran recently
dst = jl(os.path.join(OUT, "doctor-state.json"), {}) or {}
check("doctor ran < 30 min ago", time.time() - dst.get("last", 0) < 1800, True)
# 13 every job shown has working media links
for j in S["jobs"][:60]:
    for f, here in j["files"].items():
        if here and not os.path.exists(os.path.join(OUT, j["cid"], j["job"], f)):
            bad.append(f"media {j['cid']}/{j['job']}/{f} listed but missing")
print(f"{ok} checks ok, {len(bad)} mismatches")
for b_ in bad:
    print(" ✗", b_)
sys.exit(1 if bad else 0)
