"""Telegram inbox for the Studio group (systemd timer studio-inbox, every minute). Owner replies to a video:
  "ok" / "approve" / "👍"        -> approved (goes to the posting queue)
  "no" / "reject"                -> rejected
  anything else                  -> feedback: saved as an owner lesson for that channel (read by every next plan)
                                    and the video is marked "fix"
Commands: "/make <channel> [topic]" makes a video now; "/status" lists backlogs; "/lesson <channel> <text>" adds a rule."""
import json, os, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, PY, log, load, save, telegram

CFG = os.path.expanduser("~/.studio-telegram.json")
STATE = os.path.join(OUT, "tg-state.json")
YES = {"ok", "okay", "approve", "approved", "yes", "haan", "post", "👍", "✅"}
NO = {"no", "reject", "nahi", "drop", "❌", "👎"}


def api(cfg, method, **params):
    url = f"https://api.telegram.org/bot{cfg['token']}/{method}"
    req = urllib.request.Request(url, data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=70))


def set_status(cid, job, status, note=None):
    p = os.path.join(ROOT, "channels", cid, "done.json")
    done = load(p, [])
    for d in done:
        if d["job"] == job:
            d["status"] = status
            if note:
                d.setdefault("feedback", []).append(note)
    save(p, done)


def add_lesson(cid, text, job=None):
    p = os.path.join(ROOT, "channels", cid, "lessons.md")
    if not os.path.exists(p):
        open(p, "w", encoding="utf-8").write(f"# {cid} lessons (owner feedback; read before every plan)\n")
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"- {time.strftime('%d %b')}{' ' + job if job else ''}: {text.strip()}\n")


def main():
    cfg = load(CFG)
    if not cfg:
        return
    st = load(STATE, {"offset": 0})
    upd = api(cfg, "getUpdates", offset=st["offset"], timeout=0).get("result", [])
    tgmap = load(os.path.join(OUT, "tg-map.json"), {})
    changed = False
    for u in upd:
        st["offset"] = u["update_id"] + 1
        m = u.get("message") or {}
        if str(m.get("chat", {}).get("id")) != str(cfg["chat"]):
            continue
        text = (m.get("text") or m.get("caption") or "").strip()
        if not text:
            continue
        low = text.lower()
        rep = m.get("reply_to_message", {}).get("message_id")
        if rep and str(rep) in tgmap:
            j = tgmap[str(rep)]
            if low in YES:
                set_status(j["channel"], j["job"], "approved"); telegram(f"✅ {j['channel']} {j['job']} approved")
            elif low in NO:
                set_status(j["channel"], j["job"], "rejected"); telegram(f"❌ {j['channel']} {j['job']} rejected")
            else:
                set_status(j["channel"], j["job"], "fix", text); add_lesson(j["channel"], text, j["job"])
                telegram(f"📝 Saved as a lesson for {j['channel']} (every next video reads it). {j['job']} marked 'fix'.")
            changed = True
        elif low.startswith("/make"):
            parts = text.split(maxsplit=2)
            cid = parts[1] if len(parts) > 1 else "tech"
            args = [PY, os.path.join(ROOT, "engine", "make.py"), cid] + ([parts[2]] if len(parts) > 2 else [])
            subprocess.Popen(args, stdout=open(os.path.join(OUT, "manual.log"), "a"), stderr=subprocess.STDOUT)
            telegram(f"🎬 making a {cid} video" + (f": {parts[2]}" if len(parts) > 2 else ""))
        elif low.startswith("/lesson"):
            parts = text.split(maxsplit=2)
            if len(parts) == 3:
                add_lesson(parts[1], parts[2]); telegram(f"📝 lesson saved for {parts[1]}"); changed = True
        elif low.startswith("/status"):
            lines = []
            for cid in sorted(os.listdir(os.path.join(ROOT, "channels"))):
                done = load(os.path.join(ROOT, "channels", cid, "done.json"), [])
                if done:
                    c = {}
                    for d in done:
                        c[d.get("status")] = c.get(d.get("status"), 0) + 1
                    lines.append(f"{cid}: " + ", ".join(f"{k} {v}" for k, v in c.items()))
            telegram("\n".join(lines) or "nothing made yet")
    save(STATE, st)
    if changed:
        subprocess.run([PY, os.path.join(ROOT, "engine", "sync.py")], timeout=300)


if __name__ == "__main__":
    main()
