"""Comment-to-DM + keyword DM replies for every Studio page (Instagram + Facebook/Messenger). Official Graph API only,
no webhook: polls every 10 min (timer studio-dm). Uses the same Ads MCP login as publish.py (owner's own pages need no App Review).

1. Comment keyword -> private reply (one DM per comment; Meta allows it within 7 days of the comment) + a short public reply
   "DM check karo" so others see it works.
2. Someone DMs the keyword (Instagram Direct or Messenger) -> same message, inside Meta's 24 h window only.

Message: if the page posted something AFTER the commented post (serial: the next part), link it; else "jaldi aa raha hai, follow
karo" + profile link. Per-channel config: channels/<id>/channel.json "dm" (keywords, text_next, text_wait, public_reply).

API budget (shared with posting on the Ads MCP app, which hit Meta's #4 app limit on 18 Nov): comments come NESTED in the media
call, page key + username are cached for 12 h, so a page costs ~5 calls a run. Every response's X-App-Usage is read; above 60 %
the run stops and the next runs skip for 30 min. Caps: 40 DMs per page per day, one DM per person per post.
State ~/studio-out/dm-state.json. New channel = add ~/.studio-accounts/<id>.json (page_id); Instagram "Allow access to
messages" must be ON in the app.

Human Agent (7-day window, 18 Nov): Meta allows the HUMAN_AGENT tag only for a real person answering, never for a bot. So the bot
never uses it. Keyword DMs that arrive older than 23 h (poller paused, DMs stopped, window missed) are listed in Telegram once
("late"), and the owner sends the reply himself:
  python engine/dm.py --human <channel> <ig|messenger> <recipient_id> "text"      (tag HUMAN_AGENT, up to 7 days after the message)
  python engine/dm.py [--dry] [--only <channel>]"""
import datetime, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import OUT, log, load, save, channel, telegram
G = "https://graph.facebook.com/v23.0"
STATE = os.path.join(OUT, "dm-state.json")
DRY = "--dry" in sys.argv
ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
DAY_CAP, LOOKBACK_DAYS, USAGE_STOP = 40, 7, 60
DEFAULT = {
    "raaz": {"keywords": ["PART2", "PART 2", "AAGE"], "cta": "Comment karo \"PART2\", agla part seedha DM mein 📩"},
    "katha": {"keywords": ["AAGE", "KATHA", "PART2", "PART 2"], "cta": "Comment karo \"AAGE\", agli katha seedha DM mein 📩",
              "text_next": "Ye rahi agli katha 👇\n{next}\n\nRoz ek katha ke liye follow karo {handle}",
              "text_wait": "Agli katha jaldi aa rahi hai! Follow karo {handle} taaki miss na ho 🔔\n{profile}"},
    "tech": {"keywords": ["TECH", "LINK", "PART2", "PART 2"], "cta": "Comment karo \"TECH\", agla explainer seedha DM mein 📩",
             "text_next": "Ye raha agla explainer 👇\n{next}\n\nAise aur ke liye follow karo {handle}",
             "text_wait": "Agla explainer jaldi aa raha hai! Follow karo {handle} taaki miss na ho 🔔\n{profile}"},
}

def cta(cid):
    """Caption line that tells viewers the keyword (seo.text_for adds it on Instagram + Facebook). "" = none."""
    try:
        return _cfg(cid).get("cta", "")
    except Exception:
        return ""
BASE = {
    "keywords": ["PART2", "PART 2"],
    "text_next": "Ye raha agla part 👇\n{next}\n\nAise aur ke liye follow karo {handle}",
    "text_wait": "Agla part jaldi aa raha hai! Follow karo {handle} taaki miss na ho 🔔\n{profile}",
    "public_reply": "DM check karo 📩",
}

class Busy(Exception):
    pass

class Blocked(Exception):
    """Meta restricted messaging on this page (spam / action block): stop sending for the rest of the day and tell the owner."""

USAGE = {"max": 0}

def _r(url, data=None):
    """One Graph call. Keeps Meta's error text and tracks X-App-Usage / X-Business-Use-Case-Usage."""
    body = urllib.parse.urlencode(data).encode() if data else None
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=60)
        out = json.load(resp)
        hdrs = resp.headers
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("error", {})
        except ValueError:
            err = {}
        if err.get("code") in (368, 1390008, 2018292) or "temporarily blocked" in (err.get("message") or "").lower():
            raise Blocked(f"#{err.get('code')} {err.get('message', '')[:140]}")
        if err.get("code") in (4, 17, 32, 613, 80001, 80002, 80005, 80006):
            USAGE["max"] = 100
            raise Busy(f"#{err.get('code')} {err.get('message', '')[:120]}")
        raise RuntimeError(f"{e.code} #{err.get('code')}/{err.get('error_subcode')} {err.get('message', str(e))[:160]}")
    for h in ("X-App-Usage", "X-Business-Use-Case-Usage"):
        v = hdrs.get(h)
        if v:
            nums = [int(x) for x in re.findall(r'"(?:call_count|total_cputime|total_time)"\s*:\s*(\d+)', v)]
            USAGE["max"] = max([USAGE["max"]] + nums)
    if USAGE["max"] >= USAGE_STOP:
        raise Busy(f"app usage {USAGE['max']}%")
    return out

