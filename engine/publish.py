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
                                    "share_to_feed": "true", "access_token": tok})
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


def youtube(acc, mp4, title, desc):
    y = acc["yt"]
    tok = _req("https://oauth2.googleapis.com/token", {"client_id": y["client_id"], "client_secret": y["client_secret"],
                                                       "refresh_token": y["refresh_token"], "grant_type": "refresh_token"})["access_token"]
    meta = json.dumps({"snippet": {"title": title[:95] + " #shorts", "description": desc, "categoryId": "27"},
                       "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}).encode()
    r = urllib.request.Request("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                               data=meta, headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                                                   "X-Upload-Content-Type": "video/mp4"})
    loc = urllib.request.urlopen(r, timeout=120).headers["Location"]
    up = urllib.request.Request(loc, data=open(mp4, "rb").read(), method="PUT",
                                headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"})
    return json.load(urllib.request.urlopen(up, timeout=900))["id"]


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
    acc = resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
    p = os.path.join(ROOT, "channels", cid, "done.json")
    done = load(p, [])
    nxt = next((d for d in done if d.get("status") == "approved"), None)
    if not nxt:
        log("publish", cid, "nothing approved"); return
    if not acc:
        log("publish", cid, "no accounts connected yet"); return
    job = os.path.join(OUT, cid, nxt["job"])
    plan = load(os.path.join(job, "plan.json"), {})
    mp4 = os.path.join(job, f"{cid}-{nxt['job']}.mp4")
    caption = (plan.get("caption", "") + "\n\n" + " ".join(plan.get("hashtags", [])[:8])).strip()
    if dry:
        log("publish dry", cid, nxt["job"], caption[:80]); return
    res = {}
    for name, fn in (("ig", lambda: instagram(acc, mp4, caption)), ("fb", lambda: facebook(acc, mp4, caption)),
                     ("yt", lambda: youtube(acc, mp4, plan.get("title", ""), caption))):
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


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for cid in args or [c for c in os.listdir(os.path.join(ROOT, "channels")) if os.path.isdir(os.path.join(ROOT, "channels", c))]:
        post_one(cid, "--dry" in sys.argv)
