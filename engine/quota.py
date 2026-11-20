"""One view of every free quota Studio spends (20 Nov audit: the state was spread over six files and nobody saw that
Muse's 40 images or Cloudflare's 10,000 neurons were gone until a picture failed).
  left()   -> [{"pool", "used", "cap", "left", "resets", "note"}], read from the files the engine already writes
  line()   -> one text line per pool for STATE.md / Telegram
  spend()  -> OmniRoute calls today on the Studio key, split into reels vs other work (self-repair, reading, tests)
Read only: nothing here calls a provider.  python engine/quota.py"""
import glob, json, os, time
from core import OUT, HOME, load

UTC_DAY = lambda: time.strftime("%Y-%m-%d", time.gmtime())


def _gemini():
    st = load(os.path.join(OUT, "gemini-keys.json"), {}) or {}
    keys = st.get("keys") or {}
    try:
        n = sum(1 for l in open(os.path.join(HOME, ".studio-gemini.key")) if l.strip())
    except Exception:
        n = len(keys)
    today = st.get("day") == time.strftime("%Y-%m-%d")
    out = {}
    for k, v in (keys.items() if today else []):
        for m in v.get("out") or []:
            out[m] = out.get(m, 0) + 1
    calls = sum(v.get("ok", 0) for v in keys.values()) if today else 0
    rows = [{"pool": "Gemini keys", "used": calls, "cap": None, "left": None, "resets": "midnight Pacific",
             "note": f"{n} keys; out for the day: " + (", ".join(f"{m} on {c}/{n}" for m, c in sorted(out.items())) or "none")}]
    return rows


def _muse():
    rows = []
    for name, f, cap in (("Muse bridge 2 images", "~/musebridge2/usage.json", 40), ("Muse bridge 2 videos", "~/musebridge2/usage.json", 15)):
        u = load(os.path.expanduser(f), {}) or {}
        kind = "image" if "images" in name else "video"
        used = u.get(kind, 0) if u.get("day") == time.strftime("%Y-%m-%d") else 0
        rows.append({"pool": name, "used": used, "cap": cap, "left": max(0, cap - used), "resets": "daily", "note": ""})
    return rows


def _cloudflare():
    out = (load(os.path.join(OUT, "cf-quota.json"), {}) or {}).get("day") == UTC_DAY()
    return [{"pool": "Cloudflare neurons", "used": None, "cap": 10000, "left": 0 if out else None, "resets": "00:00 UTC",
             "note": "used up today" if out else "not reported out today (~1,400 a klein picture)"}]


def _pollinations():
    st = load(os.path.join(OUT, "poll-quota.json"), {}) or {}
    try:
        n = sum(1 for l in open(os.path.join(HOME, ".studio-pollinations.key")) if l.strip())
    except Exception:
        n = 0
    dead = sum(1 for v in st.values() if v == UTC_DAY())
    return [{"pool": "Pollinations keys", "used": None, "cap": n, "left": n - dead, "resets": "00:00 UTC",
             "note": f"{dead} of {n} keys out of balance today"}]


REEL_WORDS = ("plan one vertical", "strict senior editor", "fixing scenes of a planned", "check a short scripture",
              "prompt engineer for flux", "the best short-form clipper", "on-screen notes for one clip", "check that a reels script",
              "second, independent check", "fix only these", "fix one line", "art director", "strictest reviewer",
              "finishing editor", "check a finished vertical clip", "rewrite this reel plan", "editor of a top indian")


def spend(day=None):
    """OmniRoute attempts today on the Studio key: reels vs everything else, and how many failed."""
    day = day or time.strftime("%Y-%m-%d", time.gmtime())
    tot = {"reels": [0, 0], "other": [0, 0]}
    for f in glob.glob(os.path.join(HOME, ".omniroute", "call_logs", day, "*.json")):
        try:
            head = open(f).read(5000)
            i = head.find('"summary":'); j = head.find('},"requestBody"')
            s = json.loads(head[i + 10:j + 1])
        except Exception:
            continue
        if s.get("apiKeyName") != "studio":
            continue
        k = "reels" if any(w in head[j:].lower() for w in REEL_WORDS) else "other"
        tot[k][0] += 1
        tot[k][1] += 0 if s.get("status") == 200 else 1
    return tot


def left():
    rows = []
    for f in (_gemini, _muse, _cloudflare, _pollinations):
        try:
            rows += f()
        except Exception as e:
            rows.append({"pool": f.__name__[1:], "used": None, "cap": None, "left": None, "resets": "", "note": f"unreadable: {e}"})
    return rows


def line(r):
    a = f"{r['used']} used" if r.get("used") is not None else ""
    b = f"{r['left']} of {r['cap']} left" if r.get("left") is not None and r.get("cap") else ""
    return f"- {r['pool']}: " + ", ".join(x for x in (b, a, r.get("note")) if x) + (f" (resets {r['resets']})" if r.get("resets") else "")


if __name__ == "__main__":
    for r in left():
        print(line(r))
    s = spend()
    print(f"- OmniRoute today (Studio key): reels {s['reels'][0]} calls ({s['reels'][1]} failed), other work {s['other'][0]} ({s['other'][1]} failed)")
