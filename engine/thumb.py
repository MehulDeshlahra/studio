"""Cover / thumbnail for every reel: a frame from the video (darkened) + big hook title + handle, 1080x1920.
  make(cid, job) -> path of cover.jpg in the job folder (best effort, never stops a build)
  stamp(mp4, cover, out) -> copy of the video whose first 3 frames are the cover, so Instagram's thumb_offset=0
                            and Facebook show the designed cover (audio untouched)."""
import os, sys, json, html, glob, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, log, sh

CHROME = next((p for p in glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux-arm64/chrome-headless-shell"))), "")


def _title(plan):
    t = (plan.get("cover_text") or plan.get("title") or "").strip()
    words = t.replace("|", " ").split()
    return " ".join(words[:7])


def make(cid, job):
    jd = os.path.join(OUT, cid, job)
    mp4 = os.path.join(jd, f"{cid}-{job}.mp4")
    out = os.path.join(jd, "cover.jpg")
    try:
        plan = load(os.path.join(jd, "plan.json"), {})
        ch = load(os.path.join(ROOT, "channels", cid, "channel.json"), {})
        th = ch.get("theme", {})
        acc = th.get("accent", "#f5c542")
        handle = ch.get("handle_en") if plan.get("lang") == "en" and ch.get("handle_en") else ch.get("handle", "")
        frame = os.path.join(jd, "cover-frame.jpg")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", "1.6", "-i", mp4, "-frames:v", "1", "-vf", "scale=1080:1920", frame])
        page = os.path.join(jd, "cover.html")
        title = html.escape(_title(plan).upper() if plan.get("lang") == "en" or cid == "tech" else _title(plan))
        with open(page, "w", encoding="utf-8") as f:
            f.write(f"""<!doctype html><meta charset=utf-8><style>
*{{margin:0;box-sizing:border-box}}body{{width:1080px;height:1920px;background:#000;position:relative;overflow:hidden;font-family:'Noto Sans Devanagari','DejaVu Sans',sans-serif}}
.bg{{position:absolute;inset:0;background:url(cover-frame.jpg);background-size:cover;filter:blur(14px) brightness(.42) saturate(1.1);transform:scale(1.08)}}
.shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.55),rgba(0,0,0,.1) 40%,rgba(0,0,0,.75))}}
.bar{{position:absolute;left:90px;top:620px;width:150px;height:14px;background:{acc};border-radius:7px}}
h1{{position:absolute;left:90px;right:90px;top:670px;font-size:150px;line-height:1.08;font-weight:900;color:#fff;text-shadow:0 8px 40px rgba(0,0,0,.8)}}
h1 em{{font-style:normal;color:{acc}}}
.h{{position:absolute;left:90px;bottom:300px;font-size:46px;font-weight:700;color:{acc};letter-spacing:2px}}
</style><div class=bg></div><div class=shade></div><div class=bar></div><h1>{_hl(title)}</h1><div class=h>{html.escape(handle)}</div>""")
        png = os.path.join(jd, "cover.png")
        sh([CHROME, "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files", "--window-size=1080,1920",
            f"--screenshot={png}", "file://" + page], timeout=120)
        sh(["ffmpeg", "-v", "error", "-y", "-i", png, "-q:v", "2", out])
        for x in (frame, page, png):
            if os.path.exists(x): os.remove(x)
        log("cover made", cid, job)
        return out
    except Exception as e:
        log("cover failed", cid, job, str(e)[:200])
        return None


def _hl(t):
    """Colour the last word with the accent."""
    w = t.split(" ")
    return " ".join(w[:-1] + [f"<em>{w[-1]}</em>"]) if len(w) > 1 else t


def stamp(mp4, cover, out):
    sh(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-i", cover, "-filter_complex",
        "[1:v]scale=1080:1920,format=yuv420p[c];[0:v][c]overlay=0:0:enable='lt(n,3)'[v]", "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out],
       timeout=1800)
    return out


if __name__ == "__main__":
    print(make(sys.argv[1], sys.argv[2]))
