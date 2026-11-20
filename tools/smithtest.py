"""Picture-step test (20 Nov): redraw 3 scenes of the known-bad Navkar Bhav reel 1118-2242 through engine/picsmith.py
(bible + prompt engineer + reference + Decisions check) and put the results side by side with the old frames in
~/studio-out/smithtest/sheet.jpg. Telegram gets the per-scene result. python tools/smithtest.py"""
import copy, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "engine")); sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import picsmith, muse
from core import ROOT, OUT, load, telegram

cid, job, scenes = "jain", "1118-2242", (0, 3, 7)
ch = load(os.path.join(ROOT, "channels", cid, "channel.json"), {}); ch["id"] = cid
jd = os.path.join(OUT, cid, job)
p = copy.deepcopy(load(os.path.join(jd, "plan.json"), {})); p.pop("bible", None); p.pop("pic_redraws", None)
adir = os.path.join(OUT, "smithtest"); os.makedirs(adir, exist_ok=True)
lines = [L for L in (load(os.path.join(jd, "timing.json"), {}) or {}).get("lines", []) if L.get("end", 0) > L.get("start", 0)]


def chain(pr, n=0):
    f = os.path.join(adir, f"x{len(os.listdir(adir))}")
    return muse.image(pr, f + ".webp") or muse.omni_image(pr, f + "o.jpg") or muse.cloudflare(pr, f + "c.jpg")


report, tiles = [], []
for i in scenes:
    s = p["scenes"][i]
    img = picsmith.scene_picture(ch, p, s, i, s.get("prompt", ""), adir, chain)
    tries = s.get("pic", {}).get("tries", [])
    report.append(f"scene {i + 1}: {'OK' if tries and not tries[-1]['fails'] else 'still failing'} after {len(tries)} tries, "
                  f"refs {s.get('pic', {}).get('refs')}, last {tries[-1]['fails'] if tries else 'no picture'}")
    old = os.path.join(adir, f"old{i}.jpg")
    t = round((lines[i]["start"] + lines[i]["end"]) / 2, 2)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", os.path.join(jd, f"{cid}-{job}.mp4"), "-frames:v", "1",
                    "-vf", "scale=300:534", old])
    if img:
        new = os.path.join(adir, f"new{i}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", img, "-vf", "scale=300:534:force_original_aspect_ratio=increase,crop=300:534", new])
        tiles += [old, new]
args = []
for t in tiles:
    args += ["-i", t]
if len(tiles) >= 2:
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + args + ["-filter_complex", f"hstack={len(tiles)}", os.path.join(adir, "sheet.jpg")])
json.dump({"report": report, "bible": p.get("bible"), "scenes": {i: p["scenes"][i].get("pic") for i in scenes}},
          open(os.path.join(adir, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n".join(report))
telegram("🎨 Picture-step test (Navkar Bhav 1118-2242, old vs new in ~/studio-out/smithtest/sheet.jpg):\n" + "\n".join(report))
