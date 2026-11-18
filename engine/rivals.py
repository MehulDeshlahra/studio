"""Competitor + brand intelligence (owner 18 Nov: "see competitors, what they are doing, how; think like a brand: why
would it collab with us; store it; adapt to the latest"). Free: yt-dlp + Instagram Business Discovery + one LLM call.
Per page, every day (timer studio-rivals 05:10, light):
  track     the top channels of the niche (found from the niche searches in hookstudy.QUERIES, plus RIVALS seeds):
            subscribers over time, their 30 latest Shorts with views, median views, posting pace
  outliers  Shorts with >= 3x the channel's median: proven topics -> channels/<id>/rivals.md (ideas.py reads it)
  brands    sponsor signals in descriptions (paid promotion, use code, coupon, app links, @brand) -> knowledge/brands.json:
            which brands pay creators in OUR niches, with the evidence (the outreach list for brand deals)
  weekly    one LLM read of all of it -> knowledge/rivals.md "what they do that we do not" + brain items
  python engine/rivals.py [page] [--weekly] [--discover]"""
import json, os, re, statistics, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, read

STORE = os.path.join(ROOT, "knowledge", "rivals.json")
BRANDS = os.path.join(ROOT, "knowledge", "brands.json")
YTDLP = os.path.expanduser("~/studio-venv/bin/yt-dlp")
PAGES = ("tech", "katha", "raaz")
RIVALS = {   # seeds; discovery adds the biggest channels that post Shorts in the niche
    "tech": ["@TechnicalGuruji", "@TechBurner", "@TrakinTech", "@GyanTherapy", "@TechWiserHindi", "@ManojSaru", "@samjhoexe"],
    "katha": ["@ShriKrishnaMeriKahani", "@BhaktiSagarAR", "@SanatanSamvad", "@IndianMythologyShorts", "@DharmikKahaniyan"],
    "raaz": ["@HindiKahaniyan", "@CrimeTak", "@HorrorStoriesHindi", "@NitishRajputHindi", "@SachiKahaniyan"],
}
MAX_TRACK = 14
SPONSOR = re.compile(r"(sponsor|paid promotion|paid partnership|#ad\b|#collab|in collaboration with|use (my )?code|coupon|promo ?code|"
                     r"discount code|download (the )?app|install now|affiliate|amzn\.to|bit\.ly|link in (the )?description|"
                     r"partnered with|thanks to .{2,40} for sponsoring|brought to you by)", re.I)
LINK = re.compile(r"https?://[^\s)]+", re.I)


def _yt(args, timeout=180):
    try:
        out = subprocess.run([YTDLP if os.path.exists(YTDLP) else "yt-dlp"] + args + ["--no-warnings"],
                             capture_output=True, text=True, timeout=timeout).stdout
    except Exception as e:
        log("rivals yt-dlp fail", str(e)[:100]); return ""
    return out


def channel(handle, n=30):
    """{id, name, subs, shorts: [{id, title, views}]} from the channel's Shorts tab (one request)."""
    url = handle if handle.startswith("http") else (f"https://www.youtube.com/channel/{handle}" if handle.startswith("UC")
                                                    else f"https://www.youtube.com/{handle}")
    try:
        d = json.loads(_yt(["--flat-playlist", "-J", "--playlist-end", str(n), url.rstrip("/") + "/shorts"]) or "{}")
    except ValueError:
        return None
    if not isinstance(d, dict) or not d.get("channel_id"):        # "null" for a missing channel
        return None
    shorts = [{"id": e["id"], "title": e.get("title") or "", "views": e.get("view_count") or 0}
              for e in d.get("entries") or [] if e.get("id")]
    return {"id": d["channel_id"], "name": d.get("channel") or handle, "handle": handle, "subs": d.get("channel_follower_count") or 0,
            "about": (d.get("description") or "")[:600], "shorts": shorts}


