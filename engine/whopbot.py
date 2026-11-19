"""Whop autopilot for Cut Capsule (19 Nov, owner: "you are asking me too much, let's automate"). Uses the owner's saved Whop
login on the laptop (tools/whop.py through the laptop worker). Every 2 h (timer studio-whopbot):

1 submit   every posted campaign clip (done.json "submit", from publish.py) is submitted on its campaign page.
2 join     keeps up to MAX_ACTIVE campaigns running: the best-scored ones from engine/campaigns.py (>= JOIN_MIN) are joined,
           their brief is read, and an LLM turns it into a source entry (footage links, rules, required caption text,
           no-watermark) in channels/cutcapsule/sources.json -> engine/clipwatch.py clips it. A brief whose footage is not on
           YouTube (Drive, Dropbox...) or that needs face-cam / original content is skipped and noted.
3 retire   a source whose campaign budget is gone (or that left the directory) is switched off.
Only Telegram on what changed (joined X, submitted N, a failure). Never joins betting / other-language / zero-rate ones
(campaigns.py scores them 0)."""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, telegram
import llm

CID = "cutcapsule"
SRC = os.path.join(ROOT, "channels", CID, "sources.json")
DONE = os.path.join(ROOT, "channels", CID, "done.json")
CAMP = os.path.join(OUT, "campaigns.json")
STATE = os.path.join(OUT, "whopbot.json")
MAX_ACTIVE, JOIN_MIN = 5, 75

READ = """You read a paid clipping campaign brief for the clip page "Cut Capsule" (Instagram Reels, YouTube Shorts, Facebook;
English/Hinglish; we cut vertical clips from long YouTube videos automatically: no face cam, no voice-over, no original
filming). BRIEF PAGE TEXT:
{text}
LINKS FOUND: {links}
Return JSON:
{{"can_do": true/false, "why_not": "<if false: what we cannot do (needs face cam / original video / not on YouTube / UGC talking to camera / app demo...)>",
 "youtube_channels": ["<@handle or channel URL of the footage creator, only if the brief says to clip that channel>"],
 "youtube_videos": ["<YouTube video / live URLs given as footage>"],
 "youtube_search": ["<ALWAYS, when the footage is official brand/studio videos: a YouTube search for each named video (game/brand + video name, e.g. 'Metaphor ReFantazio Heismay Trailer'); used only if the footage links fail>"],
 "official_channel": "<the brand's official YouTube channel name if footage is its official videos, else empty>",
 "other_footage": ["<Drive / Dropbox / other links given as footage>"],
 "rules": ["<every posting rule, short: length, required sound, on-screen text, what not to show, platforms>"],
 "caption_add": "<LITERAL caption text, pasted as-is (never an instruction): EVERYTHING the caption must contain, in the order the brief asks: disclosure hashtag first (#Ad) if required, required @mentions, required lines word for word (e.g. a free-trial line, 'Blue in the Face, on Netflix'), link text; empty if none>",
 "footage_pages": ["<footage hosts that are not YouTube/Drive: Frame.io (f.io), MediaSilo, Dropbox, WeTransfer links>"],
 "no_music": true/false,
 "no_watermark": true/false, "min_s": <minimum clip length or null>, "max_s": <maximum or null>,
 "platforms": ["instagram","youtube","tiktok","x"],
 "not_paid_countries": ["<countries whose views are NOT paid, e.g. India, Pakistan, Bangladesh>"],
 "audience_rule": "<e.g. '70%+ views from US', empty if none>"}}
Footage given as a Google Doc / "content folder" link counts: list every link found in the doc text in other_footage."""


def _sources():
    d = load(SRC, {}) or {}
    d.setdefault("sources", {})
    return d


def _save_sources(d, msg):
    save(SRC, d)
    os.system(f"cd {ROOT} && git add channels/{CID}/sources.json && git commit -qm '{msg}' >/dev/null 2>&1 && "
              "git pull -q --rebase --autostash && git push -q >/dev/null 2>&1")


