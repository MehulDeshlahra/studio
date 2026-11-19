"""Studio dashboard server (stdlib only). Serves the app and a live JSON API about everything on this server.
Runs as systemd unit studio-dash on 127.0.0.1:4788; reached only through Tailscale (tailnet-only HTTPS :10000).
  GET  /api/state            everything the app shows (server, running work, jobs, issues, schedule, channels, log)
  GET  /api/brain            pages + lessons + videos as a graph
  GET  /media/<cid>/<job>/<file>   cover.jpg / review-sheet.jpg / preview.mp4 / final mp4 of a job
  POST /api/decide           {cid, job, action: approve|reject|fix, note}
  POST /api/make             {cid, topic?}  start one video now
  POST /api/settings         {auto_approve, min_score}
  POST /api/reset-failed     clear failed studio-* units"""
import glob, json, os, re, shutil, statistics, subprocess, sys, threading, time, urllib.parse, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extra

HOME = os.path.expanduser("~")
ROOT = os.path.join(HOME, "studio")

def _pages():
    """Studio pages from channels/ (18 Nov: was hard-coded)."""
    sys.path.insert(0, os.path.join(ROOT, "engine"))
    import core
    return core.pages()

OUT = os.path.join(HOME, "studio-out")
APP = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(OUT, "engine.log")
SETTINGS = os.path.join(OUT, "dash-settings.json")
FOLLOW_HIST = os.path.join(OUT, "dash-followers.json")
PY = os.path.join(HOME, "studio-venv", "bin", "python")
G = "https://graph.facebook.com/v23.0"
# 18 Nov: same defaults as engine/daily.py (owner: no self-imposed daily caps; free keys are the only limit). The old 30/8
# here made the brief say "15 of 8 budget cap, over limit" while nothing was capped.
TTS_CAP = os.environ.get("STUDIO_TTS_CAP"); REELS_CAP = os.environ.get("STUDIO_REELS_CAP")
TTS_CAP = int(TTS_CAP) if TTS_CAP else "no cap"; REELS_CAP = int(REELS_CAP) if REELS_CAP else "no cap"

CHANNELS = [  # channels on the dashboard (owner 17 Nov; Navkar Bhav, Finance Fuel, Getmeflat, Fibbi added 18 Nov)
    {"id": "tech", "name": "Kaise Tech", "group": "Studio", "color": "#facc15", "page": "1474228909103892", "ig": "kaise.tech", "yt": "@kaise.tech.official"},
    {"id": "katha", "name": "Puraan Ki Katha", "group": "Studio", "color": "#fb923c", "page": "1453056947892202", "ig": "puraankikatha", "yt": "@puraankikatha"},
    {"id": "raaz", "name": "Aage Suno", "group": "Studio", "color": "#a78bfa", "page": "1501633449691931", "ig": "aagesuno", "yt": "@aagesuno"},
    {"id": "jain", "name": "Navkar Bhav", "group": "Studio", "color": "#f2c14e", "page": "1498175213370788", "ig": "navkarbhav", "yt": None},
    {"id": "finance", "name": "Finance Fuel", "group": "Studio", "color": "#84cc16", "page": "1445486545315323", "ig": "finance.fuel", "yt": None},
    {"id": "cutcapsule", "name": "Cut Capsule", "group": "Studio", "color": "#ffd830", "page": "1443258675911320", "ig": "cutcapsule", "yt": None},
    {"id": "vajra", "name": "Vajra Formwork", "group": "Business", "color": "#34d399", "page": "1296793536861294", "ig": "vajraformwork", "yt": "channel/UCLl1cgbkcTjv5188ZIeAIlQ"},
    {"id": "planstalk", "name": "Planstalk", "group": "Business", "color": "#38bdf8", "page": None, "ig": "planstalkindia", "yt": None},
    {"id": "marginmart", "name": "MarginMart", "group": "Business", "color": "#f472b6", "page": None, "ig": "marginmartofficial", "yt": None},
    {"id": "getmeflat", "name": "Getmeflat", "group": "Business", "color": "#f97316", "page": None, "ig": "getmeflat", "yt": None},
    {"id": "fibbi", "name": "Fibbi", "group": "Business", "color": "#e11d48", "page": None, "ig": "fibbi.club", "yt": None},
]
STAGES = [("research", "Research", "research.json"), ("plan", "Script", "plan.json"), ("voice", "Voice", "vo-raw.wav"),
          ("pace", "Pace", "vo-paced.wav"), ("align", "Captions", "timing.json"), ("images", "Visuals", "assets.json"),
          ("compose", "Edit", "cues.json"), ("mix", "Music", "mix.wav"), ("render", "Render", "raw.mp4"),
          ("master", "Master", "{final}"), ("qc", "Checks", "qc.json"), ("cover", "Cover", "cover.jpg"),
          ("review", "Review", "review.json")]
FROM_MAP = {"voice": "voice", "compose": "compose", "assets": "images", "render": "render", "mix": "mix", "images": "images", "align": "align"}


ERRLOG = os.path.join(OUT, "dash-errors.log")


def log_exc(path):
    """Keep the traceback of a failed endpoint so the self-check agent can find the faulty line."""
    try:
        import traceback
        with open(ERRLOG, "a", encoding="utf-8") as f:
            f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {path}\n{traceback.format_exc()}")
        if os.path.getsize(ERRLOG) > 200000:
            data = open(ERRLOG, encoding="utf-8", errors="ignore").read()[-80000:]
            open(ERRLOG, "w", encoding="utf-8").write(data)
    except Exception:
        pass


def jload(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def jsave(p, v):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


# ---------------- server metrics (sampled in the background) ----------------
HIST = []          # [(t, cpu%, mem%, load1)]
_prev = None


def _cpu():
    """Returns (total %, normal-priority % = user+system, background % = niced Studio work)."""
    global _prev
    with open("/proc/stat") as f:
        v = list(map(int, f.readline().split()[1:]))
    cur = (v[0] + v[2] + v[5] + v[6], v[1], v[3] + v[4], sum(v))
    if _prev is None:
        _prev = cur; return 0.0, 0.0, 0.0
    dn, dni, di, dt = (cur[k] - _prev[k] for k in range(4)); _prev = cur
    if not dt:
        return 0.0, 0.0, 0.0
    return round(100 * (1 - di / dt), 1), round(100 * dn / dt, 1), round(100 * dni / dt, 1)


def _mem():
    m = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":"); m[k] = int(v.split()[0])
    return m["MemTotal"], m["MemAvailable"]


def sampler():
    while True:
        try:
            c, cn, cb = _cpu(); tot, av = _mem(); l1 = os.getloadavg()[0]
            HIST.append((int(time.time()), c, round(100 * (1 - av / tot), 1), round(l1, 2), cn, cb))
            del HIST[:-240]
        except Exception:
            pass
        time.sleep(5)


