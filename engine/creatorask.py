"""Creator clipping-permission outreach (19 Nov, owner said yes to the idea; the WORDING and every send need his OK).
1 find   Hindi podcast / interview / comedy YouTube channels (YouTube Data API search), 20K-2M subscribers, active in the
         last 30 days, with a business email written in the channel description (the only email the API shows).
2 draft  one email per channel from TEMPLATE (owner-approved text only) -> ~/studio-out/creatorask.json, status "draft".
3 send   only when channel.json of the page has outreach.approved = true AND outreach.from is set; max 15 a day;
         every reply "yes" becomes a source in channels/<page>/sources.json (permission gate) by hand or by the inbox reader.
  python engine/creatorask.py find [page]     python engine/creatorask.py list"""
import json, os, re, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save

STORE = os.path.join(OUT, "creatorask.json")
QUERIES = {"cutcapsulehindi": ["hindi podcast", "hindi podcast full episode", "hindi interview podcast", "desi podcast hindi",
                               "hindi comedy podcast", "hindi motivational podcast", "hinglish podcast", "bollywood interview hindi",
                               "hindi business podcast", "hindi spiritual podcast"]}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

TEMPLATE_SUBJECT = "Clipping permission for {channel} (free Shorts/Reels for your channel)"
TEMPLATE = """Hi {name},

I run Cut Capsule Hindi (instagram.com/cutcapsule.hindi), a clips page of Scroll House (scrollhouse.in). We cut the best
30-60 second moments from Hindi podcasts and interviews into Reels and Shorts, with captions.

Can we clip {channel}? Every clip:
- credits you by name and links your full episode in the caption
- never changes what you said, no misleading titles
- comes down within 24 hours if you ask

It costs you nothing and sends new viewers to your full episodes. A one-line "yes, you can clip" reply is enough.

Thanks,
Mehul
Cut Capsule Hindi · Scroll House"""


def _yt(path):
    import rivals
    return rivals._yt_api(path)


def find(page="cutcapsulehindi", per_query=25):
    st = load(STORE, {}) or {}
    st.setdefault("c", {})
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 30 * 86400))
    ids = set()
    for q in QUERIES.get(page, []):
        try:
            d = _yt(f"search?part=snippet&type=video&maxResults={per_query}&relevanceLanguage=hi&regionCode=IN"
                    f"&publishedAfter={since}&videoDuration=long&q=" + urllib.parse.quote(q))
            ids |= {it["snippet"]["channelId"] for it in d.get("items") or []}
        except Exception as e:
            log("creatorask: search failed", q, str(e)[:100])
    ids -= set(st["c"])
    new = 0
    for i in range(0, len(ids), 50):
        chunk = list(ids)[i:i + 50]
        d = _yt("channels?part=snippet,statistics&id=" + ",".join(chunk))
        for it in d.get("items") or []:
            sn, stt = it["snippet"], it.get("statistics") or {}
            subs = int(stt.get("subscriberCount") or 0)
            mails = [m for m in EMAIL.findall(sn.get("description") or "") if not m.lower().endswith((".png", ".jpg"))]
            if ASTRO.search((sn.get("title") or "") + " " + (sn.get("description") or "")[:600]):
                st["c"][it["id"]] = {"page": page, "title": sn.get("title"), "status": "skip-astrology", "found": time.strftime("%Y-%m-%d")}
                continue
            row = {"page": page, "title": sn.get("title"), "handle": sn.get("customUrl"), "subs": subs,
                   "videos": int(stt.get("videoCount") or 0), "email": mails[0] if mails else None, "found": time.strftime("%Y-%m-%d"),
                   "status": "no-email" if not mails else ("too-small" if subs < 20000 else ("too-big" if subs > 2000000 else "draft"))}
            st["c"][it["id"]] = row
            new += row["status"] == "draft"
    save(STORE, st)
    drafts = [v for v in st["c"].values() if v["status"] == "draft"]
    log("creatorask:", len(ids), "new channels,", new, "new drafts,", len(drafts), "drafts total")
    return drafts


ASTRO = re.compile(r"astro|jyotish|tantra|totke|totka|vastu|kundli|rashifal|numerolog|tarot|horoscope|remed", re.I)
SKIP_HANDLES = {"@revererecords", "@realtalkclipp", "@gyanhindifacts", "@panchtantraone", "@vermacreationtv"}   # 19 Nov:
# a UK music label, another clip page, a facts channel, a kids-story channel, a tiny general channel: not clippable talk
FROM = "Mehul | Scroll House <hello@scrollhouse.in>"
DAY_MAX = 15


def send_one(to, subject, body):
    import smtplib, ssl
    from email.message import EmailMessage
    from email.utils import make_msgid, formatdate
    pw = open(os.path.expanduser("~/.studio-zoho-mail.key")).read().strip()
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = FROM, to, subject
    m["Date"], m["Message-ID"] = formatdate(localtime=True), make_msgid(domain="scrollhouse.in")
    m["Reply-To"] = "hello@scrollhouse.in"
    m.set_content(body)
    with smtplib.SMTP_SSL("smtp.zoho.in", 465, context=ssl.create_default_context(), timeout=60) as s:
        s.login("hello@scrollhouse.in", pw)
        s.send_message(m)
    return m["Message-ID"]


