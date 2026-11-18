"""Growth extras approved by the owner on 17 Nov (items 2-11 of the brainstorm). Small, separate, each safe to fail.
  cliffhanger_line(ch, topic, plan)   2: a different, specific "next part" line every day for Aage Suno serials
  recap_story(cid, row, acc)          3: an Instagram/Facebook Story the day a serial part goes up ("Pichhle part mein...")
  guess_question(ch, topic)           4: the first comment asks viewers to guess what happens next (comments.py posts it)
  festival_today()                    5: today's Hindu festival (free calendar list below + the planner) -> Katha topic first
  katha_series()                      6: 5-7 part Katha series (Jyotirlinga, Dashavatar, Mahabharat characters...) as a queue
  mythbust_due(cid)                   7: one Kaise Tech myth-buster a week (Monday)
  long_cut(cid, story)                8: all parts of a finished serial joined into one long YouTube video
  STING                               9: each page's signature sound on the first frame (sfx file per page)
  scene_dropoff(cid)                  10: where people leave (avg watch vs scene times) -> lessons for the planner
  best_frame(job_dir, plan)           11: the strongest frame of the video for the cover (vision pick)
  python engine/extras.py festival|katha_series|dropoff <cid>"""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log, sh

# ---------- 9: signature sound on frame 0 (files in ~/studio-assets/audio/sfx/) ----------
STING = {"tech": "sfx/whoosh-fast.mp3", "katha": "sfx/impact.mp3", "raaz": "sfx/air-zoom.mp3"}


# ---------- 2 + 4: Aage Suno serial lines ----------
def cliffhanger_line(ch, topic, plan):
    """'Part n kal' becomes a specific teaser ('Part 4 mein pata chalega darwaza kisne khola')."""
    m = re.search(r" - Part (\d+)$", str(topic or ""))
    if not m:
        return None
    try:
        import serials
        s, n = serials._find(ch, topic)
        if not s or n >= len(s["parts"]):
            return None
        nxt = s["parts"][n]
        import plan as planner
        r = planner.ask(f'Write ONE short Hinglish line (Roman letters, 6-11 words) that teases Part {n + 1} of our serial without '
                        f'spoiling it. Next part is about: {nxt.get("beats", "")[:300]}. Start with "Part {n + 1} mein". '
                        'JSON {"line": "..."}', max_tokens=200) or {}
        line = str(r.get("line", "")).strip()
        return line if 4 <= len(line.split()) <= 14 else None
    except Exception as e:
        log("cliffhanger line failed", str(e)[:100]); return None


def guess_question(ch, topic):
    m = re.search(r" - Part (\d+)$", str(topic or ""))
    if not m:
        return None
    return "Aapko kya lagta hai aage kya hoga? Sabse sahi guess wale ko kal pin karenge 👇"


