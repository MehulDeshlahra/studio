"""First-comment question + replies to the top comments (Studio pages only, free Gemini keys, official APIs only).
Runs every 30 min (timer studio-comments, :25). For every video posted in the last 10 days, on each platform it was posted to:
  1. once: post the video's question as the first comment (plan.seo.comment_q). The APIs cannot PIN a comment; pin it by
     hand if you want (long-press the comment) - the question is already there as the first one.
  2. reply to the best unanswered comments (most liked, then newest): a short warm reply in the commenter's language.
     The reply may only use facts from the video's own script; for anything else it says thanks and that a video on it can
     come. No links, no promotion, no replies to abuse/spam (those are skipped, not answered).
  Caps: 6 replies per video per run, 15 per page per day. State: ~/studio-out/comments-state.json.
  When a video has a Part 2 queued for tomorrow (series.py), the first comment says so.
  python engine/comments.py [--dry]"""
import json, os, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save
import publish
G = publish.G
STATE = os.path.join(OUT, "comments-state.json")
DRY = "--dry" in sys.argv

REPLY = """You are the voice of the page "{name}" replying to comments on one of our Shorts. The video says:
\"\"\"{vo}\"\"\"
Comments (id | likes | text):
{items}
For each comment write ONE short reply (max 14 words), warm and human, in the commenter's own language (Hindi/Hinglish in Roman
letters, or English). Use ONLY facts that are in the video text above; if the comment asks something the video does not cover,
thank them and say a video on it can come. No links, no hashtags, no promotion, no emoji spam (max one emoji).
Return null for comments that are spam, abuse, hate, politics, about money/medical advice, or only a link/tag/emoji.
JSON {{"replies": {{"<id>": "reply text or null"}}}}"""


def _ig_comments(acc, media):
    d = publish._req(f"{G}/{media}/comments?fields=id,text,username,like_count,timestamp,replies.limit(3){{id,username}}&limit=50&access_token={acc['page_token']}")
    me = publish._req(f"{G}/{acc['ig_user_id']}?fields=username&access_token={acc['page_token']}").get("username")
    out = []
    for c in d.get("data", []):
        mine = c.get("username") == me or any(r.get("username") == me for r in (c.get("replies") or {}).get("data", []))
        out.append({"id": c["id"], "text": c.get("text", ""), "likes": c.get("like_count", 0), "answered": mine, "ts": c.get("timestamp", "")})
    return out


def _fb_comments(acc, vid):
    d = publish._req(f"{G}/{vid}/comments?fields=id,message,from,like_count,comment_count,created_time,comments.limit(3){{from}}&limit=50&access_token={acc['page_token']}")
    out = []
    for c in d.get("data", []):
        mine = (c.get("from") or {}).get("id") == acc["page_id"] or any((r.get("from") or {}).get("id") == acc["page_id"] for r in (c.get("comments") or {}).get("data", []))
        out.append({"id": c["id"], "text": c.get("message", ""), "likes": c.get("like_count", 0), "answered": mine, "ts": c.get("created_time", "")})
    return out


def _yt_token(acc):
    y = acc["yt"]
    return publish._req("https://oauth2.googleapis.com/token", {"client_id": y["client_id"], "client_secret": y["client_secret"],
                                                                "refresh_token": y["refresh_token"], "grant_type": "refresh_token"})["access_token"]


def _yt_comments(acc, vid):
    tok = _yt_token(acc)
    r = urllib.request.Request("https://www.googleapis.com/youtube/v3/commentThreads?part=snippet,replies&maxResults=50&order=relevance&videoId=" + vid,
                               headers={"Authorization": "Bearer " + tok})
    d = json.load(urllib.request.urlopen(r, timeout=60))
    out = []
    for t in d.get("items", []):
        sn = t["snippet"]["topLevelComment"]["snippet"]
        out.append({"id": t["snippet"]["topLevelComment"]["id"], "text": sn.get("textOriginal", ""), "likes": sn.get("likeCount", 0),
                    "answered": bool(t.get("replies")) or t["snippet"].get("canReply") is False, "ts": sn.get("publishedAt", "")})
    return out


