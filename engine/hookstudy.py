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
from core import pages as _pages
import llm, research

QUERIES = {
    "tech": ["tech facts hindi shorts", "phone kaise kaam karta hai shorts", "technology explained in hindi shorts",
             "internet kaise chalta hai shorts", "hindi tech gyan shorts", "science facts hindi shorts", "kaise kaam karta hai animation hindi"],
    "katha": ["pauranik katha shorts hindi", "mahabharat ki kahani shorts", "ramayan ka rahasya shorts",
              "hindu mythology facts hindi shorts", "shiv ji ki katha shorts"],
    "raaz": ["real crime story hindi shorts", "rahasya kahani shorts hindi", "mystery story hindi shorts",
             "sachi ghatna hindi shorts", "detective story hindi shorts", "horror kahani hindi shorts", "crime story animated hindi shorts"],
    "jain": ["jain katha shorts", "mahavir swami katha shorts", "jain dharma facts hindi shorts", "navkar mantra shorts", "tirthankar katha hindi shorts"],
    "finance": ["personal finance hindi shorts", "paisa kaise bachaye shorts", "sip kya hai shorts", "credit score hindi shorts", "income tax hindi shorts", "money tips hindi shorts"],
}

NICHE = {"tech": "an explainer or fact video about technology, science or how everyday things work (phones, internet, apps, AI, gadgets, machines)",
         "katha": "a Hindu mythology / puranic story or explanation told in Hindi (gods, epics, temples, legends)",
         "raaz": "a narrated story or case about crime, mystery, horror, suspense or strange real events (not a movie scene, not a vlog)",
    "jain": "a Jain dharma story or explanation told in Hindi (Tirthankaras, Mahavir Swami, Jain saints and kings, Jain festivals, ahimsa, Jain philosophy)",
    "finance": "a personal-finance or money explainer for Indians (saving, investing basics, loans, credit cards, tax, UPI, banking, scams); not stock tips or get-rich schemes",
}

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
    "jain": [],
    "finance": [],
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


HASHTAGS = {   # 18 Nov (owner: "you only see top creators; search hashtags for similar topics")
    "tech": ["techinhindi", "hinditech", "techgyan", "mobiletipsinhindi", "googleassistant", "chatgpthindi", "upipayment",
             "techfacts", "androidhacks", "jiophone"],
    "katha": ["mahabharat", "ramayan", "sanatandharma", "hindumythology", "krishna", "shivpuran", "puranas", "bhakti"],
    "raaz": ["hindistory", "mysterystory", "horrorstories", "kahani", "crimestory", "suspense", "storytime"],
    "jain": ["jainism", "jaindharma", "mahavirswami", "navkarmantra", "jainstories", "paryushan", "jaintemple", "jainstatus"],
    "finance": ["personalfinance", "financetips", "moneytips", "sipinvestment", "mutualfunds", "financeinhindi", "creditscore", "incometax", "savingmoney"],
}
HT_STATE = os.path.join(os.path.expanduser("~/studio-out"), "ig-hashtags.json")


