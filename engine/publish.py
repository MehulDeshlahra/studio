"""Post approved videos (systemd timer studio-post at each channel's slots). Official APIs only.
Accounts per channel: ~/.studio-accounts/<channel>.json (never in git):
 {"ig_user_id": "...", "page_id": "...", "page_token": "long-lived page token (instagram_content_publish, pages_manage_posts)",
  "yt": {"client_id": "...", "client_secret": "...", "refresh_token": "..."}}
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


def post_one(cid, dry=False):
    acc = load(os.path.expanduser(f"~/.studio-accounts/{cid}.json"))
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