# ---------- 3: recap Story ----------
def recap_story(cid, row, acc, plan):
    """Story image: the part's cover + 'PART n AAJ' + one recap line; posted on IG (and FB) Stories after the part posts."""
    import publish
    jd = os.path.join(OUT, cid, row["job"])
    cv = os.path.join(jd, "cover.jpg")
    if not os.path.exists(cv) or not acc.get("ig_user_id"):
        return None
    m = re.search(r"Part (\d+)", str(row.get("topic") or plan.get("title") or ""))
    part = m.group(1) if m else ""
    recap = (plan.get("recap") or (plan.get("scenes") or [{}])[0].get("vo", ""))[:90]
    out = os.path.join(jd, "story.jpg")
    t1 = f"PART {part} AAJ" if part else "NAYI KAHANI"
    txt = os.path.join(jd, "story.txt"); open(txt, "w", encoding="utf-8").write(recap)
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    sh(["ffmpeg", "-v", "error", "-y", "-i", cv, "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=brightness=-0.15,"
        f"drawtext=fontfile={font}:text='{t1}':fontsize=96:fontcolor=0xf2b134:x=(w-tw)/2:y=260:box=1:boxcolor=black@0.55:boxborderw=26,"
        f"drawtext=fontfile={font}:textfile={txt}:fontsize=52:fontcolor=white:x=(w-tw)/2:y=1500:box=1:boxcolor=black@0.55:boxborderw=20,"
        f"drawtext=fontfile={font}:text='Reel dekho - link profile pe':fontsize=44:fontcolor=white:x=(w-tw)/2:y=1680",
        "-frames:v", "1", "-q:v", "2", out], timeout=120)
    try:
        # IG Stories need a public URL; the dashboard serves /media/<cid>/<job>/<file> over Tailscale only, so use the
        # resumable upload the same way as reels (IG accepts image upload by URL only) -> skip IG if no public URL.
        pub = os.environ.get("STUDIO_PUBLIC_MEDIA")          # optional public base URL (e.g. a free static host)
        if pub:
            url = f"{pub.rstrip('/')}/{cid}/{row['job']}/story.jpg"
            c = publish._req(f"{publish.G}/{acc['ig_user_id']}/media", {"media_type": "STORIES", "image_url": url, "access_token": acc["page_token"]})
            publish._req(f"{publish.G}/{acc['ig_user_id']}/media_publish", {"creation_id": c["id"], "access_token": acc["page_token"]})
        # Facebook Page Story from a local file: upload an unpublished photo, then photo_stories
        ph = publish._req(f"{publish.G}/{acc['page_id']}/photos", None) if False else None
        import urllib.request, uuid
        b = "----st" + uuid.uuid4().hex
        body = (f"--{b}\r\nContent-Disposition: form-data; name=\"published\"\r\n\r\nfalse\r\n"
                f"--{b}\r\nContent-Disposition: form-data; name=\"access_token\"\r\n\r\n{acc['page_token']}\r\n"
                f"--{b}\r\nContent-Disposition: form-data; name=\"source\"; filename=\"story.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode() \
            + open(out, "rb").read() + f"\r\n--{b}--\r\n".encode()
        r = json.load(urllib.request.urlopen(urllib.request.Request(f"{publish.G}/{acc['page_id']}/photos", data=body,
                                                                    headers={"Content-Type": f"multipart/form-data; boundary={b}"}), timeout=120))
        publish._req(f"{publish.G}/{acc['page_id']}/photo_stories", {"photo_id": r["id"], "access_token": acc["page_token"]})
        log("recap story posted", cid, row["job"], "(fb" + (" + ig" if pub else "") + ")")
        return True
    except Exception as e:
        log("recap story failed", cid, row["job"], str(e)[:160]); return None


# ---------- 5: festivals ----------
# Fixed-date and approximate 2026-2027 dates (Hindu calendar is lunar; the planner double-checks the date and skips if unsure).
FESTIVALS = {
    "2026-11-24": "Kartik Purnima / Dev Deepawali", "2026-12-01": "Gita Jayanti (Mokshada Ekadashi)", "2026-12-23": "Dattatreya Jayanti",
    "2027-01-14": "Makar Sankranti", "2027-02-11": "Vasant Panchami", "2027-03-06": "Maha Shivratri", "2027-03-22": "Holi",
    "2027-04-15": "Ram Navami", "2027-04-21": "Hanuman Jayanti", "2027-05-19": "Akshaya Tritiya", "2027-07-18": "Guru Purnima",
    "2027-08-17": "Raksha Bandhan", "2027-08-25": "Janmashtami", "2027-09-04": "Ganesh Chaturthi", "2027-10-01": "Navratri begins",
    "2027-10-10": "Dussehra", "2027-10-29": "Diwali", "2027-10-31": "Bhai Dooj", "2027-11-03": "Chhath Puja",
}


def festival_today(days_ahead=1):
    """The festival happening tomorrow (a Katha video is made a day ahead so it posts on the day)."""
    for k in range(0, days_ahead + 1):
        d = time.strftime("%Y-%m-%d", time.localtime(time.time() + k * 86400))
        if d in FESTIVALS:
            return d, FESTIVALS[d]
    return None, None


# ---------- 6: Katha series ----------
KATHA_SERIES = [
    ("12 Jyotirlinga ki katha", ["Somnath", "Mallikarjun", "Mahakaleshwar", "Omkareshwar", "Kedarnath", "Bhimashankar", "Kashi Vishwanath"]),
    ("Vishnu ke Dashavatar", ["Matsya", "Kurma", "Varaha", "Narasimha", "Vamana", "Parashurama", "Rama"]),
    ("Mahabharat ke anjaane yoddha", ["Barbarik", "Ghatotkacha", "Iravan", "Vikarna", "Yuyutsu"]),
    ("Ramayan ke chhupe kirdaar", ["Jatayu", "Shabari", "Urmila", "Kumbhakarna", "Vibhishan"]),
    ("Shiv ji ke avatar", ["Virabhadra", "Bhairav", "Hanuman", "Ashwatthama", "Sharabha"]),
]


def katha_next(ch):
    """Next topic of the running Katha series: '<series> - Part n: <subject>' (state in channels/katha/series-state.json)."""
    p = os.path.join(ROOT, "channels", ch["id"], "series-state.json")
    st = load(p, {"i": 0, "n": 0}) or {"i": 0, "n": 0}
    if st.get("redo"):          # 18 Nov: a part whose build died (janitor.py) is made again before the series moves on
        topic = st["redo"].pop(0); save(p, st)
        return topic
    name, subs = KATHA_SERIES[st["i"] % len(KATHA_SERIES)]
    if st["n"] >= len(subs):
        st = {"i": st["i"] + 1, "n": 0}; name, subs = KATHA_SERIES[st["i"] % len(KATHA_SERIES)]
    topic = f"{name} - Part {st['n'] + 1}: {subs[st['n']]}"
    st["n"] += 1; save(p, st)
    return topic


# ---------- 7: Tech myth-buster ----------
MYTHS = ["Raat bhar charging se battery kharab hoti hai?", "5G se sehat ko nuksan hota hai?", "Incognito mode mein koi nahi dekhta?",
         "Zyada bars matlab fast internet?", "Phone ko chawal mein rakhne se theek hota hai?", "Apps band karne se battery bachti hai?",
         "Megapixel zyada matlab photo achhi?", "Mac ko virus nahi hota?", "Airplane mode mein phone jaldi charge hota hai?",
         "Flight mode na karo toh plane gir sakta hai?"]


def mythbust_due(ch):
    """Monday: one myth-buster (if not made this week)."""
    if time.strftime("%a") != "Mon":
        return None
    done = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), []) or []
    wk = time.strftime("%Y-%W")
    if any(d.get("myth_week") == wk for d in done):
        return None
    used = {str(d.get("topic", "")).lower() for d in done}
    for m in MYTHS:
        if m.lower() not in used:
            return "MYTH: " + m
    return None