def hashtag_top(page, tags=None, per=4, min_likes=500):
    """Top reels for hashtags through the official Hashtag Search API (any public account posting with the tag, not only
    the big creators). Instagram allows 30 different hashtags per account per 7 days: tracked in HT_STATE, and a tag
    searched in the last 7 days reuses its id (no new slot). Returns the same shape as ig_top."""
    import publish
    now = time.time()
    st = load(HT_STATE, {}) or {}
    accs = []                                     # 30 tags/week PER account: use whichever of our pages has slots left
    for p_ in [page] + [x for x in _pages() if x != page]:
        a_ = publish.resolve(load(os.path.expanduser(f"~/.studio-accounts/{p_}.json")) or {})
        if a_.get("ig_user_id"):
            used = {k: v for k, v in (st.get(a_["ig_user_id"]) or {}).items() if now - v.get("t", 0) < 7 * 86400}
            accs.append((a_, used))
    if not accs:
        return []
    want = [t_.lstrip("#").lower() for t_ in (tags or HASHTAGS.get(page, []))]
    acc, mine = next(((a_, u) for a_, u in accs if any(t_ in u for t_ in want)), None) or max(accs, key=lambda x: -len(x[1]))
    out = []
    for tag in (tags or HASHTAGS.get(page, [])):
        tag = tag.lstrip("#").lower()
        h = mine.get(tag)
        if not h:
            if len(mine) >= 28:                           # keep 2 slots spare
                log("hashtag: weekly limit near, skip", tag); continue
            try:
                d = publish._req(f"{publish.G}/ig_hashtag_search?user_id={acc['ig_user_id']}&q={tag}&access_token={acc['page_token']}")
                h = mine[tag] = {"id": d["data"][0]["id"], "t": now}
            except Exception as e:
                log("hashtag search fail", tag, str(e)[:80]); continue
        # 18 Nov: for broad tags "top" is mostly carousels/images and the reels sit in "recent" with few likes so far, so
        # both edges are read; a recent reel ranks by likes per hour since posting (a small page breaking out right now).
        f = "id,caption,like_count,comments_count,media_type,media_url,permalink,timestamp"
        vids = []
        for edge in ("top_media", "recent_media"):
            try:
                d = publish._req(f"{publish.G}/{h['id']}/{edge}?user_id={acc['ig_user_id']}&fields={f}&limit=50&access_token={acc['page_token']}")
            except Exception as e:
                log("hashtag", edge, "fail", tag, str(e)[:80]); continue
            for m in d.get("data", []):
                if m.get("media_type") != "VIDEO" or not m.get("media_url"):
                    continue                                # no file = licensed music, cannot be watched
                likes = (m.get("like_count") or 0) + 3 * (m.get("comments_count") or 0)
                try:
                    age_h = max(1.0, (now - time.mktime(time.strptime(m["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))) / 3600)
                except Exception:
                    age_h = 24.0
                if edge == "top_media" and likes >= min_likes:
                    m["_score"] = likes
                elif edge == "recent_media" and likes >= 200 and likes / age_h >= 20:   # real breakouts only (tested: broad tags are noise)
                    m["_score"] = likes / age_h * 24
                else:
                    continue
                vids.append(m)
        vids.sort(key=lambda m: -m["_score"])
        for m in vids[:per]:
            out.append({"id": m["permalink"], "url": m["permalink"], "video": m["media_url"], "title": (m.get("caption") or "")[:90],
                        "views": (m.get("like_count") or 0) * 30, "likes": m.get("like_count"), "comments": m.get("comments_count"),
                        "channel": "#" + tag, "followers": None})
        time.sleep(1)
    st[acc["ig_user_id"]] = mine
    save(HT_STATE, st)
    seen, uniq = set(), []
    for r in out:
        if r["url"] not in seen:
            seen.add(r["url"]); uniq.append(r)
    return _fit_reels(page, uniq)


def _fit_reels(page, rows):
    """Hashtags are global: #iphonetricks gave Arabic posts and street magic. One cheap planner call on the captions keeps
    only reels on our niche for an Indian (Hindi/Hinglish/English) audience, before any video is downloaded or watched."""
    if not rows:
        return rows
    try:
        import plan as planner
        lines = "\n".join(f'{i + 1}. [{r["channel"]}] {r["title"][:160]}' for i, r in enumerate(rows))
        r = planner.ask(f"Our page makes {NICHE.get(page, page)} for an Indian audience (Hindi, Hinglish or English).\n"
                        "Below are captions of Instagram reels found under hashtags. Keep a reel only if it is clearly on that niche "
                        "AND made for Indian / Hindi / Hinglish / English viewers (other languages, ads of big brands, "
                        "comedy, magic, music, memes = drop).\n" + lines +
                        '\nReturn JSON {"keep": [numbers of the reels to keep]}', max_tokens=400) or {}
        keep = {int(x) for x in r.get("keep", []) if str(x).isdigit()}
        kept = [x for i, x in enumerate(rows) if i + 1 in keep]
        log("hashtag reels:", len(rows), "found,", len(kept), "on niche")
        return kept
    except Exception as e:
        log("hashtag fit check failed", str(e)[:100]); return rows


def watch_file(mp4_url, prompt):
    """Instagram reel: download the file (<= 25 MB) and send it inline to Gemini (free keys), returns parsed JSON."""
    import base64, urllib.request, tts
    b = urllib.request.urlopen(urllib.request.Request(mp4_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read(26_000_000)
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(b).decode()}},
                                    {"text": __import__("core").dated(prompt) + "\n\nReturn ONLY valid JSON."}]}],
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
        ht = hashtag_top(page)                               # 18 Nov: smaller pages winning on the same topics
        found += ht
        log("hookstudy", page, "instagram reels found:", len(ig), "+ hashtag reels:", len(ht))
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
