"""Dashboard extras: job detail, channel posts, connected sources, 'needs you', morning brief and the Ask box.
Read-only except where api.py's POST routes say otherwise. All AI calls use the engine's free Gemini key path."""
import json, os, re, subprocess, sys, time, urllib.request

HOME = os.path.expanduser("~")
ROOT = os.path.join(HOME, "studio")
OUT = os.path.join(HOME, "studio-out")
LOG = os.path.join(OUT, "engine.log")
G = "https://graph.facebook.com/v23.0"
BRIEF = os.path.join(OUT, "dash-brief.json")
TASKS = os.path.join(OUT, "owner-tasks.json")
_c = {}


def cached(key, ttl, fn):
    v = _c.get(key)
    if v and time.time() - v[0] < ttl:
        return v[1]
    try:
        r = fn()
    except Exception as e:
        r = {"error": str(e)[:200]}
    _c[key] = (time.time(), r)
    return r


def jload(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def grep_log(pattern, n=4000):
    try:
        with open(LOG, "rb") as f:
            f.seek(0, 2); s = f.tell(); f.seek(max(0, s - 400 * n))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except Exception:
        return []
    rx = re.compile(pattern)
    return [l for l in lines if rx.search(l)]


def ts(line):
    try:
        return int(time.mktime(time.strptime(line[:19], "%Y-%m-%d %H:%M:%S")))
    except Exception:
        return None


# ---------------- one job, in detail ----------------
def job_detail(api, cid, job):
    st = next((j for j in api.state_cache().get("jobs", []) if j["cid"] == cid and j["job"] == job), None)
    if not st:
        st = api.job_state(cid, job)
    jd = os.path.join(OUT, cid, job)
    first = min([os.path.getmtime(os.path.join(jd, f)) for f in os.listdir(jd)] or [time.time()]) if os.path.isdir(jd) else time.time()
    prev = first; rows = []
    for s in st["steps"]:
        if s["done"]:
            rows.append({**s, "start": int(prev), "dur": max(0, int(s["t"] - prev))}); prev = s["t"]
        else:
            rows.append({**s, "start": int(prev) if s.get("active") else None, "dur": int(time.time() - prev) if s.get("active") else None})
    logs = [l for l in grep_log(re.escape(job))][-60:]
    plan = jload(os.path.join(jd, "plan.json"), {}) or {}
    rv = jload(os.path.join(jd, "review.json"), {}) or {}
    return {**st, "timeline": rows, "logs": logs[::-1], "scenes": [{"type": s.get("type"), "vo": s.get("vo", "")[:200]} for s in plan.get("scenes", [])],
            "hashtags": plan.get("hashtags", []), "review_full": rv}


# ---------------- latest posts of a channel (likes/comments; views from stats when we have them) ----------------
def posts(igid):
    def f():
        ut = open(os.path.join(HOME, ".studio-meta-user.token")).read().strip()
        d = json.load(urllib.request.urlopen(f"{G}/{igid}/media?fields=caption,like_count,comments_count,media_type,media_product_type,permalink,timestamp,thumbnail_url,media_url&limit=12&access_token={ut}", timeout=30))
        out = []
        for m in d.get("data", []):
            out.append({"caption": (m.get("caption") or "")[:120], "likes": m.get("like_count", 0), "comments": m.get("comments_count", 0),
                        "type": m.get("media_product_type") or m.get("media_type"), "url": m.get("permalink"), "t": m.get("timestamp", "")[:16].replace("T", " "),
                        "thumb": m.get("thumbnail_url") or (m.get("media_url") if m.get("media_type") == "IMAGE" else None)})
        return out
    return cached("posts-" + igid, 1800, f)


# ---------------- connected sources ----------------
def _tg():
    cfg = jload(os.path.join(HOME, ".studio-telegram.json"))
    if not cfg:
        return ("bad", "Not set up")
    d = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{cfg['token']}/getMe", timeout=15))
    return ("ok", "@" + d["result"]["username"] + " · group Studio360") if d.get("ok") else ("bad", "Bot token rejected")


def sources(state):
    out = []

    def add(name, what, lvl, detail, last=None, test=None):
        out.append({"name": name, "what": what, "lvl": lvl, "detail": detail, "last": last, "test": test})
    td = state.get("token_days")
    mp = grep_log(r"published|stats:|insights")
    add("Meta (Ads MCP login)", "Posting, followers, insights", "ok" if (td or 0) >= 21 else "warn" if (td or 0) > 7 else "bad",
        f"Data access {td} days left" if td is not None else "Not checked yet", ts(mp[-1]) if mp else int(time.time()), "meta")
    t = cached("tg", 600, lambda: _tg())
    tg = grep_log(r"sent for approval|telegram")
    add("Telegram bot", "Approvals in Studio360", t[0] if isinstance(t, tuple) else "bad", t[1] if isinstance(t, tuple) else t.get("error", ""), ts(tg[-1]) if tg else None, "telegram")
    gl = grep_log(r"plan text by|tts gemini|gemini text fail|429|RESOURCE_EXHAUSTED")
    good = [l for l in gl if "fail" not in l and "429" not in l and "EXHAUSTED" not in l]
    badl = [l for l in gl if l not in good]
    lvl = "ok" if good and (not badl or ts(good[-1]) > ts(badl[-1])) else "warn" if good else "bad"
    add("Gemini (free credits)", "Scripts, voice, review", lvl, ("Last error: " + badl[-1][20:120]) if lvl != "ok" and badl else
        (good[-1][20:80] if good else "No call yet"), ts(good[-1]) if good else None)
    for name, ok in state["server"]["muse"].items():
        lg = os.path.join(HOME, "musebridge2" if name == "bridge 2" else "musebridge", "musebridge.log")
        add(f"Muse {name}", "Images and clips", "ok" if ok else "bad", "Answering" if ok else "Not answering",
            int(os.path.getmtime(lg)) if os.path.exists(lg) else None)
    cf = os.path.exists(os.path.join(HOME, "videngine", "cf.token"))
    cl = grep_log(r"cloudflare")
    add("Cloudflare FLUX", "Backup images", "ok" if cf else "bad", "Key saved" if cf else "No key", ts(cl[-1]) if cl else None)
    yt = [c for c in state["channels"] if c["group"] == "Studio" and c.get("yt")]
    linked = [c for c in yt if c.get("yt_ok")]
    add("YouTube uploader", "Shorts upload", "ok" if yt and len(linked) == len(yt) else "info", f"{len(linked)} of {len(yt)} channels linked · needs a one-time login", None)
    tsj = cached("tsc", 300, lambda: json.loads(run(["tailscale", "status", "--json"]) or "{}"))
    online = (tsj.get("Self") or {}).get("Online") if isinstance(tsj, dict) else None
    add("Tailscale", "Private access to this page", "ok" if online else "warn", "Online" if online else "Status unknown", None)
    ds = jload(os.path.join(OUT, "doctor-state.json"), {}) or {}
    add("Doctor (self-repair)", "Finds and fixes breaks every 10 min", "ok" if ds.get("last") and time.time() - ds["last"] < 1800 else "bad",
        ("Last fixes: " + " | ".join(ds.get("last_did") or [])[-200:]) if ds.get("last_did") else "Nothing needed fixing", ds.get("last"))
    lr = jload(os.path.join(ROOT, "knowledge", "learned.json"), []) or []
    try:
        import brain as _b
        bs = _b.stats()
    except Exception:
        bs = {}
    add("Learner (GitHub + files)", "Reads links and files you send in Studio360", "ok" if lr else "info",
        f"{len(lr)} sources read · {bs.get('active', 0)} items in the brain" if lr else "Nothing sent yet",
        int(time.mktime(time.strptime(lr[-1]["t"], "%Y-%m-%d %H:%M"))) if lr else None)
    gt = run(["git", "-C", ROOT, "log", "-1", "--format=%ct %s"]).strip()
    add("GitHub (studio repo)", "Code + lessons backup", "ok" if gt else "warn", gt.split(" ", 1)[1][:80] if gt else "No commits", int(gt.split()[0]) if gt else None)
    q = os.path.join(HOME, "vajra-automation", "social", "queue.json")
    add("VAJRA automation", "Posting on GitHub Actions", "ok" if os.path.exists(q) else "warn", "Queue file synced" if os.path.exists(q) else "Repo not on server",
        int(os.path.getmtime(q)) if os.path.exists(q) else None)
    return out


def test_source(name):
    if name == "telegram":
        _c.pop("tg", None); r = cached("tg", 600, lambda: _tg()); return {"ok": isinstance(r, tuple) and r[0] == "ok", "detail": r[1] if isinstance(r, tuple) else r}
    if name == "meta":
        import api
        api._cache["t"] = 0; p = api.meta_pages(); return {"ok": bool(p), "detail": f"{len([k for k in p if not k.startswith('_')])} pages read"}
    return {"ok": False, "detail": "no test"}


# ---------------- what needs the owner ----------------
DEFAULT_TASKS = [
    {"id": "yt-login", "title": "Link YouTube for Kaise Tech and Aage Suno", "why": "Shorts are not uploaded until you log in once (5 min).", "done": False},
    {"id": "warmup", "title": "Warm up the new Instagram accounts", "why": "Profile photo, bio, a few likes and comments each day until 20 Nov.", "done": False},
]


def tasks():
    t = jload(TASKS)
    if t is None:
        t = DEFAULT_TASKS
        with open(TASKS, "w", encoding="utf-8") as f:
            json.dump(t, f, ensure_ascii=False, indent=1)
    return t


def set_task(tid, done):
    t = tasks()
    for x in t:
        if x["id"] == tid:
            x["done"] = bool(done)
    with open(TASKS, "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False, indent=1)
    return t


def needs_you(state):
    out = []
    for j in state["jobs"]:
        if j["status"] in ("waiting", "ready"):
            out.append({"kind": "approve", "lvl": "wait", "title": f"Approve: {j['title']}", "sub": f"{j['cid']} · {'English' if j['lang'] == 'en' else 'Hindi'} · visual {j['review'].get('score') or '?'}/10", "cid": j["cid"], "job": j["job"]})
    for i in state["issues"]:
        if i["lvl"] == "bad":
            out.append({"kind": "issue", "lvl": "bad", "title": i["title"], "sub": i.get("fix") or i.get("detail", "")})
    for t in tasks():
        if not t.get("done"):
            out.append({"kind": "task", "lvl": "info", "title": t["title"], "sub": t["why"], "id": t["id"]})
    return out[:8]


# ---------------- morning brief + Ask (Gemini free key via the planner) ----------------
def _ctx(state):
    j = [{"channel": x["cid"], "video": x["title"], "status": x["status"], "progress": x["pct"], "review_problems": x["review"].get("problems")} for x in state["jobs"][:14]]
    ch = [{"name": c["name"], "ig_followers": c["igF"], "fb_followers": c["fb"], "status": c["note"], "pipeline": c["counts"]} for c in state["channels"]]
    srv = {k: state["server"][k] for k in ("cpu", "mem_pct", "disk_pct", "load", "muse")}
    cut = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 7200))
    acts = [a["t"][11:16] + " " + a["msg"][:140] for a in state["activity"] if a["t"] >= cut][:30]
    return json.dumps({"now": time.strftime("%a %d %b %H:%M IST"), "doing_now": state["doing"], "server": srv, "videos": j, "channels": ch,
                       "issues": [{"level": i["lvl"], "title": i["title"], "detail": i["detail"][:160]} for i in state["issues"]],
                       "schedule": [{"what": s["name"], "in_min": (s["in"] or 0) // 60} for s in state["schedule"]], "recent_log": acts}, ensure_ascii=False)


def _ask_llm(prompt):
    sys.path.insert(0, os.path.join(ROOT, "engine")); sys.path.insert(0, os.path.join(ROOT, "lib"))
    import plan as planner
    return planner.ask(prompt, max_tokens=1500)


_bg = {"run": False}


def brief(state, force=False):
    b = jload(BRIEF, {}) or {}
    if force or not b.get("t"):
        return _make_brief(state)
    if time.time() - b["t"] > 1800 and not _bg["run"]:          # stale: rewrite in the background, show the last one meanwhile
        import threading
        _bg["run"] = True
        threading.Thread(target=lambda: (_make_brief(state), _bg.update(run=False)), daemon=True).start()
    return b


def _make_brief(state):
    p = ("You write the owner's short status brief for his video studio dashboard. Plain English, no hype, no emojis.\n"
         "Describe the situation of the LAST 2 HOURS only; ignore anything older. Videos 'held' are being rebuilt by the server "
         "automatically (say so briefly, do not list log errors). Mention disk only if it is above 85% full. Mention CPU only if the "
         "priority CPU is above 85%. Say what the owner needs to do, or that nothing is needed.\n"
         "Data (live, from the server):\n" + _ctx(state) + "\n\n"
         'Return JSON {"headline": "one sentence: the single most important thing right now", '
         '"lines": ["4-7 short lines: what got done, what is in progress, what needs the owner, any risk, what happens next"]}. '
         "Use only facts from the data. Say numbers exactly.")
    r = _ask_llm(p) or {}
    b = {"t": int(time.time()), "headline": r.get("headline", ""), "lines": r.get("lines", [])[:7]}
    with open(BRIEF, "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False)
    return b


def ask(state, q):
    p = ("Answer the owner's question about his video studio using ONLY this live server data. Plain English, 2-5 short lines, "
         "say where each number comes from (e.g. 'from the engine log', 'from Meta'). If the data does not answer it, say so.\n"
         "Data:\n" + _ctx(state) + f"\n\nQuestion: {q[:500]}\n" + 'Return JSON {"answer": "..."}')
    r = _ask_llm(p) or {}
    return {"answer": r.get("answer") or "I could not get an answer right now."}