def gemini_keys():
    """Free Gemini keys: today's calls per key (engine/tts.py _KeyWatch writes ~/studio-out/gemini-keys.json)."""
    try:
        st = json.load(open(os.path.expanduser("~/studio-out/gemini-keys.json")))
    except Exception:
        st = {}
    try:
        tails = [l.strip()[-6:] for l in open(os.path.expanduser("~/.studio-gemini.key")) if l.strip()]
    except Exception:
        tails = []
    ks = st.get("keys", {}) if st.get("day") else {}
    return {"day": st.get("day"), "alerted": st.get("alerted"),
            "list": [dict({"id": "…" + t[-4:], "ok": 0, "fail": 0, "out": [], "models": {}}, **{k: v for k, v in ks.get(t, {}).items()}, id="…" + t[-4:]) for t in tails]}


def server():
    tot, av = _mem(); du = shutil.disk_usage("/")
    with open("/proc/uptime") as f:
        up = float(f.read().split()[0])
    la = os.getloadavg()
    muse = {}
    for port, name in ((20241, "bridge 2"), (20240, "bridge 1")):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3); muse[name] = True
        except Exception:
            muse[name] = False
    rec = HIST[-12:]                                        # last minute
    cpu_norm = round(sum(h[4] for h in rec) / len(rec), 1) if rec else 0
    cpu_bg = round(sum(h[5] for h in rec) / len(rec), 1) if rec else 0
    return {"cores": os.cpu_count(), "cpu": HIST[-1][1] if HIST else 0, "cpu_norm": cpu_norm, "cpu_bg": cpu_bg, "mem_pct": round(100 * (1 - av / tot), 1),
            "mem_used_gb": round((tot - av) / 1048576, 1), "mem_total_gb": round(tot / 1048576, 1),
            "disk_pct": round(100 * du.used / du.total, 1), "disk_free_gb": round(du.free / 1e9, 1), "disk_total_gb": round(du.total / 1e9),
            "load": [round(x, 2) for x in la], "uptime_h": round(up / 3600, 1), "muse": muse, "keys": gemini_keys(),
            "hist": [{"t": h[0], "cpu": h[1], "mem": h[2], "load": h[3], "norm": h[4], "bg": h[5]} for h in HIST[-120:]]}


# ---------------- what is running right now ----------------
KINDS = [("make.py", "Making video"), ("translate.py", "English edition"), ("publish.py", "Posting"), ("stats.py", "Reading stats"),
         ("scout.py", "Scouting trends"), ("inbox.py", "Reading Telegram"), ("brand.py", "Brand images"), ("send.py", "Sending to Telegram"),
         ("daily.py", "Scheduler")]


def processes():
    out, tick = [], os.sysconf("SC_CLK_TCK")
    with open("/proc/uptime") as f:
        up = float(f.read().split()[0])
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                args = f.read().decode(errors="ignore").split("\0")
            line = " ".join(args)
            if "/studio/engine/" not in line and "engine/" not in line:
                if "hyperframes" in line and "render" in line and "npm" not in args[0]:
                    pass
                else:
                    continue
            with open(f"/proc/{pid}/stat") as f:
                st = f.read().rsplit(")", 1)[1].split()
            age = up - int(st[19]) / tick
            out.append({"pid": int(pid), "args": args, "line": line, "age": int(age)})
        except Exception:
            continue
    return out


def parse_job(args):
    def opt(k):
        return args[args.index(k) + 1] if k in args and args.index(k) + 1 < len(args) else None
    script = next((os.path.basename(a) for a in args if a.endswith(".py")), "")
    i = next((k for k, a in enumerate(args) if a.endswith(".py")), -1)
    pos = [a for a in args[i + 1:] if not a.startswith("--")]
    flags = {a for a in args if a.startswith("--")}
    vals = {opt(k) for k in ("--job", "--from", "--lang", "--until", "--lane") if opt(k)}
    pos = [a for a in pos if a not in vals]
    return {"script": script, "cid": pos[0] if pos else None, "job": opt("--job") or (pos[1] if script in ("translate.py", "send.py") and len(pos) > 1 else None),
            "frm": opt("--from"), "lang": opt("--lang"), "until": opt("--until"), "lane": opt("--lane"), "flags": sorted(flags)}


def render_median():
    xs = []
    try:
        for line in tail_lines(LOG, 4000):
            m = re.search(r"rendered in (\d+) s", line)
            if m:
                xs.append(int(m.group(1)))
    except Exception:
        pass
    return int(statistics.median(xs[-12:])) if xs else 300


def tail_lines(p, n):
    try:
        with open(p, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 400 * n))
            return f.read().decode("utf-8", "ignore").splitlines()[-n:]
    except Exception:
        return []


# ---------------- jobs ----------------
def job_state(cid, job, active=None):
    jd = os.path.join(OUT, cid, job)
    final = f"{cid}-{job}.mp4"
    t0 = active["started"] if active else 0
    frm = FROM_MAP.get((active or {}).get("frm") or "", None)
    order = [s[0] for s in STAGES]
    cut = order.index(frm) if frm in order else 0
    steps, prev_t = [], 0
    for k, (key, label, fn) in enumerate(STAGES):
        p = os.path.join(jd, fn.replace("{final}", final))
        t = os.path.getmtime(p) if os.path.exists(p) else 0
        done = bool(t)
        if active and k >= cut and t and t < t0 - 5 and key not in ("research", "plan", "images"):   # visuals are reused, not remade
            done = False                      # an old file from an earlier build that this run will remake
        steps.append({"key": key, "label": label, "done": done, "t": int(t) if done else 0})
        prev_t = max(prev_t, t if done else 0)
    if not active and os.path.exists(os.path.join(jd, final)):
        for st_ in steps:                      # finished: files older runs never made (cover, qc) are not "missing steps"
            st_["done"] = True
    if active and active.get("until") == "assets":
        steps = steps[:6]
    cur = next((i for i, s in enumerate(steps) if not s["done"]), None)
    n = len([s for s in steps if s['key'] not in ('research', 'plan', 'images')]); doneN = sum(1 for s in steps if s['done'] and s['key'] in ('render', 'audio', 'video', 'final'))
    pct = doneN / n
    eta = None
    if active and cur is not None:
        steps[cur]["active"] = True
        if steps[cur]["key"] == "render":
            med = render_median(); since = time.time() - max(prev_t, t0)
            frac = min(0.95, since / med) if med else 0
            steps[cur]["sub"] = round(frac, 2); pct = (doneN + frac) / n; eta = max(0, int(med - since))
    plan = jload(os.path.join(jd, "plan.json"), {}) or {}
    rv = jload(os.path.join(jd, "review.json"), {}) or {}
    qc = jload(os.path.join(jd, "qc.json"), {}) or {}
    meta = jload(os.path.join(jd, "meta.json"), {}) or {}
    files = {f: os.path.exists(os.path.join(jd, f)) for f in ("cover.jpg", "review-sheet.jpg", "preview.mp4", final)}
    fin_t = [int(os.path.getmtime(os.path.join(jd, x))) for x in (final, "review.json", "cover.jpg") if os.path.exists(os.path.join(jd, x))]   # not the folder time: cleanups touch folders
    mt = max([s["t"] for s in steps] + fin_t) or int(os.path.getmtime(jd))
    return {"cid": cid, "job": job, "title": plan.get("title") or meta.get("topic") or job, "lang": "en" if job.endswith("-en") or plan.get("lang") == "en" else "hi",
            "steps": steps, "pct": round(pct, 3), "eta": eta, "updated": mt, "files": files, "final": final,
            "review": ({"ok": None, "problems": [], "minor": [], "score": None} if active else
                       {"ok": rv.get("ok"), "problems": rv.get("problems", [])[:4], "minor": rv.get("minor", [])[:3],
                        "score": ((rv.get("checks") or {}).get("vision") or {}).get("score")}),
            "doctor_tries": meta.get("doctor_tries", 1 if meta.get("doctor_rebuilt") else 0), "doctor_code": meta.get("doctor_code"),
            "qc": {"dur": (qc.get("format") or {}).get("dur"), "lufs": (qc.get("format") or {}).get("lufs")},
            "caption": plan.get("caption", ""), "active": bool(active), "pid": (active or {}).get("pid"),
            "topic": meta.get("topic") or plan.get("topic") or "", "stage": meta.get("stage"), "request": meta.get("request") or "", "prepped": bool(meta.get("prepped_at")) and not files.get(final), "started": int(t0) if active else None}


