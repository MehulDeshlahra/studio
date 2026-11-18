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


_YT_TOKEN = [None, 0]


def _yt_api(path):
    """YouTube Data API v3 with our own page's login (18 Nov: YouTube asks the server's datacenter IP to 'sign in to
    confirm you are not a bot' for full video pages, so yt-dlp -j fails here; the official API does not)."""
    import publish, urllib.request
    if not _YT_TOKEN[0] or time.time() - _YT_TOKEN[1] > 3000:
        acc = load(os.path.expanduser("~/.studio-accounts/tech.json")) or {}
        y = acc["yt"]
        _YT_TOKEN[0] = publish._req("https://oauth2.googleapis.com/token", {"client_id": y["client_id"], "client_secret": y["client_secret"],
                                    "refresh_token": y["refresh_token"], "grant_type": "refresh_token"})["access_token"]
        _YT_TOKEN[1] = time.time()
    r = urllib.request.Request("https://www.googleapis.com/youtube/v3/" + path, headers={"Authorization": "Bearer " + _YT_TOKEN[0]})
    return json.load(urllib.request.urlopen(r, timeout=30))


def sponsors(video_ids, cname):
    """Descriptions of recent videos (50 per API call, 1 quota unit): sponsor lines and the brands / links in them."""
    hits = []
    ids = [v for v in dict.fromkeys(video_ids) if v]
    for i in range(0, len(ids), 50):
        try:
            items = _yt_api("videos?part=snippet&id=" + ",".join(ids[i:i + 50])).get("items", [])
        except Exception as e:
            log("rivals: youtube api failed", str(e)[:120]); return hits
        for it in items:
            sn = it.get("snippet") or {}
            for line in (sn.get("description") or "").splitlines():
                if SPONSOR.search(line):
                    hits.append({"video": it["id"], "title": (sn.get("title") or "")[:90], "line": line.strip()[:220],
                                 "links": LINK.findall(line)[:3], "channel": cname, "date": (sn.get("publishedAt") or "")[:10]})
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
    leaders = sorted([kv for kv in ok.items() if subs(kv[1]) >= 100_000], key=lambda kv: -subs(kv[1]))[:8]
    rest = [kv for kv in ok.items() if kv[0] not in dict(leaders) and 10_000 <= subs(kv[1]) < 2_000_000 and kv[1].get("median", 0) >= 20_000]
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
    keys = list(todo)
    lines = [f'{i + 1}. "{todo[k]["name"]}" | about: {todo[k].get("about", "")[:160]} | Shorts: '
             + " / ".join(s["title"][:60] for s in (todo[k].get("shorts") or [])[:6]) for i, k in enumerate(keys)]
    r = planner.ask(f"Our page makes {hookstudy.NICHE.get(page, page)} for an Indian Hindi/Hinglish audience.\n"
                    "Label each YouTube channel below: \"direct\" = mostly the same kind of Shorts for the same audience "
                    "(Indian, Hindi/Hinglish); \"adjacent\" = same audience and same broad topic (e.g. phone reviews for a tech "
                    "explainer page, devotional songs for a mythology page): brands that sponsor them would sponsor us; "
                    "\"no\" = anything else (politics, podcasts, life hacks, comedy, vlogs, finance, news, YouTube-growth "
                    "tips, English-only, other countries).\n"
                    + "\n".join(lines) + '\nReturn JSON {"fit": ["direct"|"adjacent"|"no" for channel 1, 2, 3, ... in order]}', max_tokens=1500) or {}
    fit = r.get("fit")
    if isinstance(fit, list) and len(fit) == len(keys):
        for k, v in zip(keys, fit):
            v = str(v).lower()
            chans[k]["fit"] = v in ("direct", "adjacent", "true")
            chans[k]["kind"] = v if v in ("direct", "adjacent") else "no"
    else:
        log("rivals: niche check gave no usable answer", str(r)[:120])


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
        ids = [json.loads(l).get("id") for l in _yt(["--flat-playlist", "-j", "--playlist-end", "8", url]).splitlines() if l.strip().startswith("{")]
        ids += [s["id"] for s in (rec.get("shorts") or [])[:6]]
        hits += sponsors([i for i in ids if i], rec["name"])
    pb = bj.setdefault(page, {"hits": []})
    k = lambda h: (h["channel"], h["line"].lower()[:120])          # the same disclaimer on every video counts once
    seen, merged = set(), []
    for h in pb["hits"] + hits:
        if k(h) not in seen:
            seen.add(k(h)); merged.append(h)
    pb["hits"] = merged[-300:]
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
        L.append(f"## {r['name']} [{r.get('tier', '')}, {r.get('kind', '')}] ({subs:,} subs{', +%s in 7 days' % f'{g:,}' if g else ''}; usual Short {r.get('median', 0):,} views)")
        for s in r.get("outliers", [])[:4]:
            L.append(f"- {s['views']:,} views: {s['title'][:100]}")
    bj = (load(BRANDS, {}) or {}).get(page, {})
    if bj.get("hits"):
        L += ["", "## Brands that pay creators in this niche (from sponsor lines)"]
        for h in bj["hits"][-12:]:
            L.append(f"- {h['channel']}: {h['line'][:150]}")
    em = edit_metrics(page)
    if em:
        L += ["", "## How the winners edit (measured on the laptop from their real Shorts)", em]
    txt = "\n".join(L) + "\n"
    open(os.path.join(ROOT, "channels", page, "rivals.md"), "w", encoding="utf-8", newline="\n").write(txt)
    _measure_todo()
    return txt


