"""Comment-to-DM + keyword DM replies for every Studio page (Instagram + Facebook/Messenger). Official Graph API only,
no webhook: polls every 5 min (timer studio-dm). Uses the same Ads MCP login as publish.py (owner's own pages need no App Review).

1. Comment keyword -> private reply (one DM per comment, Meta allows it within 7 days of the comment) + a short public reply
   "DM check karo" so others see it works.
2. Someone DMs the keyword (Instagram Direct or Messenger) -> same message, inside Meta's 24 h window only.

Message: if the page posted something AFTER the commented post (serial: the next part), link it; else "kal aa raha hai, follow karo"
+ profile link. Per-channel config in channels/<id>/channel.json "dm" (keywords, text_next, text_wait, public_reply); defaults below.
Caps: 40 DMs per page per day, one DM per person per post. State ~/studio-out/dm-state.json.
New channel = add ~/.studio-accounts/<id>.json (page_id); Instagram "Allow access to messages" must be ON in the app.
  python engine/dm.py [--dry] [--only <channel>]"""
import json, os, re, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, channel
import publish
G = publish.G
STATE = os.path.join(OUT, "dm-state.json")
DRY = "--dry" in sys.argv
ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
DAY_CAP, LOOKBACK_DAYS = 40, 7

def _r(url, data=None):
    """publish._req, but Meta's error text is kept (urllib hides it)."""
    import urllib.error
    try:
        return publish._req(url, data)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", {})
            raise RuntimeError(f"{e.code} #{msg.get('code')}/{msg.get('error_subcode')} {msg.get('message', '')[:160]}")
        except (ValueError, AttributeError):
            raise RuntimeError(str(e))
DEFAULT = {
    "raaz": {"keywords": ["PART2", "PART 2", "AAGE"]},
    "katha": {"keywords": ["KATHA", "AAGE", "PART2", "PART 2"]},
    "tech": {"keywords": ["TECH", "LINK", "PART2", "PART 2"]},
}
BASE = {
    "keywords": ["PART2", "PART 2"],
    "text_next": "Ye raha agla part 👇\n{next}\n\nAise aur ke liye follow karo {handle}",
    "text_wait": "Agla part jaldi aa raha hai! Follow karo {handle} taaki miss na ho 🔔\n{profile}",
    "public_reply": "DM check karo 📩",
}

def _cfg(cid):
    c = dict(BASE); c.update(DEFAULT.get(cid, {}))
    c.update((channel(cid) or {}).get("dm") or {})
    c["keywords"] = [k.upper() for k in c["keywords"]]
    return c

def _match(text, kws):
    t = " " + re.sub(r"[^A-Z0-9 ]", " ", (text or "").upper()) + " "
    t = re.sub(r"\s+", " ", t)
    return any(f" {k} " in t or (" " not in k and k in t.replace(" ", "")) for k in kws)

def _ts(s):
    s = s.replace("+0000", "+00:00")
    try:
        import datetime
        return datetime.datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0

def _send(acc, sender_id, recipient, text):
    if DRY:
        log("dm DRY", sender_id, recipient, text[:80].replace("\n", " | ")); return True
    _r(f"{G}/{sender_id}/messages", {"recipient": json.dumps(recipient), "message": json.dumps({"text": text}),
                                               "access_token": acc["page_token"]})
    return True

def _public(acc, plat, comment_id, text):
    if DRY or not text:
        return
    try:
        _r(f"{G}/{comment_id}/replies" if plat == "ig" else f"{G}/{comment_id}/comments",
                     {"message": text, "access_token": acc["page_token"]})
    except Exception as e:
        log("dm public reply fail", plat, str(e)[:120])

def _media(acc, plat):
    tok = acc["page_token"]
    if plat == "ig":
        d = _r(f"{G}/{acc['ig_user_id']}/media?fields=id,permalink,timestamp&limit=30&access_token={tok}")
        return [{"id": m["id"], "url": m.get("permalink", ""), "t": _ts(m.get("timestamp", ""))} for m in d.get("data", [])]
    out = []
    for edge in ("video_reels", "posts"):
        try:
            f = "id,permalink_url,created_time" if edge == "posts" else "id,permalink_url,created_time"
            d = _r(f"{G}/{acc['page_id']}/{edge}?fields={f}&limit=30&access_token={tok}")
            out += [{"id": m["id"], "url": m.get("permalink_url", ""), "t": _ts(m.get("created_time", ""))} for m in d.get("data", [])]
        except Exception as e:
            log("dm fb media fail", edge, str(e)[:100])
    seen, uniq = set(), []
    for m in out:
        if m["id"] not in seen:
            seen.add(m["id"]); uniq.append(m)
    return uniq

def _comments(acc, plat, mid):
    tok = acc["page_token"]
    if plat == "ig":
        d = _r(f"{G}/{mid}/comments?fields=id,text,username,from,timestamp&limit=50&access_token={tok}")
        return [{"id": c["id"], "text": c.get("text", ""), "who": ((c.get("from") or {}).get("id") or c.get("username", "")),
                 "user": c.get("username", ""), "t": _ts(c.get("timestamp", ""))} for c in d.get("data", [])]
    d = _r(f"{G}/{mid}/comments?fields=id,message,from,created_time&limit=50&access_token={tok}")
    return [{"id": c["id"], "text": c.get("message", ""), "who": (c.get("from") or {}).get("id", ""), "user": (c.get("from") or {}).get("name", ""),
             "t": _ts(c.get("created_time", ""))} for c in d.get("data", [])]

