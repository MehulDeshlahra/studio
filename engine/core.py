"""Shared helpers for the Studio engine (runs on the Oracle server; also works on the laptop for tests)."""
import json, os, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))        # the studio repo
sys.path.insert(0, os.path.join(ROOT, "lib"))
HOME = os.path.expanduser("~")
ASSETS = os.environ.get("STUDIO_ASSETS", os.path.join(HOME, "studio-assets"))   # audio library (not in git)
OUT = os.environ.get("STUDIO_OUT", os.path.join(HOME, "studio-out"))
PY = sys.executable
def github_headers(extra=None):
    """GitHub API headers; with the owner's read-only token (~/.studio-github.token) the limit is 5000/h, not 60/h."""
    h = {"User-Agent": "studio-learner", "Accept": "application/vnd.github+json"}
    try:
        t = open(os.path.join(HOME, ".studio-github.token")).read().strip()
        if t:
            h["Authorization"] = "Bearer " + t
    except OSError:
        pass
    return dict(h, **(extra or {}))


def log(*a):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    try:
        with open(os.path.join(OUT, "engine.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def sh(cmd, check=True, timeout=None, env=None, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=cwd)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {(r.stderr or r.stdout)[-800:]}")
    return r.stdout


def dur(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def load(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


STICKY = ("removed", "posted")   # owner / publish decisions a stale copy must never undo


def save(path, data, force=()):
    """Atomic JSON save. channels/*/done.json is merged under a lock (18 Nov: mehul.py and make.py held the list for
    minutes and wrote it back, turning the owner's 'removed' into 'rejected' and dropping rows added meanwhile).
    force = jobs whose status this caller may change even if it is sticky (the owner's own actions)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.basename(path) == "done.json" and isinstance(data, list):
        lk = None
        try:
            import fcntl
            lk = open(path + ".lock", "w"); fcntl.flock(lk, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        try:
            cur = {d.get("job"): d for d in (load(path, []) or []) if isinstance(d, dict)}
            mine = {d.get("job") for d in data if isinstance(d, dict)}
            for d in data:
                c = cur.get(d.get("job"))
                if c and c.get("status") in STICKY and d.get("status") != c.get("status") and d.get("job") not in force:
                    d["status"] = c["status"]
                    for k in ("posted", "removed_why", "pruned"):
                        if k in c:
                            d[k] = c[k]
            data = list(data) + [c for j, c in cur.items() if j not in mine]     # rows another process added
            tmp = path + ".tmp"
            json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(tmp, path)
        finally:
            if lk:
                lk.close()
        return
    tmp = path + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def channel(cid):
    c = load(os.path.join(ROOT, "channels", cid, "channel.json"))
    if not c:
        raise SystemExit(f"no channel {cid}")
    return c


def read(path, limit=None):
    try:
        t = open(path, encoding="utf-8").read()
        return t[-limit:] if limit else t
    except OSError:
        return ""


def telegram(text, video=None, photo=None):
    """Studio Telegram group (~/.studio-telegram.json {"token","chat"}). Silently logs when not set up yet."""
    cfg = load(os.path.join(HOME, ".studio-telegram.json"))
    if not cfg:
        log("telegram not set up; message:", text[:200])
        return False
    try:
        if video or photo:
            f = video or photo
            kind = "sendVideo" if video else "sendPhoto"
            r = json.loads(sh(["curl", "-s", "-m", "300", "-F", f"chat_id={cfg['chat']}", "-F", f"caption={text[:1000]}",
                               "-F", "supports_streaming=true",
                               "-F", f"{'video' if video else 'photo'}=@{f}", f"https://api.telegram.org/bot{cfg['token']}/{kind}"]))
        else:
            body = json.dumps({"chat_id": cfg["chat"], "text": text[:4000]}).encode()
            r = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{cfg['token']}/sendMessage",
                          data=body, headers={"Content-Type": "application/json"}), timeout=60))
        return r.get("result", {}).get("message_id") or True
    except Exception as e:
        log("telegram error", e)
        return False