METRICS = os.path.join(ROOT, "knowledge", "edit-metrics.json")


def _measure_todo():
    """The laptop's idle job list: every page's outlier Shorts not measured yet (tools/laptop_worker.py idle_work)."""
    db = load(STORE, {}) or {}
    have = {m["url"] for m in (load(METRICS, []) or [])}
    todo = []
    for page in PAGES:
        for cid, r in (db.get(page) or {}).get("channels", {}).items():
            for s in (r.get("outliers") or [])[:3]:
                u = f"https://www.youtube.com/shorts/{s['id']}"
                if u not in have:
                    todo.append({"url": u, "page": page, "channel": r["name"], "views": s["views"], "title": s["title"][:90]})
    os.makedirs(os.path.join(OUT, "laptop"), exist_ok=True)
    save(os.path.join(OUT, "laptop", "measure-todo.json"), todo[:120])


def collect_metrics():
    """Merge the laptop's measure-*.json results into knowledge/edit-metrics.json."""
    import glob
    allm = load(METRICS, []) or []
    seen = {m["url"] for m in allm}
    for f in sorted(glob.glob(os.path.join(OUT, "laptop", "done", "measure-*.json"))):
        try:
            for m in json.load(open(f)):
                if m.get("url") not in seen and not m.get("error"):
                    allm.append(m); seen.add(m["url"])
            os.remove(f)
        except Exception:
            pass
    save(METRICS, allm[-3000:])
    return allm


def edit_metrics(page):
    ms = [m for m in (load(METRICS, []) or []) if m.get("page") == page and m.get("dur")]
    if len(ms) < 3:
        return ""
    med = lambda k: statistics.median([m[k] for m in ms if m.get(k) is not None]) if any(m.get(k) is not None for m in ms) else None
    return (f"- {len(ms)} winning Shorts measured: median length {med('dur'):.0f} s, {med('cuts_per_10s'):.1f} cuts per 10 s, "
            f"first cut at {med('first_cut') or 0:.1f} s, loudness {med('lufs') or 0:.0f} LUFS")


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
    try:
        collect_metrics()
    except Exception as e:
        log("rivals: metrics merge failed", str(e)[:120])
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