def discover(page, per_q=25):
    """Channels that post Shorts in the niche, biggest first (by subscribers)."""
    import hookstudy
    found = {}
    for q in hookstudy.QUERIES.get(page, [])[:5]:
        for line in _yt([f"ytsearch{per_q}:{q}", "--flat-playlist", "-j"]).splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            cid = e.get("channel_id")
            if cid and cid not in found:
                found[cid] = e.get("channel") or cid
    return list(found)


def sponsors(video_ids, cname):
    """Full metadata of a few recent videos: sponsor lines and the brands / links in them."""
    hits = []
    for vid in video_ids:
        try:
            d = json.loads(_yt(["-j", "--skip-download", f"https://www.youtube.com/watch?v={vid}"], 120) or "{}")
        except ValueError:
            continue
        desc = d.get("description") or ""
        for line in desc.splitlines():
            if SPONSOR.search(line):
                hits.append({"video": vid, "title": (d.get("title") or "")[:90], "line": line.strip()[:220],
                             "links": LINK.findall(line)[:3], "channel": cname, "date": d.get("upload_date")})
    return hits


def track(page, rediscover=False):
    db = load(STORE, {}) or {}
    pg = db.setdefault(page, {"channels": {}, "updated": ""})
    chans = pg["channels"]
    handles = list(RIVALS.get(page, []))
    if rediscover or len(chans) < 6:
        handles += discover(page)
    seen_ids = set(chans)
    day = time.strftime("%Y-%m-%d")
    known = [c.get("handle") or cid for cid, c in chans.items()]
    todo = list(dict.fromkeys(known + [h for h in handles if h not in known]))[:MAX_TRACK * 2 + 4]   # tracked first, then new ones
    for h in todo:
        c = channel(h)
        if not c or not c["shorts"]:
            continue
        rec = chans.setdefault(c["id"], {"name": c["name"], "handle": h, "subs_hist": [], "first": day})
        rec.update(name=c["name"], handle=h, about=c["about"])
        if not rec["subs_hist"] or rec["subs_hist"][-1][0] != day:
            rec["subs_hist"].append([day, c["subs"]]); rec["subs_hist"] = rec["subs_hist"][-120:]
        views = [s["views"] for s in c["shorts"] if s["views"]]
        rec["median"] = int(statistics.median(views)) if views else 0
        rec["shorts"] = c["shorts"][:30]
        rec["outliers"] = [s for s in c["shorts"] if rec["median"] and s["views"] >= 3 * rec["median"]][:6]
        seen_ids.add(c["id"])
        time.sleep(1)
    _fit(page, chans)
    # keep 8 leaders (most subscribers) + 6 climbers (smaller channels with big Shorts: how a NEW page grows), on niche only
    subs = lambda r: r["subs_hist"][-1][1] if r.get("subs_hist") else 0
    ok = {k: v for k, v in chans.items() if v.get("fit", True)}
    leaders = sorted(ok.items(), key=lambda kv: -subs(kv[1]))[:8]
    rest = [kv for kv in ok.items() if kv[0] not in dict(leaders) and subs(kv[1]) < 2_000_000]
    climbers = sorted(rest, key=lambda kv: -(kv[1].get("median", 0) / max(1, subs(kv[1]))))[:6]
    for k, v in leaders:
        v["tier"] = "leader"
    for k, v in climbers:
        v["tier"] = "climber"
    pg["channels"] = dict(leaders + climbers)
    pg["off_niche"] = sorted(set(pg.get("off_niche", [])) | {k for k, v in chans.items() if v.get("fit") is False})
    pg["updated"] = time.strftime("%Y-%m-%d %H:%M")
    save(STORE, db)
    return pg


