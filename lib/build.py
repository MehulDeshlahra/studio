"""Assemble a HyperFrames project for one video: template.html + words.json + boxes.json -> render/index.html.
  python lib/build.py videos/<id>
"""
import json, os, shutil, sys

v = sys.argv[1]
r = os.path.join(v, "render")
os.makedirs(os.path.join(r, "assets"), exist_ok=True)
words = json.load(open(os.path.join(v, "words.json"), encoding="utf-8"))
boxes = json.load(open(os.path.join(v, "cap", "boxes.json"), encoding="utf-8"))["boxes"]
html = open(os.path.join(v, "template.html"), encoding="utf-8").read()
html = (html.replace("__WORDS__", json.dumps(words, ensure_ascii=False))
            .replace("__BOXES__", json.dumps(boxes))
            .replace("__DUR__", f"{words['dur'] + 0.8:.2f}"))   # tail: the closing line holds 2 s
open(os.path.join(r, "index.html"), "w", encoding="utf-8").write(html)
shutil.copy(os.path.join(v, "cap", "page.png"), os.path.join(r, "assets", "page.png"))
if os.path.isdir(os.path.join(v, "assets", "fonts")):
    shutil.copytree(os.path.join(v, "assets", "fonts"), os.path.join(r, "assets", "fonts"), dirs_exist_ok=True)
shutil.copy(os.path.join(v, "mix.wav"), os.path.join(r, "mix.wav"))
print("built", os.path.join(r, "index.html"), f"{words['dur']:.2f}s")
