"""Post approved videos (systemd timer studio-post at each channel's slots). Official APIs only.
Accounts per channel: ~/.studio-accounts/<channel>.json (never in git): {"page_id": "...", "yt": {...optional}}
Posting key (same as VAJRA and MarginMart, owner 12/17 Nov): Mehul's "Ads MCP" Meta login (~/.studio-meta-user.token,
never expires, data access renews when he logs in to Meta). The Page key and the linked Instagram id are read from it on
every run, so posts can later be promoted as ads on the existing post. A fixed "page_token" in the file still works.
Instagram: resumable upload of the local file (no public hosting needed). Facebook Page: video reels. YouTube: Shorts.
  python engine/publish.py [channel] [--dry]"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, telegram, sh

G = "https://graph.facebook.com/v23.0"


def _req(url, data=None, headers=None, method=None):
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    r = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        return json.load(urllib.request.urlopen(r, timeout=600))
    except urllib.error.HTTPError as e:
        if e.code in (400, 401) and "graph.facebook.com" in url:   # 190 = token refused: drop cached page keys
            try:
                b = e.read(2000).decode("utf-8", "ignore")
                e.fp = __import__("io").BytesIO(b.encode()); e.read = e.fp.read
                if '"code":190' in b.replace(" ", "") and os.path.exists(META_CACHE):
                    os.remove(META_CACHE); log("meta: a cached key was refused, cache cleared")
            except Exception:
                pass
        raise


MEDIA_REPO = os.path.expanduser("~/studio-media")
MEDIA_RAW = "https://raw.githubusercontent.com/offhours-lab/studio-media/main/"


def _public_url(mp4, name):
    """Put the file in the public repo (offhours-lab/studio-media) and wait until raw.githubusercontent serves it."""
    import shutil, subprocess
    subprocess.run(["git", "-C", MEDIA_REPO, "pull", "-q", "--rebase"], timeout=120)
    os.makedirs(os.path.join(MEDIA_REPO, "reels"), exist_ok=True)
    shutil.copy(mp4, os.path.join(MEDIA_REPO, "reels", name))
    for c in (["git", "-C", MEDIA_REPO, "add", "-A"], ["git", "-C", MEDIA_REPO, "commit", "-qm", "reel " + name],
              ["git", "-C", MEDIA_REPO, "push", "-q"]):
        subprocess.run(c, timeout=300)
    url = MEDIA_RAW + "reels/" + name
    for _ in range(30):
        try:
            if urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30).status == 200:
                return url
        except Exception:
            pass
        time.sleep(10)
    return url


def instagram(acc, mp4, caption):
    """19 Nov: the first Reel by the resumable upload failed (rupload 'ProcessingFailedError', also with the v27 URI) and
    by the FB video URL (2207076). By video_url from our public repo it published at once: that is the route now."""
    tok, uid = acc["page_token"], acc["ig_user_id"]
    url = _public_url(mp4, f"{uid}-{int(time.time())}.mp4")
    c = _req(f"{G}/{uid}/media", {"media_type": "REELS", "video_url": url, "caption": caption,
                                    "share_to_feed": "true", "access_token": tok})
    cid = c["id"]
    for _ in range(60):
        st = _req(f"{G}/{cid}?fields=status_code,status&access_token={tok}")
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError("IG processing error: " + str(st))
        time.sleep(10)
    p = _req(f"{G}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    return p["id"]


def instagram_resumable(acc, mp4, caption):
    tok, uid = acc["page_token"], acc["ig_user_id"]
    c = _req(f"{G}/{uid}/media", {"media_type": "REELS", "upload_type": "resumable", "caption": caption,
                                    "share_to_feed": "true", "thumb_offset": "0", "access_token": tok})
    cid = c["id"]
    size = os.path.getsize(mp4)
    # 19 Nov: Instagram moved the upload host to v27.0; the hard-coded v23.0 URL failed ("ProcessingFailedError", the
    # Finance Fuel Reel went out on FB only). Use the upload URI the create call returns.
    _req(c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/v23.0/{cid}", open(mp4, "rb").read(),
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


META_CACHE = os.path.join(OUT, "meta-cache.json")


def resolve(acc):
    """Fill page_token + ig_user_id from the Ads MCP user login.
    18 Nov: every caller (publish, stats, comments, stories, hookstudy, money, rivals) asked Meta again, 2 calls each; a burst
    hit the app's hourly limit (#4 'Application request limit reached', 114%). Page tokens made from a long-lived user
    token do not expire, so they are cached for 12 h (a refused token clears the cache: see _req), the login check once a day."""
    if not acc or acc.get("page_token") or not acc.get("page_id"):
        return acc
    cache = load(META_CACHE, {}) or {}
    c = cache.get(acc["page_id"])
    if c and time.time() - c.get("t", 0) < 12 * 3600:
        return dict(acc, **{k: v for k, v in c.items() if k in ("page_token", "ig_user_id")})
    try:
        ut = open(os.path.expanduser("~/.studio-meta-user.token")).read().strip()
        d = _req(f"{G}/{acc['page_id']}?fields=access_token,instagram_business_account&access_token={ut}")
        acc = dict(acc, page_token=d["access_token"])
        if d.get("instagram_business_account"):
            acc["ig_user_id"] = d["instagram_business_account"]["id"]
        cache[acc["page_id"]] = {"page_token": acc["page_token"], "ig_user_id": acc.get("ig_user_id"), "t": time.time()}
        if time.time() - cache.get("_login_checked", 0) > 86400:
            cache["_login_checked"] = time.time()
            dbg = _req(f"{G}/debug_token?input_token={ut}&access_token={ut}")["data"]
            left = (dbg.get("data_access_expires_at", 0) - time.time()) / 86400
            if left < 21:
                telegram(f"⚠️ Meta login data access ends in {left:.0f} days: Mehul, log in to Meta Business Suite once, or posting stops.")
        save(META_CACHE, cache)
    except Exception as e:
        log("meta login: no page key", str(e)[:200])
        if c:                                             # Meta busy or rate-limited: yesterday's key still works
            return dict(acc, **{k: v for k, v in c.items() if k in ("page_token", "ig_user_id")})
    return acc


def serial_order(ch, done, cands):
    """18 Nov: serial parts must go out in order, one story at a time. The approved list was posted oldest first, so a new
    story's Part 1 (built earlier) could jump in before the running story's next part. Rules: a part goes out only after
    the part before it; the story already on air comes first; if its next part is not ready, nothing goes out today
    (a day's gap is better than a cliffhanger answered by a different story). Returns (ordered candidates, reason)."""
    import serials
    posted = {d["job"] for d in done if d.get("status") == "posted"}
    info = {d["job"]: serials._find(ch, d.get("topic")) for d in cands}
    def ready(d):
        s, n = info[d["job"]]
        return not s or n == 1 or s["made_jobs"].get(str(n - 1)) in posted
    on_air = [s for s in serials.stories(ch["id"]) if any(j in posted for j in (s.get("made_jobs") or {}).values())
              and not s.get("closed") and not all(s["made_jobs"].get(str(p["n"])) in posted for p in s["parts"])]
    if on_air:
        s = on_air[0]
        mine = [d for d in cands if info[d["job"]][0] and info[d["job"]][0]["slug"] == s["slug"] and ready(d)]
        if mine:
            return sorted(mine, key=lambda d: info[d["job"]][1]), ""
        last = max((str((d.get("posted") or {}).get("at", "")) for d in done if d["job"] in set(s["made_jobs"].values())), default="")
        if last and time.time() - time.mktime(time.strptime(last[:16], "%Y-%m-%d %H:%M")) < 2 * 86400:
            return [], f"serial '{s['title']}' is on air and its next part is not approved yet: nothing posted today"
        # waited 2 days (a part rejected or stuck): do not block the page for ever; the next story goes on
        why = f"serial '{s['title']}' waited 2 days for its next part: posting the next story instead"
        ok = [d for d in cands if ready(d)]
        return sorted(ok, key=lambda d: ((info[d["job"]][0] or {}).get("started", ""), info[d["job"]][1] or 0)), why
    ok = [d for d in cands if ready(d)]
    return sorted(ok, key=lambda d: ((info[d["job"]][0] or {}).get("started", ""), info[d["job"]][1] or 0)), ""


SERIES_RX = re.compile(r"(.+) - Part (\d+):")


def series_order(cid, done, cands):
    """18 Nov: Katha series parts ('12 Jyotirlinga ki katha - Part 2: ...') go out in order. A part waits while the part
    before it is still coming (approved, building, held, or in the redo queue); other videos post meanwhile."""
    st = load(os.path.join(ROOT, "channels", cid, "series-state.json"), {}) or {}
    posted = {str(d.get("topic")) for d in done if d.get("status") == "posted"}
    coming = {str(d.get("topic")) for d in done if d.get("status") in ("approved", "made", "waiting", "ready", "held")}
    coming |= set(st.get("redo") or [])
    def key(d):
        m = SERIES_RX.match(str(d.get("topic") or ""))
        return (m.group(1), int(m.group(2))) if m else None
    def ready(d):
        k = key(d)
        if not k or k[1] == 1:
            return True
        prev = [t for t in posted | coming if (SERIES_RX.match(t) and SERIES_RX.match(t).group(1) == k[0]
                                                 and int(SERIES_RX.match(t).group(2)) == k[1] - 1)]
        return any(t in posted for t in prev) or not prev
    out = [d for d in cands if ready(d)]
    held_back = [d["job"] for d in cands if d not in out]
    if held_back:
        log("publish", cid, "series parts wait for the part before them:", ", ".join(held_back))
    return sorted(out, key=lambda d: (key(d) or ("", 0))[1])


def post_one(cid, dry=False):
    ch = load(os.path.join(ROOT, "channels", cid, "channel.json"), {})
    if ch.get("post") is False:
        log("publish", cid, "posting is off for this page (channel.json post=false)"); return
    w = ch.get("warmup", {})
    day = time.strftime("%Y-%m-%d")
    if w.get("post_from") and day < w["post_from"]:
        log("publish", cid, "warm-up: no posts before", w["post_from"]); return
    # 19 Nov: a page can post at its own hours (IST, the server clock): Cut Capsule earns only on US/global views, so it
    # posts at US evening (06:30 IST = 8 pm New York) from its own timer (studio-post-us) instead of 13:00/20:00.
    hours = [int(h) for h in (ch.get("schedule") or {}).get("post_hours_ist") or []]
    # 19 Nov (owner: "why only 1 a day?"): schedule.ramp = [[date, posts_per_day], ...] raises the pace step by step
    # (new-account warming: ~1 Reel/day for 2 weeks, then more). The page's hours are in priority order: N posts a day
    # use the first N hours. Instagram's own API cap is 50 posts / 24 h, YouTube uploads 100 / day: the limit is ours.
    ramp = (ch.get("schedule") or {}).get("ramp") or []
    ppd = int((ch.get("schedule") or {}).get("posts_per_day", 1) or 1)
    for d0, n0 in ramp:
        if day >= d0:
            ppd = int(n0)
    if hours:
        hr = int(time.strftime("%H"))
        if hr not in hours[:max(1, ppd)]:
            log("publish", cid, "not one of today's posting hours", hours[:max(1, ppd)], f"({ppd}/day)"); return
    elif w.get("one_a_day_until") and day < w["one_a_day_until"] and int(time.strftime("%H")) < 17:
        log("publish", cid, "warm-up: only the evening slot until", w["one_a_day_until"]); return
    if not ramp and w.get("one_a_day_until") and day < w["one_a_day_until"]:
        ppd = 1
    p = os.path.join(ROOT, "channels", cid, "done.json")
    done = load(p, [])
    # 18 Nov: posts_per_day was never read, so after the warm-up (27 Nov) every page would post at both slots
    # (13:00 and 20:00), katha and Aage Suno (1 a day) included. One a day = the evening slot only.
    today_n = sum(1 for d in done if str((d.get("posted") or {}).get("at", "")).startswith(day))
    if today_n >= ppd:
        log("publish", cid, f"already posted {today_n} today (posts_per_day {ppd})"); return
    if ppd == 1 and not hours and int(time.strftime("%H")) < 17:
        log("publish", cid, "one post a day: the evening slot"); return
    acc = resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
    # 17 Nov: English editions (-en) only go out once the page has an English account (handle_en); the English page is parked
    cands = [d for d in done if d.get("status") == "approved" and (not d["job"].endswith("-en") or ch.get("handle_en"))]
    if ch.get("serial") and cands:
        cands, why = serial_order(dict(ch, id=cid), done, cands)
        if why:
            log("publish", cid, why)
    elif cands:
        cands = series_order(cid, done, cands)
    nxt = cands[0] if cands else None
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
    caption = seo.text_for(plan, "ig", mc, cid=cid) if "seo" in sys.modules else (plan.get("caption", "") + "\n\n" + " ".join(plan.get("hashtags", [])[:8])).strip()
    fbcap = seo.text_for(plan, "fb", mc, cid=cid) if "seo" in sys.modules else caption
    ytx = seo.text_for(plan, "yt", mc, cid=cid) if "seo" in sys.modules else {"title": plan.get("title", ""), "description": caption, "tags": []}
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
    # 19 Nov: a campaign may allow only some platforms (Jo Koy: Instagram Reels only); its source's "platforms" decides
    only = None
    _sk = (plan.get("clip") or {}).get("source")
    if _sk:
        _pl = [str(x).lower() for x in ((((load(os.path.join(ROOT, "channels", cid, "sources.json"), {}) or {}).get("sources")
                                          or {}).get(_sk) or {}).get("platforms") or [])]
        if _pl:
            only = {n for n, words in (("ig", ("instagram", "ig", "reels")), ("fb", ("facebook", "fb")),
                                       ("yt", ("youtube", "yt", "shorts"))) if any(w in p for p in _pl for w in words)}
            log("publish", cid, "campaign platforms", _pl, "->", sorted(only))
    for name, fn in (("ig", lambda: instagram(acc, mp4, caption)), ("fb", lambda: facebook(acc, mp4, fbcap)),
                     ("yt", lambda: youtube(acc, mp4, ytx["title"], ytx["description"], ytx.get("tags"), cv))):
        if only is not None and name not in only:
            continue
        if name == "yt" and not acc.get("yt"):
            continue
        if name in ("ig", "fb") and not acc.get("page_token"):
            continue
        if name == "ig" and not acc.get("ig_user_id"):
            log("publish", cid, "no Instagram linked to the Page yet"); continue
        try:
            res[name] = fn(); log("published", cid, name, res[name])
        except Exception as e:
            # 19 Nov: "HTTP Error 400: Bad Request" alone hid the reason; keep the platform's own error text
            body = ""
            try:
                body = (e.read() or b"").decode("utf-8", "ignore")[:400] if hasattr(e, "read") else ""
            except Exception:
                pass
            res[name + "_error"] = (str(e) + " " + body)[:500]; log("publish fail", cid, name, e, body)
            try:
                from core import telegram
                telegram(f"⚠️ {cid}: {name.upper()} post failed ({str(e)[:80]} {body[:160]}). The other platforms went out.")
            except Exception:
                pass
    if res.get("yt"):                                          # 19 Nov: serial / series parts go into one YouTube playlist per story
        try:
            import ytlists
            ytlists.add(acc, dict(ch, id=cid), nxt, res["yt"])
        except Exception as e:
            log("ytlists failed", str(e)[:150])
    nxt["status"] = "posted" if any(k in res for k in ("ig", "fb", "yt")) else "approved"
    nxt["posted"] = {"at": time.strftime("%Y-%m-%d %H:%M"), **res}
    save(p, done)
    telegram(f"📤 {cid} {nxt['job']} posted: {res}")
    src_key = (plan.get("clip") or {}).get("source")
    if src_key and any(k in res for k in ("ig", "yt")):
        # 19 Nov: a campaign clip earns only once its post link is submitted on Whop (the owner's login): say exactly what
        try:
            s = ((load(os.path.join(ROOT, "channels", cid, "sources.json"), {}) or {}).get("sources") or {}).get(src_key) or {}
            links = []
            if res.get("ig"):
                pl = _req(f"{G}/{res['ig']}?fields=permalink&access_token={acc['page_token']}").get("permalink")
                links.append(pl or f"Instagram media {res['ig']}")
            if res.get("yt"):
                links.append(f"https://youtube.com/shorts/{res['yt']}")
            if s.get("share_back"):                    # 19 Nov: creators who asked for their clips get them by email
                try:
                    import creatorask
                    creatorask.share_clip(cid, src_key, mp4, links)
                except Exception as e:
                    log("share_back failed", src_key, str(e)[:150])
            if s.get("campaign_url"):
                nxt["submit"] = {"campaign": s.get("campaign_url"), "links": links, "at": time.strftime("%Y-%m-%d %H:%M")}
                save(p, done)
                os.system("sudo systemctl start --no-block studio-whopbot.service")   # engine/whopbot.py submits it on Whop now
            log("campaign clip posted, whopbot submits:", s.get("campaign_url") or src_key, links)
        except Exception as e:
            log("campaign submit note failed", str(e)[:120])
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