def _fit(page, chans):
    """One planner call for every channel not judged yet: is it really a Hindi/Indian channel of this niche?"""
    import hookstudy, plan as planner
    todo = {k: v for k, v in chans.items() if "fit" not in v}
    if not todo:
        return
    lines = [f'{k}: "{v["name"]}" | about: {v.get("about", "")[:160]} | Shorts: ' + " / ".join(s["title"][:60] for s in (v.get("shorts") or [])[:6])
             for k, v in todo.items()]
    r = planner.ask(f"Our page makes {hookstudy.NICHE.get(page, page)} for an Indian Hindi/Hinglish audience.\n"
                    "For each YouTube channel below say if it is a DIRECT competitor: same kind of Shorts, same audience "
                    "(Indian, Hindi/Hinglish). Big general creators, English-only, vlogs, news, finance, comedy = false.\n"
                    + "\n".join(lines) + '\nReturn JSON {"fit": {"<channel id>": true|false}}', max_tokens=1500) or {}
    for k, v in (r.get("fit") or {}).items():
        if k in chans:
            chans[k]["fit"] = bool(v)


def growth(rec, days=7):
    h = rec.get("subs_hist") or []
    if len(h) < 2:
        return None
    old = next((x for x in h if (time.mktime(time.strptime(h[-1][0], "%Y-%m-%d")) - time.mktime(time.strptime(x[0], "%Y-%m-%d"))) <= days * 86400), h[0])
    return h[-1][1] - old[1]


def brand_scan(page):
    """Sponsor lines in the 4 newest videos (long ones carry most deals) of every tracked channel."""
    db = load(STORE, {}) or {}
    bj = load(BRANDS, {}) or {}
    hits = []
    for cid, rec in (db.get(page) or {}).get("channels", {}).items():
        url = f"https://www.youtube.com/channel/{cid}/videos"
        ids = [json.loads(l).get("id") for l in _yt(["--flat-playlist", "-j", "--playlist-end", "3", url]).splitlines() if l.strip().startswith("{")]
        ids += [s["id"] for s in (rec.get("shorts") or [])[:2]]
        hits += sponsors([i for i in ids if i], rec["name"])
    pb = bj.setdefault(page, {"hits": []})
    keys = {(h["video"], h["line"]) for h in pb["hits"]}
    pb["hits"] = (pb["hits"] + [h for h in hits if (h["video"], h["line"]) not in keys])[-300:]
    pb["updated"] = time.strftime("%Y-%m-%d %H:%M")
    save(BRANDS, bj)
    return hits


def page_md(page):
    """channels/<page>/rivals.md: what the planner and ideas.py read (proven topics + what the leaders do)."""
    db = load(STORE, {}) or {}
    chans = (db.get(page) or {}).get("channels", {})
    L = [f"# Rivals of {page} (engine/rivals.py, {time.strftime('%Y-%m-%d')})",
         "Proven topics = Shorts with 3x+ their channel's usual views. Never copy a title: take the QUESTION behind it.", ""]
    for cid, r in sorted(chans.items(), key=lambda kv: -(kv[1]["subs_hist"][-1][1] if kv[1].get("subs_hist") else 0)):
        subs = r["subs_hist"][-1][1] if r.get("subs_hist") else 0
        g = growth(r)
        L.append(f"## {r['name']} [{r.get('tier', '')}] ({subs:,} subs{', +%s in 7 days' % f'{g:,}' if g else ''}; usual Short {r.get('median', 0):,} views)")
        for s in r.get("outliers", [])[:4]:
            L.append(f"- {s['views']:,} views: {s['title'][:100]}")
    bj = (load(BRANDS, {}) or {}).get(page, {})
    if bj.get("hits"):
        L += ["", "## Brands that pay creators in this niche (from sponsor lines)"]
        for h in bj["hits"][-12:]:
            L.append(f"- {h['channel']}: {h['line'][:150]}")
    txt = "\n".join(L) + "\n"
    open(os.path.join(ROOT, "channels", page, "rivals.md"), "w", encoding="utf-8", newline="\n").write(txt)
    return txt


