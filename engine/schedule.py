"""Posting that is never late (owner 20 Nov: "find the best way to post on insta fb and yt ... posting should happen
instantly without any issue").

Before: everything ran AT the slot, one page after another (picture check, captions, cover stamp, git upload, Instagram
processing, uploads): 20 Nov 20:00 Katha went out 20:06, Tech 20:11, the rest later. Now each platform publishes at the
slot by itself, prepared hours ahead:
  Facebook  Reel uploaded ahead with video_state=SCHEDULED + scheduled_publish_time: Facebook publishes it at the slot.
  YouTube   uploaded ahead as private with status.publishAt: YouTube makes it public at the slot.
  Instagram (no scheduling in the API) media container created and processed ahead (valid 24 h); at the slot ONE
            media_publish call (~2 s) makes it live.

  python engine/schedule.py stage   (timer every 15 min) picks each page's reel for its next slot (same rules as before:
                                     warm-up, posts per day, hours, serial / series order, "aap" check, picture check)
                                     and prepares all three platforms. Status approved -> scheduled.
  python engine/schedule.py fire    (timer every minute) publishes every Instagram container whose slot has come, all
                                     pages at once; records the post; Whop submit, playlists, serial extras follow.
  python engine/schedule.py status  what is scheduled, when, where
A slot less than 12 min away, or a platform whose preparation failed, is uploaded directly at the slot (in parallel).
A scheduled reel the owner pulls (status changed) is taken off Facebook / YouTube by the next stage run."""
import datetime as dt, fcntl, json, os, sys, threading, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, telegram
import publish as P

LEAD_MIN = 12 * 60            # Facebook needs a scheduled time at least 10 min ahead
WINDOW = 23 * 3600            # Instagram containers expire after 24 h


# ---------------------------------------------------------------- done.json, safely
def _lock(cid):
    f = open(os.path.join(OUT, f".done-{cid}.lock"), "w")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


def update(cid, job, fn):
    """Re-read done.json under a lock, change one row, write it back (stale copies never overwrite newer data)."""
    p = os.path.join(ROOT, "channels", cid, "done.json")
    lk = _lock(cid)
    try:
        rows = load(p, []) or []
        for d in rows:
            if d["job"] == job:
                fn(d)
        save(p, rows)
    finally:
        lk.close()


def channel(cid):
    return load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}


def pages():
    return sorted(c for c in os.listdir(os.path.join(ROOT, "channels")) if os.path.isdir(os.path.join(ROOT, "channels", c)))


# ---------------------------------------------------------------- when
def day_slots(ch, day):
    """[datetime] of the page's posting slots on this IST date (same rules publish.post_one used)."""
    if ch.get("post") is False:
        return []
    w = ch.get("warmup", {}) or {}
    ds = day.strftime("%Y-%m-%d")
    if w.get("post_from") and ds < w["post_from"]:
        return []
    sc = ch.get("schedule") or {}
    ppd = int(sc.get("posts_per_day", 1) or 1)
    ramp = sc.get("ramp") or []
    for d0, n0 in ramp:
        if ds >= d0:
            ppd = int(n0)
    if not ramp and w.get("one_a_day_until") and ds < w["one_a_day_until"]:
        ppd = 1
    hours = [int(h) for h in sc.get("post_hours_ist") or []]
    if hours:
        times = [(h, 30) for h in hours[:max(1, ppd)]]
    else:
        times = [(20, 0)] if ppd <= 1 else [(13, 0), (20, 0)][:ppd]
    return sorted(dt.datetime(day.year, day.month, day.day, h, m) for h, m in times)


def next_slot(cid, ch, rows, now):
    """The first free slot from now on (today or tomorrow), or None."""
    taken = {int((d.get("sched") or {}).get("slot", 0)) for d in rows if d.get("status") in ("scheduled", "posted")}
    for off in (0, 1):
        day = (now + dt.timedelta(days=off)).date()
        sl = day_slots(ch, day)
        if not sl:
            continue
        ds = day.strftime("%Y-%m-%d")
        legacy = sum(1 for d in rows if str((d.get("posted") or {}).get("at", "")).startswith(ds) and not d.get("sched"))
        used = legacy + sum(1 for d in rows if d.get("sched") and dt.datetime.fromtimestamp(d["sched"]["slot"]).date() == day
                            and d.get("status") in ("scheduled", "posted"))
        if used >= len(sl):
            continue
        for t in sl:
            ts = int(t.timestamp())
            if ts > now.timestamp() + 60 and ts not in taken:
                return ts
    return None


