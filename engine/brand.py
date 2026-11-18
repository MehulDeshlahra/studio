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
TAG = {"tech": "Har cheez kaise kaam karti hai"}
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


def _site_mod():
    """engine/site.py by path ("import site" would give the standard library module)."""
    import importlib.util
    sp = importlib.util.spec_from_file_location("studio_site", os.path.join(ROOT, "engine", "site.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def texts(cid, ch):
    """Page texts used on every platform: (about <=150, long description <=250, link, IG bio <=150)."""
    sm = _site_mod()
    tag = ch.get("tagline") or TAG.get(cid, "")
    blurb = ch.get("site_blurb") or sm.BLURB.get(cid, "")
    link = f"https://scrollhouse.in/go/{cid}.html"
    long = (blurb + " A Scroll House page.")[:250]
    ig = f"{tag}\nA Scroll House page".strip()[:150]
    return tag[:150], long, link, ig


def youtube(cid, acc, ch, d, s, h):
    """YouTube allows the banner, description, keywords and country through the API (not the profile picture)."""
    y = acc.get("yt")
    if not y:
        return
    about, long, link, _ig = texts(cid, ch)
    key = hashlib.sha1((h + long + link).encode()).hexdigest()[:10]
    if s.get("yt") == key:
        return
    tok = publish._req("https://oauth2.googleapis.com/token", {"client_id": y["client_id"], "client_secret": y["client_secret"],
                       "refresh_token": y["refresh_token"], "grant_type": "refresh_token"})["access_token"]
    au = {"Authorization": "Bearer " + tok}
    cur = publish._req("https://www.googleapis.com/youtube/v3/channels?part=id,brandingSettings&mine=true", headers=au)["items"][0]
    up = publish._req("https://www.googleapis.com/upload/youtube/v3/channelBanners/insert?uploadType=media",
                      data=open(os.path.join(d, "yt_banner.png"), "rb").read(), headers=dict(au, **{"Content-Type": "image/png"}), method="POST")
    bs = cur.get("brandingSettings", {})
    bs.setdefault("channel", {}).update({"description": f"{long}\n{link}", "country": "IN"})
    bs.setdefault("image", {})["bannerExternalUrl"] = up["url"]
    publish._req("https://www.googleapis.com/youtube/v3/channels?part=brandingSettings",
                 data=json.dumps({"id": cur["id"], "brandingSettings": bs}).encode(), headers=dict(au, **{"Content-Type": "application/json"}), method="PUT")
    s["yt"] = key
    log("brand: YouTube banner + description set", cid)


def pack(cid, ch):
    """One zip per page with exactly what only the owner can upload (no API): written for a phone, sent on Telegram."""
    import zipfile
    d = os.path.join(BRAND, cid)
    about, long, link, ig = texts(cid, ch)
    readme = (f"{ch.get('name', cid)}: upload pack\n\nInstagram: Edit profile > bio, paste:\n{ig}\nLink: {link}\n"
              "Instagram DP: use dp_safe.png only if the current DP is a wide wordmark (the circle crop cuts it).\n"
              "Instagram highlights: New highlight, pick any story, edit cover, upload hl_series / hl_sources / hl_about.\n"
              "YouTube (studio.youtube.com > Customization > Profile): DP = dp_safe.png. Banner and description are already set.\n")
    z = os.path.join(d, f"{cid}-brand-pack.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for n in ("dp_safe.png", "yt_banner.png", "hl_series.png", "hl_sources.png", "hl_about.png"):
            if os.path.exists(os.path.join(d, n)):
                zf.write(os.path.join(d, n), n)
        zf.writestr("README.txt", readme)
    return z


def tg_document(path, caption):
    cfg = load(os.path.expanduser("~/.studio-telegram.json"))
    if not cfg:
        return False
    r = subprocess.run(["curl", "-s", "-m", "300", "-F", f"chat_id={cfg['chat']}", "-F", f"caption={caption[:900]}", "-F", f"document=@{path}",
                        f"https://api.telegram.org/bot{cfg['token']}/sendDocument"], capture_output=True, text=True)
    return '"ok":true' in r.stdout.replace(" ", "")


def owner_tasks(todo):
    """Dashboard 'Needs you' (dashboard/extra.py reads owner-tasks.json; ticking there marks it done)."""
    from core import OUT
    p = os.path.join(OUT, "owner-tasks.json")
    ts = load(p, []) or []
    have = {x.get("id") for x in ts if isinstance(x, dict)}
    new = [{"id": "brand-ig-" + c, "title": f"Upload the {c} brand pack (Instagram highlights, bio, YouTube DP)",
            "why": "Instagram and YouTube have no API for these. The zip is on Telegram; bios in knowledge/bios.md.", "done": False}
           for c in todo if "brand-ig-" + c not in have]
    for x in ts:                                     # YouTube was linked 18 Nov for the pages with a "yt" token
        if isinstance(x, dict) and x.get("id") == "yt-login" and not x.get("done"):
            x["done"] = True
    json.dump(ts + new, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def bios(pgs, st):
    out = ["# Bios (auto-written by engine/brand.py; the API cannot set these on Instagram or YouTube: paste once)", ""]
    for cid in pgs:
        ch = channel(cid)
        about, long, link, ig = texts(cid, ch)
        out += [f"## {ch.get('name', cid)}", f"- Instagram bio ({len(ig)} chars):", "```", ig, "```", f"- Instagram link: {link}",
                f"- YouTube description: {long} {link}", f"- Facebook (set automatically): {about}", ""]
    open(os.path.join(ROOT, "knowledge", "bios.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out))


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
        kind = render(cid, ch["theme"], ch.get("tagline") or TAG.get(cid, ""), ch.get("name", cid))
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
    about, long, link, _ig = texts(cid, ch)
    key = hashlib.sha1((about + long + link).encode()).hexdigest()[:10]
    if pid and s.get("fb_profile") != key:
        try:
            publish._req(f"{publish.G}/{pid}", {"access_token": acc["page_token"], "about": about, "description": long, "website": link}, method="POST")
            s["fb_profile"] = key
            log("brand: Facebook about/website set", cid)
        except Exception as e:
            log("brand: Facebook about failed", cid, str(e)[:200])
    try:
        youtube(cid, acc, ch, d, s, h)
    except Exception as e:
        log("brand: YouTube failed", cid, str(e)[:300])
    if changed:
        s["owner_note"] = False


def main():
    force = "--force" in sys.argv
    want = [a for a in sys.argv[1:] if not a.startswith("--")] or list(pages())
    st = load(STATE, {}) or {}
    try:
        bios(list(pages()), st)
    except Exception as e:
        log("brand: bios failed", str(e)[:150])
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
        telegram("\U0001F3A8 Brand kit done. Set automatically: Facebook DP, cover, about and website on all pages; YouTube banner and "
                 "description where YouTube is linked. Next: one zip per page with what only you can upload (Instagram highlights and bio, YouTube DP).")
        for c in todo:
            try:
                tg_document(pack(c, channel(c)), f"{channel(c).get('name', c)}: upload pack")
            except Exception as e:
                log("brand: pack failed", c, str(e)[:150])
        try:
            owner_tasks(todo)
        except Exception as e:
            log("brand: owner tasks failed", str(e)[:150])
        for c in todo:
            st[c]["owner_note"] = True
    save(STATE, st)


if __name__ == "__main__":
    main()
