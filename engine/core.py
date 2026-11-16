"""Shared helpers for the Studio engine (runs on the Oracle server; also works on the laptop for tests)."""
import json, os, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))        # the studio repo
sys.path.insert(0, os.path.join(ROOT, "lib"))
HOME = os.path.expanduser("~")
ASSETS = os.environ.get("STUDIO_ASSETS", os.path.join(HOME, "studio-assets"))   # audio library (not in git)
OUT = os.environ.get("STUDIO_OUT", os.path.join(HOME, "studio-out"))
PY = sys.executable


def log(*a):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    try:
        with open(os.path.join(OUT, "engine.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def sh(cmd, check=True, timeout=None, env=None):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
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


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
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
            sh(["curl", "-s", "-m", "300", "-F", f"chat_id={cfg['chat']}", "-F", f"caption={text[:1000]}",
                "-F", f"{'video' if video else 'photo'}=@{f}", f"https://api.telegram.org/bot{cfg['token']}/{kind}"])
        else:
            body = json.dumps({"chat_id": cfg["chat"], "text": text[:4000]}).encode()
            urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{cfg['token']}/sendMessage",
                                   data=body, headers={"Content-Type": "application/json"}), timeout=60)
        return True
    except Exception as e:
        log("telegram error", e)
        return False