# ---------------------------------------------------------------- which
def pick(cid, ch, rows):
    """The reel for the next slot: approved, serial / series order, 'aap' check, picture check (hours ahead now)."""
    cands = [d for d in rows if d.get("status") == "approved" and (not d["job"].endswith("-en") or ch.get("handle_en"))]
    if not cands and ch.get("kind") != "clips":
        ok_ = [d for d in rows if d.get("status") == "made" and not d["job"].endswith("-en")
               and (load(os.path.join(OUT, cid, d["job"], "review.json"), {}) or {}).get("ok")
               and os.path.exists(os.path.join(OUT, cid, d["job"], f"{cid}-{d['job']}.mp4"))]
        if ok_:
            cands = [ok_[-1]]
            log("schedule", cid, "nothing approved: the reviewed reel waiting for the owner takes the slot", ok_[-1]["job"])
    if ch.get("kind") == "clips" and cands:
        # 20 Nov: a clip whose campaign is paused / retired earns nothing (Whop greys out Submit): post a paying one
        srcs = (load(os.path.join(ROOT, "channels", cid, "sources.json"), {}) or {}).get("sources") or {}
        def _pays(d):
            sk_ = ((load(os.path.join(OUT, cid, d["job"], "plan.json"), {}) or {}).get("clip") or {}).get("source")
            s_ = srcs.get(sk_) or {}
            return not s_.get("campaign_url") or s_.get("active", True)
        paying = [d for d in cands if _pays(d)]
        if len(paying) < len(cands):
            log("schedule", cid, f"skipped {len(cands) - len(paying)} clip(s) from paused/finished campaigns")
        cands = paying
    if ch.get("serial") and cands:
        cands, why = P.serial_order(dict(ch, id=cid), rows, cands)
        if why:
            log("schedule", cid, why)
    elif cands:
        cands = P.series_order(cid, rows, cands)
    # 20 Nov (owner: "where is part 2?"): a reel that answers a part already posted ("Jawab kal") goes first. A reel
    # names the part it answers in plan.json "part_of"; it is ready once that part is posted
    posted_ = {d["job"] for d in rows if d.get("status") == "posted"}

    def _answers(d):
        po = (load(os.path.join(OUT, cid, d["job"], "plan.json"), {}) or {}).get("part_of")
        return bool(po) and po in posted_
    cands = sorted(cands, key=lambda d: not _answers(d))
    for c in cands[:3]:
        if not cid.startswith("cutcapsule"):
            try:
                import respect
                rp = respect.problems(load(os.path.join(OUT, cid, c["job"], "plan.json"), {}) or {})
            except Exception:
                rp = []
            if rp:
                log("schedule: informal address HOLD", cid, c["job"], rp[0][:160])
                update(cid, c["job"], lambda d: d.update(status="held", review=rp[:6] + (d.get("review") or [])))
                continue
        if ch.get("visual_checks") and ch.get("kind") != "clips":
            try:
                import review
                jd_ = os.path.join(OUT, cid, c["job"])
                pc = review.picture_check(os.path.join(jd_, f"{cid}-{c['job']}.mp4"),
                                          (load(os.path.join(jd_, "timing.json"), {}) or {}).get("lines", []), ch["visual_checks"],
                                          frame_checks=ch.get("frame_checks"), frame_context=ch.get("frame_context", ""))
                hard = []
                if pc.get("problems"):
                    import strict
                    hard = strict.split(["picture check: " + x for x in pc["problems"]])[0]
                if hard:
                    log("schedule: picture check HOLD", cid, c["job"], hard[0][:200])
                    update(cid, c["job"], lambda d: d.update(status="held", review=["pre-post " + x for x in hard[:6]] + (d.get("review") or [])))
                    continue
            except Exception as e:
                log("schedule: picture check could not run, keeping the reel", cid, c["job"], str(e)[:100])
        return c
    return None


# ---------------------------------------------------------------- prepare
def _texts(cid, job, plan):
    import seo
    try:
        seo.make(cid, plan, job)
        plan = load(os.path.join(job, "plan.json"), {})
    except Exception as e:
        log("seo failed, plan caption used", str(e)[:120])
    mc = plan.get("music_credit")
    return plan, seo.text_for(plan, "ig", mc, cid=cid), seo.text_for(plan, "fb", mc, cid=cid), seo.text_for(plan, "yt", mc, cid=cid)


