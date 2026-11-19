"""Footage grabber for review/share pages that yt-dlp and gdown cannot read (19 Nov: CoD MW4 footage is on MediaSilo,
SEGA's on Frame.io). Opens the page in a headless browser, plays / opens each asset, and records every video stream the
page loads (mp4 / m3u8 / webm responses). Then downloads the largest few with ffmpeg.

  python tools/grab.py <url> <dest_dir> [max_files]     -> JSON list of [name, path] on stdout
Used by tools/laptop_worker.py _fetch_any for f.io / frame.io / mediasilo / wetransfer links."""
import json, os, re, subprocess, sys, time

NOWIN = 0x08000000 if os.name == "nt" else 0
VID = re.compile(r"\.(mp4|m3u8|webm|mov)(\?|$)|/manifest|mime=video|video/mp4", re.I)


def find_streams(url, max_assets=8):
    from playwright.sync_api import sync_playwright
    seen = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
        page = ctx.new_page()

        def on_resp(r):
            try:
                ct = (r.headers or {}).get("content-type", "")
                u = r.url
                if ("video" in ct or "mpegurl" in ct or VID.search(u)) and not u.startswith("blob:"):
                    size = int((r.headers or {}).get("content-length") or 0)
                    key = re.sub(r"[?#].*$", "", u) if ".m3u8" not in u else u
                    if key not in seen or size > seen[key][1]:
                        seen[key] = (u, size, ct)
            except Exception:
                pass
        page.on("response", on_resp)
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(8000)
        # Frame.io / review pages list assets by file name: open each one so its player loads the stream
        names = page.get_by_text(re.compile(r"\.(mp4|mov|mxf|m4v|webm)$", re.I))
        for i in range(min(names.count(), max_assets)):
            try:
                before = page.url
                names.nth(i).click(timeout=4000); page.wait_for_timeout(7000)
                if page.url != before:
                    page.go_back(timeout=20000); page.wait_for_timeout(4000)
            except Exception:
                continue
        # click play buttons and asset thumbnails so each video starts loading
        sels = ["button[aria-label*=play i]", "[data-testid*=play i]", "video", "[class*=thumbnail] img", "[class*=asset] img",
                "[class*=Thumbnail]", "[class*=card] img"]
        clicked = 0
        for s in sels:
            loc = page.locator(s)
            for i in range(min(loc.count(), max_assets)):
                try:
                    loc.nth(i).click(timeout=3000); page.wait_for_timeout(4000); clicked += 1
                    if page.url != url and "share" not in page.url and clicked > 1:
                        page.go_back(timeout=20000); page.wait_for_timeout(3000)
                except Exception:
                    continue
        # <video src> elements the page holds directly
        try:
            for src in page.eval_on_selector_all("video, video source", "els => els.map(e => e.currentSrc || e.src).filter(Boolean)"):
                if not src.startswith("blob:"):
                    seen.setdefault(re.sub(r"[?#].*$", "", src), (src, 0, "video"))
        except Exception:
            pass
        b.close()
    # one stream per asset: the HLS master (main/master .m3u8 = best video + audio), else the highest-resolution mp4.
    # HLS segments (.m4s/.ts/init.mp4) and per-track playlists are never downloaded on their own.
    UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
    assets = {}
    for u, size, ct in seen.values():
        path = u.split("?")[0]
        if re.search(r"\.(m4s|ts|aac)$|/init\.mp4$|media-(vid|aud)\.m3u8$", path):
            continue
        m = UUID.search(path)
        aid = m.group(0) if m else path
        if re.search(r"/(main|master|index|playlist)\.m3u8$", path) or "mpegurl" in ct:
            rank = 10_000
        else:
            r = re.search(r"_(\d{3,4})(p|_best)?\.mp4$", path)
            rank = int(r.group(1)) if r else (size // 1_000_000)
        if aid not in assets or rank > assets[aid][0]:
            assets[aid] = (rank, u)
    return [u for _, u in sorted(assets.values(), key=lambda x: -x[0])]


def download(urls, dest, max_files=6):
    os.makedirs(dest, exist_ok=True)
    got = []
    for i, u in enumerate(urls):
        if len(got) >= max_files:
            break
        f = os.path.join(dest, f"grab-{int(time.time())}-{i}.mp4")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", u, "-c", "copy", f], capture_output=True, text=True,
                           timeout=3600, creationflags=NOWIN)
        if r.returncode == 0 and os.path.exists(f) and os.path.getsize(f) > 500_000:
            got.append([os.path.basename(u.split("?")[0])[:80] or f"asset {i + 1}", f])
        elif os.path.exists(f):
            os.remove(f)
    return got


if __name__ == "__main__":
    url, dest = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    streams = find_streams(url)
    print(json.dumps({"streams": streams[:20], "files": download(streams, dest, n)}))