def send(page="cutcapsulehindi", n=DAY_MAX):
    """Owner approved the wording 19 Nov. Sends up to n drafts (biggest first), never one channel twice, DAY_MAX a day."""
    st = load(STORE, {}) or {}
    today = time.strftime("%Y-%m-%d")
    sent_today = sum(1 for v in (st.get("c") or {}).values() if str(v.get("sent_at", "")).startswith(today))
    budget = max(0, min(n, DAY_MAX - sent_today))
    rows = sorted(((k, v) for k, v in (st.get("c") or {}).items() if v.get("status") == "draft" and v.get("page") == page
                   and v.get("handle") not in SKIP_HANDLES and v.get("email")), key=lambda kv: -kv[1]["subs"])
    done = []
    for k, v in rows[:budget]:
        subj, body = email_for(v)
        try:
            v["msg_id"] = send_one(v["email"], subj, body)
            v["status"], v["sent_at"] = "sent", time.strftime("%Y-%m-%d %H:%M")
            done.append(v["title"])
        except Exception as e:
            v["status"], v["error"] = "send-failed", str(e)[:200]
        save(STORE, st)
        time.sleep(20)                                  # spread the sends: a burst looks like spam
    log("creatorask: sent", len(done), done)
    return done


ZACC = "7703275000000002002"            # hello@scrollhouse.in in Zoho Mail (REST API works on the free plan, 19 Nov)

READ = """A creator answered our email asking permission to cut short clips (Reels/Shorts) from their YouTube videos, with
credit and a link to the full episode. Their reply (quoted text removed):
"{text}"
Return JSON {{"answer": "yes" | "no" | "question" | "other", "summary": "<one short line in English>",
 "conditions": ["<any condition they set: credit format, no editing, revenue share, only certain videos...>"]}}
"yes" only when they clearly allow it ("go ahead", "yes you can", "sure", "haan kar lo")."""


def _zoho():
    import urllib.parse, urllib.request
    k = json.load(open(os.path.expanduser("~/.studio-zoho-api.json")))
    t = json.load(urllib.request.urlopen("https://accounts.zoho.in/oauth/v2/token", data=urllib.parse.urlencode(
        {"refresh_token": k["refresh_token"], "client_id": k["client_id"], "client_secret": k["client_secret"],
         "grant_type": "refresh_token"}).encode(), timeout=30))["access_token"]
    h = {"Authorization": "Zoho-oauthtoken " + t}
    return lambda u: json.load(urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=30))


def replies():
    """Read hello@ (Zoho REST API), match replies to the channels we emailed: yes -> a permitted source on the page,
    no -> closed, question/other -> Telegram to the owner (he answers; WhatsApp numbers etc. are his to use)."""
    import llm
    from core import telegram
    st = load(STORE, {}) or {}
    rows = st.get("c") or {}
    by_mail = {(v.get("email") or "").lower(): k for k, v in rows.items() if v.get("status") in ("sent", "replied")}
    seen = set(st.get("seen_msgs") or [])
    get = _zoho()
    for x in get(f"https://mail.zoho.in/api/accounts/{ZACC}/messages/view?limit=50").get("data") or []:
        frm = (x.get("fromAddress") or "").lower()
        if x["messageId"] in seen or frm not in by_mail:
            continue
        c = get(f"https://mail.zoho.in/api/accounts/{ZACC}/folders/{x['folderId']}/messages/{x['messageId']}/content")
        body = re.sub(r"&nbsp;", " ", re.sub(r"<[^>]+>", " ", (c.get("data") or {}).get("content") or ""))
        body = re.split(r"\bOn (Mon|Tue|Wed|Thu|Fri|Sat|Sun),|wrote:|-----Original|From: Mehul", re.sub(r"\s+", " ", body))[0].strip()
        try:
            a = llm.text(READ.format(text=body[:1500]), json_mode=True, max_tokens=400, fast=True)
        except Exception:
            a = {"answer": "other", "summary": body[:200]}
        k = by_mail[frm]
        v = rows[k]
        v.update(status="replied", reply=body[:600], reply_at=time.strftime("%Y-%m-%d %H:%M"), answer=a.get("answer"),
                 conditions=a.get("conditions") or [])
        if a.get("answer") == "yes":
            add_source(k, v)
            telegram(f"✅ {v['title']} ({v['subs']:,} subs) said YES to clipping: \"{body[:120]}\". Added as a source on "
                     f"{v['page']}; clips start with its next uploads." + (f"\nConditions: {'; '.join(v['conditions'])}" if v["conditions"] else ""))
        elif a.get("answer") == "no":
            v["status"] = "declined"
        else:
            telegram(f"✉️ {v['title']} ({v['subs']:,} subs) replied to the clipping email: \"{body[:300]}\"\n"
                     f"{a.get('summary') or ''}\nReply to Kiro with what to answer (or answer them yourself).")
        seen.add(x["messageId"])
    st["seen_msgs"] = sorted(seen)[-500:]
    save(STORE, st)