def _platforms(cid, plan, acc):
    only = None
    sk = (plan.get("clip") or {}).get("source")
    if sk:
        pl = [str(x).lower() for x in ((((load(os.path.join(ROOT, "channels", cid, "sources.json"), {}) or {}).get("sources")
                                          or {}).get(sk) or {}).get("platforms") or [])]
        if pl:
            only = {n for n, words in (("ig", ("instagram", "ig", "reels")), ("fb", ("facebook", "fb")),
                                       ("yt", ("youtube", "yt", "shorts"))) if any(w in p for p in pl for w in words)}
    out = []
    for n in ("ig", "fb", "yt"):
        if only is not None and n not in only:
            continue
        if n == "yt" and not acc.get("yt"):
            continue
        if n in ("ig", "fb") and not acc.get("page_token"):
            continue
        if n == "ig" and not acc.get("ig_user_id"):
            continue
        out.append(n)
    return out


def _err(e):
    body = ""
    try:
        body = (e.read() or b"").decode("utf-8", "ignore")[:300] if hasattr(e, "read") else ""
    except Exception:
        pass
    return (str(e) + " " + body)[:400]


def fb_schedule(acc, mp4, caption, slot, url=None):
    tok, pid = acc["page_token"], acc["page_id"]
    s = P._req(f"{P.G}/{pid}/video_reels", {"upload_phase": "start", "access_token": tok})
    vid = s["video_id"]
    if url:      # 20 Nov: Facebook fetches the public file itself (a binary push from here stalled 10 min x 3 pages)
        P._req(s["upload_url"], b"", {"Authorization": f"OAuth {tok}", "file_url": url}, "POST")
    else:
        P._req(s["upload_url"], open(mp4, "rb").read(),
               {"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(os.path.getsize(mp4))}, "POST")
    P._req(f"{P.G}/{pid}/video_reels", {"upload_phase": "finish", "video_id": vid, "video_state": "SCHEDULED",
                                         "scheduled_publish_time": str(int(slot)), "description": caption, "access_token": tok})
    return vid


def yt_schedule(acc, mp4, ytx, thumb, slot):
    y = acc["yt"]
    tok = P._req("https://oauth2.googleapis.com/token", {"client_id": y["client_id"], "client_secret": y["client_secret"],
                                                         "refresh_token": y["refresh_token"], "grant_type": "refresh_token"})["access_token"]
    title = ytx["title"][:90] if "#shorts" in ytx["title"].lower() else ytx["title"][:90] + " #shorts"
    at = dt.datetime.utcfromtimestamp(slot).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = json.dumps({"snippet": {"title": title, "description": ytx["description"], "categoryId": "27", "tags": (ytx.get("tags") or [])[:15]},
                       "status": {"privacyStatus": "private", "publishAt": at, "selfDeclaredMadeForKids": False}}).encode()
    r = urllib.request.Request("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                               data=meta, headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                                                   "X-Upload-Content-Type": "video/mp4"})
    loc = urllib.request.urlopen(r, timeout=120).headers["Location"]
    up = urllib.request.Request(loc, data=open(mp4, "rb").read(), method="PUT",
                                headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"})
    vid = json.load(urllib.request.urlopen(up, timeout=900))["id"]
    if thumb and os.path.exists(thumb):
        try:
            urllib.request.urlopen(urllib.request.Request(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                                   data=open(thumb, "rb").read(), method="POST",
                                   headers={"Authorization": f"Bearer {tok}", "Content-Type": "image/jpeg"}), timeout=120)
        except Exception as e:
            log("youtube thumbnail not set", str(e)[:100])
    return vid


_GIT = threading.Lock()          # one git push to the public media repo at a time (pages prepare side by side)


def ig_container(acc, mp4, caption, url=None):
    tok, uid = acc["page_token"], acc["ig_user_id"]
    if not url:
        with _GIT:
            url = P._public_url(mp4, f"{uid}-{int(time.time())}.mp4")
    c = P._req(f"{P.G}/{uid}/media", {"media_type": "REELS", "video_url": url, "caption": caption, "share_to_feed": "true",
                                        "access_token": tok})
    for _ in range(90):
        st = P._req(f"{P.G}/{c['id']}?fields=status_code,status&access_token={tok}")
        if st.get("status_code") == "FINISHED":
            return c["id"], url
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError("IG container " + str(st)[:200])
        time.sleep(10)
    raise RuntimeError("IG container not ready after 15 min")


def prepare(cid, ch, d, slot, only=None):
    """Get one reel ready on every platform for `slot` (unix time). Writes d['sched'] and status 'scheduled'.
    only = [platforms] retries just those on an already scheduled reel (keeps what is ready)."""
    acc = P.resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
    if not acc:
        log("schedule", cid, "no accounts connected"); return
    job = os.path.join(OUT, cid, d["job"])
    plan, cap, fbcap, ytx = _texts(cid, job, load(os.path.join(job, "plan.json"), {}))
    mp4 = os.path.join(job, f"{cid}-{d['job']}.mp4")
    cv = os.path.join(job, "cover.jpg")
    if os.path.exists(cv):
        try:
            import thumb
            mp4 = thumb.stamp(mp4, cv, os.path.join(job, "post.mp4"))
        except Exception as e:
            log("cover stamp failed, posting plain", str(e)[:120])
    plats = _platforms(cid, plan, acc)
    if only:
        sch = dict(d.get("sched") or {})
        for n in only:
            sch.pop(n + "_prep_error", None)
        sch["retried"] = int(time.time())
        plats_do = [n for n in plats if n in only]
    else:
        sch = {"slot": int(slot), "at": dt.datetime.fromtimestamp(slot).strftime("%Y-%m-%d %H:%M"), "platforms": plats,
               "mp4": mp4, "prepared": time.strftime("%Y-%m-%d %H:%M")}
        plats_do = plats
    direct = slot - time.time() < LEAD_MIN
    update(cid, d["job"], lambda r: r.update(status="scheduled", sched=sch))      # claim the reel first
    url = sch.get("url")
    if not url and ("ig" in plats_do or "fb" in plats_do):   # one public copy for Instagram AND Facebook to fetch
        try:
            with _GIT:
                url = P._public_url(mp4, f"{cid}-{d['job']}-{int(time.time())}.mp4")
            ok_ = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30).status == 200
            if not ok_:
                url = None
        except Exception as e:
            log("schedule: public copy failed (direct uploads instead)", cid, str(e)[:120]); url = None
        sch["url"] = url

    def do(n):
        try:
            if n == "fb" and not direct:
                sch["fb"] = fb_schedule(acc, mp4, fbcap, slot, url)
            elif n == "yt" and not direct:
                sch["yt"] = yt_schedule(acc, mp4, ytx, cv, slot)
            elif n == "ig":
                sch["ig_container"], sch["ig_url"] = ig_container(acc, mp4, cap, url)
            log("schedule: ready", cid, d["job"], n, "for", sch["at"])
        except Exception as e:
            sch[n + "_prep_error"] = _err(e); log("schedule: prepare failed", cid, n, sch[n + "_prep_error"][:200])
    ths = [threading.Thread(target=do, args=(n,)) for n in plats_do]
    [t.start() for t in ths]; [t.join() for t in ths]
    update(cid, d["job"], lambda r: r.update(sched=sch))


def unschedule(cid, d):
    """Owner pulled a scheduled reel: take it off Facebook and YouTube before they publish it."""
    s = d.get("sched") or {}
    acc = P.resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
    if s.get("fb"):
        try:
            P._req(f"{P.G}/{s['fb']}?access_token={acc['page_token']}", method="DELETE")
        except Exception as e:
            log("unschedule fb failed", cid, d["job"], _err(e)[:120])
    if s.get("yt") and acc.get("yt"):
        try:
            y = acc["yt"]
            tok = P._req("https://oauth2.googleapis.com/token", {"client_id": y["client_id"], "client_secret": y["client_secret"],
                                                                 "refresh_token": y["refresh_token"], "grant_type": "refresh_token"})["access_token"]
            urllib.request.urlopen(urllib.request.Request(f"https://www.googleapis.com/youtube/v3/videos?id={s['yt']}", method="DELETE",
                                                          headers={"Authorization": f"Bearer {tok}"}), timeout=60)
        except Exception as e:
            log("unschedule yt failed", cid, d["job"], _err(e)[:120])
    update(cid, d["job"], lambda r: (r.pop("sched", None), r.setdefault("unscheduled", time.strftime("%Y-%m-%d %H:%M"))))
    log("schedule: taken off FB/YT (owner changed it)", cid, d["job"])


def stage():
    now = dt.datetime.now()
    jobs = []
    for cid in pages():
        ch = channel(cid)
        rows = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
        for d in rows:                                   # pulled by the owner after it was scheduled
            if d.get("sched") and d.get("status") not in ("scheduled", "posted") and d["sched"].get("slot", 0) > time.time() \
                    and (d["sched"].get("fb") or d["sched"].get("yt")):
                unschedule(cid, d)
        sc_ = [d for d in rows if d.get("status") == "scheduled"]
        # 20 Nov: up to one prepared reel per daily slot (clip pages post 4 a day); finish what is missing on each
        for d in sc_:
            s = d.get("sched") or {}
            miss = [n for n in s.get("platforms") or [] if not (s.get("ig_container") if n == "ig" else s.get(n))]
            if miss and s.get("slot", 0) - time.time() > LEAD_MIN and time.time() - s.get("retried", 0) > 600:
                jobs.append((cid, ch, d, s["slot"], miss))
        if len(sc_) >= max(1, len(day_slots(ch, (now + dt.timedelta(hours=12)).date()))) or any(j[0] == cid for j in jobs):
            continue
        slot = next_slot(cid, ch, rows, now)
        if not slot or slot - time.time() > WINDOW:
            continue
        c = pick(cid, ch, rows)
        if not c:
            log("schedule", cid, "nothing to schedule for", dt.datetime.fromtimestamp(slot).strftime("%Y-%m-%d %H:%M"))
            if slot - time.time() < 3 * 3600 and ch.get("post") is not False:
                k = f"{cid}:{slot}"
                st = load(os.path.join(OUT, "schedule-warned.json"), {}) or {}
                if k not in st:
                    telegram(f"🚨 {cid}: nothing approved for the {dt.datetime.fromtimestamp(slot).strftime('%H:%M')} slot. "
                             "The prep lane builds this page first.")
                    st[k] = time.time(); save(os.path.join(OUT, "schedule-warned.json"), st)
            continue
        jobs.append((cid, ch, c, slot))
    ths = [threading.Thread(target=prepare, args=j) for j in jobs]   # all pages side by side
    [t.start() for t in ths]; [t.join() for t in ths]


# ---------------------------------------------------------------- publish at the slot
def _direct(cid, acc, n, d, s):
    job = os.path.join(OUT, cid, d["job"])
    plan, cap, fbcap, ytx = _texts(cid, job, load(os.path.join(job, "plan.json"), {}))
    mp4 = s.get("mp4") or os.path.join(job, f"{cid}-{d['job']}.mp4")
    if n == "ig":
        return P.instagram(acc, mp4, cap)
    if n == "fb":
        if s.get("url"):                                # Facebook fetches the public copy (no binary push)
            tok, pid = acc["page_token"], acc["page_id"]
            st = P._req(f"{P.G}/{pid}/video_reels", {"upload_phase": "start", "access_token": tok})
            P._req(st["upload_url"], b"", {"Authorization": f"OAuth {tok}", "file_url": s["url"]}, "POST")
            P._req(f"{P.G}/{pid}/video_reels", {"upload_phase": "finish", "video_id": st["video_id"], "video_state": "PUBLISHED",
                                                 "description": fbcap, "access_token": tok})
            return st["video_id"]
        return P.facebook(acc, mp4, fbcap)
    return P.youtube(acc, mp4, ytx["title"], ytx["description"], ytx.get("tags"), os.path.join(job, "cover.jpg"))


def fire_one(cid, d):
    s = dict(d.get("sched") or {})
    acc = P.resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
    res, lock = {}, threading.Lock()

    def go(n):
        try:
            if n == "ig" and s.get("ig_container"):
                try:
                    v = P._req(f"{P.G}/{acc['ig_user_id']}/media_publish", {"creation_id": s["ig_container"], "access_token": acc["page_token"]})["id"]
                except Exception as e:                   # expired / refused container: upload now instead
                    log("schedule: IG container refused, uploading now", cid, _err(e)[:150])
                    v = _direct(cid, acc, "ig", d, s)
            elif n in ("fb", "yt") and s.get(n):
                v = s[n]                                 # the platform publishes it at the slot by itself
            else:
                v = _direct(cid, acc, n, d, s)          # no preparation (late approval / prep failed): upload now
            with lock:
                res[n] = v
            log("published", cid, n, v)
        except Exception as e:
            with lock:
                res[n + "_error"] = _err(e)
            log("publish fail", cid, n, res[n + "_error"][:200])
            telegram(f"⚠️ {cid}: {n.upper()} post failed ({res[n + '_error'][:200]}). The other platforms went out.")
    ths = [threading.Thread(target=go, args=(n,)) for n in s.get("platforms") or ["ig", "fb", "yt"]]
    [t.start() for t in ths]; [t.join() for t in ths]
    ok = any(k in res for k in ("ig", "fb", "yt"))
    update(cid, d["job"], lambda r: r.update(status="posted" if ok else "approved",
                                             posted={"at": time.strftime("%Y-%m-%d %H:%M"), **res}))
    if not ok:
        telegram(f"🚨 {cid} {d['job']}: nothing went out at {s.get('at')}: {str(res)[:300]}")
        return
    after(cid, d, acc, res, s)


def after(cid, d, acc, res, s):
    """What publish.post_one did after a post: playlist, Whop submit for campaign clips, serial extras, one Telegram line."""
    ch = channel(cid)
    job = os.path.join(OUT, cid, d["job"])
    plan = load(os.path.join(job, "plan.json"), {})
    if res.get("yt"):
        try:
            import ytlists
            ytlists.add(acc, dict(ch, id=cid), d, res["yt"])
        except Exception as e:
            log("ytlists failed", str(e)[:120])
    sk = (plan.get("clip") or {}).get("source")
    if sk and any(k in res for k in ("ig", "yt")):
        try:
            src = ((load(os.path.join(ROOT, "channels", cid, "sources.json"), {}) or {}).get("sources") or {}).get(sk) or {}
            links = []
            if res.get("ig"):
                pl = P._req(f"{P.G}/{res['ig']}?fields=permalink&access_token={acc['page_token']}").get("permalink")
                links.append(pl or f"Instagram media {res['ig']}")
            if res.get("yt"):
                links.append(f"https://youtube.com/shorts/{res['yt']}")
            if src.get("share_back"):
                try:
                    import creatorask
                    creatorask.share_clip(cid, sk, s.get("mp4"), links)
                except Exception as e:
                    log("share_back failed", sk, str(e)[:120])
            if src.get("campaign_url"):
                update(cid, d["job"], lambda r: r.update(submit={"campaign": src["campaign_url"], "links": links,
                                                                  "at": time.strftime("%Y-%m-%d %H:%M")}))
                # 20 Nov owner: "do whop in priority, every time": the submit-only unit (no login check, no joining)
                os.system("sudo systemctl start --no-block studio-whopsubmit.service")
            log("campaign clip posted, whopbot submits:", src.get("campaign_url") or sk, links)
        except Exception as e:
            log("campaign submit note failed", str(e)[:120])
    if any(k in res for k in ("ig", "fb")) and ch.get("serial"):
        try:
            import extras, serials
            extras.recap_story(cid, d, acc, plan)
            st, n = serials._find(ch, d.get("topic"))
            if st and n == len(st["parts"]):
                lc = extras.long_cut(cid, st)
                if lc and acc.get("yt"):
                    P.youtube(acc, lc, f"{st['title']} - Poori Kahani (All Parts)", f"{st['logline']}\n\nSaare parts ek saath.",
                              [st["title"], "hindi story", "kahani"], None)
        except Exception as e:
            log("serial extras failed", str(e)[:120])
    from core import fyi
    fyi(f"📤 {cid} {d['job']} posted: {res}")


def fire():
    due = []
    for cid in pages():
        for d in load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []:
            if d.get("status") == "scheduled" and (d.get("sched") or {}).get("slot", 1e12) <= time.time() + 20:
                due.append((cid, d))
    ths = [threading.Thread(target=fire_one, args=x) for x in due]    # every page at the same moment
    [t.start() for t in ths]; [t.join() for t in ths]


def status():
    for cid in pages():
        for d in load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []:
            if d.get("status") == "scheduled":
                s = d.get("sched") or {}
                print(f"{cid:17s} {d['job']:15s} {s.get('at')}  ig={'ready' if s.get('ig_container') else '-'} "
                      f"fb={s.get('fb', '-')} yt={s.get('yt', '-')} errors={[k for k in s if k.endswith('_error')]}")


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "status"
    lk = open(os.path.join(OUT, f".schedule-{a}.lock"), "w")
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("schedule", a, "already running"); sys.exit(0)
    {"stage": stage, "fire": fire, "status": status}[a]()
