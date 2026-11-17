"""Hook study (owner 17 Nov: "compare with 10 top Hindi faceless reels per page; write down what the winners do in the
first 2 seconds and feed it to the planner and the brain").
Per page: search YouTube Shorts in the niche (yt-dlp, same as research.py), keep the 10 most-viewed FACELESS ones,
let Gemini WATCH each (by URL, through OmniRoute) with a first-2-seconds checklist, then distil the patterns into rules.
Output:
  channels/<id>/hooks.md      (the planner reads it before every plan)
  knowledge/hooks.json        (raw notes per video, for the dashboard / later study)
  brain items (area "hook")   (so other pages can reuse them)
Our own posted reels join the comparison automatically once stats.py has numbers (avg watch time, views).
  python engine/hookstudy.py [page ...]      (weekly timer: studio-hooks, Mondays 05:30)"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log
import llm, research

QUERIES = {
    "tech": ["tech facts hindi shorts", "phone kaise kaam karta hai shorts", "technology explained in hindi shorts",
             "internet kaise chalta hai shorts", "hindi tech gyan shorts"],
    "katha": ["pauranik katha shorts hindi", "mahabharat ki kahani shorts", "ramayan ka rahasya shorts",
              "hindu mythology facts hindi shorts", "shiv ji ki katha shorts"],
    "raaz": ["real crime story hindi shorts", "rahasya kahani shorts hindi", "mystery story hindi shorts",
             "sachi ghatna hindi shorts", "detective story hindi shorts"],
}

HOOK_PROMPT = """You study short-video hooks. Watch ONLY the first 3 seconds of this Short very carefully, then the rest once.
Return JSON:
{"faceless": true/false (true if no presenter/creator face is the main thing on screen),
 "language": "hindi|hinglish|english|other",
 "first_words": "exact first spoken words (first 2 s), in Roman script",
 "first_text": "exact on-screen text in the first 2 s, or empty",
 "frame0": "what the very first frame shows (subject, framing, colour)",
 "motion_0_2s": "what moves / cuts in the first 2 s (zoom, whip, cut count)",
 "sound_0_2s": "music/sfx/voice start (silent start? hit? riser?)",
 "hook_type": "question|shock fact|myth bust|you-statement|story cold open|number|mystery|challenge|other",
 "time_to_first_cut_s": number,
 "why_viewers_stay": "one sentence",
 "what_we_can_copy_without_copying": "one sentence: the principle, not the content"}"""

DISTIL = """You are the head of a faceless Shorts studio. Below are notes on the {n} most-viewed faceless Shorts in our niche
"{page}" (Hindi audience), with their view counts. Our own results (may be empty): {ours}
Notes:
{notes}
Write the rules for OUR first 2 seconds. Be concrete and testable (e.g. "first spoken word is the subject noun, no
greeting; on-screen text <= 4 words, appears at frame 0; first cut before 1.2 s"). Weight by views.
Return JSON {{"rules": ["6-9 rules"], "patterns": [{{"hook_type": "...", "share": "x of {n}", "example": "first words"}}],
"avoid": ["3-5 things the winners never do"], "summary": "2 sentences"}}"""


def _ytdlp(url, n):
    import subprocess
    try:
        out = subprocess.run([research.YTDLP if os.path.exists(research.YTDLP) else "yt-dlp", url, "--flat-playlist", "-j",
                              "--no-warnings", "--playlist-end", str(n)], capture_output=True, text=True, timeout=180).stdout
    except Exception as e:
        log("hookstudy yt-dlp fail", str(e)[:100]); return []
    rows = []
    for line in out.splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows


def top_shorts(q, n=40):
    """YouTube search lists mostly tiny new uploads and no view-sorted Shorts (tested 17 Nov), so: find the CHANNELS that
    post in this niche, read each channel's Shorts tab (view counts included), keep the big ones."""
    chans = {}
    for d in _ytdlp(f"ytsearch{n}:{q}", n):
        cid = d.get("channel_id") or d.get("uploader_id")
        if cid and cid not in chans:
            chans[cid] = d.get("channel") or d.get("uploader") or cid
    vids = []
    for cid, name in list(chans.items())[:14]:
        base = f"https://www.youtube.com/channel/{cid}" if cid.startswith("UC") else f"https://www.youtube.com/{cid}"
        for d in _ytdlp(base + "/shorts", 30):
            if d.get("id") and (d.get("view_count") or 0) >= 50000:
                vids.append({"id": d["id"], "title": d.get("title"), "views": d.get("view_count") or 0, "dur": d.get("duration"),
                             "channel": name, "url": f"https://www.youtube.com/shorts/{d['id']}"})
    vids.sort(key=lambda v: -v["views"])
    out, per = [], {}
    for v in vids:                                            # max 2 per channel, so one big channel does not decide alone
        if per.get(v["channel"], 0) < 2:
            out.append(v); per[v["channel"]] = per.get(v["channel"], 0) + 1
    return out


def study(page, n=10):
    found, seen = [], set()
    for q in QUERIES.get(page, []):
        for v in top_shorts(q):
            if v["id"] not in seen:
                seen.add(v["id"]); found.append(v)
    found.sort(key=lambda v: -v["views"])
    notes, tried = [], 0
    for v in found:
        if len(notes) >= n or tried >= n * 2:
            break
        tried += 1
        try:
            a = llm.watch(v["url"], HOOK_PROMPT)
        except Exception as e:
            log("hookstudy watch fail", v["url"], str(e)[:100]); continue
        if not isinstance(a, dict) or not a.get("faceless", True):
            continue
        a.update({k: v.get(k) for k in ("url", "title", "views", "channel")})
        notes.append(a); log("hookstudy", page, f"{v['views']:,}", v["url"], "|", str(a.get("first_words"))[:60])
    return found, notes


def ours(page):
    """Our posted reels with stats (avg watch time / views), best first."""
    d = load(os.path.join(ROOT, "channels", page, "done.json"), []) or []
    rows = d if isinstance(d, list) else d.get("done", [])
    out = []
    for r in rows:
        st = (r or {}).get("stats") or {}
        if st.get("views"):
            out.append({"job": r.get("job"), "views": st.get("views"), "avg_watch_s": st.get("avg_watch_s"),
                        "hook": (r.get("title") or r.get("hook") or "")[:80]})
    return sorted(out, key=lambda x: -(x["views"] or 0))[:10]


def run(pages):
    allnotes = load(os.path.join(ROOT, "knowledge", "hooks.json"), {}) or {}
    for page in pages:
        found, notes = study(page)
        if len(notes) < 4:
            log("hookstudy", page, "too few faceless videos watched:", len(notes)); continue
        mine = ours(page)
        txt = "\n".join(f"- {x['views']:,} views | type {x.get('hook_type')} | words \"{x.get('first_words')}\" | text \"{x.get('first_text')}\""
                        f" | frame0 {x.get('frame0')} | motion {x.get('motion_0_2s')} | sound {x.get('sound_0_2s')}"
                        f" | first cut {x.get('time_to_first_cut_s')} s | stays because {x.get('why_viewers_stay')}" for x in notes)
        r = llm.text(DISTIL.format(n=len(notes), page=page, notes=txt, ours=json.dumps(mine, ensure_ascii=False) or "none"), json_mode=True)
        if not isinstance(r, dict) or not r.get("rules"):
            log("hookstudy distil failed", page); continue
        day = time.strftime("%Y-%m-%d")
        md = [f"# What the top faceless {page} Shorts do in the first 2 seconds ({day}, {len(notes)} videos watched)",
              "", r.get("summary", ""), "", "## Rules for our first 2 seconds (obey)"] + [f"- {x}" for x in r["rules"]] + \
             ["", "## Never"] + [f"- {x}" for x in r.get("avoid", [])] + ["", "## Hook types among the winners"] + \
             [f"- {p.get('hook_type')}: {p.get('share')} (e.g. \"{p.get('example')}\")" for p in r.get("patterns", [])] + \
             ["", "## Videos studied"] + [f"- {x['views']:,} views: {x.get('title')} ({x['url']}) first words \"{x.get('first_words')}\"" for x in notes]
        if mine:
            md += ["", "## Our posted reels (best first)"] + [f"- {m['views']:,} views, avg watch {m.get('avg_watch_s')} s: {m['hook']}" for m in mine]
        with open(os.path.join(ROOT, "channels", page, "hooks.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(md) + "\n")
        allnotes[page] = {"day": day, "notes": notes, "distil": r}
        try:
            import brain
            brain.add([{"title": f"{page} hook rule: {x[:60]}", "text": x, "area": "hook", "kind": "rule"} for x in r["rules"]],
                      f"hookstudy {day}")
        except Exception as e:
            log("hookstudy brain add failed", str(e)[:100])
        log("hookstudy", page, "rules:", len(r["rules"]), "from", len(notes), "videos")
    save(os.path.join(ROOT, "knowledge", "hooks.json"), allnotes)


if __name__ == "__main__":
    run(sys.argv[1:] or list(QUERIES))