def _cfg(cid):
    c = dict(BASE); c.update(DEFAULT.get(cid, {}))
    c.update((channel(cid) or {}).get("dm") or {})
    c["keywords"] = [k.upper() for k in c["keywords"]]
    return c

def _match(text, kws):
    t = re.sub(r"\s+", " ", " " + re.sub(r"[^A-Z0-9 ]", " ", (text or "").upper()) + " ")
    return any(f" {k} " in t or (" " not in k and k in t.replace(" ", "")) for k in kws)

def _ts(s):
    try:
        return datetime.datetime.fromisoformat((s or "").replace("+0000", "+00:00")).timestamp()
    except ValueError:
        return 0

def _token_file():
    """Own app first: Planstalk Connect user token (~/.studio-meta-connect.token, own rate budget); else the shared Ads MCP
    login used for posting (its app-wide limit #4 was hit on 18 Nov, so DMs should not live on it)."""
    own = os.path.expanduser("~/.studio-meta-connect.token")
    return own if os.path.exists(own) and os.path.getsize(own) > 20 else os.path.expanduser("~/.studio-meta-user.token")

def _account(cid, st):
    """page key, ig id, username: cached 12 h (2-3 calls saved per run)."""
    c = st.setdefault("acc", {}).get(cid)
    if c and time.time() - c.get("at", 0) < 12 * 3600:
        return c
    a = load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")) or {}
    if not a.get("page_id"):
        return None
    if a.get("page_token"):
        c = {"page_id": a["page_id"], "page_token": a["page_token"]}
    else:
        ut = open(_token_file()).read().strip()
        d = _r(f"{G}/{a['page_id']}?fields=access_token,instagram_business_account{{id,username}}&access_token={ut}")
        c = {"page_id": a["page_id"], "page_token": d["access_token"]}
        if d.get("instagram_business_account"):
            c["ig_user_id"] = d["instagram_business_account"]["id"]
            c["ig_username"] = d["instagram_business_account"].get("username", "")
    c["at"] = time.time()
    st["acc"][cid] = c
    return c

CF_IG = "id,text,username,from,timestamp"
CF_FB = "id,message,from,created_time"

def _media(acc, plat):
    """Recent posts WITH their comments, one call per edge."""
    tok = acc["page_token"]
    if plat == "ig":
        d = _r(f"{G}/{acc['ig_user_id']}/media?fields=id,permalink,timestamp,comments.limit(50){{{CF_IG}}}&limit=15&access_token={tok}")
        return [{"id": m["id"], "url": m.get("permalink", ""), "t": _ts(m.get("timestamp")),
                 "c": [{"id": c["id"], "text": c.get("text", ""), "who": (c.get("from") or {}).get("id") or c.get("username", ""),
                        "user": c.get("username", ""), "t": _ts(c.get("timestamp"))} for c in (m.get("comments") or {}).get("data", [])]}
                for m in d.get("data", [])]
    out, seen = [], set()
    for edge in ("video_reels", "posts"):
        try:
            d = _r(f"{G}/{acc['page_id']}/{edge}?fields=id,permalink_url,created_time,comments.limit(50){{{CF_FB}}}&limit=15&access_token={tok}")
        except RuntimeError as e:
            log("dm fb media fail", edge, str(e)[:120]); continue
        for m in d.get("data", []):
            if m["id"] in seen:
                continue
            seen.add(m["id"])
            url = m.get("permalink_url", "")
            if url.startswith("/"):
                url = "https://www.facebook.com" + url
            out.append({"id": m["id"], "url": url, "t": _ts(m.get("created_time")),
                        "c": [{"id": c["id"], "text": c.get("message", ""), "who": (c.get("from") or {}).get("id", ""),
                               "user": (c.get("from") or {}).get("name", ""), "t": _ts(c.get("created_time"))}
                              for c in (m.get("comments") or {}).get("data", [])]})
    return out

def _links(acc):
    h = acc.get("ig_username") or ""
    return ("@" + h if h else ""), (f"https://instagram.com/{h}" if h else "")

