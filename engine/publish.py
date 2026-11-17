"""Post approved videos (systemd timer studio-post at each channel's slots). Official APIs only.
Accounts per channel: ~/.studio-accounts/<channel>.json (never in git): {"page_id": "...", "yt": {...optional}}
Posting key (same as VAJRA and MarginMart, owner 12/17 Nov): Mehul's "Ads MCP" Meta login (~/.studio-meta-user.token,
never expires, data access renews when he logs in to Meta). The Page key and the linked Instagram id are read from it on
every run, so posts can later be promoted as ads on the existing post. A fixed "page_token" in the file still works.
Instagram: resumable upload of the local file (no public hosting needed). Facebook Page: video reels. YouTube: Shorts.
  python engine/publish.py [channel] [--dry]"""
import json, os, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, telegram, sh

G = "https://graph.facebook.com/v23.0"


def _req(url, data=None, headers=None, method=None):
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    r = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    return json.load(urllib.request.urlopen(r, timeout=600))


def instagram(acc, mp4, caption):
    tok, uid = acc["page_token"], acc["ig_user_id"]
    c = _req(f"{G}/{uid}/media", {"media_type": "REELS", "upload_type": "resumable", "caption": caption,
                                    "share_to_feed": "true", "thumb_offset": "0", "access_token": tok})
    cid = c["id"]
    size = os.path.getsize(mp4)
    _req(f"https://rupload.facebook.com/ig-api-upload/v23.0/{cid}", open(mp4, "rb").read(),
         {"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}, "POST")
    for _ in range(60):
        st = _req(f"{G}/{cid}?fields=status_code,status&access_token={tok}")
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError("IG processing error: " + str(st))
        time.sleep(10)
    p = _req(f"{G}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    return p["id"]


def facebook(acc, mp4, caption):
    tok, pid = acc["page_token"], acc["page_id"]
    s = _req(f"{G}/{pid}/video_reels", {"upload_phase": "start", "access_token": tok})
    vid = s["video_id"]
    _req(s["upload_url"], open(mp4, "rb").read(),
         {"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(os.path.getsize(mp4))}, "POST")
    _req(f"{G}/{pid}/video_reels", {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                     "description": caption, "access_token": tok})
    return vid


def youtube(acc, mp4, title, desc, tags=None, thumb=None):
    y = acc["yt"]
    tok = _req("https://oauth2.googleapis.com/token", {"client_id": y["client_id"], "client_secret": y["client_secret"],
                                                       "refresh_token": y["refresh_token"], "grant_type": "refresh_token"})["access_token"]
    meta = json.dumps({"snippet": {"title": (title[:90] if "#shorts" in title.lower() else title[:90] + " #shorts"), "description": desc,
                                   "categoryId": "27", "tags": (tags or [])[:15]},
                       "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}).encode()
    r = urllib.request.Request("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                               data=meta, headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                                                   "X-Upload-Content-Type": "video/mp4"})
    loc = urllib.request.urlopen(r, timeout=120).headers["Location"]
    up = urllib.request.Request(loc, data=open(mp4, "rb").read(), method="PUT",
                                headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"})
    vid = json.load(urllib.request.urlopen(up, timeout=900))["id"]
    if thumb and os.path.exists(thumb):                       # custom cover (needs a verified channel; failure is harmless)
        try:
            urllib.request.urlopen(urllib.request.Request(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                                   data=open(thumb, "rb").read(), method="POST",
                                   headers={"Authorization": f"Bearer {tok}", "Content-Type": "image/jpeg"}), timeout=120)
        except Exception as e:
            log("youtube thumbnail not set", str(e)[:100])
    return vid


def resolve(acc):
    """Fill page_token + ig_user_id from the Ads MCP user login."""
    if not acc or acc.get("page_token") or not acc.get("page_id"):
        return acc
    try:
        ut = open(os.path.expanduser("~/.studio-meta-user.token")).read().strip()
        d = _req(f"{G}/{acc['page_id']}?fields=access_token,instagram_business_account&access_token={ut}")
        acc = dict(acc, page_token=d["access_token"])
        if d.get("instagram_business_account"):
            acc["ig_user_id"] = d["instagram_business_account"]["id"]
        dbg = _req(f"{G}/debug_token?input_token={ut}&access_token={ut}")["data"]
        left = (dbg.get("data_access_expires_at", 0) - time.time()) / 86400
        if left < 21:
            telegram(f"⚠️ Meta login data access ends in {left:.0f} days: Mehul, log in to Meta Business Suite once, or posting stops.")
    except Exception as e:
        log("meta login: no page key", str(e)[:200])
    return acc


def post_one(cid, dry=False):
    ch = load(os.path.join(ROOT, "channels", cid, "channel.json"), {})
    if ch.get("post") is False:
        log("publish", cid, "posting is off for this page (channel.json post=false)"); return
    w = ch.get("warmup", {})
    day = time.strftime("%Y-%m-%d")
    if w.get("post_from") and day < w["post_from"]:
        log("publish", cid, "warm-up: no posts before", w["post_from"]); return
    if w.get("one_a_day_until") and day < w["one_a_day_until"] and int(time.strftime("%H")) < 17:
        log("publish", cid, "warm-up: only the evening slot until", w["one_a_day_until"]); return
    acc = resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
    p = os.path.join(ROOT, "channels", cid, "done.json")
    done = load(p, [])
    # 17 Nov: English editions (-en) only go out once the page has an English account (handle_en); the English page is parked
    nxt = next((d for d in done if d.get("status") == "approved" and (not d["job"].endswith("-en") or ch.get("handle_en"))), None)
    if not nxt:
        log("publish", cid, "nothing approved"); return
    if not acc:
        log("publish", cid, "no accounts connected yet"); return
    job = os.path.join(OUT, cid, nxt["job"])
    plan = load(os.path.join(job, "plan.json"), {})
    mp4 = os.path.join(job, f"{cid}-{nxt['job']}.mp4")
    try:                                                       # 17 Nov: platform-specific caption/title/hashtags (engine/seo.py)
        import seo
        seo.make(cid, plan, job)
        plan = load(os.path.join(job, "plan.json"), {})
    except Exception as e:
        log("seo failed, using the plan caption", str(e)[:150])
    mc = plan.get("music_credit")
    caption = seo.text_for(plan, "ig", mc) if "seo" in sys.modules else (plan.get("caption", "") + "\n\n" + " ".join(plan.get("hashtags", [])[:8])).strip()
    fbcap = seo.text_for(plan, "fb", mc) if "seo" in sys.modules else caption
    ytx = seo.text_for(plan, "yt", mc) if "seo" in sys.modules else {"title": plan.get("title", ""), "description": caption, "tags": []}
    cv = os.path.join(job, "cover.jpg")
    if os.path.exists(cv):
        try:
            import thumb
            mp4 = thumb.stamp(mp4, cv, os.path.join(job, "post.mp4"))
        except Exception as e:
            log("cover stamp failed, posting plain", str(e)[:150])
    if dry:
        log("publish dry", cid, nxt["job"], caption[:80]); return
    res = {}
    for name, fn in (("ig", lambda: instagram(acc, mp4, caption)), ("fb", lambda: facebook(acc, mp4, fbcap)),
                     ("yt", lambda: youtube(acc, mp4, ytx["title"], ytx["description"], ytx.get("tags"), cv))):
        if name == "yt" and not acc.get("yt"):
            continue
        if name in ("ig", "fb") and not acc.get("page_token"):
            continue
        if name == "ig" and not acc.get("ig_user_id"):
            log("publish", cid, "no Instagram linked to the Page yet"); continue
        try:
            res[name] = fn(); log("published", cid, name, res[name])
        except Exception as e:
            res[name + "_error"] = str(e)[:300]; log("publish fail", cid, name, e)
    nxt["status"] = "posted" if any(k in res for k in ("ig", "fb", "yt")) else "approved"
    nxt["posted"] = {"at": time.strftime("%Y-%m-%d %H:%M"), **res}
    save(p, done)
    telegram(f"📤 {cid} {nxt['job']} posted: {res}")
    if any(k in res for k in ("ig", "fb")) and ch.get("serial"):
        try:                                                   # 17 Nov: recap Story the day a part goes up; long cut at the end
            import extras, serials
            extras.recap_story(cid, nxt, acc, plan)
            s, n = serials._find(ch, nxt.get("topic"))
            if s and n == len(s["parts"]):
                lc = extras.long_cut(cid, s)
                if lc and acc.get("yt"):
                    vid = youtube(acc, lc, f"{s['title']} - Poori Kahani (All Parts)", f"{s['logline']}\n\nSaare parts ek saath. Har roz ek nayi kahani.", [s["title"], "hindi story", "kahani"], None)
                    log("long cut on YouTube", cid, vid)
        except Exception as e:
            log("serial extras failed", str(e)[:150])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for cid in args or [c for c in os.listdir(os.path.join(ROOT, "channels")) if os.path.isdir(os.path.join(ROOT, "channels", c))]:
        post_one(cid, "--dry" in sys.argv)
