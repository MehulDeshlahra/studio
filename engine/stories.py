"""Daily Instagram + Facebook Stories for every Studio page (owner 18 Nov: "every channel should get stories daily").
Same idea as VAJRA's social/story.py: Instagram only takes a Story from a PUBLIC image URL, so every frame is pushed to the
public repo offhours-lab/studio-media (raw.githubusercontent.com serves it), then published through the Graph API.
Facebook Page Stories upload the file directly (unpublished photo -> photo_stories).
Two Stories a day per page (timer studio-stories, 11:00 and 19:00 IST), different formats, rotated so two in a row never
look alike. Content per page:
  tech  : MYTH ya SACH (question frame + answer frame), TECH FACT, "AAJ KA REEL" teaser, POLL (reply 1 or 2)
  katha : AAJ KI KATHA line, KAUN THA YE? (quiz + answer), festival card on festival days, teaser of the next reel
  raaz  : recap of the last part ("PICHHLE PART MEIN..."), GUESS KARO (reply), cast card ("KAUN HAI YE?"), next part teaser
Words come from the page's own reels (plan.json: title, hook, recap, claims) so a Story never invents facts; Gemini only
picks and shortens. Picture = a scene image of a recent reel (never the same one twice in 14 days).
API Stories cannot carry stickers, so each Story asks for a DM reply.
  python engine/stories.py [page ...] [--dry]"""
import base64, json, os, random, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, sh

DRY = "--dry" in sys.argv
MEDIA = os.path.expanduser("~/studio-media")
RAW = "https://raw.githubusercontent.com/offhours-lab/studio-media/main/"
STATE = os.path.join(OUT, "stories-state.json")
W, H = 1080, 1920
FONT = next((f for f in ("/usr/share/fonts/truetype/montserrat/Montserrat-Black.ttf", os.path.expanduser("~/.fonts/Montserrat-Black.ttf"),
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if os.path.exists(f)), "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FORMATS = {"tech": ["myth", "fact", "teaser", "poll"], "katha": ["katha", "quiz", "teaser", "festival"],
           "raaz": ["recap", "guess", "cast", "teaser"],
    "jain": ["katha", "quiz", "teaser", "festival"],
    "finance": ["myth", "fact", "teaser", "poll"],
}
THEME = {"tech": ("#0b0d12", "#f5c542"), "katha": ("#1a0d05", "#e8b04a"), "raaz": ("#05080a", "#f2b134"),
    "jain": ("#160d04", "#f2c14e"),
    "finance": ("#06110c", "#33d17a"),
}

ASK = """You write ONE Instagram Story for the faceless page "{name}" ({fmt_page}). Story type: {kind}.
Use ONLY facts from this material (our own reel; never invent facts, numbers or names):
{material}
Rules: Hinglish in Roman letters (short, spoken, warm); big text max 6 words per line; it must make people reply in DM or
tap to the reel. Types:
 myth   : top = a common belief as a question ("Raat bhar charging = battery kharab?"), answer = "SACH:" + 1 short line
 fact   : top = "KYA AAP JAANTE HO?", body = one surprising fact from the material (max 14 words)
 teaser : top = "AAJ KA REEL", body = the hook as a question without the answer
 poll   : top = a question with two options "1) ...  2) ...", ask = "Reply 1 ya 2"
 katha  : top = "AAJ KI KATHA", body = one line that makes you want the story (max 14 words)
 quiz   : top = "KAUN THA YE?" + a clue (max 12 words), answer = the name
 festival: top = the festival name, body = one line about why it is celebrated (from the material only)
 recap  : top = "PICHHLE PART MEIN...", body = what happened last time in 2 short lines (no spoiler of the end)
 guess  : top = "AAGE KYA HOGA?", body = the cliffhanger as a question, ask = "DM mein apna guess bhejo"
 cast   : top = "KAUN HAI YE?" + the character's name, body = one line about them from the material
JSON {{"top": "...", "body": "...", "answer": "... or empty", "ask": "reply ask, MAX 24 characters (e.g. 'DM karo: SACH ya JHOOTH?')"}}
For myth and quiz the answer goes ONLY in "answer" (never in "body")."""


def _pages():
    out = []
    for cid in sorted(os.listdir(os.path.join(ROOT, "channels"))):
        c = load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}
        if c.get("status") in ("pilot", "active", "live", "live (warm-up)"):
            out.append((cid, c))
    return out