# ---------- 8: long YouTube cut of a finished serial ----------
def long_cut(cid, story):
    jobs = [story["made_jobs"].get(str(p["n"])) for p in story["parts"]]
    files = [os.path.join(OUT, cid, j, f"{cid}-{j}.mp4") for j in jobs if j]
    files = [f for f in files if os.path.exists(f)]
    if len(files) < len(story["parts"]):
        return None
    out = os.path.join(OUT, cid, f"serial-{story['slug']}.mp4")
    lst = out + ".txt"
    open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out], timeout=900)
    os.remove(lst)
    log("long cut made", cid, story["slug"], len(files), "parts")
    return out


# ---------- 10: where people leave ----------
def scene_dropoff(cid):
    """For posted videos with stats: compare avg watch time with scene start times. The scene where the average viewer
    leaves is noted with its line, and the 3 most common 'leave' scene types/lines become a lesson for the planner."""
    done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
    notes = []
    for d in done:
        st = d.get("stats") or {}
        aw = st.get("avg_watch_s")
        if not aw:
            continue
        tj = load(os.path.join(OUT, cid, d["job"], "timing.json"), {}) or {}
        pl = load(os.path.join(OUT, cid, d["job"], "plan.json"), {}) or {}
        lines = tj.get("lines") or []
        k = next((i for i, L in enumerate(lines) if L.get("start", 0) <= aw < (lines[i + 1]["start"] if i + 1 < len(lines) else 1e9)), None)
        if k is None:
            continue
        sc = (pl.get("scenes") or [{}] * (k + 1))[k] if k < len(pl.get("scenes") or []) else {}
        notes.append({"job": d["job"], "views": st.get("views"), "avg_watch_s": aw, "dur": tj.get("dur"), "leave_scene": k + 1,
                      "type": sc.get("type"), "line": sc.get("vo", "")[:90]})
    if len(notes) >= 3:
        early = sorted(notes, key=lambda x: x["avg_watch_s"])[:3]
        txt = "; ".join(f"scene {n['leave_scene']} ({n['type']}: \"{n['line'][:50]}\") at {n['avg_watch_s']} s" for n in early)
        lp = os.path.join(ROOT, "channels", cid, "lessons-auto.md")
        cur = open(lp, encoding="utf-8").read() if os.path.exists(lp) else ""
        line = f"- Retention ({time.strftime('%d %b')}): the average viewer leaves at {txt}. Make those moments stronger (new info, a cut, a question) and shorten anything before them."
        if "Retention (" + time.strftime('%d %b') not in cur:
            with open(lp, "a", encoding="utf-8", newline="\n") as f:
                f.write(line + "\n")
    save(os.path.join(OUT, f"dropoff-{cid}.json"), notes)
    return notes


