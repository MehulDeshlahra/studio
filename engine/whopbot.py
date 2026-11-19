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
 "other_footage": ["<Drive / Dropbox / other links given as footage>"],
 "rules": ["<every posting rule, short: length, required sound, on-screen text, what not to show, platforms>"],
 "caption_add": "<text the caption MUST contain: tags, @mentions, #ad, link text; empty if none>",
 "no_watermark": true/false, "min_s": <minimum clip length or null>, "max_s": <maximum or null>,
 "platforms": ["instagram","youtube","tiktok","x"]}}"""


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
    d = laptop.job({"kind": "whop", "cmd": cmd, "args": list(args)}, f"whop {cmd}", wait=wait)
    r = load(os.path.join(d, "result.json"), {}) or {}
    shot = os.path.join(d, "shot.png")
    if os.path.exists(shot):
        keep = os.path.join(OUT, CID, "whop-shots"); os.makedirs(keep, exist_ok=True)
        r["shot_server"] = os.path.join(keep, f"{time.strftime('%m%d-%H%M%S')}-{cmd}.png")
        os.replace(shot, r["shot_server"])
    return r


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
        r = _job("brief", v["url"])
        if r.get("error"):
            log("whopbot: brief failed", v.get("title"), r["error"][:120]); continue
        try:
            b = llm.text(READ.format(text=(r.get("text") or "")[:12000], links=", ".join(r.get("footage") or [])[:2000]), json_mode=True,
                         max_tokens=1500)
        except Exception as e:
            log("whopbot: brief read failed", str(e)[:120]); continue
        yt = [x for x in (b.get("youtube_videos") or []) + (r.get("footage") or []) if re.search(r"(youtube\.com/(watch|live|shorts)|youtu\.be/)", str(x))]
        chans = [x for x in (b.get("youtube_channels") or []) if x]
        if not b.get("can_do") or not (yt or chans):
            st.setdefault("skipped", {})[k] = {"title": v.get("title"), "why": b.get("why_not") or "no YouTube footage",
                                               "other": b.get("other_footage"), "t": now}
            log("whopbot: skip", v.get("title"), "-", b.get("why_not") or "no YouTube footage"); continue
        key = re.sub(r"[^a-z0-9]+", "-", (v.get("brand") or v.get("title") or "campaign").lower()).strip("-")[:30]
        while key in d["sources"] and d["sources"][key].get("campaign_id") != k:
            key += "-2"
        rules = [str(x)[:200] for x in b.get("rules") or []]
        if b.get("min_s") or b.get("max_s"):
            rules.append(f"clip length {b.get('min_s') or 20}-{b.get('max_s') or 58} s")
        d["sources"][key] = {"platform": "whop", "campaign_url": v["url"], "campaign_id": k, "title": v.get("title"),
                             "channels": chans, "videos": sorted(set(yt)), "match": chans + sorted(set(yt)), "rules": rules,
                             "caption_add": str(b.get("caption_add") or "")[:300], "no_watermark": bool(b.get("no_watermark")),
                             "platforms": b.get("platforms") or [], "clips_per_video": 4, "active": True, "auto": True,
                             "rate": (v.get("why") or [""])[0], "added": time.strftime("%Y-%m-%d %H:%M"), "added_t": now,
                             "brief_shot": r.get("shot_server")}
        active.add(k); joined.append(f"{v.get('score')}/100 {v.get('brand') or ''}: {v.get('title')} ({', '.join((v.get('why') or [])[:2])})")
        log("whopbot: joined", key, v.get("title"))
    if joined:
        _save_sources(d, f"whopbot: joined {len(joined)} campaign(s)")
        telegram("🤝 Joined on Whop and clipping now:\n• " + "\n• ".join(joined))
        os.system("sudo systemctl start --no-block studio-clipwatch.service")
    return joined


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
    join_best(st)
    st["last"] = time.strftime("%Y-%m-%d %H:%M")
    save(STATE, st)


if __name__ == "__main__":
    run()