def _job(cmd, *args, wait=900):
    import laptop
    try:     # 19 Nov: the laptop busy with a long transcribe = "did not pick the job up", which crashed the whole run
        d = laptop.job({"kind": "whop", "cmd": cmd, "args": list(args)}, f"whop {cmd}", wait=wait)
    except Exception as e:
        log("whopbot: laptop job failed", cmd, str(e)[:150])
        return {"error": str(e)[:300]}
    r = load(os.path.join(d, "result.json"), {}) or {}
    shot = os.path.join(d, "shot.png")
    if os.path.exists(shot):
        keep = os.path.join(OUT, CID, "whop-shots"); os.makedirs(keep, exist_ok=True)
        r["shot_server"] = os.path.join(keep, f"{time.strftime('%m%d-%H%M%S')}-{cmd}.png")
        os.replace(shot, r["shot_server"])
    return r


def _yt_find(q, official=""):
    """Best YouTube match for a named official video: the result from a channel whose name contains the brand wins."""
    import urllib.parse, rivals
    try:
        d = rivals._yt_api("search?part=snippet&type=video&maxResults=8&q=" + urllib.parse.quote(q))
    except Exception as e:
        log("whopbot: YouTube search failed", q, str(e)[:100]); return None
    items = [it for it in d.get("items") or [] if (it.get("id") or {}).get("videoId")]
    if not items:
        return None
    off = re.sub(r"[^a-z0-9]", "", official.lower())
    words = [w for w in re.findall(r"[a-z0-9]{3,}", q.lower())]

    def rank(it):
        sn = it.get("snippet") or {}
        ch = re.sub(r"[^a-z0-9]", "", (sn.get("channelTitle") or "").lower())
        title = (sn.get("title") or "").lower()
        return (bool(off) and (off in ch or ch in off), sum(w in title for w in words))
    best = max(items, key=rank)
    return "https://www.youtube.com/watch?v=" + best["id"]["videoId"]


def logged_in():
    try:
        return bool(_job("check", wait=300).get("logged_in"))
    except Exception as e:
        log("whopbot: check failed", str(e)[:120]); return False


def submit_all(st):
    done = load(DONE, []) or []
    n_ok, fails = 0, []
    for d in done:
        s = d.get("submit") or {}
        if not s.get("campaign") or s.get("submitted") or s.get("tries", 0) >= 3:
            continue
        for link in s.get("links") or []:
            if link in (s.get("ok_links") or []) or not link.startswith("http"):
                continue
            r = _job("submit", s["campaign"], link)
            if r.get("ok"):
                s.setdefault("ok_links", []).append(link); n_ok += 1
            else:
                fails.append(f"{d['job']}: {r.get('why') or r.get('error') or 'not confirmed'}")
        s["tries"] = s.get("tries", 0) + 1
        if set(s.get("ok_links") or []) >= {x for x in s.get("links") or [] if x.startswith("http")}:
            s["submitted"] = time.strftime("%Y-%m-%d %H:%M")
    save(DONE, done)
    if n_ok or fails:
        telegram(f"💰 Whop: {n_ok} clip link(s) submitted." + ("\n⚠ Not submitted: " + "; ".join(fails[:4]) if fails else ""))
    return n_ok


def join_best(st):
    camp = (load(CAMP, {}) or {}).get("c") or {}
    d = _sources()
    active = {v.get("campaign_id") for v in d["sources"].values() if v.get("active", True) and v.get("campaign_id")}
    tried = st.setdefault("tried", {})
    now = time.time()
    picks = sorted(((k, v) for k, v in camp.items() if now - v.get("last_seen", 0) < 86400 and v.get("score", 0) >= JOIN_MIN
                    and k not in active and now - tried.get(k, 0) > 7 * 86400), key=lambda kv: -kv[1]["score"])
    joined = []
    for k, v in picks:
        if len(active) >= MAX_ACTIVE:
            break
        tried[k] = now
        res = make_source(k, v, d, st)          # opens the campaign (joins it) + reads the brief
        if not res:
            continue
        active.add(k); joined.append(f"{v.get('score')}/100 " + res)
    if joined:
        _save_sources(d, f"whopbot: joined {len(joined)} campaign(s)")
        telegram("🤝 Joined on Whop and clipping now:\n• " + "\n• ".join(joined))
        os.system("sudo systemctl start --no-block studio-clipwatch.service")
    return joined


