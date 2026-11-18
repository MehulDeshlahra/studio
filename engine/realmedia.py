"""realmedia: real logos and real photos for scenes that name a real thing (brand, app, product, place, public figure).

A scene may carry  "real": {"q": "search query", "kind": "logo|photo", "subject": "what the picture must show"}.
fetch() searches the web (Bing images, then Wikimedia Commons), downloads the best-looking candidates, lets Gemini
look at them and pick the one that really shows the subject, then lays it out for the video:
  classic look  -> 1080x1920 frame: blurred copy of the picture behind, the real picture sharp in front
  lab look      -> 900:760 canvas on black (the lab compositor blends it with 'lighten'); logos sit on a light card
Returns the image path, or None (the caller then makes an AI image as before)."""
import base64, html, json, os, re, shutil, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import log, sh

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
WATERMARKED = re.compile(r"alamy|shutterstock|dreamstime|istockphoto|gettyimages|depositphotos|123rf|bigstock|adobestock|stock\.adobe|canstock|agefotostock|pond5", re.I)


WM_UA = {"User-Agent": "StudioBot/1.0 (https://kaise.tech; mehuldeshlahra12@gmail.com) python-urllib", "Accept-Language": "en"}


def _get(url, timeout=20, maxb=12_000_000):
    """Wikimedia asks bots for a descriptive User-Agent with a contact, and answers 429 when we are fast: wait and retry."""
    hdr = WM_UA if "wikimedia.org" in url or "wikipedia.org" in url else H
    for attempt in range(4):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout)
            return r.read(maxb), (r.headers.get("content-type") or "").lower()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                try:
                    w = min(40, int(e.headers.get("Retry-After") or 8))
                except Exception:
                    w = 8
                time.sleep(w + 2 * attempt); continue
            raise


def bing(q, n=14):
    try:
        t = _get("https://www.bing.com/images/search?" + urllib.parse.urlencode({"q": q, "form": "HDRSC2", "first": 1}), 25)[0].decode("utf8", "ignore")
    except Exception as e:
        log("realmedia bing fail", str(e)[:80]); return []
    out = []
    for m in re.findall(r'class="iusc"[^>]*? m="([^"]+)"', t):
        try:
            d = json.loads(html.unescape(m))
            if d.get("murl"):
                out.append(d["murl"])
        except Exception:
            pass
    return out[:n]


def commons(q, n=6):
    try:
        u = ("https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrlimit=%d&prop=imageinfo&iiprop=url%%7Cmime&iiurlwidth=1400&format=json&gsrsearch=%s"
             % (n, urllib.parse.quote(q)))
        d = json.loads(_get(u, 25)[0])
        return [p["imageinfo"][0]["thumburl"] for p in d.get("query", {}).get("pages", {}).values()
                if p.get("imageinfo") and p["imageinfo"][0].get("mime", "").startswith("image/") and "svg" not in p["imageinfo"][0]["mime"]]
    except Exception as e:
        log("realmedia commons fail", str(e)[:80]); return []


def official_logo(q):
    """18 Nov: Bing gave junk for "ChatGPT logo" and the judge rightly refused all of it. Wikidata keeps each brand's
    official logo file (P154, rendered to PNG by Commons) and website (P856 -> app icon). Returns [urls], best first."""
    name = re.sub(r"\b(official|logo|icon|app)\b", "", q, flags=re.I).strip() or q
    try:
        s = json.loads(_get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "wbsearchentities", "search": name, "language": "en", "limit": 3, "format": "json"}), 20)[0])
        out = []
        for hit in s.get("search", [])[:3]:
            e = json.loads(_get(f"https://www.wikidata.org/wiki/Special:EntityData/{hit['id']}.json", 20)[0])["entities"][hit["id"]]
            cl = e.get("claims", {})
            for c in cl.get("P154", [])[:1]:
                f = c["mainsnak"].get("datavalue", {}).get("value")
                if f:
                    out.append("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(f.replace(" ", "_")) + "?width=1000")
            for c in cl.get("P856", [])[:1]:
                site = c["mainsnak"].get("datavalue", {}).get("value")
                if site:
                    dom = urllib.parse.urlparse(site).netloc
                    out.append(f"https://www.google.com/s2/favicons?domain={dom}&sz=256")
            if out:
                return out
    except Exception as e:
        log("realmedia wikidata fail", name, str(e)[:80])
    return []


def _icon(src, out):
    """A square app-icon JPEG on white (transparent logos would turn black)."""
    sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", "color=c=white:s=256x256[bg];[0:v]scale=232:232:force_original_aspect_ratio=decrease[l];[bg][l]overlay=(W-w)/2:(H-h)/2",
        "-frames:v", "1", "-q:v", "2", out], timeout=60)


