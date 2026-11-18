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
             "internet kaise chalta hai shorts", "hindi tech gyan shorts", "science facts hindi shorts", "kaise kaam karta hai animation hindi"],
    "katha": ["pauranik katha shorts hindi", "mahabharat ki kahani shorts", "ramayan ka rahasya shorts",
              "hindu mythology facts hindi shorts", "shiv ji ki katha shorts"],
    "raaz": ["real crime story hindi shorts", "rahasya kahani shorts hindi", "mystery story hindi shorts",
             "sachi ghatna hindi shorts", "detective story hindi shorts", "horror kahani hindi shorts", "crime story animated hindi shorts"],
}

NICHE = {"tech": "an explainer or fact video about technology, science or how everyday things work (phones, internet, apps, AI, gadgets, machines)",
         "katha": "a Hindu mythology / puranic story or explanation told in Hindi (gods, epics, temples, legends)",
         "raaz": "a narrated story or case about crime, mystery, horror, suspense or strange real events (not a movie scene, not a vlog)"}

HOOK_PROMPT = """You study short-video hooks. Watch ONLY the first 3 seconds of this Short very carefully, then the rest once.
FIRST decide if this Short is really {niche_desc}. Movie scenes, trailers, ads, gossip, vlogs, news, music, comedy skits and
anything else is NOT on niche.
Return JSON:
{{"on_niche": true/false,
 "faceless": true/false (true if no presenter/creator face is the main thing on screen),
 "language": "hindi|hinglish|english|other",
 "first_words": "exact first spoken words (first 2 s), in Roman script",
 "first_text": "exact on-screen text in the first 2 s, or empty",
 "frame0": "what the very first frame shows (subject, framing, colour)",
 "motion_0_2s": "what moves / cuts in the first 2 s (zoom, whip, cut count)",
 "sound_0_2s": "music/sfx/voice start (silent start? hit? riser?)",
 "hook_type": "question|shock fact|myth bust|you-statement|story cold open|number|mystery|challenge|other",
 "time_to_first_cut_s": number,
 "why_viewers_stay": "one sentence",
 "what_we_can_copy_without_copying": "one sentence: the principle, not the content"}}"""

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


IG_ACCOUNTS = {   # public business/creator accounts in each niche (owner can add more; the agent may too)
    "tech": ["samjho.exe", "techburner", "trakintech", "technicalguruji", "gyanfactory"],
    "katha": ["sanatani.kahaniyan", "bhakti.stories", "mythology.in.hindi", "dharmikgyan", "puranikkatha"],
    "raaz": ["horror.kahaniya", "crimetak", "rahasya.kahani", "hindistoryshorts", "kahaniwala"],
}


def ig_top(page, per=6):
    """Top reels of niche accounts on Instagram itself, through the official Business Discovery API (any public
    business/creator account; uses the page's own login). Returns [{url, title, views(likes as proxy), channel}]."""
    import publish
    acc = publish.resolve(load(os.path.expanduser(f"~/.studio-accounts/{page}.json")) or {})
    if not acc.get("ig_user_id"):
        return []
    out = []
    names = IG_ACCOUNTS.get(page, []) + list((load(os.path.join(ROOT, "knowledge", "ig-accounts.json"), {}) or {}).get(page, []))
    for u in dict.fromkeys(names):
        f = ("business_discovery.username(%s){username,followers_count,media.limit(25){caption,like_count,comments_count,"
             "media_product_type,permalink,media_url}}" % u)
        try:
            d = publish._req(f"{publish.G}/{acc['ig_user_id']}?fields=" + f.replace("{", "%7B").replace("}", "%7D") + f"&access_token={acc['page_token']}")
        except Exception as e:
            log("hookstudy ig skip", u, str(e)[:60]); continue
        b = d.get("business_discovery") or {}
        reels = [m for m in (b.get("media") or {}).get("data", []) if m.get("media_product_type") == "REELS" and m.get("permalink") and m.get("media_url")]   # no file = cannot be watched (licensed music)
        reels.sort(key=lambda m: -((m.get("like_count") or 0) + 3 * (m.get("comments_count") or 0)))
        for m in reels[:per]:
            out.append({"id": m["permalink"], "url": m["permalink"], "video": m.get("media_url"), "title": (m.get("caption") or "")[:90],
                        "views": (m.get("like_count") or 0) * 30, "likes": m.get("like_count"), "comments": m.get("comments_count"),
                        "channel": "ig:" + u, "followers": b.get("followers_count")})
    return out


def watch_file(mp4_url, prompt):
    """Instagram reel: download the file (<= 25 MB) and send it inline to Gemini (free keys), returns parsed JSON."""
    import base64, urllib.request, tts
    b = urllib.request.urlopen(urllib.request.Request(mp4_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read(26_000_000)
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(b).decode()}},
                                    {"text": prompt + "\n\nReturn ONLY valid JSON."}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2, "maxOutputTokens": 8000}}
    # 18 Nov: 1500 tokens cut shot-by-shot answers mid-JSON; more models because 3.8-flash/3.5-lite were 503 for hours
    for m in tts.usable(["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]):
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(m)})
            d = json.load(urllib.request.urlopen(r, timeout=240))
            return llm.parse_json("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
        except Exception as e:
            log("hookstudy ig watch fail", m, str(e)[:80])
    raise RuntimeError("could not watch the reel")


def study(page, n=10):
    found, seen = [], set()
    for q in QUERIES.get(page, []):
        for v in top_shorts(q):
            if v["id"] not in seen:
                seen.add(v["id"]); found.append(v)
    try:                                                     # 18 Nov: Instagram winners join the YouTube ones
        ig = ig_top(page)
        found += ig
        log("hookstudy", page, "instagram reels found:", len(ig))
    except Exception as e:
        log("hookstudy instagram failed", str(e)[:100])
    found.sort(key=lambda v: -v["views"])
    notes, tried, loose = [], 0, []
    for v in found:
        if len(notes) >= n or tried >= n * 2:
            break
        tried += 1
        try:
            hp = HOOK_PROMPT.format(niche_desc=NICHE.get(page, "a short-form explainer in this niche"))
            a = watch_file(v["video"], hp) if v.get("video") else llm.watch(v["url"], hp)
        except Exception as e:
            log("hookstudy watch fail", v["url"], str(e)[:100]); continue
        if not isinstance(a, dict) or a.get("on_niche") is False:
            continue
        if not a.get("faceless", True):                 # keep on-niche videos with a presenter as a fallback (raaz has few faceless winners)
            a.update({k: v.get(k) for k in ("url", "title", "views", "channel")}); loose.append(a); continue
        a.update({k: v.get(k) for k in ("url", "title", "views", "channel")})
        notes.append(a); log("hookstudy", page, f"{v['views']:,}", v["url"], "|", str(a.get("first_words"))[:60])
    if len(notes) < 3:
        notes += loose[:6 - len(notes)]
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
        if len(notes) < 3:
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