def tgmap():
    m = jload(os.path.join(OUT, "tg-map.json"), {}) or {}
    return {(v.get("channel"), v.get("job")) for v in m.values()}


_head = {"t": 0, "v": ""}


def head():
    if time.time() - _head["t"] > 60:
        _head.update(t=time.time(), v=run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"]).strip())
    return _head["v"]


def jobs(running):
    act = {}
    for r in running:
        p = r.get("job")
        if p and p.get("script") == "make.py" and p.get("cid") and p.get("job"):
            k = (p["cid"], p["job"])
            if k not in act or r["age"] < act[k]["age"]:        # the newest process is the one doing the work (a re-voice child)
                act[k] = {"started": time.time() - r["age"], "frm": p.get("frm"), "until": p.get("until"), "age": r["age"], "pid": r.get("pid")}
        elif p and p.get("script") == "make.py" and p.get("cid") in _pages():
            base = os.path.join(OUT, p["cid"])                    # new video without --job: its folder is the newest one made after start
            t0 = time.time() - r["age"]
            ds = [d for d in (os.listdir(base) if os.path.isdir(base) else []) if os.path.getmtime(os.path.join(base, d)) >= t0 - 30]
            if ds:
                d = max(ds, key=lambda d: os.path.getmtime(os.path.join(base, d)))
                act[(p["cid"], d)] = {"started": t0, "frm": None, "until": p.get("until"), "age": r["age"], "pid": r.get("pid")}
    sent = tgmap(); out = []
    for c in _pages():
        done = {d["job"]: d for d in (jload(os.path.join(ROOT, "channels", c, "done.json"), []) or [])}
        base = os.path.join(OUT, c)
        if not os.path.isdir(base):
            continue
        for j in os.listdir(base):
            if not os.path.isdir(os.path.join(base, j)):
                continue
            s = job_state(c, j, act.get((c, j)))
            d = done.get(j)
            st = (d or {}).get("status")
            if s["active"]:
                status = "building"
            elif s.get("stage") == "cancelled" and not st:     # 19 Nov: stopped by the owner from the Run tab
                status = "cancelled"
            elif st in ("posted",):
                status = "posted"
            elif st in ("approved",):
                status = "approved"
            elif st in ("rejected",):
                status = "rejected"
            elif st in ("removed",):          # 18 Nov: was missing, so a removed video with a failed review showed as held
                status = "removed"
            elif st == "held" or s["review"]["ok"] is False:
                status = "held"
            elif s["review"]["ok"] and (c, j) in sent:
                status = "waiting"
            elif s["review"]["ok"]:
                status = "ready"
            elif s["prepped"]:
                status = "prepped"
            elif s["pct"] < 1:
                status = "paused"
            else:
                status = "made"
            s["status"] = status; s["posted"] = (d or {}).get("posted"); s["held_why"] = (d or {}).get("review")
            if status == "held":      # 18 Nov: the healer (engine/healer.py) owns held videos; show its real step
                hit = ((jload(os.path.join(OUT, "healer.json"), {}) or {}).get("items") or {}).get(f"held:{c}:{j}") or {}
                last = (hit.get("steps") or [{}])[-1]
                s["held_state"] = "waiting" if hit.get("state") == "parked" else "retrying"
                s["healer"] = {"state": hit.get("state") or ("working" if hit else "queued"), "step": last.get("step"),
                               "result": last.get("result"), "why": hit.get("why")}
            out.append(s)
    out.sort(key=lambda x: (not x["active"], -x["updated"]))
    return out


# ---------------- schedule ----------------
NICE = {"studio-inbox": "Read Telegram replies", "studio-prep": "Prep lane (script, voice, visuals)", "studio-make": "Render lane",
        "studio-scout": "Scout trends + tech news", "studio-stats": "Morning stats report", "studio-post": "Post approved videos",
        "studio-doctor": "Doctor (self-repair)", "studio-learn": "Learn from GitHub (weekly)",
        "studio-selfcheck": "Self-check and self-fix", "studio-radar": "Tools radar (daily)",
        "studio-trends": "Trending topics scout (daily)", "studio-hooks": "Hook study of top Shorts (weekly)",
        "studio-weekly": "Weekly report (Sunday)", "studio-comments": "Pinned question + comment replies", "studio-mehul": "Mehul agent (acts for the owner)", "studio-stories": "Daily Stories (IG + FB)",
        "studio-healer": "Healer (fixes held videos + unknown errors)", "studio-omnimap": "Model map (tests every free model, daily)",
        "studio-dm": "Comment-to-DM (every 10 min)", "studio-domainwatch": "scrollhouse.in watcher (hourly)",
        "studio-learn-deep": "Deep repo reader (3 a day)", "studio-janitor": "Janitor (cleanup, daily)",
        "studio-rivals": "Competitors + brands (daily)", "studio-money": "Money milestones (daily)",
        "studio-site": "scrollhouse.in site rebuild (daily)", "studio-lessons": "Lessons agent (rule book from mistakes, daily)"}


def schedule():
    try:
        ts = json.loads(run(["systemctl", "list-timers", "--all", "-o", "json", "studio*"]) or "[]")
    except Exception:
        ts = []
    now = time.time(); out = []
    for t in ts:
        u = t["unit"].replace(".timer", "")
        nxt = t.get("next") or 0; last = t.get("last") or 0
        state = run(["systemctl", "is-active", u + ".service"]).strip()
        out.append({"unit": u, "name": NICE.get(u, u), "next": int(nxt / 1e6) if nxt else None, "in": int(nxt / 1e6 - now) if nxt else None,
                    "last": int(last / 1e6) if last else None, "running": state in ("active", "activating")})
    out.sort(key=lambda x: x["in"] if x["in"] is not None else 1e12)
    return out


def failed_units():
    try:
        us = json.loads(run(["systemctl", "list-units", "--all", "--failed", "-o", "json", "studio*"]) or "[]")
    except Exception:
        us = []
    out = []
    for u in us:
        last = run(["journalctl", "-u", u["unit"], "-n", "3", "--no-pager", "-o", "cat"]).strip().splitlines()
        out.append({"unit": u["unit"], "desc": u.get("description", "")[:120], "last": (last[-1] if last else "")[:220]})
    return out


# ---------------- channels (Meta numbers cached 30 min) ----------------
META_DISK = os.path.join(OUT, "dash-meta-cache.json")
_cache = jload(META_DISK, {}) or {"t": 0, "pages": {}}     # 18 Nov: survives a dashboard restart (no burst on restart)
META_TTL = 1800      # 18 Nov: selfcheck 'fixed' this to 0 at 07:49 -> 2 Meta calls per page refresh (every 5 s) -> the
                     # whole Meta app hit '(#4) Application request limit reached' (167%) and posting/DMs/stats were refused.
                     # Never lower this below 600; follower counts change slowly.


def meta_pages():
    if time.time() - _cache.get("t", 0) < max(600, META_TTL) and _cache.get("pages"):
        return _cache["pages"]
    if time.time() < _cache.get("busy_until", 0):          # Meta refused us: back off 15 min, even with nothing cached
        return _cache.get("pages") or {}
    try:
        ut = open(os.path.join(HOME, ".studio-meta-user.token")).read().strip()
        d = json.load(urllib.request.urlopen(f"{G}/me/accounts?fields=name,id,followers_count,fan_count,instagram_business_account{{id,username,followers_count,media_count}}&limit=50&access_token={ut}", timeout=30))
        pages = {}
        for p in d.get("data", []):
            ig = p.get("instagram_business_account") or {}
            pages[ig.get("username") or p["id"]] = {"fb": p.get("followers_count", p.get("fan_count", 0)) or 0, "ig": ig.get("followers_count", 0) or 0,
                                                   "posts": ig.get("media_count", 0) or 0, "page": p["id"], "name": p["name"], "igid": ig.get("id")}
        dbg = json.load(urllib.request.urlopen(f"{G}/debug_token?input_token={ut}&access_token={ut}", timeout=30))["data"]
        pages["_token_days"] = round((dbg.get("data_access_expires_at", 0) - time.time()) / 86400)
        _cache.update(t=time.time(), pages=pages, err=None)
        jsave(META_DISK, _cache)
        h = jload(FOLLOW_HIST, {}) or {}
        day = time.strftime("%Y-%m-%d")
        h[day] = {k: v["ig"] + v["fb"] for k, v in pages.items() if isinstance(v, dict)}
        jsave(FOLLOW_HIST, dict(sorted(h.items())[-90:]))
    except Exception as e:
        body = ""
        try:
            body = e.read().decode()[:200] if hasattr(e, "read") else ""
        except Exception:
            pass
        _cache["err"] = (str(e) + " " + body)[:300]
        _cache["busy_until"] = time.time() + 900            # do not retry on every 5 s refresh while Meta is limiting us
        jsave(META_DISK, _cache)
    return _cache["pages"]


_vj = {"t": 0}


def vajra_sync():
    """VAJRA's queue lives in a GitHub repo that its own jobs push to; keep the server copy fresh (every 10 min)."""
    if time.time() - _vj["t"] < 600:
        return
    _vj["t"] = time.time()
    threading.Thread(target=lambda: subprocess.run(["git", "-C", os.path.join(HOME, "vajra-automation"), "pull", "-q", "--ff-only"],
                                                   capture_output=True, timeout=60), daemon=True).start()


def channels(jl):
    pages = meta_pages(); hist = jload(FOLLOW_HIST, {}) or {}
    days = sorted(hist)[-30:]
    out = []
    for c in CHANNELS:
        p = pages.get(c["ig"], {})
        cfg = jload(os.path.join(ROOT, "channels", c["id"], "channel.json"), {}) or {}
        acc = jload(os.path.join(HOME, ".studio-accounts", c["id"] + ".json"), {}) or {}
        mine = [j for j in jl if j["cid"] == c["id"]]
        cnt = {}
        for j in mine:
            cnt[j["status"]] = cnt.get(j["status"], 0) + 1
        w = cfg.get("warmup") or {}
        day = time.strftime("%Y-%m-%d")
        if c["group"] == "Studio":
            if cfg.get("post") is False:
                status, note = "off", "Posting off"
            elif w.get("post_from") and day < w["post_from"]:
                status, note = "warm", f"Warm-up · first post {w['post_from'][8:]} Nov"
            else:
                status, note = "live", "Live"
            yt_ok = bool(acc.get("yt"))
        elif c["id"] == "vajra":
            vajra_sync()
            q = jload(os.path.join(HOME, "vajra-automation", "social", "queue.json"), {}) or {}
            posts = q.get("posts", [])
            pend = [x for x in posts if not x.get("posted")]
            cnt = {"queued": len(pend), "on_hold": len(q.get("hold", []))}
            status, note, yt_ok = "live", "Live · 1 reel a day 19:30 (GitHub)", True
        else:
            status, note, yt_ok = "manual", "Manual · not automated", None
        spark = [hist[d].get(c["ig"], None) for d in days]
        out.append({**c, "igid": p.get("igid"), "fb": p.get("fb", 0), "igF": p.get("ig", 0), "posts": p.get("posts", 0), "status": status, "note": note,
                    "counts": cnt, "yt_ok": yt_ok, "spark": spark,
                    "fb_url": f"https://facebook.com/{p.get('page') or c['page']}" if (p.get("page") or c["page"]) else None})
    return out, pages.get("_token_days")


# ---------------- activity log ----------------
BAD = re.compile(r"\b(traceback|error|errno|fail|failed|exception|cancelled|hold:|problems)\b", re.I)


def classify(line):
    l = line.lower()
    if l.startswith("ideas ") or l.startswith("plan "):
        return "info"
    if " hold" in l and "review " in l:                       # a held video is something to watch, not an error
        return "warn"
    if BAD.search(line):
        return "bad"
    if any(k in l for k in ("warn", "retry", "limited", "skip", "not sent", "fallback", "warm-up", "nothing approved", "to fix", "still failing", "voice gate")):
        return "warn"
    if any(k in l for k in ("published", "posted", "approved", "sent for approval", "passed", "rendered in", "ok ", "prepped", "cover made", "matched")):
        return "ok"
    if any(k in l for k in ("job ", "daily: run", "lane", "plan", "tts", "render")):
        return "run"
    return "info"


_jc = {"t": 0, "m": []}


def job_channel(msg):
    """Log lines that only name a job (preflight 1117-0145 ...) get that job's page."""
    if time.time() - _jc["t"] > 60:
        m = []
        for c in _pages():
            base = os.path.join(OUT, c)
            if os.path.isdir(base):
                m += [(j, c) for j in os.listdir(base)]
        _jc.update(t=time.time(), m=sorted(m, key=lambda x: -len(x[0])))
    for j, c in _jc["m"]:
        if re.search(rf"(?<![\w-]){re.escape(j)}(?![\w-])", msg):
            return c
    return None


def activity(n=160):
    out = []
    for line in tail_lines(LOG, n):
        m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (.*)", line)
        if not m:
            continue
        msg = m.group(2)
        cid = next((c["id"] for c in CHANNELS if re.search(rf"\b{c['id']}\b", msg)), None) or job_channel(msg)
        out.append({"t": m.group(1), "msg": msg[:260], "lvl": classify(msg), "cid": cid})
    return out[::-1]


def friendly(p):
    l = p.lower()
    for k, t in (("of the script was found", "Voice did not match the script"), ("visual score", "Low visual score"),
                 ("spoken instructions", "Instructions spoken at the start"), ("starts late", "Something spoken before the script"),
                 ("does not start with the first line", "English voice did not start with the script"),
                 ("loudness", "Loudness or peak out of range"), ("true peak", "Loudness or peak out of range"), ("blank frame", "Blank stretch in the picture"),
                 ("end card", "Missing end card"), ("headline", "Missing headline"), ("caption", "Caption problem (overlap, faint, stuck)"),
                 ("overlap", "Text overlapping"), ("cut", "Text cut off"), ("faint", "Text too faint to read"), ("empty", "Empty scene"),
                 ("language", "Wrong language on screen"), ("fit", "Picture does not fit the voice")):
        if k in l:
            return t
    return re.sub(r"^visual:\s*", "", p)[:60]


def quality(days=7):
    """First-pass rate per day: of the videos whose FIRST final review happened that day, how many passed it.
    Also: reviews per video, holds caught before render (no render time spent), top hold reasons."""
    first, reviews, pre_held, reasons = {}, {}, {}, {}
    rx = re.compile(r"^(\d{4}-\d\d-\d\d) [\d:]+ review (\w+) (\S+) (PASS|HOLD)(?::\s*(.*))?")
    try:
        with open(LOG, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "held BEFORE render" in line:
                    pre_held[line[:10]] = pre_held.get(line[:10], 0) + 1
                    continue
                m = rx.match(line)
                if not m:
                    continue
                day, cid, job, res, why = m.groups()
                k = (cid, job)
                reviews[k] = reviews.get(k, 0) + 1
                if k not in first:
                    first[k] = (day, res == "PASS")
                if res == "HOLD" and why:
                    for key in {friendly(p) for p in why.split(" | ")[:4]}:
                        reasons[key] = reasons.get(key, 0) + 1
    except Exception:
        pass
    out = []
    for i in range(days - 1, -1, -1):
        day = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
        vs = [ok for (d, ok) in first.values() if d == day]
        out.append({"day": day, "videos": len(vs), "passed": sum(vs), "rate": round(100 * sum(vs) / len(vs)) if vs else None,
                    "pre_held": pre_held.get(day, 0)})
    allv = [ok for (d, ok) in first.values() if d >= out[0]["day"]]
    return {"days": out, "rate7": round(100 * sum(allv) / len(allv)) if allv else None, "videos7": len(allv), "passed7": sum(allv),
            "avg_reviews": round(sum(reviews.values()) / max(1, len(reviews)), 1),
            "reasons": sorted(reasons.items(), key=lambda x: -x[1])[:6]}


def budgets():
    b = (jload(os.path.join(OUT, "budget.json"), {}) or {}).get(time.strftime("%Y-%m-%d"), {})
    return [{"name": "Voice (Gemini TTS)", "used": b.get("tts", 0), "cap": TTS_CAP},
            {"name": "New videos today", "used": b.get("reels", 0), "cap": REELS_CAP}]


# ---------------- issues ----------------
def issues(srv, fails, jl, sched, token_days, chs):
    out = []

    def add(lvl, title, detail="", fix="", action=None, key=None):
        out.append({"lvl": lvl, "title": title, "detail": detail, "fix": fix, "action": action, "key": key or title})
    for f in fails:
        add("bad", f"Job failed: {f['unit']}", f["last"] or f["desc"], "Clear it once the cause is fixed.", "reset-failed")
    if srv["disk_pct"] >= 93:
        add("bad", f"Disk almost full ({srv['disk_pct']}%)", f"{srv['disk_free_gb']} GB free", "Old job folders and caches can be deleted.")
    elif srv["disk_pct"] >= 85:
        add("warn", f"Disk {srv['disk_pct']}% full", f"{srv['disk_free_gb']} GB free of {srv['disk_total_gb']} GB", "The doctor cleans caches and old render files automatically.")
    if srv["mem_total_gb"] - srv["mem_used_gb"] < 1:
        add("warn", "Low memory", f"{srv['mem_used_gb']} of {srv['mem_total_gb']} GB used")
    # 17 Nov: 100% CPU is fine when it is niced Studio work using spare cores. Warn only when NORMAL-priority work
    # (job bot, Muse browser, dashboard) is itself near the limit for a full minute.
    if srv["cpu_norm"] >= 85:
        add("warn", "Server busy with priority work", f"job bot and other normal-priority work use {srv['cpu_norm']:.0f}% of the CPU; Studio waits")
    for name, ok in srv["muse"].items():
        if not ok:
            add("warn", f"Muse {name} is down", "images fall back to Cloudflare / Pollinations", "Restart the Muse browser.")
    for j in jl:
        if j["active"] and time.time() - max([s["t"] for s in j["steps"]] + [j["started"] or 0]) > 2700:
            add("bad", f"Looks stuck: {j['job']}", "no progress for 45+ minutes")
    held = [j for j in jl if j["status"] == "held"]
    if held:
        wait = [j for j in held if j.get("held_state") == "waiting"]
        add("info", f"{len(held)} video{'s' if len(held) > 1 else ''} held by the reviewer",
            "; ".join(f"{j['title'][:40]} ({len(j['review']['problems']) or 'see Runs'})" if False else j["title"][:44] for j in held[:5]),
            f"Nothing for you. {len(held) - len(wait)} being rebuilt by the server" + (f", {len(wait)} wait for the next code fix." if wait else "."), None, "held-group")
    for s in sched:
        if s["in"] is None and not s["running"]:
            add("warn", f"Timer not scheduled: {s['unit']}")
    if token_days is not None and token_days < 21:
        add("warn" if token_days > 7 else "bad", f"Meta login access ends in {token_days} days", "", "Log in to Meta Business Suite once.")
    for c in chs:
        if c["group"] == "Studio" and c["yt"] and not c["yt_ok"]:
            add("info", f"YouTube not connected: {c['name']}", "Shorts are not uploaded yet", "One-time 5-minute login.", None, f"yt-{c['id']}")
    errs = [a for a in activity(300) if a["lvl"] == "bad" and time.time() - time.mktime(time.strptime(a["t"], "%Y-%m-%d %H:%M:%S")) < 7200]
    seen = set()
    for e in errs:
        k = re.sub(r"\d+", "#", e["msg"])[:60]
        if k in seen or "HOLD" in e["msg"] or "PROBLEMS" in e["msg"] or "retry" in e["msg"] or "held BEFORE" in e["msg"] or "doctor:" in e["msg"] \
                or "healer:" in e["msg"] or "omnimap:" in e["msg"] \
                or "gemini text fail" in e["msg"] or "vision fail" in e["msg"] or "alignment failed" in e["msg"] \
                or " ig skip " in e["msg"] or "omniroute image fail" in e["msg"] \
                or "clip failed -> still image" in e["msg"] or "web search fail" in e["msg"] \
                or e["msg"].startswith("preflight ") \
                or re.search(r"gemini[\w -]* fail.*(429|503|Too Many Requests|Service Unavailable|timed out)", e["msg"]):      # recovered by a fallback
            continue
        seen.add(k); add("warn", "Error in the last 2 h", e["msg"][:240], "", None, "log-" + k)
        if len(seen) >= 4:
            break
    dst = jload(os.path.join(OUT, "doctor-state.json"), {}) or {}
    if not dst.get("last") or time.time() - dst["last"] > 1800:
        add("warn", "Doctor has not run for 30+ min", "the self-repair agent (studio-doctor timer) is not running")
    uniq_ = {}
    for u in (jload(os.path.join(OUT, "doctor-unknown.json"), []) or [])[-30:]:      # one line per problem, the newest text
        uniq_[u["what"]] = u
    hs = jload(os.path.join(OUT, "healer.json"), {}) or {}
    hitems = hs.get("items") or {}
    if hs.get("log") and time.time() - os.path.getmtime(os.path.join(OUT, "healer.json")) > 2700:
        add("warn", "Healer has not run for 45+ min", "the agent that fixes held videos and unknown errors (studio-healer timer) is not running")
    for k, it in list(hitems.items())[-200:]:          # 18 Nov: only what the healer is still working on (not quota noise)
        if k.startswith("unk:") and it.get("state") in ("open", "parked"):
            add("info", f"Healer {'working on' if it['state'] == 'open' else 'parked'}: " + it.get("what", "")[:80],
                (it.get("why") or it.get("detail") or "")[:200], key="heal-" + k)
    sc = jload(os.path.join(OUT, "selfcheck.json"), {}) or {}
    if not sc.get("last") or time.time() - sc["last"] > 5400:
        add("warn", "Self-check has not run for 90+ min", "the agent that tests and fixes the studio's own code is not running")
    for fnd in (sc.get("findings") or [])[:3]:
        add("info", "Self-check found: " + fnd["kind"] + " " + fnd.get("where", ""), fnd["msg"], "It tries to fix this itself; otherwise it is noted for the next fix session.", None, "sc-" + fnd["kind"] + fnd.get("where", ""))
    rank = {"bad": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda x: rank[x["lvl"]])


def now_sentence(running, jl):
    act = [j for j in jl if j["active"]]
    if act:
        parts = []
        for j in act:
            cur = next((s["label"] for s in j["steps"] if s.get("active")), "Finishing")
            nm = next(c["name"] for c in CHANNELS if c["id"] == j["cid"])
            parts.append(f"Making a {nm}{' English' if j['lang'] == 'en' else ''} video, now at the {cur.lower()} step")
        return " · ".join(parts)
    other = [r for r in running if r.get("kind") and r["kind"] not in ("Scheduler", "Making video")]
    return other[0]["kind"] if other else "Idle · waiting for the next timer"


def state():
    procs = processes(); running = []
    for p in procs:
        j = parse_job(p["args"]); kind = next((k for s, k in KINDS if j["script"] == s), None)
        if kind is None and "hyperframes" in p["line"]:
            kind = "Render (Chrome)"
        if kind:
            running.append({"pid": p["pid"], "kind": kind, "age": p["age"], "job": j, "cmd": p["line"][-160:]})
    srv = server(); jl = jobs(running); sched = schedule(); fails = failed_units()
    chs, token_days = channels(jl)
    iss = issues(srv, fails, jl, sched, token_days, chs)
    st = {"auto_approve": False, "min_score": 9, **(jload(SETTINGS, {}) or {})}
    out = {"now": int(time.time()), "doing": now_sentence(running, jl), "server": srv, "running": running, "jobs": jl[:40],
            "schedule": sched, "issues": iss, "channels": chs, "budgets": budgets(), "activity": activity(), "settings": st,
            "token_days": token_days, "render_median": render_median(), "quality": quality(), "offers": offers_list()}
    out["needs"] = extra.needs_you(out)
    _last.update(t=time.time(), s=out)
    return out


_last = {"t": 0, "s": None}


def offers_list():
    """19 Nov: offer reels (engine/offers.py registry, counts kept by engine/dm.py), newest first."""
    out = []
    for cid, kws in (jload(os.path.join(OUT, "offers.json"), {}) or {}).items():
        for kw, o in (kws or {}).items():
            out.append({"cid": cid, "kw": kw, "gift": o.get("gift", ""), "url": o.get("url"), "job": o.get("job", ""),
                        "made": o.get("made", ""), "stats": o.get("stats") or {}})
    return sorted(out, key=lambda x: x["made"], reverse=True)[:40]


def state_cache():
    return _last["s"] if _last["s"] and time.time() - _last["t"] < 20 else state()


# ---------------- brain graph ----------------
def brain():
    nodes, links = [{"id": "brain", "label": "Shared brain", "kind": "core"}], []
    shared = open(os.path.join(ROOT, "knowledge", "lessons.md"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "knowledge", "lessons.md")) else ""
    for i, l in enumerate([x[2:].strip() for x in shared.splitlines() if x.startswith("- ")][:24]):
        nodes.append({"id": f"s{i}", "label": l[:140], "kind": "lesson", "cid": None}); links.append({"s": "brain", "t": f"s{i}"})
    # 19 Nov: the rules distilled from every page's mistakes (engine/lessons.py), shown as their own hub
    lr = os.path.join(ROOT, "knowledge", "lessons-learnt.md")
    if os.path.exists(lr):
        rules = [x[2:].strip() for x in open(lr, encoding="utf-8").read().splitlines() if x.startswith("- ")]
        if rules:
            nodes.append({"id": "learnt", "label": "Rules learnt from mistakes", "kind": "hub", "color": "#dc2626"})
            links.append({"s": "brain", "t": "learnt"})
            for i, l in enumerate(rules[:40]):
                nodes.append({"id": f"lr{i}", "label": l[:160], "kind": "lesson", "cid": None}); links.append({"s": "learnt", "t": f"lr{i}"})
    for c in [c for c in CHANNELS if c.get("group") == "Studio"]:     # 19 Nov: was CHANNELS[:3] (new pages missing)
        nodes.append({"id": c["id"], "label": c["name"], "kind": "page", "color": c["color"]}); links.append({"s": "brain", "t": c["id"]})
        for fn, kind in (("lessons.md", "lesson"), ("lessons-auto.md", "auto")):
            p = os.path.join(ROOT, "channels", c["id"], fn)
            if not os.path.exists(p):
                continue
            ls = [x[2:].strip() for x in open(p, encoding="utf-8").read().splitlines() if x.startswith("- ")]
            seen_, uniq = set(), []
            for x in reversed(ls):                       # newest first, no repeats
                k_ = re.sub(r"\W+", " ", x.lower())[:50]
                if k_ not in seen_:
                    seen_.add(k_); uniq.append(x)
            for i, l in enumerate(uniq[:10][::-1]):
                nid = f"{c['id']}-{kind}{i}"            # was fn[:4]: 'lessons.md' and 'lessons-auto.md' both gave "less" -> same id, loose nodes
                nodes.append({"id": nid, "label": l[:140], "kind": kind, "cid": c["id"], "color": c["color"]}); links.append({"s": c["id"], "t": nid})
        for d in (jload(os.path.join(ROOT, "channels", c["id"], "done.json"), []) or [])[-10:]:
            nid = f"v-{c['id']}-{d['job']}"
            nodes.append({"id": nid, "label": d.get("title") or d["job"], "kind": "video", "cid": c["id"], "status": d.get("status"), "color": c["color"]})
            links.append({"s": c["id"], "t": nid})
    try:
        sys.path.insert(0, os.path.join(ROOT, "engine"))
        import brain as brainmod
        got = [i for i in brainmod.items() if i.get("on", True)][-60:]
        if got:
            nodes.append({"id": "learn", "label": "Learned from repos", "kind": "hub", "color": "#0d9488"}); links.append({"s": "brain", "t": "learn"})
            for i in got:
                nodes.append({"id": "b" + i["id"], "label": f"{i['title']}: {i['text']}"[:160], "kind": "learned", "build": i.get("kind") == "build", "color": "#0d9488"})
                links.append({"s": "learn", "t": "b" + i["id"]})
    except Exception:
        pass
    return {"nodes": nodes, "links": links}


# ---------------- actions ----------------
def decide(cid, job, action, note=""):
    sys.path.insert(0, os.path.join(ROOT, "engine"))
    import inbox
    if action == "approve":
        inbox.set_status(cid, job, "approved"); inbox.telegram(f"✅ {cid} {job} approved (dashboard)")
    elif action == "reject":
        inbox.set_status(cid, job, "rejected"); inbox.telegram(f"❌ {cid} {job} rejected (dashboard)")
    elif action == "remove":      # 18 Nov (owner): take an approved video out of the queue; never posted, files kept
        inbox.set_status(cid, job, "removed"); inbox.telegram(f"🗑 {cid} {job} removed from the queue (dashboard)")
    elif action == "fix":
        inbox.set_status(cid, job, "fix", note); inbox.add_lesson(cid, note, job); inbox.telegram(f"✍️ {cid} {job} feedback (dashboard): {note[:200]}")
    else:
        raise ValueError("unknown action")
    return {"ok": True}


def make_now(cid, topic=""):
    if cid not in _pages():
        raise ValueError("unknown channel")
    unit = f"studio-job-dash-{int(time.time())}"
    ch = jload(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}
    if ch.get("kind") == "clips":                  # 19 Nov: CutCapsule: a video link -> the best moments as finished clips
        m = re.search(r"https?://\S+", topic or "")
        if not m:
            raise ValueError("paste a YouTube link for a clip page")
        tail = [m.group(0)] + (["--n", re.search(r"\b(\d{1,2})\s*clips?\b", topic).group(1)] if re.search(r"\b(\d{1,2})\s*clips?\b", topic) else [])
        engine = [PY, os.path.join(ROOT, "engine", "clipper.py"), cid] + tail
    else:
        engine = [PY, os.path.join(ROOT, "engine", "make.py"), cid] + ([topic[:600], "--request"] if topic else [])   # 19 Nov: researched + named, not copied
    cmd = ["sudo", "systemd-run", f"--unit={unit}", "--uid=ubuntu", "-p", "CPUWeight=20", "-p", "MemoryHigh=2600M", "-p", "MemoryMax=3400M", "-p", "Nice=15", f"--working-directory={ROOT}", f"-E", f"HOME={HOME}"] + engine
    subprocess.run(cmd, capture_output=True, timeout=20)
    return {"ok": True, "unit": unit}


def _stop_pid(pid):
    """Stop the build process: its own systemd unit when it has one (dashboard / manual / healer jobs), else the process
    tree. Never the dashboard itself."""
    unit = None
    try:
        m = re.search(r"/((studio|run)-[\w.@-]+\.service)", open(f"/proc/{int(pid)}/cgroup").read())
        unit = m.group(1) if m else None
    except Exception:
        pass
    if unit and unit.startswith("studio-dash"):
        unit = None
    if unit:
        subprocess.run(["sudo", "systemctl", "stop", "--no-block", unit], capture_output=True, timeout=20)
    else:
        subprocess.run(["sudo", "pkill", "-TERM", "-P", str(int(pid))], capture_output=True, timeout=20)
        subprocess.run(["sudo", "kill", "-TERM", str(int(pid))], capture_output=True, timeout=20)
    return unit or f"pid {pid}"


def change_job(cid, job, action, to="", topic=""):
    """19 Nov (owner: "requested LLP vs Pvt Ltd but selected the wrong page... give option to do changes in run tab").
    action "stop": stop the build and mark it cancelled (the healer then leaves it alone).
    action "redo": stop it if it is building, then make the topic (edited or the same) again on page `to`."""
    if cid not in _pages() or not re.fullmatch(r"[A-Za-z0-9_-]+", job or "") or not os.path.isdir(os.path.join(OUT, cid, job)):
        raise ValueError("unknown run")
    if action not in ("stop", "redo"):
        raise ValueError("unknown action")
    to = to or cid
    if action == "redo" and to not in _pages():
        raise ValueError("unknown page")
    jd = os.path.join(OUT, cid, job)
    meta = jload(os.path.join(jd, "meta.json"), {}) or {}
    plan = jload(os.path.join(jd, "plan.json"), {}) or {}
    topic = (topic or meta.get("request") or meta.get("topic") or plan.get("topic") or "").strip()
    cur = next((j for j in state().get("jobs", []) if j["cid"] == cid and j["job"] == job), None)   # fresh: the right pid
    stopped = None
    if cur and cur.get("active") and cur.get("pid"):
        stopped = _stop_pid(cur["pid"])
    done = {d["job"]: d for d in (jload(os.path.join(ROOT, "channels", cid, "done.json"), []) or [])}
    if job not in done:                    # a finished / posted video keeps its status; only an unfinished one is cancelled
        meta.update(stage="cancelled", cancelled_at=time.strftime("%Y-%m-%d %H:%M"),
                    cancelled_why=f"owner: remade on {to}" if action == "redo" else "owner stopped it")
        jsave(os.path.join(jd, "meta.json"), meta)
    out = {"ok": True, "stopped": stopped, "cancelled": job not in done}
    if action == "redo":
        if not topic:
            raise ValueError("no topic to remake")
        out["started"] = make_now(to, topic)["unit"]; out["page"] = to; out["topic"] = topic[:160]
    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path).path
        try:
            if u == "/api/state":
                return self.send(200, state())
            if u == "/api/brain":
                return self.send(200, brain())
            qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if u == "/api/job":
                return self.send(200, extra.job_detail(sys.modules[__name__], qs["cid"], qs["job"]))
            if u == "/api/posts":
                c = next((x for x in state_cache()["channels"] if x["id"] == qs.get("cid")), None)
                return self.send(200, extra.posts(c["igid"]) if c and c.get("igid") else [])
            if u == "/api/learned":
                sys.path.insert(0, os.path.join(ROOT, "engine"))
                import brain as brainmod
                bq = open(os.path.join(ROOT, "knowledge", "build-queue.md"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "knowledge", "build-queue.md")) else ""
                top = sorted([i for i in brainmod.items() if i.get("uses")], key=lambda i: -(i.get("wins", 0) / max(1, i["uses"])))[:8]
                return self.send(200, {"stats": brainmod.stats(), "learned": (jload(os.path.join(ROOT, "knowledge", "learned.json"), []) or [])[::-1][:40],
                                       "build_open": bq.count("- [ ]"), "build_done": bq.count("- [x]"),
                                       "top": [{"title": i["title"], "uses": i["uses"], "wins": i.get("wins", 0)} for i in top]})
            if u == "/api/radar":
                return self.send(200, (jload(os.path.join(ROOT, "knowledge", "radar.json"), []) or [])[::-1][:30])
            if u == "/api/ideas":
                h = jload(os.path.join(ROOT, "channels", qs.get("cid", "x").replace("/", ""), "ideas.json"), []) or []
                return self.send(200, h[-1] if h else {})
            if u == "/api/sources":
                try:
                    return self.send(200, extra.sources(state_cache()))
                except Exception as e:
                    return self.send(500, {"error": str(e)})
            if u == "/api/brief":
                return self.send(200, extra.brief(state_cache(), qs.get("force") == "1"))
            if u.startswith("/dp/"):                           # 19 Nov: page profile pictures (engine/brand.py writes them)
                n = u[4:].replace(".jpg", "")
                p = os.path.join(OUT, "dp", n + ".jpg")
                if not re.fullmatch(r"[a-z0-9_-]+", n) or not os.path.isfile(p):
                    return self.send(404, {"error": "no picture"})
                return self.file(p)
            if u.startswith("/media/"):
                parts = u.split("/")[2:]
                if len(parts) != 3 or any(p in ("", ".", "..") or "/" in p for p in parts):
                    return self.send(404, {"error": "bad path"})
                if parts[2] == "cover-s.jpg":                      # 360 px thumbnail, made once and cached next to the cover
                    big, small = os.path.join(OUT, parts[0], parts[1], "cover.jpg"), os.path.join(OUT, parts[0], parts[1], "cover-s.jpg")
                    if os.path.exists(big) and (not os.path.exists(small) or os.path.getmtime(small) < os.path.getmtime(big)):
                        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", big, "-vf", "scale=360:-2", "-q:v", "5", small], timeout=30)
                p = os.path.realpath(os.path.join(OUT, *parts))
                if not p.startswith(os.path.realpath(OUT) + os.sep) or not os.path.isfile(p):
                    return self.send(404, {"error": "not found"})
                return self.file(p)
            f = "index.html" if u in ("/", "") else u.lstrip("/")
            p = os.path.realpath(os.path.join(APP, f))
            if p.startswith(APP + os.sep) and os.path.isfile(p) and not p.endswith(".py"):
                return self.file(p)
            return self.send(404, {"error": "not found"})
        except Exception as e:
            log_exc(u)
            return self.send(500, {"error": str(e)[:300]})

    def file(self, p):
        ext = p.rsplit(".", 1)[-1].lower()
        ct = {"html": "text/html; charset=utf-8", "js": "text/javascript", "css": "text/css", "jpg": "image/jpeg", "png": "image/png",
              "mp4": "video/mp4", "svg": "image/svg+xml", "json": "application/json", "webmanifest": "application/manifest+json"}.get(ext, "application/octet-stream")
        size = os.path.getsize(p); rng = self.headers.get("Range")
        if rng and ext == "mp4":
            a, _, b = rng.replace("bytes=", "").partition("-")
            a = int(a or 0); b = min(int(b) if b else a + 2_000_000, size - 1)
            with open(p, "rb") as f:
                f.seek(a); data = f.read(b - a + 1)
            self.send_response(206); self.send_header("Content-Type", ct); self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {a}-{b}/{size}"); self.send_header("Content-Length", str(len(data))); self.end_headers()
            self.wfile.write(data); return
        with open(p, "rb") as f:
            data = f.read()
        self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(size))
        if ext == "mp4":
            self.send_header("Accept-Ranges", "bytes")
        # 19 Nov: profile pictures were re-asked on every 4 s redraw (no-cache); they change at most daily
        self.send_header("Cache-Control", "max-age=3600" if os.sep + "dp" + os.sep in p else "no-cache"); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path).path
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}") if n < 100000 else {}
            if u == "/api/decide":
                return self.send(200, decide(body["cid"], body["job"], body["action"], body.get("note", "")[:1000]))
            if u == "/api/make":
                return self.send(200, make_now(body["cid"], body.get("topic", "")))
            if u == "/api/change":
                return self.send(200, change_job(body["cid"], body["job"], body.get("action", ""), body.get("to", ""),
                                                 str(body.get("topic", ""))[:300]))
            if u == "/api/settings":
                st = {"auto_approve": False, "min_score": 9, **(jload(SETTINGS, {}) or {})}
                if "auto_approve" in body:
                    st["auto_approve"] = bool(body["auto_approve"])
                if "min_score" in body:
                    st["min_score"] = max(7, min(10, int(body["min_score"])))
                jsave(SETTINGS, st); return self.send(200, st)
            if u == "/api/ask":
                return self.send(200, extra.ask(state_cache(), body.get("q", "")))
            if u == "/api/task":
                return self.send(200, extra.set_task(body["id"], body.get("done", True)))
            if u == "/api/test":
                return self.send(200, extra.test_source(body.get("name", "")))
            if u == "/api/reset-failed":
                subprocess.run(["sudo", "systemctl", "reset-failed", "studio-*"], capture_output=True, timeout=20)
                return self.send(200, {"ok": True})
            return self.send(404, {"error": "not found"})
        except Exception as e:
            log_exc(u)
            return self.send(400, {"error": str(e)[:300]})


if __name__ == "__main__":
    threading.Thread(target=sampler, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "4788"))), H).serve_forever()