def _text(cfg, acc, media, after_t):
    handle, profile = _links(acc)
    newer = sorted([x for x in media if x["t"] > after_t and x.get("url")], key=lambda x: x["t"])
    if newer:
        return cfg["text_next"].format(next=newer[0]["url"], handle=handle, profile=profile).strip()
    return cfg["text_wait"].format(handle=handle, profile=profile).strip()

BLOCK_CODES = ("#368/", "#10/", "#100/33", "#613/", "spam", "blocked", "temporarily")

def _blocked(st, cid, msg):
    """Meta spam/action-block style errors: stop all DMs for 24 h and tell the owner once (never keep hammering a flagged page)."""
    if any(b in msg for b in BLOCK_CODES):
        st["block_until"] = time.time() + 24 * 3600
        log("dm STOPPED 24 h", cid, msg[:120])
        try:
            telegram(f"⚠ Studio DM bot stopped for 24 h: Meta refused a DM on '{cid}' ({msg[:140]}). Nothing to do unless it repeats tomorrow.")
        except Exception:
            pass

def _send(acc, sender_id, recipient, text):
    if DRY:
        log("dm DRY", sender_id, json.dumps(recipient), text[:90].replace("\n", " | ")); return
    _r(f"{G}/{sender_id}/messages", {"recipient": json.dumps(recipient), "message": json.dumps({"text": text}),
                                     "access_token": acc["page_token"]})

def _public(acc, plat, comment_id, text):
    if DRY or not text:
        return
    try:
        _r(f"{G}/{comment_id}/replies" if plat == "ig" else f"{G}/{comment_id}/comments", {"message": text, "access_token": acc["page_token"]})
    except RuntimeError as e:
        log("dm public reply fail", plat, str(e)[:120])

def comments_to_dm(cid, acc, cfg, st, budget, media_by):
    sent = 0
    me = {acc.get("ig_user_id"), acc.get("page_id"), acc.get("ig_username")}
    for plat in ("ig", "fb"):
        media = media_by.get(plat) or []
        sender = acc.get("ig_user_id") if plat == "ig" else acc["page_id"]
        for m in media:
            for c in m["c"]:
                if sent >= budget:
                    return sent
                key, pkey = f"{plat}:{c['id']}", f"{plat}:{m['id']}:{c['who']}"
                if key in st["done"] or c["who"] in me or c["user"] in me or time.time() - c["t"] > LOOKBACK_DAYS * 86400:
                    continue
                if not _match(c["text"], cfg["keywords"]):
                    continue
                if DRY:
                    _send(acc, sender, {"comment_id": c["id"]}, _text(cfg, acc, media, m["t"])); continue
                st["done"][key] = int(time.time())
                if pkey in st["done"]:
                    continue
                try:
                    _send(acc, sender, {"comment_id": c["id"]}, _text(cfg, acc, media, m["t"]))
                    st["done"][pkey] = int(time.time()); sent += 1
                    log("dm sent", cid, plat, c["user"], repr(c["text"][:30]))
                    _public(acc, plat, c["id"], cfg.get("public_reply"))
                    time.sleep(2)
                except RuntimeError as e:
                    log("dm send fail", cid, plat, c["id"], str(e)[:200])
                    _blocked(st, cid, str(e))
                    if "#10900" in str(e) or "#551" in str(e) or "#100" in str(e):
                        continue                                    # this comment/person cannot be DMed; go on with the next one
    return sent

def send_human(cid, plat, rid, text):
    """Owner-triggered reply with the HUMAN_AGENT tag (7 days). Not used by the poller."""
    st = load(STATE, {}) or {}
    acc = _account(cid, st)
    sender = acc["ig_user_id"] if plat in ("ig", "instagram") else acc["page_id"]
    _r(f"{G}/{sender}/messages", {"recipient": json.dumps({"id": rid}), "messaging_type": "MESSAGE_TAG", "tag": "HUMAN_AGENT",
                                  "message": json.dumps({"text": text}), "access_token": acc["page_token"]})
    print("sent with HUMAN_AGENT tag")

