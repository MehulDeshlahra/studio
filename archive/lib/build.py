"""Assemble a HyperFrames project for one video: template.html + words.json + cap/boxes.json -> render/index.html.
  python lib/build.py videos/<id>
Copies videos/<id>/assets/ (images, fonts) and mix.wav into render/. Older layout (cap/page.png) still works.
"""
import json, os, shutil, sys

v = sys.argv[1]
r = os.path.join(v, "render")
os.makedirs(os.path.join(r, "assets"), exist_ok=True)
words = json.load(open(os.path.join(v, "words.json"), encoding="utf-8"))
bx = json.load(open(os.path.join(v, "cap", "boxes.json"), encoding="utf-8"))
boxes = bx.get("boxes", bx)
html = open(os.path.join(v, "template.html"), encoding="utf-8").read()
dur = words["dur"] + 0.8                                  # tail: the closing line holds 2 s
html = (html.replace("__WORDS__", json.dumps(words, ensure_ascii=False))
            .replace("__BOXES__", json.dumps(boxes, ensure_ascii=False))
            .replace("__DUR__", f"{dur:.2f}"))
open(os.path.join(r, "index.html"), "w", encoding="utf-8").write(html)
if os.path.exists(os.path.join(v, "cap", "page.png")):
    shutil.copy(os.path.join(v, "cap", "page.png"), os.path.join(r, "assets", "page.png"))
if os.path.isdir(os.path.join(v, "assets")):
    shutil.copytree(os.path.join(v, "assets"), os.path.join(r, "assets"), dirs_exist_ok=True)
if os.path.exists(os.path.join(v, "mix.wav")):
    shutil.copy(os.path.join(v, "mix.wav"), os.path.join(r, "mix.wav"))
print("built", os.path.join(r, "index.html"), f"{dur:.2f}s")