def _probe(path):
    try:
        o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=30).stdout.strip().split(",")
        return int(o[0]), int(o[1])
    except Exception:
        return 0, 0


def download(urls, work, kind, want=6, min_side=None):
    got = []
    for i, u in enumerate(urls):
        if len(got) >= want:
            break
        if WATERMARKED.search(u):                 # stock sites burn a watermark into every preview (alamy in real-02)
            continue
        try:
            b, ct = _get(u, 15)
            if len(b) < 6000 or "image" not in ct or "svg" in ct or "gif" in ct:
                continue
            raw = os.path.join(work, f"raw{i}")
            open(raw, "wb").write(b)
            png = os.path.join(work, f"c{len(got)}.png")
            sh(["ffmpeg", "-v", "error", "-y", "-i", raw, "-frames:v", "1", "-vf", "scale='min(1600,iw)':-2", png], timeout=60)
            w, h = _probe(png)
            if min(w, h) < (min_side or (300 if kind == "logo" else 600)):
                continue
            got.append({"path": png, "w": w, "h": h, "url": u})
        except Exception:
            continue
    return got


def _gemini(parts):
    import tts, llm
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1, "maxOutputTokens": 600}}
    for m in tts.usable(MODELS):
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(m)})
            d = json.load(urllib.request.urlopen(r, timeout=120))
            return llm.parse_json("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
        except Exception as e:
            log("realmedia gemini fail", m, str(e)[:100])
    try:                                                   # 18 Nov: our Gemini keys out -> same question through OmniRoute
        return llm.from_parts(parts, max_tokens=600)
    except Exception as e:
        log("realmedia omniroute fail", str(e)[:120])
    return None


JUDGE = """The picture shows {n} candidate images (A, B, C ...) for a video scene about: "{subject}" ({kind}).
Pick the ONE that best shows exactly this subject. Good: the real, recognisable subject, clean, sharp, no watermark,
no big text banner or caption on top, not a collage, not a meme, not a different brand/person, not a tiny thumbnail.
For a logo: the official logo alone, clear and centred, on a plain white or solid background. REJECT any image that shows a grey/white checkerboard pattern (fake transparency), a mock-up, a business card, or a logo shrunk small inside a big empty area. For a photo: a natural well-lit photo of the subject.
Return JSON {{"best": "A" or "none", "why": "6 words"}}. Use "none" when no candidate really shows the subject."""


def pick(cands, subject, kind, work):
    if os.environ.get("REALMEDIA_NO_JUDGE"):          # tests only: take the first candidate
        return 0, "judge bypassed (test)"
    ins, fc = [], ""
    for i, c in enumerate(cands):
        ins += ["-i", c["path"]]
        fc += (f"[{i}:v]scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:color=0x888888,"
               f"drawtext=text='{'ABCDEF'[i]}':x=8:y=4:fontsize=44:fontcolor=yellow:box=1:boxcolor=black@0.7[t{i}];")
    fc += "".join(f"[t{i}]" for i in range(len(cands))) + (f"hstack={len(cands)}" if len(cands) > 1 else "null")   # hstack needs 2+ inputs
    sheet = os.path.join(work, "pick.jpg")
    sh(["ffmpeg", "-v", "error", "-y"] + ins + ["-filter_complex", fc, "-frames:v", "1", "-q:v", "3", sheet], timeout=60)
    r = _gemini([{"text": JUDGE.format(n=len(cands), subject=subject, kind=kind)},
                 {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(sheet, "rb").read()).decode()}}]) or {}
    if not r:
        return -2, "judge unavailable"
    b = str(r.get("best", "none")).strip().upper()[:1]
    return ("ABCDEF".find(b) if b in "ABCDEF"[:len(cands)] else -1), r.get("why", "")


def trim_margins(src, work):
    """Logos come with big empty borders (usually white): crop to the artwork plus a small margin. Returns a path."""
    try:
        o = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-vf", "negate,cropdetect=limit=40:round=2:reset=0", "-frames:v", "2", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=60).stderr
        m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", o)
        if not m:
            return src
        w, h, x, y = map(int, m[-1])
        W0, H0 = _probe(src)
        if w < 80 or h < 40 or w * h > 0.92 * W0 * H0 or w * h < 0.04 * W0 * H0:
            return src
        pad = int(max(w, h) * 0.06)
        x0, y0 = max(0, x - pad), max(0, y - pad)
        out = os.path.join(work, "trim.png")
        sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"crop={min(W0 - x0, w + 2 * pad)}:{min(H0 - y0, h + 2 * pad)}:{x0}:{y0}", out], timeout=60)
        return out
    except Exception:
        return src


