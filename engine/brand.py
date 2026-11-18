"""Brand kit for every page, automatic (19 Nov, owner: "do all you can, automate everything").
The owner's real Instagram DP is the source of truth. Daily (and whenever it changes) for each page:
  1. fetch the page's Instagram DP  -> brand/<id>/src.jpg
  2. render circle-safe DP, YouTube banner, Facebook cover, 3 Instagram highlight covers (engine/brandimg.py, Pillow)
  3. set the Facebook page picture + cover through the Graph API (pages_manage_metadata / pages_manage_posts)
  4. one Telegram note listing what only the owner can upload (IG DP and highlights, YouTube DP and banner: no API)
Files are in brand/<id>/ (images are gitignored; server copy is the master). State: brand/state.json.
Usage: brand.py [--force] [page ...]"""
import hashlib, json, mimetypes, os, subprocess, sys, urllib.parse, urllib.request, uuid
from core import ROOT, load, save, log, pages, channel, telegram
import publish

BRAND = os.path.join(ROOT, "brand")
STATE = os.path.join(BRAND, "state.json")
IMG = os.path.join(ROOT, "engine", "brandimg.py")
PY = "/usr/bin/python3"               # has Pillow; the studio venv does not


def multipart(url, fields, fname, path):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{fname}"; filename="{os.path.basename(path)}"\r\n'
                 f'Content-Type: {mimetypes.guess_type(path)[0] or "image/png"}\r\n\r\n'.encode() + open(path, "rb").read() + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    r = urllib.request.Request(url, data=b"".join(parts), headers={"Content-Type": f"multipart/form-data; boundary={b}"}, method="POST")
    return json.load(urllib.request.urlopen(r, timeout=300))


def render(cid, th, tag, name):
    r = subprocess.run([PY, IMG, cid, th["bg"], th["accent"], th["accent2"], tag or "", name], capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(r.stderr[-300:])
    return r.stdout.strip()


def do_page(cid, st, force):
    ch = channel(cid)
    acc = load(os.path.expanduser(f"~/.studio-accounts/{cid}.json"))
    acc = publish.resolve(acc) if acc else None
    d = os.path.join(BRAND, cid)
    os.makedirs(d, exist_ok=True)
    s = st.setdefault(cid, {})
    if not acc or not acc.get("ig_user_id") or not acc.get("page_token"):
        log("brand:", cid, "no Meta keys yet")
        return
    info = publish._req(f"{publish.G}/{acc['ig_user_id']}?fields=username,profile_picture_url&access_token={acc['page_token']}")
    url = info.get("profile_picture_url")
    if not url:
        log("brand:", cid, "no Instagram DP set yet")
        return
    raw = urllib.request.urlopen(url, timeout=60).read()
    h = hashlib.sha1(raw).hexdigest()[:12]
    changed = force or s.get("src") != h or not os.path.exists(os.path.join(d, "yt_banner.png"))
    if changed:
        open(os.path.join(d, "src.jpg"), "wb").write(raw)
        kind = render(cid, ch["theme"], ch.get("tagline", ""), ch.get("name", cid))
        s.update(src=h, kind=kind, fb_dp=None, fb_cover=None)
        log("brand: rendered", cid, kind)
    pid = acc.get("page_id")
    if pid and (changed or not s.get("fb_dp")):
        try:
            res = multipart(f"{publish.G}/{pid}/picture", {"access_token": acc["page_token"], "redirect": "false"}, "source",
                            os.path.join(d, "dp_safe.png"))
            s["fb_dp"] = h if res.get("success", True) else None
            log("brand: Facebook DP set", cid)
        except Exception as e:
            log("brand: Facebook DP failed", cid, str(e)[:200])
    if pid and (changed or not s.get("fb_cover")):
        try:
            ph = multipart(f"{publish.G}/{pid}/photos", {"access_token": acc["page_token"], "published": "false"}, "source",
                           os.path.join(d, "fb_cover.png"))
            publish._req(f"{publish.G}/{pid}", {"access_token": acc["page_token"], "cover": ph["id"], "offset_y": "0"}, method="POST")
            s["fb_cover"] = h
            log("brand: Facebook cover set", cid)
        except Exception as e:
            log("brand: Facebook cover failed", cid, str(e)[:200])
    if changed:
        s["owner_note"] = False


def main():
    force = "--force" in sys.argv
    want = [a for a in sys.argv[1:] if not a.startswith("--")] or list(pages())
    st = load(STATE, {}) or {}
    for cid in want:
        try:
            do_page(cid, st, force)
        except Exception as e:
            log("brand: failed", cid, str(e)[:200])
    if "scrollhouse" not in st or force:
        r = subprocess.run([PY, IMG, "scrollhouse"], capture_output=True, text=True)
        st["scrollhouse"] = {"src": "v1"} if r.returncode == 0 else {}
    todo = [c for c in want if c in st and st[c].get("src") and not st[c].get("owner_note")]
    if todo:
        telegram("🎨 Brand kit ready on the server (brand/<page>/): " + ", ".join(todo) +
                 ". Facebook DP + cover are set automatically. For you to upload by hand (no API): Instagram DP (dp_safe.png, "
                 "only if the logo is a wide wordmark), highlight covers (hl_*.png), YouTube DP + banner (yt_banner.png).")
        for c in todo:
            st[c]["owner_note"] = True
    save(STATE, st)


if __name__ == "__main__":
    main()