def adopt_joined(st):
    """19 Nov (owner joined 5 himself): campaigns on his Content Rewards 'Campaigns' page that have no source yet get one."""
    r = _job("look", "https://contentrewards.com/c/campaigns", wait=600)
    text = r.get("text") or ""
    camp = (load(CAMP, {}) or {}).get("c") or {}
    d = _sources()
    have = {v.get("campaign_id") for v in d["sources"].values()}
    low = text.lower()
    # each joined card reads "Joined\n<brand>\n· 6d ago\n<title>"; a brand renames its campaign sometimes (Eneba's
    # "Eneba Clipping and UGC" shows as "BroPacks - Discover Games on Eneba"), so a brand with ONE campaign also matches
    nb = {}
    for v in camp.values():
        nb[(v.get("brand") or "").lower()] = nb.get((v.get("brand") or "").lower(), 0) + 1
    sk = st.get("skipped") or {}
    mine = [k for k, v in camp.items() if v.get("title") and k not in have and
            time.time() - (sk.get(k) or {}).get("t", 0) > 7 * 86400 and
            (v["title"][:40].lower() in low or k in text or
             (v.get("brand") and nb.get(v["brand"].lower()) == 1 and f"joined\n{v['brand'].lower()}\n" in low))]
    log("whopbot: joined by the owner without a source:", [camp[k]["title"] for k in mine])
    added = []
    for k in mine:
        res = make_source(k, camp[k], d, st)
        if res:
            added.append(res)
    if added:
        _save_sources(d, f"whopbot: sources for {len(added)} joined campaign(s)")
        telegram("✂️ Clipping now for the campaigns you joined:\n• " + "\n• ".join(added))
        os.system("sudo systemctl start --no-block studio-clipwatch.service")
    return added


