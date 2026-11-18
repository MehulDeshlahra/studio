"""Money milestones per page (owner 18 Nov: "the ultimate goal is to earn money"). Daily, free, official APIs only:
followers on Instagram / Facebook / YouTube + YouTube Shorts views of the last 90 days, compared with every payout gate.
Writes knowledge/money.json (history) and the "Money" block of STATE.md; the weekly report and the Mehul agent read it.
Gates (checked 18 Nov 2026, sources in knowledge/MONEY.md):
  YouTube  fan funding / Shopping: 500 subs + 3 public uploads in 90 days + 3M Shorts views in 90 days
           ad revenue (YPP): 1,000 subs + 10M Shorts views in 90 days (new applicants: 20M from Feb 2027)
  Instagram Gifts 500 followers, Creator Marketplace 1,000 (brands find you), Subscriptions 10,000
  Facebook  Stars 500 followers for 30 days; Content Monetization by invite
  Brands    real deals start around 10,000 followers with steady views (micro tier Rs 8,000-50,000 a reel)
  python engine/money.py [--print]"""
import json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save

STORE = os.path.join(ROOT, "knowledge", "money.json")
PAGES = ("tech", "katha", "raaz")
GATES = [("yt", "subs", 500, "YouTube fan funding (+3M Shorts views/90d)"),
         ("yt", "subs", 1000, "YouTube ads (+10M Shorts views/90d; 20M from Feb 2027)"),
         ("ig", "followers", 500, "Instagram Gifts"), ("ig", "followers", 1000, "Instagram Creator Marketplace"),
         ("fb", "followers", 500, "Facebook Stars"), ("ig", "followers", 10000, "brand deals + IG Subscriptions")]


def yt_numbers(acc):
    import publish
    y = acc.get("yt")
    if not y:
        return {}
    tok = publish._req("https://oauth2.googleapis.com/token", {"client_id": y["client_id"], "client_secret": y["client_secret"],
                       "refresh_token": y["refresh_token"], "grant_type": "refresh_token"})["access_token"]
    H = {"Authorization": f"Bearer {tok}"}
    c = json.load(urllib.request.urlopen(urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/channels?part=statistics&mine=true", headers=H), timeout=30))["items"][0]["statistics"]
    out = {"subs": int(c.get("subscriberCount", 0)), "views_total": int(c.get("viewCount", 0)), "videos": int(c.get("videoCount", 0))}
    try:                                                  # Analytics: views of the last 90 days (scope may be missing)
        end = time.strftime("%Y-%m-%d"); start = time.strftime("%Y-%m-%d", time.localtime(time.time() - 90 * 86400))
        a = json.load(urllib.request.urlopen(urllib.request.Request(
            f"https://youtubeanalytics.googleapis.com/v2/reports?ids=channel==MINE&startDate={start}&endDate={end}&metrics=views",
            headers=H), timeout=30))
        out["views_90d"] = int((a.get("rows") or [[0]])[0][0])
    except Exception:
        out["views_90d"] = None
    return out


def numbers(cid):
    import publish
    acc = publish.resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")) or {})
    n = {}
    try:
        if acc.get("ig_user_id"):
            u = publish._req(f"{publish.G}/{acc['ig_user_id']}?fields=followers_count,media_count&access_token={acc['page_token']}")
            n["ig"] = {"followers": u.get("followers_count", 0), "posts": u.get("media_count", 0)}
        if acc.get("page_id"):
            p = publish._req(f"{publish.G}/{acc['page_id']}?fields=followers_count,fan_count&access_token={acc['page_token']}")
            n["fb"] = {"followers": p.get("followers_count") or p.get("fan_count") or 0}
    except Exception as e:
        log("money: meta numbers failed", cid, str(e)[:120])
    try:
        n["yt"] = yt_numbers(acc)
    except Exception as e:
        log("money: youtube numbers failed", cid, str(e)[:120])
    return n


def run():
    db = load(STORE, {}) or {}
    day = time.strftime("%Y-%m-%d")
    for cid in PAGES:
        n = numbers(cid)
        h = db.setdefault(cid, [])
        if h and h[-1]["day"] == day:
            h[-1] = {"day": day, **n}
        else:
            h.append({"day": day, **n})
        db[cid] = h[-400:]
    save(STORE, db)
    return db


def _rate(h, plat, key, days=7):
    pts = [(x["day"], (x.get(plat) or {}).get(key)) for x in h if (x.get(plat) or {}).get(key) is not None]
    if len(pts) < 2:
        return None
    d0 = next((p for p in pts if (time.mktime(time.strptime(pts[-1][0], "%Y-%m-%d")) - time.mktime(time.strptime(p[0], "%Y-%m-%d"))) <= days * 86400), pts[0])
    span = max(1, (time.mktime(time.strptime(pts[-1][0], "%Y-%m-%d")) - time.mktime(time.strptime(d0[0], "%Y-%m-%d"))) / 86400)
    return (pts[-1][1] - d0[1]) / span


def lines():
    db = load(STORE, {}) or {}
    L = []
    for cid in PAGES:
        h = db.get(cid) or []
        if not h:
            continue
        x = h[-1]
        ig, fb, yt = x.get("ig") or {}, x.get("fb") or {}, x.get("yt") or {}
        s = (f"- {cid}: IG {ig.get('followers', '-')} · FB {fb.get('followers', '-')} · YT {yt.get('subs', '-')} subs"
             + (f", {yt['views_90d']:,} views/90d" if yt.get("views_90d") is not None else ""))
        nxt = []
        for plat, key, need, what in GATES:
            have = (x.get(plat) or {}).get(key)
            if have is None or have >= need:
                continue
            r = _rate(h, plat, key)
            eta = f", ~{(need - have) / r:.0f} days at the 7-day pace" if r and r > 0 else ""
            nxt.append(f"{what}: {have}/{need}{eta}")
            if len(nxt) >= 2:
                break
        L.append(s + (" | next: " + "; ".join(nxt) if nxt else ""))
    return L


if __name__ == "__main__":
    run()
    print("\n".join(lines()))