def _post(acc, plat, target, text, reply_to=None):
    if DRY:
        log("comments DRY", plat, reply_to or target, text[:70]); return True
    if plat == "ig":
        publish._req(f"{G}/{reply_to}/replies" if reply_to else f"{G}/{target}/comments", {"message": text, "access_token": acc["page_token"]})
    elif plat == "fb":
        publish._req(f"{G}/{reply_to or target}/comments", {"message": text, "access_token": acc["page_token"]})
    else:
        tok = _yt_token(acc)
        body = ({"snippet": {"parentId": reply_to, "textOriginal": text}} if reply_to
                else {"snippet": {"videoId": target, "topLevelComment": {"snippet": {"textOriginal": text}}}})
        url = "https://www.googleapis.com/youtube/v3/" + ("comments" if reply_to else "commentThreads") + "?part=snippet"
        urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                               headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"}), timeout=60)
    return True


def run():
    import plan as planner
    from core import channel
    st = load(STATE, {}) or {}
    today = time.strftime("%Y-%m-%d")
    for cid in [c for c in os.listdir(os.path.join(ROOT, "channels")) if os.path.isdir(os.path.join(ROOT, "channels", c))]:
        acc = publish.resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
        if not acc:
            continue
        ch = channel(cid)
        done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
        used_today = st.setdefault("day", {}).setdefault(today + ":" + cid, 0)
        for row in done:
            pst = row.get("posted") or {}
            if row.get("status") != "posted" or not pst.get("at"):
                continue
            if time.time() - time.mktime(time.strptime(pst["at"], "%Y-%m-%d %H:%M")) > 10 * 86400:
                continue
            key = f"{cid}/{row['job']}"
            s = st.setdefault(key, {"asked": {}, "replied": []})
            plan = load(os.path.join(OUT, cid, row["job"], "plan.json"), {})
            vo = " ".join(x.get("vo", "") for x in plan.get("scenes", []))[:1500]
            q = ((plan.get("seo") or {}).get("comment_q") or plan.get("comment_q") or "").strip()
            for plat in ("ig", "fb", "yt"):
                target = pst.get(plat)
                if not target or (plat == "yt" and not acc.get("yt")) or (plat in ("ig", "fb") and not acc.get("page_token")):
                    continue
                try:
                    if q and not s["asked"].get(plat) and time.time() - time.mktime(time.strptime(pst["at"], "%Y-%m-%d %H:%M")) > 120:
                        if _post(acc, plat, target, q):
                            s["asked"][plat] = time.strftime("%H:%M"); log("comments first comment", cid, row["job"], plat)
                    cs = {"ig": _ig_comments, "fb": _fb_comments, "yt": _yt_comments}[plat](acc, target)
                    todo = [c for c in cs if not c["answered"] and c["id"] not in s["replied"] and c["text"].strip() and "http" not in c["text"].lower()
                            and c["text"].strip() != q]
                    todo.sort(key=lambda c: (-c["likes"], c["ts"]), reverse=False)
                    todo = todo[:min(6, max(0, 15 - used_today))]
                    if not todo:
                        continue
                    r = planner.ask(REPLY.format(name=ch.get("name", cid), vo=vo, items="\n".join(f"{c['id']} | {c['likes']} | {c['text'][:300]}" for c in todo)), max_tokens=1500) or {}
                    reps = (r.get("replies") if isinstance(r, dict) else None) or {}
                    for c in todo:
                        t = reps.get(c["id"])
                        s["replied"].append(c["id"])                      # even skipped ones: never look at them again
                        if t and isinstance(t, str) and 2 < len(t) < 220 and "http" not in t:
                            _post(acc, plat, target, t.strip(), reply_to=c["id"])
                            used_today += 1; log("comments reply", cid, plat, repr(c["text"][:40]), "->", repr(t[:50]))
                            time.sleep(4)
                except Exception as e:
                    log("comments fail", cid, row["job"], plat, str(e)[:160])
        st["day"][today + ":" + cid] = used_today
    st["day"] = {k: v for k, v in st["day"].items() if k[:10] >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))}
    save(STATE, st)


if __name__ == "__main__":
    run()