def layout(src, out, kind, lab):
    """Lay the real picture out for the video; out is a JPEG."""
    if lab:
        # 1350x1140 (= 900:760 x1.5) on black. Logo: light rounded-ish card; photo: fitted.
        if kind == "logo":
            fc = ("color=c=black:s=1350x1140[bg];color=c=0xffffff:s=1100x900[card];[0:v]scale=860:660:force_original_aspect_ratio=decrease[l];"
                  "[card][l]overlay=(W-w)/2:(H-h)/2[c];[bg][c]overlay=(W-w)/2:(H-h)/2")
        else:
            fc = ("color=c=black:s=1350x1140[bg];[0:v]scale=1250:1040:force_original_aspect_ratio=decrease[p];[bg][p]overlay=(W-w)/2:(H-h)/2")
    else:
        if kind == "logo":
            fc = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:6,eq=brightness=-0.25[bg];"
                  "color=c=0xffffff:s=900x760[card];[b]scale=700:560:force_original_aspect_ratio=decrease[l];[card][l]overlay=(W-w)/2:(H-h)/2[c];"
                  "[bg][c]overlay=(W-w)/2:(H-h)/2")
        else:
            fc = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:6,eq=brightness=-0.3[bg];"
                  "[b]scale=1040:1180:force_original_aspect_ratio=decrease[p];[bg][p]overlay=(W-w)/2:(H-h)/2")
    sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", fc, "-frames:v", "1", "-q:v", "2", out], timeout=90)
    return out


LEDGER = os.path.join(os.path.expanduser("~/studio-out"), "realmedia-usage.json")
NO_REPEAT_DAYS = 30


def _ledger():
    try:
        return json.load(open(LEDGER))
    except Exception:
        return {}


def _used_recently(key):
    return time.time() - _ledger().get(key, 0) < NO_REPEAT_DAYS * 86400


def _mark_used(key):
    d = _ledger()
    d = {k: v for k, v in d.items() if time.time() - v < 90 * 86400}
    d[key] = time.time()
    try:
        tmp = LEDGER + ".tmp"; json.dump(d, open(tmp, "w")); os.replace(tmp, LEDGER)
    except Exception:
        pass


def _fingerprint(png):
    """8x8 average-hash of the picture: the same photo from two different URLs gets the same key."""
    try:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", png, "-vf", "scale=8:8,format=gray", "-f", "rawvideo", "-"],
                             capture_output=True, timeout=30).stdout
        if len(raw) == 64:
            m = sum(raw) / 64
            return "h" + "".join("1" if b > m else "0" for b in raw)
    except Exception:
        pass
    return None


def _similar(fp):
    """True when a picture used in the last 30 days differs from fp by <= 5 of 64 bits."""
    if not fp:
        return False
    for k, t in _ledger().items():
        if k.startswith("h") and len(k) == 65 and time.time() - t < NO_REPEAT_DAYS * 86400 \
                and sum(a != b for a, b in zip(k[1:], fp[1:])) <= 5:
            return True
    return False