def _material(cid, ch, kind):
    done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
    rows = [d for d in done if not d["job"].endswith("-en") and os.path.exists(os.path.join(OUT, cid, d["job"], "plan.json"))]
    if kind == "festival":
        try:
            import extras
            day, fest = extras.festival_today(0)
            if not fest:
                return None, None
            return f"Festival today: {fest}.", None
        except Exception:
            return None, None
    if kind in ("recap", "guess", "cast") and ch.get("serial"):
        import serials
        # 18 Nov: a recap / cast card of a part nobody has seen (or a rejected one) makes no sense: posted parts only
        posted = {d["job"] for d in done if d.get("status") == "posted"}
        sts = [s for s in serials.stories(cid) if any(j in posted for j in (s.get("made_jobs") or {}).values())]
        if not sts:
            return None, None
        s = sts[-1]
        n = max(int(k) for k, j in s["made_jobs"].items() if j in posted)
        part = s["parts"][n - 1]
        job = s["made_jobs"][str(n)]
        mat = f"Serial: {s['title']} ({s['genre']}). Logline: {s['logline']}\nPart {n}: {part.get('beats')}\nCliffhanger: {part.get('cliffhanger')}\nCast: {json.dumps(s['cast'], ensure_ascii=False)}"
        return mat, job
    # 18 Nov: picked from any of the last 6 rows, so Stories teased rejected and held videos ("AAJ KA REEL" for a reel that
    # never goes out). Teaser = the next approved video (the one publish.py posts today); others = posted or approved ones.
    if kind == "teaser":
        nxt = next((d for d in rows if d.get("status") == "approved"), None)
        rows = [nxt] if nxt else []
    else:
        rows = [d for d in rows if d.get("status") in ("posted", "approved")][-6:]
    if not rows:
        return None, None
    d = random.choice(rows)
    p = load(os.path.join(OUT, cid, d["job"], "plan.json"), {}) or {}
    vo = " ".join(x.get("vo", "") for x in p.get("scenes", []))[:1200]
    mat = f"Reel title: {p.get('title')}\nScript: {vo}\nFacts (sourced): {json.dumps([c.get('claim') for c in p.get('claims', [])][:6], ensure_ascii=False)}"
    return mat, d["job"]


def _picture(cid, job, used):
    cands = []
    if job:
        a = load(os.path.join(OUT, cid, job, "assets.json"), {}) or {}
        cands = [v.get("image") for k, v in sorted(a.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 99) if (v or {}).get("image")]
        # 18 Nov: never the cover (it already carries its own big text, Story text on top looked cluttered)
    cands = [c for c in cands if c and os.path.exists(c) and time.time() - used.get(c, 0) > 14 * 86400]
    return cands[0] if cands else None


def _esc(t):
    return (t or "").replace("\\", "").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def _frame(cid, pic, top, body, ask, out, answer=False):
    bg, acc = THEME.get(cid, THEME["tech"])
    lines = []
    def wrap(t, n):
        w, cur, res = t.split(), "", []
        for x in w:
            if len(cur) + len(x) + 1 > n:
                res.append(cur); cur = x
            else:
                cur = (cur + " " + x).strip()
        if cur:
            res.append(cur)
        return res[:4]
    tl, bl = wrap(top.upper(), 18), wrap(body, 26)
    vf = []
    if pic:
        src = ["-i", pic]
        vf.append(f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},eq=brightness=-0.12:saturation=1.05")
        vf.append(f"drawbox=x=60:y=300:w={W - 120}:h=760:color=black@0.62:t=fill")
    else:
        src = ["-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}"]
    y = 360
    for t in tl:
        vf.append(f"drawtext=fontfile={FONT}:text='{_esc(t)}':fontsize=96:fontcolor={acc}:x=(w-tw)/2:y={y}:borderw=4:bordercolor=black@0.7"); y += 112
    y += 60
    for t in bl:
        vf.append(f"drawtext=fontfile={FONT}:text='{_esc(t)}':fontsize=70:fontcolor=white:x=(w-tw)/2:y={y}:borderw=3:bordercolor=black@0.7"); y += 86
    if ask:
        vf.append(f"drawbox=x=90:y=1560:w={W - 180}:h=150:color={acc}@0.95:t=fill")
        a_ = ask.strip()[:40]
        fs_ = 58 if len(a_) <= 24 else 50 if len(a_) <= 30 else 42
        vf.append(f"drawtext=fontfile={FONT}:text='{_esc(a_)}':fontsize={fs_}:fontcolor=black:x=(w-tw)/2:y={1635 - fs_ // 2}")
    sh(["ffmpeg", "-v", "error", "-y"] + src + ["-vf", ",".join(vf), "-frames:v", "1", "-q:v", "3", out], timeout=120)
    return out