def _text(cfg, acc, media, m):
    handle = "@" + (acc.get("ig_username") or "").lstrip("@") if acc.get("ig_username") else ""
    profile = f"https://instagram.com/{acc['ig_username']}" if acc.get("ig_username") else ""
    newer = sorted([x for x in media if x["t"] > m["t"] and x.get("url")], key=lambda x: x["t"])
    if newer:
        return cfg["text_next"].format(next=newer[0]["url"], handle=handle, profile=profile).strip()
    return cfg["text_wait"].format(handle=handle, profile=profile).strip()

def comments_to_dm(cid, acc, cfg, st, budget):
    sent = 0
    for plat in ("ig", "fb"):
        if plat == "ig" and not acc.get("ig_user_id"):
            continue
        sender = acc["ig_user_id"] if plat == "ig" else acc["page_id"]
        me = {acc.get("ig_user_id"), acc.get("page_id"), acc.get("ig_username")}
        try:
            media = _media(acc, plat)
        except Exception as e:
            log("dm media fail", cid, plat, str(e)[:150]); continue
        for m in [x for x in media if time.time() - x["t"] < 30 * 86400]:
            try:
                cs = _comments(acc, plat, m["id"])
            except Exception as e:
                log("dm comments fail", cid, plat, m["id"], str(e)[:120]); continue
            for c in cs:
                if sent >= budget:
                    return sent
                key = f"{plat}:{c['id']}"
                pkey = f"{plat}:{m['id']}:{c['who']}"
                if key in st["done"] or c["who"] in me or c["user"] in me or time.time() - c["t"] > LOOKBACK_DAYS * 86400:
                    continue
                if not _match(c["text"], cfg["keywords"]):
                    continue
                st["done"][key] = int(time.time())
                if pkey in st["done"]:
                    continue
                try:
                    _send(acc, sender, {"comment_id": c["id"]}, _text(cfg, acc, media, m))
                    st["done"][pkey] = int(time.time()); sent += 1
                    log("dm sent", cid, plat, c["user"], repr(c["text"][:30]))
                    _public(acc, plat, c["id"], cfg.get("public_reply"))
                    time.sleep(3)
                except Exception as e:
                    log("dm send fail", cid, plat, c["id"], str(e)[:200])
    return sent

def inbox_keywords(cid, acc, cfg, st, budget):
    """Someone typed the keyword in DM: answer once per conversation per day, only inside the 24 h window."""
    sent = 0
    for plat in ("instagram", "messenger"):
        if plat == "instagram" and not acc.get("ig_user_id"):
            continue
        sender = acc["ig_user_id"] if plat == "instagram" else acc["page_id"]
        mine = {acc.get("ig_user_id"), acc.get("page_id")}
        try:
            d = _r(f"{G}/{acc['page_id']}/conversations?platform={plat}&fields=updated_time,messages.limit(1){{id,message,from,created_time}}"
                             f"&limit=25&access_token={acc['page_token']}")
        except Exception as e:
            log("dm inbox fail", cid, plat, str(e)[:150]); continue
        for conv in d.get("data", []):
            if sent >= budget:
                return sent
            msg = ((conv.get("messages") or {}).get("data") or [{}])[0]
            frm = (msg.get("from") or {}).get("id")
            if not msg.get("id") or frm in mine or time.time() - _ts(msg.get("created_time", "")) > 23 * 3600:
                continue
            key = f"msg:{msg['id']}"
            if key in st["done"] or not _match(msg.get("message", ""), cfg["keywords"]):
                continue
            st["done"][key] = int(time.time())
            try:
                media = _media(acc, "ig" if plat == "instagram" else "fb")
                latest = max(media, key=lambda x: x["t"]) if media else None
                text = (cfg["text_next"].format(next=latest["url"], handle="@" + acc.get("ig_username", ""),
                                               profile=f"https://instagram.com/{acc.get('ig_username', '')}") if latest and latest.get("url")
                        else _text(cfg, acc, [], {"t": 0}))
                _send(acc, sender, {"id": frm}, text)
                sent += 1; log("dm inbox reply", cid, plat, frm)
                time.sleep(3)
            except Exception as e:
                log("dm inbox send fail", cid, plat, str(e)[:200])
    return sent

def run():
    st = load(STATE, {}) or {}
    st.setdefault("done", {}); st.setdefault("day", {})
    today = time.strftime("%Y-%m-%d")
    adir = os.path.expanduser("~/.studio-accounts")
    for f in sorted(os.listdir(adir)) if os.path.isdir(adir) else []:
        cid = f[:-5]
        if not f.endswith(".json") or (ONLY and cid != ONLY):
            continue
        try:
            acc = publish.resolve(load(os.path.join(adir, f)))
        except Exception as e:
            log("dm resolve fail", cid, str(e)[:150]); continue
        if not acc or not acc.get("page_token"):
            continue
        if acc.get("ig_user_id") and not acc.get("ig_username"):
            try:
                acc["ig_username"] = _r(f"{G}/{acc['ig_user_id']}?fields=username&access_token={acc['page_token']}").get("username", "")
            except Exception:
                acc["ig_username"] = ""
        cfg = _cfg(cid)
        dk = today + ":" + cid
        used = st["day"].get(dk, 0)
        used += comments_to_dm(cid, acc, cfg, st, DAY_CAP - used)
        used += inbox_keywords(cid, acc, cfg, st, DAY_CAP - used)
        st["day"][dk] = used
    cut = time.time() - 40 * 86400
    st["done"] = {k: v for k, v in st["done"].items() if v > cut}
    st["day"] = {k: v for k, v in st["day"].items() if k[:10] >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))}
    if not DRY:
        save(STATE, st)

if __name__ == "__main__":
    run()
