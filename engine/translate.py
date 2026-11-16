"""Make the English edition of a finished job: same pictures/clips, script REWRITTEN (not word-for-word) in natural
Indian English, card/title/option texts too. No Muse cost; one voice request.
  python engine/translate.py <channel> <job>     -> job "<job>-en", then make.py <channel> --lang en --job <job>-en --from voice"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import OUT, load, save, log
import plan as planner

FIELDS = ("vo", "title", "big", "small", "who", "quote", "label", "hud_right", "options", "nodes")


def main(cid, job):
    src = os.path.join(OUT, cid, job)
    dst = os.path.join(OUT, cid, job + "-en")
    hi = load(os.path.join(src, "plan.json"))
    slim = {"title": hi.get("title"), "caption": hi.get("caption"), "hud_left": hi.get("hud_left"),
            "scenes": [{k: s[k] for k in FIELDS if s.get(k)} for s in hi["scenes"]]}
    prompt = f"""Rewrite this vertical-video plan for an ENGLISH-speaking Indian audience. Keep the same number of scenes,
in the same order, each scene still matching its picture. Do NOT translate word for word: write natural, punchy spoken
Indian English with the same meaning, twists and clues (a clue must still work). Keep proper names. Keep each vo
short (4-16 words). Translate every on-screen text field too (title, big, small, who, quote, label, hud_right,
options, nodes), keep them as short as the original. Return the same JSON shape plus "hashtags" (7 English hashtags)
and "end_line" (2-4 words, e.g. "Part 2 tomorrow" or "New story daily").
PLAN:
{json.dumps(slim, ensure_ascii=False)}"""
    en = planner.ask(prompt)
    if len(en.get("scenes", [])) != len(hi["scenes"]):
        raise SystemExit(f"scene count changed: {len(en.get('scenes', []))} vs {len(hi['scenes'])}")
    out = dict(hi)
    out["lang"] = "en"
    for k in ("title", "caption", "hashtags", "end_line", "hud_left"):
        if en.get(k):
            out[k] = en[k]
    out["scenes"] = []
    for s, e in zip(hi["scenes"], en["scenes"]):
        n = dict(s)
        n.update({k: e[k] for k in FIELDS if e.get(k)})
        n["keywords"] = []
        out["scenes"].append(n)
    os.makedirs(os.path.join(dst, "assets"), exist_ok=True)
    save(os.path.join(dst, "plan.json"), out)
    save(os.path.join(dst, "research.json"), load(os.path.join(src, "research.json"), {"top": [], "watched": []}))
    a = load(os.path.join(src, "assets.json"), {})
    for k, v in a.items():
        for kind, f in v.items():
            d = os.path.join(dst, "assets", os.path.basename(f))
            shutil.copy(f, d)
            v[kind] = d
    save(os.path.join(dst, "assets.json"), a)
    log("english plan ready", dst, sum(len(s["vo"].split()) for s in out["scenes"]), "words")
    return job + "-en"


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