def _host(files):
    """Copy frames into the public repo, push, wait until raw.githubusercontent serves them. Keeps 3 days of files."""
    d = os.path.join(MEDIA, "stories")
    subprocess.run(["git", "-C", MEDIA, "pull", "-q", "--rebase"], timeout=120)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        p = os.path.join(d, f)
        if f.endswith(".jpg") and time.time() - os.path.getmtime(p) > 3 * 86400:
            os.remove(p)
    names = []
    for src in files:
        n = f"{time.strftime('%Y%m%d-%H%M%S')}-{os.path.basename(src)}"
        shutil.copy(src, os.path.join(d, n)); names.append(n)
    for c in (["git", "-C", MEDIA, "add", "-A"], ["git", "-C", MEDIA, "commit", "-qm", "stories"], ["git", "-C", MEDIA, "push", "-q"]):
        subprocess.run(c, check=True, timeout=180)
    urls = []
    for n in names:
        u = RAW + "stories/" + n
        for _ in range(30):
            try:
                if urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=20).status == 200:
                    break
            except Exception:
                pass
            time.sleep(6)
        else:
            raise RuntimeError("not public yet: " + n)
        urls.append(u)
    return urls


def _post_ig(acc, url):
    import publish
    c = publish._req(f"{publish.G}/{acc['ig_user_id']}/media", {"media_type": "STORIES", "image_url": url, "access_token": acc["page_token"]})
    for _ in range(20):
        st = publish._req(f"{publish.G}/{c['id']}?fields=status_code&access_token={acc['page_token']}")
        if st.get("status_code") in ("FINISHED", None):
            break
        time.sleep(4)
    return publish._req(f"{publish.G}/{acc['ig_user_id']}/media_publish", {"creation_id": c["id"], "access_token": acc["page_token"]})["id"]


def _post_fb(acc, path):
    import publish, uuid
    b = "----st" + uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"published\"\r\n\r\nfalse\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"access_token\"\r\n\r\n{acc['page_token']}\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"source\"; filename=\"s.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode() \
        + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request(f"{publish.G}/{acc['page_id']}/photos", data=body,
                                                                headers={"Content-Type": f"multipart/form-data; boundary={b}"}), timeout=120))
    return publish._req(f"{publish.G}/{acc['page_id']}/photo_stories", {"photo_id": r["id"], "access_token": acc["page_token"]}).get("post_id", r["id"])


def one(cid, ch, st):
    import plan as planner, publish
    hist = st.setdefault(cid, {"last": [], "used": {}})
    kinds = [k for k in FORMATS.get(cid, ["teaser"]) if k not in hist["last"][-2:]]
    if cid == "katha":
        try:
            import extras
            if extras.festival_today(0)[1]:
                kinds = ["festival"] + kinds
        except Exception:
            pass
    work = os.path.join(OUT, "stories", cid); os.makedirs(work, exist_ok=True)
    for kind in kinds:
        mat, job = _material(cid, ch, kind)
        if not mat:
            continue
        r = planner.ask(ASK.format(name=ch.get("name", cid), fmt_page=ch.get("format", "")[:160], kind=kind, material=mat), max_tokens=600) or {}
        if not isinstance(r, dict) or not r.get("top"):
            continue
        pic = _picture(cid, job, hist["used"])
        frames = [_frame(cid, pic, r["top"], r.get("body", ""), r.get("ask", ""), os.path.join(work, f"{kind}-1.jpg"))]
        if r.get("answer") and kind in ("myth", "quiz"):
            frames.append(_frame(cid, pic, "JAWAB", r["answer"], "Aur aise sawal? Follow karo", os.path.join(work, f"{kind}-2.jpg")))
        log("story", cid, kind, "|", r["top"][:50], "|", str(r.get("body", ""))[:60])
        if DRY:
            return {"kind": kind, "frames": frames}
        acc = publish.resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
        res = {}
        try:
            urls = _host(frames)
            res["ig"] = [_post_ig(acc, u) for u in urls] if acc.get("ig_user_id") else None
        except Exception as e:
            log("story ig failed", cid, str(e)[:160]); res["ig_error"] = str(e)[:160]
        try:
            res["fb"] = [_post_fb(acc, f) for f in frames]
        except Exception as e:
            log("story fb failed", cid, str(e)[:160]); res["fb_error"] = str(e)[:160]
        hist["last"] = (hist["last"] + [kind])[-6:]
        if pic:
            hist["used"][pic] = time.time()
        log("story posted", cid, kind, res)
        return res
    log("story: nothing to say today for", cid)
    return None


def run(pages=None):
    st = load(STATE, {}) or {}
    out = {}
    for cid, ch in _pages():
        if pages and cid not in pages:
            continue
        w = ch.get("warmup", {})
        if not DRY and w.get("post_from") and time.strftime("%Y-%m-%d") < w["post_from"]:
            log("story", cid, "warm-up: no stories before", w["post_from"]); continue
        try:
            out[cid] = one(cid, ch, st)
        except Exception as e:
            log("story failed", cid, str(e)[:160])
    save(STATE, st)
    return out


if __name__ == "__main__":
    print(json.dumps(run([a for a in sys.argv[1:] if not a.startswith("--")] or None), ensure_ascii=False, indent=1)[:1500])