def video_clip(q, out_mp4, subject=None, secs=6.0):
    """A real video clip from Wikimedia Commons (free licences, no key): <= 60 MB, >= 640 px wide, cut to 'secs' seconds,
    laid out 1080x1920 (landscape clips get a blurred copy behind). Returns {"path", "credit", "url"} or None."""
    subject = subject or q
    work = out_mp4 + ".work"
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work, exist_ok=True)
    try:
        u = ("https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrlimit=15&prop=imageinfo"
             "&iiprop=url%7Cmime%7Csize%7Cextmetadata&format=json&gsrsearch=" + urllib.parse.quote(q + " filetype:video"))
        d = json.loads(_get(u, 30)[0])
        cands = []
        for p in d.get("query", {}).get("pages", {}).values():
            i = (p.get("imageinfo") or [{}])[0]
            lic = (i.get("extmetadata", {}).get("LicenseShortName", {}) or {}).get("value", "")
            if not i.get("url") or i.get("size", 0) > 60e6 or (i.get("width") or 0) < 640 or not re.search(r"public domain|cc0|cc by", lic, re.I) \
                    or re.search(r"\bNC\b|\bND\b", lic):
                continue
            if _used_recently("v:" + i["url"]):
                continue
            auth = re.sub(r"<[^>]+>", "", (i.get("extmetadata", {}).get("Artist", {}) or {}).get("value", "") or "").strip()[:40]
            cands.append({"url": i["url"], "title": p["title"], "lic": lic, "author": auth, "size": i["size"]})
        shots = []
        for c in cands[:5]:
            try:
                raw = os.path.join(work, f"v{len(shots)}.webm")
                with open(raw, "wb") as f:
                    f.write(_get(c["url"], 90, 62_000_000)[0])
                dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", raw],
                                           capture_output=True, text=True, timeout=30).stdout.strip() or 0)
                if dur < 3:
                    continue
                ss = max(0.0, min(dur - secs - 0.2, dur * 0.3))
                png = os.path.join(work, f"c{len(shots)}.png")
                sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss + 1:.2f}", "-i", raw, "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", png], timeout=90)
                shots.append({"path": png, "raw": raw, "ss": ss, "dur": dur, **c})
            except Exception:
                continue
        if not shots:
            log("realmedia: no usable video for", q); return None
        i, why = pick(shots[:6], subject, "photo", work)
        if i < 0:
            log("realmedia: no video fits", repr(subject), why); return None
        c = shots[i]
        vf = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:6,eq=brightness=-0.25[bg];"
              "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,fps=30,format=yuv420p")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{c['ss']:.2f}", "-t", f"{secs:.2f}", "-i", c["raw"], "-an", "-vf", vf,
            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-g", "30", "-movflags", "+faststart", out_mp4], timeout=300)
        _mark_used("v:" + c["url"])
        credit = f"{c['title'][5:60].rsplit('.', 1)[0]} ({c['author'] or 'Wikimedia Commons'}, {c['lic']})"
        log("realmedia clip ok", repr(q), credit[:80])
        return {"path": out_mp4, "credit": credit, "url": c["url"], "frame": c["path"]}
    except Exception as e:
        log("realmedia clip failed", q, str(e)[:120]); return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


def fetch(real, out_path, lab=False, raw=False):
    """real = scene['real']; returns out_path or None. raw=True: the trimmed picture itself (an icon for a chat header),
    not laid out on the video canvas."""
    q = (real.get("q") or "").strip()
    kind = "logo" if str(real.get("kind", "photo")).lower().startswith("logo") else "photo"
    subject = real.get("subject") or q
    if not q:
        return None
    work = out_path + ".work"
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work, exist_ok=True)
    try:
        qs = [q + (" logo" if kind == "logo" and "logo" not in q.lower() else "")]
        if kind == "logo":                                        # the official file first: no judging needed
            off = download(official_logo(q), work, kind, want=2, min_side=120)
            if off:
                src = trim_margins(off[0]["path"], work)
                if raw:
                    _icon(src, out_path)
                else:
                    layout(src, out_path, kind, lab)
                log("realmedia ok", repr(q), "official logo", off[0]["url"][:90])
                return out_path
        urls = bing(qs[0] + " -transparent -checkered") + commons(q)
        cands = download(urls, work, kind)
        if not cands:
            log("realmedia: no usable images for", q); return None
        if kind == "photo":                                       # never the same picture within 30 days (URL or look-alike)
            cands = [c for c in cands if not _used_recently("u:" + c["url"]) and not _similar(_fingerprint(c["path"]))]
            if not cands:
                log("realmedia: every candidate was used in the last 30 days:", q); return None
        i, why = pick(cands[:6], subject, kind, work)
        if i < 0:
            log("realmedia: none fits", repr(subject), why); return None
        src = trim_margins(cands[i]["path"], work) if kind == "logo" else cands[i]["path"]
        if raw:
            _icon(src, out_path)
        else:
            layout(src, out_path, kind, lab)
        if kind == "photo":
            _mark_used("u:" + cands[i]["url"])
            fp = _fingerprint(cands[i]["path"])
            if fp:
                _mark_used(fp)
        log("realmedia ok", repr(q), kind, cands[i]["url"][:70])
        return out_path
    except Exception as e:
        log("realmedia failed", q, str(e)[:120]); return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":   # python engine/realmedia.py "UPI logo" logo out.jpg [lab]
    print(fetch({"q": sys.argv[1], "kind": sys.argv[2], "subject": sys.argv[1]}, sys.argv[3], len(sys.argv) > 4))
