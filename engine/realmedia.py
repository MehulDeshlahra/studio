"""realmedia: real logos and real photos for scenes that name a real thing (brand, app, product, place, public figure).

A scene may carry  "real": {"q": "search query", "kind": "logo|photo", "subject": "what the picture must show"}.
fetch() searches the web (Bing images, then Wikimedia Commons), downloads the best-looking candidates, lets Gemini
look at them and pick the one that really shows the subject, then lays it out for the video:
  classic look  -> 1080x1920 frame: blurred copy of the picture behind, the real picture sharp in front
  lab look      -> 900:760 canvas on black (the lab compositor blends it with 'lighten'); logos sit on a light card
Returns the image path, or None (the caller then makes an AI image as before)."""
import base64, html, json, os, re, shutil, subprocess, sys, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import log, sh

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]


def _get(url, timeout=20, maxb=12_000_000):
    r = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=timeout)
    return r.read(maxb), (r.headers.get("content-type") or "").lower()


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


def _probe(path):
    try:
        o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=30).stdout.strip().split(",")
        return int(o[0]), int(o[1])
    except Exception:
        return 0, 0


def download(urls, work, kind, want=6):
    got = []
    for i, u in enumerate(urls):
        if len(got) >= want:
            break
        try:
            b, ct = _get(u, 15)
            if len(b) < 6000 or "image" not in ct or "svg" in ct or "gif" in ct:
                continue
            raw = os.path.join(work, f"raw{i}")
            open(raw, "wb").write(b)
            png = os.path.join(work, f"c{len(got)}.png")
            sh(["ffmpeg", "-v", "error", "-y", "-i", raw, "-frames:v", "1", "-vf", "scale='min(1600,iw)':-2", png], timeout=60)
            w, h = _probe(png)
            if min(w, h) < (300 if kind == "logo" else 600):
                continue
            got.append({"path": png, "w": w, "h": h, "url": u})
        except Exception:
            continue
    return got


def _gemini(parts):
    import tts, llm
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1, "maxOutputTokens": 600}}
    for m in MODELS:
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key()})
            d = json.load(urllib.request.urlopen(r, timeout=120))
            return llm.parse_json("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
        except Exception as e:
            log("realmedia gemini fail", m, str(e)[:100])
    return None


JUDGE = """The picture shows {n} candidate images (A, B, C ...) for a video scene about: "{subject}" ({kind}).
Pick the ONE that best shows exactly this subject. Good: the real, recognisable subject, clean, sharp, no watermark,
no big text banner or caption on top, not a collage, not a meme, not a different brand/person, not a tiny thumbnail.
For a logo: the official logo alone, clear and centred, on a plain white or solid background. REJECT any image that shows a grey/white checkerboard pattern (fake transparency), a mock-up, a business card, or a logo shrunk small inside a big empty area. For a photo: a natural well-lit photo of the subject.
Return JSON {{"best": "A" or "none", "why": "6 words"}}. Use "none" when no candidate really shows the subject."""


def pick(cands, subject, kind, work):
    ins, fc = [], ""
    for i, c in enumerate(cands):
        ins += ["-i", c["path"]]
        fc += (f"[{i}:v]scale=320:320:force_original_aspect_ratio=decrease,pad=320:320:(ow-iw)/2:(oh-ih)/2:color=0x888888,"
               f"drawtext=text='{'ABCDEF'[i]}':x=8:y=4:fontsize=44:fontcolor=yellow:box=1:boxcolor=black@0.7[t{i}];")
    fc += "".join(f"[t{i}]" for i in range(len(cands))) + f"hstack={len(cands)}"
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


def fetch(real, out_path, lab=False):
    """real = scene['real']; returns out_path or None."""
    q = (real.get("q") or "").strip()
    kind = "logo" if str(real.get("kind", "photo")).lower().startswith("logo") else "photo"
    subject = real.get("subject") or q
    if not q:
        return None
    work = out_path + ".work"
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work, exist_ok=True)
    try:
        qs = [q + (" logo" if kind == "logo" and "logo" not in q.lower() else "")]
        urls = bing(qs[0] + " -transparent -checkered") + commons(q)
        cands = download(urls, work, kind)
        if not cands:
            log("realmedia: no usable images for", q); return None
        i, why = pick(cands[:6], subject, kind, work)
        if i < 0:
            log("realmedia: none fits", repr(subject), why); return None
        src = trim_margins(cands[i]["path"], work) if kind == "logo" else cands[i]["path"]
        layout(src, out_path, kind, lab)
        log("realmedia ok", repr(q), kind, cands[i]["url"][:70])
        return out_path
    except Exception as e:
        log("realmedia failed", q, str(e)[:120]); return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":   # python engine/realmedia.py "UPI logo" logo out.jpg [lab]
    print(fetch({"q": sys.argv[1], "kind": sys.argv[2], "subject": sys.argv[1]}, sys.argv[3], len(sys.argv) > 4))