def make_source(k, v, d, st):
    """Read the brief of a joined campaign and write its source entry. Returns a one-line summary, or None (skipped)."""
    now = time.time()
    r = _job("brief", v["url"])
    if r.get("error"):
        log("whopbot: brief failed", v.get("title"), r["error"][:120])
        st.get("tried", {}).pop(k, None)          # a laptop hiccup is not a verdict on the campaign: try again next run
        return None
    try:
        # 19 Nov: studio-text's big model took 8-10 min per 18k-char brief; Gemini Flash-Lite reads it in seconds
        p = READ.format(text=(r.get("text") or "")[:18000], links=", ".join(r.get("footage") or [])[:2000])
        b = llm._chain(["gemini/gemini-3.1-flash-lite"] + llm.TEXT_MODELS, p + "\n\nReturn ONLY valid JSON, no other text.",
                       True, 3000, timeout=120)
    except Exception as e:
        log("whopbot: brief read failed", str(e)[:120]); return None
    foot = [x for x in (b.get("youtube_videos") or []) + (b.get("other_footage") or []) + (b.get("footage_pages") or [])
            + (r.get("footage") or [])
            if re.search(r"(youtube\.com/(watch|live|shorts)|youtu\.be/|drive\.google\.com/(file|drive/folders|drive/u/\d+/folders)"
                         r"|(^|//|\.)(f\.io|frame\.io|wetransfer\.com|we\.tl)/)", str(x))]
    # 19 Nov (SEGA): footage named but not linked ("use the Launch Trailer"): find each on YouTube, preferring the brand's channel
    # (also when the only footage link is dead: CoD's MediaSilo folder says "This link could not be found")
    for q in ([] if foot else (b.get("youtube_search") or []))[:4]:
        u = _yt_find(str(q), str(b.get("official_channel") or ""))
        if u:
            foot.append(u); log("whopbot: found footage on YouTube", q, "->", u)
    # one link per footage item: "...folders/X?usp=sharing" and "...folders/X" are the same folder (transcribed twice before)
    foot = list(dict.fromkeys(re.sub(r"\?usp=\w+$", "", str(x).rstrip("/.,")) for x in foot))
    chans = [x for x in (b.get("youtube_channels") or []) if x]
    # 19 Nov: Flash-Lite once said "can do" for Eneba, whose brief bans automated clipping. Hard rules in code, not the model:
    brief = r.get("text") or ""
    ban = re.search(r"(no|not allow\w*|prohibit\w*|ban\w*)[^.\n]{0,40}automat\w* (clipping|edit\w*|content)|automat\w* (clipping|edit\w*)"
                    r"[^.\n]{0,30}(not allowed|prohibited|banned|rejected)|(must|required to) (add|include) your own (voice|face|reaction)",
                    brief, re.I)
    if ban:
        b["can_do"], b["why_not"] = False, f"brief bans automated clipping ('{ban.group(0)[:80]}')"
    cap = str(b.get("caption_add") or "")
    if re.search(r"\(or |first hashtag|on its own line|must include|put it", cap, re.I):   # an instruction, not caption text
        cap = " ".join(dict.fromkeys(re.findall(r"(?<![\w/])[#@][A-Za-z0-9_.]{2,30}", cap)))
        cap = re.sub(r"#Advertisement|#Sponsored", "", cap).strip()
    if re.search(r"#ad\b", brief, re.I) and "#ad" not in cap.lower():
        cap = ("#Ad\n" + cap).strip()
    b["caption_add"] = cap
    pl = " ".join(str(x).lower() for x in b.get("platforms") or [])
    if pl and not re.search(r"instagram|reels|youtube|shorts|facebook", pl):
        b["can_do"], b["why_not"] = False, f"only for {pl} (we post to Instagram, Facebook, YouTube)"
    if not b.get("can_do") or not (foot or chans):
        st.setdefault("skipped", {})[k] = {"title": v.get("title"), "why": b.get("why_not") or "no usable footage",
                                           "other": b.get("other_footage"), "t": now}
        log("whopbot: skip", v.get("title"), "-", b.get("why_not") or "no usable footage")
        telegram(f"⏭ Can't clip '{v.get('title')}': {b.get('why_not') or 'no YouTube/Drive footage in the brief'}")
        return None
    key = re.sub(r"[^a-z0-9]+", "-", (v.get("brand") or v.get("title") or "campaign").lower()).strip("-")[:30]
    while key in d["sources"] and d["sources"][key].get("campaign_id") != k:
        key += "-2"
    rules = [str(x)[:200] for x in b.get("rules") or []]
    if b.get("min_s") or b.get("max_s"):
        rules.append(f"clip length {b.get('min_s') or 20}-{b.get('max_s') or 58} s")
    d["sources"][key] = {"platform": "whop", "campaign_url": v["url"], "campaign_id": k, "title": v.get("title"),
                         "channels": chans, "videos": sorted(set(foot)), "match": chans + sorted(set(foot)), "rules": rules,
                         "caption_add": str(b.get("caption_add") or "")[:300], "no_watermark": bool(b.get("no_watermark")),
                         "platforms": b.get("platforms") or [], "clips_per_video": 4, "active": True,
                         "not_paid_countries": b.get("not_paid_countries") or [], "audience_rule": b.get("audience_rule") or "",
                         "rate": (v.get("why") or [""])[0], "added": time.strftime("%Y-%m-%d %H:%M"), "added_t": now,
                         "brief": (r.get("text") or "")[:6000], "brief_shot": r.get("shot_server")}
    log("whopbot: source", key, v.get("title"), "footage", len(foot), "channels", len(chans))
    return f"{v.get('brand') or ''}: {v.get('title')} ({len(foot)} footage link(s), {len(rules)} rules)"


def retire(st):
    camp = (load(CAMP, {}) or {}).get("c") or {}
    d = _sources()
    off = []
    for key, s in d["sources"].items():
        c = camp.get(s.get("campaign_id") or "")
        if not s.get("active", True) or not s.get("campaign_id"):
            continue
        gone = not c or time.time() - c.get("last_seen", 0) > 2 * 86400 or (c.get("availableBudgetRaw") or 0) < 50
        if gone:
            s["active"] = False; s["retired"] = time.strftime("%Y-%m-%d %H:%M"); off.append(key)
    if off:
        _save_sources(d, f"whopbot: retired {', '.join(off)}")
        telegram("🛑 Campaign budget finished, stopped clipping: " + ", ".join(off))


def run():
    import laptop
    st = load(STATE, {}) or {}
    if not laptop.available():
        log("whopbot: the laptop is off"); return
    if not logged_in():
        if time.time() - st.get("told_login", 0) > 86400:
            telegram("🔑 Whop login needed once on the laptop: run  python tools\\whop.py login  (or tell Kiro). "
                     "Joining + submitting is automatic after that.")
            st["told_login"] = time.time(); save(STATE, st)
        return
    submit_all(st)
    retire(st)
    adopt_joined(st)
    join_best(st)
    st["last"] = time.strftime("%Y-%m-%d %H:%M")
    save(STATE, st)


if __name__ == "__main__":
    run()