def inbox_keywords(cid, acc, cfg, st, budget, media_by):
    """Keyword typed in DM: one answer per message, only inside the 24 h window."""
    sent = 0
    mine = {acc.get("ig_user_id"), acc.get("page_id")}
    for plat in ("instagram", "messenger"):
        if plat == "instagram" and not acc.get("ig_user_id"):
            continue
        sender = acc["ig_user_id"] if plat == "instagram" else acc["page_id"]
        try:
            d = _r(f"{G}/{acc['page_id']}/conversations?platform={plat}&fields=messages.limit(1){{id,message,from,created_time}}"
                   f"&limit=20&access_token={acc['page_token']}")
        except RuntimeError as e:
            log("dm inbox fail", cid, plat, str(e)[:150]); continue
        for conv in d.get("data", []):
            if sent >= budget:
                return sent
            msg = ((conv.get("messages") or {}).get("data") or [{}])[0]
            frm = (msg.get("from") or {}).get("id")
            if not msg.get("id") or frm in mine:
                continue
            age = time.time() - _ts(msg.get("created_time"))
            if age > 23 * 3600:
                lk = f"late:{msg['id']}"
                if age < 7 * 86400 and lk not in st["done"] and _match(msg.get("message", ""), cfg["keywords"]) and not DRY:
                    st["done"][lk] = int(time.time())
                    try:
                        telegram(f"Studio DM, window missed ({cid}, {plat}): '{msg.get('message', '')[:60]}' from {frm}. Reply yourself within 7 days:\n"
                                 f"python engine/dm.py --human {cid} {plat} {frm} \"text\"")
                    except Exception:
                        pass
                continue
            key = f"msg:{msg['id']}"
            if key in st["done"] or not _match(msg.get("message", ""), cfg["keywords"]):
                continue
            text = _text(cfg, acc, media_by.get("ig" if plat == "instagram" else "fb") or [], 0)
            if DRY:
                _send(acc, sender, {"id": frm}, text); continue
            st["done"][key] = int(time.time())
            try:
                _send(acc, sender, {"id": frm}, text)
                sent += 1; log("dm inbox reply", cid, plat, frm)
                time.sleep(2)
            except RuntimeError as e:
                log("dm inbox send fail", cid, plat, str(e)[:200])
                _blocked(st, cid, str(e))
    return sent

def run():
    st = load(STATE, {}) or {}
    st.setdefault("done", {}); st.setdefault("day", {})
    if (time.time() < st.get("pause_until", 0) or time.time() < st.get("block_until", 0)) and not DRY:
        return
    today = time.strftime("%Y-%m-%d")
    adir = os.path.expanduser("~/.studio-accounts")
    try:
        for f in sorted(os.listdir(adir)) if os.path.isdir(adir) else []:
            cid = f[:-5]
            if not f.endswith(".json") or (ONLY and cid != ONLY):
                continue
            try:
                acc = _account(cid, st)
            except RuntimeError as e:
                log("dm account fail", cid, str(e)[:150]); continue
            if not acc:
                continue
            cfg, dk = _cfg(cid), today + ":" + cid
            used = st["day"].get(dk, 0)
            media_by = {}
            for plat in ("ig", "fb"):
                if plat == "ig" and not acc.get("ig_user_id"):
                    continue
                try:
                    media_by[plat] = [m for m in _media(acc, plat) if time.time() - m["t"] < 30 * 86400]
                except RuntimeError as e:
                    log("dm media fail", cid, plat, str(e)[:150])
            if DRY:
                log("dm DRY", cid, {p: f"{len(v)} posts / {sum(len(m['c']) for m in v)} comments" for p, v in media_by.items()},
                    "@" + acc.get("ig_username", ""), "usage", USAGE["max"])
            used += comments_to_dm(cid, acc, cfg, st, DAY_CAP - used, media_by)
            used += inbox_keywords(cid, acc, cfg, st, DAY_CAP - used, media_by)
            st["day"][dk] = used
    except Blocked as e:
        st["pause_until"] = time.mktime(time.strptime(today, "%Y-%m-%d")) + 86400 + 3600     # rest of today + 1 h
        log("dm BLOCKED by Meta, stopped until tomorrow:", str(e))
        if not DRY:
            try:
                from core import telegram
                telegram("⚠ Studio DM bot: Meta limited messaging on a page (" + str(e)[:140] + "). Stopped until tomorrow; nothing else is affected.")
            except Exception as te:
                log("dm telegram fail", str(te)[:80])
    except Busy as e:
        st["pause_until"] = time.time() + 30 * 60          # leave the shared app budget to posting for 30 min
        log("dm paused 30 min (Meta app limit, posting goes first):", str(e))
    cut = time.time() - 40 * 86400
    st["done"] = {k: v for k, v in st["done"].items() if v > cut}
    st["day"] = {k: v for k, v in st["day"].items() if k[:10] >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))}
    save(STATE, st)                                        # dry runs never mark anything sent (only caches / pause are kept)
    try:
        os.chmod(STATE, 0o600)                             # the file caches page keys
    except OSError:
        pass

if __name__ == "__main__":
    if "--human" in sys.argv:
        a = sys.argv[sys.argv.index("--human") + 1:]
        send_human(a[0], a[1], a[2], a[3])
    else:
        run()