# ---------- 11: best frame for the cover ----------
def best_image(paths, work):
    """Reorder candidate cover pictures: the most scroll-stopping first (vision pick); unchanged on any failure."""
    if len(paths) < 2:
        return paths
    try:
        import realmedia
        os.makedirs(work, exist_ok=True)
        i, why = realmedia.pick([{"path": p} for p in paths[:6]], "the most striking, emotional, high-contrast picture that would make a "
                                "stranger stop scrolling (a clear subject, a face or a dramatic moment)", "photo", work)
        if i is not None and i > 0:
            log("cover: best picture is #", i + 1, why)
            return [paths[i]] + paths[:i] + paths[i + 1:]
    except Exception as e:
        log("best image failed", str(e)[:100])
    return paths


def best_frame(job_dir, plan, n=8):
    """Grab n candidate frames (scene middles, no captions-only scenes), let Gemini pick the most striking one; returns path."""
    mp4 = next((os.path.join(job_dir, f) for f in os.listdir(job_dir) if f.endswith(".mp4") and not f.startswith(("raw", "post"))), None)
    tj = load(os.path.join(job_dir, "timing.json"), {}) or {}
    if not mp4 or not tj.get("lines"):
        return None
    cands = []
    for i, L in enumerate(tj["lines"]):
        typ = (plan.get("scenes") or [{}] * (i + 1))[i].get("type") if i < len(plan.get("scenes") or []) else None
        if typ in ("choice", "title", "card", "stat", "ui", "compare", "chart", "code"):
            continue
        cands.append((i, (L["start"] + L["end"]) / 2))
    cands = cands[:: max(1, len(cands) // n)][:n]
    if len(cands) < 2:
        return None
    work = os.path.join(job_dir, ".bf"); os.makedirs(work, exist_ok=True)
    fr = []
    for k, (i, t) in enumerate(cands):
        f = os.path.join(work, f"f{k}.jpg")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-q:v", "2", f], timeout=60)
        fr.append(f)
    try:
        import realmedia
        i, why = realmedia.pick([{"path": f} for f in fr], "the most striking, emotional, high-contrast frame that would make a stranger stop "
                                "scrolling (a clear subject, a face or a dramatic moment; not text, not empty)", "photo", work)
        if i is None or i < 0:
            return None
        out = os.path.join(job_dir, "best-frame.jpg")
        os.replace(fr[i], out)
        log("best frame for cover:", os.path.basename(job_dir), "scene", cands[i][0] + 1, why)
        return out
    except Exception as e:
        log("best frame failed", str(e)[:100]); return None
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "festival":
        print(festival_today(3))
    elif cmd == "katha_series":
        from core import channel; print(katha_next(channel("katha")))
    elif cmd == "dropoff":
        print(scene_dropoff(sys.argv[2]))