WEEKLY = """You are the strategy head of a small faceless media company with three Hindi pages (Instagram, YouTube, Facebook):
{pages}
Our own numbers so far: {ours}
Below is this week's competitor data per page (subscribers, growth, usual views, their biggest Shorts) and the sponsor lines
found in their descriptions. Think like (1) a viewer, (2) a growth strategist, (3) a BRAND deciding whom to pay.
DATA:
{data}
Return JSON {{"per_page": {{"<page>": {{"leaders_do": ["4-6 concrete things the top channels do that we do not (format, length,
cadence, series, hooks, thumbnails, CTAs)"], "proven_topics": ["5 topic questions taken from their outliers, rewritten for us"],
"gap": "the one opening nobody serves well that we can own", "brands": ["brands/categories that sponsor this niche"],
"why_a_brand_would_pick_us": "honest answer and what we must build first"}}}},
"money_moves": ["5 concrete actions this week that move us toward money (followers, reach, brand readiness), most valuable first"],
"brain": [{{"area": "growth|hook|ideas|script|visual|edit", "title": "...", "text": "a concrete, testable technique (<= 70 words)", "how": "where in our pipeline (<= 40 words)"}}]}}"""


def weekly():
    import plan as planner, brain
    db = load(STORE, {}) or {}
    bj = load(BRANDS, {}) or {}
    data = []
    for page in PAGES:
        chans = (db.get(page) or {}).get("channels", {})
        data.append(f"=== {page}")
        for cid, r in list(chans.items())[:10]:
            subs = r["subs_hist"][-1][1] if r.get("subs_hist") else 0
            data.append(f"- {r['name']}: {subs:,} subs, +{growth(r) or 0:,}/7d, usual {r.get('median', 0):,} views; top: "
                        + " | ".join(f"{s['views']:,} {s['title'][:70]}" for s in r.get("outliers", [])[:3]))
        for h in (bj.get(page) or {}).get("hits", [])[-10:]:
            data.append(f"  sponsor line ({h['channel']}): {h['line'][:140]}")
    pages = "; ".join(f"{p}: {(load(os.path.join(ROOT, 'channels', p, 'channel.json'), {}) or {}).get('format', '')[:160]}" for p in PAGES)
    ours = read(os.path.join(ROOT, "knowledge", "results.md"), 1500) or "no posts yet (launch 20 Nov)"
    r = planner.ask(WEEKLY.format(pages=pages, ours=ours, data="\n".join(data)[:24000]), max_tokens=6000) or {}
    if not r:
        return None
    L = [f"# Competitors and brands: weekly read ({time.strftime('%Y-%m-%d')}, engine/rivals.py --weekly)", ""]
    for page, x in (r.get("per_page") or {}).items():
        L += [f"## {page}", "What the leaders do that we do not:"] + [f"- {t}" for t in x.get("leaders_do", [])]
        L += ["Proven topics for us:"] + [f"- {t}" for t in x.get("proven_topics", [])]
        L += [f"Gap to own: {x.get('gap', '')}", f"Brands in this niche: {', '.join(x.get('brands', []))}",
              f"Why a brand would pick us: {x.get('why_a_brand_would_pick_us', '')}", ""]
    L += ["## Money moves this week"] + [f"{i + 1}. {t}" for i, t in enumerate(r.get("money_moves", []))]
    open(os.path.join(ROOT, "knowledge", "rivals.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    items = [i for i in r.get("brain", []) if isinstance(i, dict) and i.get("title")]
    if items:
        brain.add(items, "rivals:weekly")
    log("rivals weekly:", len(r.get("per_page") or {}), "pages,", len(items), "brain items")
    return r


def main():
    a = sys.argv[1:]
    pages = [x for x in a if x in PAGES] or list(PAGES)
    wk = "--weekly" in a or time.strftime("%a") == "Sun"
    for page in pages:
        try:
            pg = track(page, rediscover="--discover" in a or wk)
            if wk or "--brands" in a:
                brand_scan(page)
            page_md(page)
            log("rivals:", page, len(pg["channels"]), "channels tracked")
        except Exception as e:
            log("rivals failed", page, str(e)[:200])
    if wk:
        weekly()
    subprocess.run([sys.executable, os.path.join(ROOT, "engine", "sync.py")], timeout=300)


if __name__ == "__main__":
    main()
