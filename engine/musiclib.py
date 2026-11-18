"""Free music library, mood-tagged (owner 17 Nov: "free royalty-free music, 20-30 tracks per page, planner picks by mood").
Source: Kevin MacLeod / incompetech.com (1,400+ instrumental tracks, every one tagged with "feel", CC BY 4.0: free for
monetised videos with a credit line, which make.py adds to the caption). Downloads work from the server with no key.
  build()                    -> download ~25 tracks per page into ~/studio-assets/audio/music/lib/<page>/ + knowledge/music.json
  pick(page, mood, job)      -> {"file": "music/lib/<page>/x.mp3", "offset": s, "title": ..., "mood": ...} (least recently used
                                track of that mood on that page; never the same track twice within 30 days if avoidable)
  python engine/musiclib.py build | list"""
import json, os, random, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log

ASSETS = os.path.expanduser("~/studio-assets/audio")          # mix.py resolves "music/..." against this folder
LIB = os.path.join(ROOT, "knowledge", "music.json")
USAGE = os.path.join(OUT, "music-usage.json")
CREDIT = "Music: Kevin MacLeod (incompetech.com), CC BY 4.0"
LIST_URL = "https://incompetech.com/music/royalty-free/pieces.json"
MP3_URL = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
UA = {"User-Agent": "Mozilla/5.0 (StudioBot music library)"}

FEEL2MOOD = {"Suspenseful": "suspense", "Unnerving": "suspense", "Eerie": "suspense", "Mysterious": "mystery", "Mystical": "mystery",
             "Epic": "epic", "Action": "epic", "Intense": "epic", "Somber": "emotional", "Calming": "calm", "Relaxed": "calm",
             "Uplifting": "uplifting", "Bright": "uplifting", "Bouncy": "playful", "Humorous": "playful", "Driving": "driving",
             "Grooving": "driving", "Dark": "dark", "Aggressive": "dark"}
MOODS = sorted(set(FEEL2MOOD.values()))
# how many tracks of each mood each page keeps (≈25 per page)
PLAN = {"tech": {"driving": 7, "uplifting": 5, "mystery": 5, "playful": 4, "suspense": 4},
        "katha": {"epic": 6, "mystery": 6, "emotional": 5, "calm": 4, "suspense": 4},
        "raaz": {"suspense": 8, "dark": 6, "mystery": 6, "emotional": 5},
    "jain": {"calm": 7, "emotional": 6, "epic": 5, "mystery": 4},
    "finance": {"driving": 7, "uplifting": 6, "playful": 5, "suspense": 4},
}
AVOID = re.compile(r"christmas|holiday|medieval|ren faire|tavern|polka|march|anthem|kids|carol|halloween|circus|banjo|bagpipe", re.I)


def _secs(t):
    try:
        p = [int(x) for x in str(t).split(":")]
        return p[-1] + 60 * p[-2] + (3600 * p[-3] if len(p) > 2 else 0)
    except Exception:
        return 0


def build():
    pieces = json.load(urllib.request.urlopen(urllib.request.Request(LIST_URL, headers=UA), timeout=60))
    lib = load(LIB, {}) or {}
    rnd = random.Random(17)
    taken = set()
    for page, want in PLAN.items():
        have = lib.get(page, [])
        names = {t["title"] for t in have}
        for mood, n in want.items():
            pool = []
            for x in pieces:
                feels = [f.strip() for f in (x.get("feel") or "").split(",") if f.strip()]
                if not feels or FEEL2MOOD.get(feels[0]) != mood:     # the FIRST feel is the main one
                    continue
                txt = " ".join(str(x.get(k) or "") for k in ("title", "description", "instruments", "feel"))
                if AVOID.search(txt) or not (60 <= _secs(x.get("length")) <= 420) or x["title"] in taken:
                    continue
                pool.append(x)
            pool.sort(key=lambda x: x.get("uploaded") or "", reverse=True)       # newer uploads first (fresher sound)
            pool = pool[:60]; rnd.shuffle(pool)
            got = sum(1 for t in have if t["mood"] == mood)
            for x in pool:
                if got >= n:
                    break
                if x["title"] in names:
                    continue
                slug = re.sub(r"[^a-z0-9]+", "-", x["title"].lower()).strip("-")[:40]
                rel = f"music/lib/{page}/{slug}.mp3"; dst = os.path.join(ASSETS, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                try:
                    if not os.path.exists(dst):
                        b = urllib.request.urlopen(urllib.request.Request(MP3_URL + urllib.parse.quote(x["filename"]), headers=UA), timeout=120).read()
                        if len(b) < 200000:
                            continue
                        open(dst, "wb").write(b)
                except Exception as e:
                    log("musiclib download fail", x["title"], str(e)[:80]); continue
                have.append({"file": rel, "title": x["title"], "mood": mood, "feel": x.get("feel"), "bpm": x.get("bpm"),
                             "length": _secs(x.get("length")), "instruments": x.get("instruments"), "credit": CREDIT})
                names.add(x["title"]); taken.add(x["title"]); got += 1
                log("musiclib", page, mood, x["title"])
        lib[page] = have
    save(LIB, lib)
    return {p: len(v) for p, v in lib.items()}


def pick(page, mood, job=""):
    lib = (load(LIB, {}) or {}).get(page) or []
    lib = [t for t in lib if os.path.exists(os.path.join(ASSETS, t["file"]))]
    if not lib:
        return None
    use = load(USAGE, {}) or {}
    pool = [t for t in lib if t["mood"] == (mood or "").strip().lower()] or lib
    now = time.time()
    fresh = [t for t in pool if now - use.get(t["file"], 0) > 30 * 86400]
    t = dict(min(fresh or pool, key=lambda t: use.get(t["file"], 0)))
    use[t["file"]] = now; save(USAGE, use)
    t["offset"] = 2.0 if t.get("length", 0) < 120 else 6.0          # skip the slow intro of longer pieces
    log("music:", page, mood or "-", "->", t["title"], f"({t['mood']})", job)
    return t


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        print(build())
    else:
        for p, v in (load(LIB, {}) or {}).items():
            print(p, len(v), sorted({t["mood"] for t in v}))
