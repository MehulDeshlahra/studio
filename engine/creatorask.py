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
            row = {"page": page, "title": sn.get("title"), "handle": sn.get("customUrl"), "subs": subs,
                   "videos": int(stt.get("videoCount") or 0), "email": mails[0] if mails else None, "found": time.strftime("%Y-%m-%d"),
                   "status": "no-email" if not mails else ("too-small" if subs < 20000 else ("too-big" if subs > 2000000 else "draft"))}
            st["c"][it["id"]] = row
            new += row["status"] == "draft"
    save(STORE, st)
    drafts = [v for v in st["c"].values() if v["status"] == "draft"]
    log("creatorask:", len(ids), "new channels,", new, "new drafts,", len(drafts), "drafts total")
    return drafts


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


def email_for(row):
    name = re.sub(r"\s*(podcast|official|show|tv|channel)\b.*$", "", row["title"] or "", flags=re.I).strip() or row["title"]
    return TEMPLATE_SUBJECT.format(channel=row["title"]), TEMPLATE.format(name=name, channel=row["title"])


if __name__ == "__main__":
    a = sys.argv[1:] or ["list"]
    if a[0] == "test":           # one sample of the real email to the given address
        r = {"title": "Chalchitra Talks"}
        s, b = email_for(r)
        print(send_one(a[1], "[TEST] " + s, b))
    elif a[0] == "daily":        # timer: refill the list, then the day's emails
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