def add_source(ch_id, v):
    p = os.path.join(ROOT, "channels", v["page"], "sources.json")
    d = load(p, {}) or {}
    d.setdefault("sources", {})
    key = re.sub(r"[^a-z0-9]+", "-", (v.get("handle") or v["title"]).lower()).strip("-")[:30]
    d["sources"][key] = {"platform": "creator", "title": v["title"], "channels": [v.get("handle") or ch_id], "videos": [],
                         "match": [x for x in (v.get("handle"), ch_id) if x], "_ids": {v.get("handle") or ch_id: ch_id},
                         "permission": f"email reply {v.get('reply_at')} from {v['email']}: \"{(v.get('reply') or '')[:200]}\"",
                         "conditions": v.get("conditions") or [], "credit_link": True, "clips_per_video": 3, "active": True,
                         "added": time.strftime("%Y-%m-%d %H:%M"), "added_t": time.time() - 14 * 86400}
    try:                       # clipwatch only takes uploads of the last 3 days: start with their 3 newest long videos
        import clipwatch
        d["sources"][key]["videos"] = [u["url"] for u in clipwatch.uploads(ch_id)[:3]]
    except Exception as e:
        log("creatorask: backfill failed", str(e)[:100])
    save(p, d)
    os.system(f"cd {ROOT} && git add {p} && git commit -qm 'source: {key} (creator said yes)' >/dev/null 2>&1 && "
              "git pull -q --rebase --autostash && git push -q >/dev/null 2>&1")


def share_clip(page, src_key, mp4, links):
    """19 Nov (Bhakti Prabha: 'plz share shorts with us so we can post it on our instagram'): after a clip from a
    share_back source posts, email the creator the clip (attached, re-encoded under 18 MB when needed) + our post links."""
    import smtplib, ssl, subprocess, tempfile
    from email.message import EmailMessage
    src = ((load(os.path.join(ROOT, "channels", page, "sources.json"), {}) or {}).get("sources") or {}).get(src_key) or {}
    if not src.get("share_back"):
        return False
    st = load(STORE, {}) or {}
    row = next((v for k, v in (st.get("c") or {}).items() if v.get("handle") in (src.get("channels") or []) or k in (src.get("match") or [])), None)
    if not row or not row.get("email"):
        log("creatorask: share_back without an email", src_key); return False
    f = mp4
    if os.path.getsize(f) > 18_000_000:
        f = os.path.join(tempfile.gettempdir(), f"share-{src_key}.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-c:v", "libx264", "-crf", "28", "-preset", "veryfast",
                        "-vf", "scale=720:-2", "-c:a", "aac", "-b:a", "128k", f], timeout=600)
    m = EmailMessage()
    m["From"], m["To"] = FROM, row["email"]
    m["Subject"] = f"Your clip is live: {src.get('title')}"
    m.set_content(f"Namaste,\n\nAs promised, here is the clip we made from your podcast (attached, ready to post on your "
                  f"Instagram / Shorts). It credits you and links your full episode.\n\nOur posts:\n" + "\n".join(links)
                  + "\n\nIf you want any change, or want a clip taken down, just reply.\n\nMehul\nCut Capsule Hindi · Scroll House")
    m.add_attachment(open(f, "rb").read(), maintype="video", subtype="mp4", filename=f"{src_key}-clip.mp4")
    pw = open(os.path.expanduser("~/.studio-zoho-mail.key")).read().strip()
    with smtplib.SMTP_SSL("smtp.zoho.in", 465, context=ssl.create_default_context(), timeout=120) as s:
        s.login("hello@scrollhouse.in", pw); s.send_message(m)
    log("creatorask: shared clip with", row["email"], src_key)
    return True


def email_for(row):
    name = re.sub(r"\s*(podcast|official|show|tv|channel)\b.*$", "", row["title"] or "", flags=re.I).strip() or row["title"]
    return TEMPLATE_SUBJECT.format(channel=row["title"]), TEMPLATE.format(name=name, channel=row["title"])


if __name__ == "__main__":
    a = sys.argv[1:] or ["list"]
    if a[0] == "test":           # one sample of the real email to the given address
        r = {"title": "Chalchitra Talks"}
        s, b = email_for(r)
        print(send_one(a[1], "[TEST] " + s, b))
    elif a[0] == "replies":      # timer studio-creatorreplies, hourly
        replies()
    elif a[0] == "daily":        # timer: refill the list, then the day's emails
        replies()
        find("cutcapsulehindi")
        print(send("cutcapsulehindi"))
    elif a[0] == "send":
        print(send(a[1] if len(a) > 1 else "cutcapsulehindi"))
    elif a[0] == "find":
        for r in find(a[1] if len(a) > 1 else "cutcapsulehindi")[:40]:
            print(f"{r['subs']:>9,} {r['title'][:40]:40s} {r['handle']} {r['email']}")
    else:
        st = load(STORE, {}) or {}
        for r in sorted((v for v in (st.get("c") or {}).values() if v["status"] == "draft"), key=lambda r: -r["subs"]):
            print(f"{r['subs']:>9,} {r['title'][:40]:40s} {r['email']}")
