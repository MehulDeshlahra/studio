"""English version of raaz case 2 (same pictures, rewritten English script, not a word-for-word translation).
Reuses the Hindi job's images/clip: copies assets + assets.json from case2-p1, then
  make.py raaz --lang en --job case2-p1-en --from voice"""
import json, os, shutil, sys

SRC = os.path.expanduser("~/studio-out/raaz/case2-p1")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/studio-out/raaz/case2-p1-en")
os.makedirs(OUT, exist_ok=True)
hi = json.load(open(os.path.join(SRC, "plan.json"), encoding="utf-8"))

EN = [
    dict(vo="You are the detective. And this wedding... is now a crime scene."),
    dict(vo="The groom's envelope with five lakh rupees, gone!", big="₹5,00,000", small="GONE"),
    dict(vo="The bag was behind the stage. Only three people went there."),
    dict(vo="The photographer says: I was on stage taking photos the whole time.",
         who="Photographer Rohit", quote="I was on stage the whole time."),
    dict(vo="The sweet maker says: I was at the stove. Look, my hands are still sticky with syrup.",
         who="Halwai Ramesh", quote="My hands are still sticky with syrup."),
    dict(vo="And the groom's friend says: I just went to charge my phone.",
         who="Friend Sunny", quote="I just went to charge my phone."),
    dict(vo="Now listen. There's not a single drop of syrup on the bag.", title="CLUE 1"),
    dict(vo="And behind the stage... there was no power socket at all.", title="CLUE 2"),
    dict(vo="So who is the thief? Three seconds. Think.", options=["Photographer", "Sweet maker", "Groom's friend"]),
    dict(vo="Comment A, B or C. Answer tomorrow.", big="ANSWER TOMORROW", small="PART 2"),
]
assert len(EN) == len(hi["scenes"])
plan = dict(hi)
plan["lang"] = "en"
plan["title"] = "Five lakh vanished at a wedding: who is the thief? (Part 1)"
plan["caption"] = "₹5 lakh vanished at a wedding 😱 You are the detective. Who did it? Comment A, B or C. Answer in Part 2 tomorrow 🕵️"
plan["hashtags"] = ["#WhoDidIt", "#MysteryStory", "#DetectiveStory", "#Riddle", "#IndianWedding", "#Suspense", "#PlotTwist"]
plan["end_line"] = "Part 2 tomorrow"
plan["scenes"] = []
for s, e in zip(hi["scenes"], EN):
    n = dict(s); n.update(e)
    n["keywords"] = []
    if s.get("hud_right"):
        n["hud_right"] = {"SUSPECT": "SUSPECT", "SURAAG": "CLUE", "TUMHARA FAISLA": "YOUR CALL", "PART 2 KAL": "PART 2 TOMORROW"}.get(
            s["hud_right"].split(" ")[0] if s["hud_right"].startswith(("SUSPECT", "SURAAG")) else s["hud_right"], s["hud_right"])
        if s["hud_right"].startswith(("SUSPECT", "SURAAG")):
            n["hud_right"] = s["hud_right"].replace("SURAAG", "CLUE")
    plan["scenes"].append(n)
json.dump(plan, open(os.path.join(OUT, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
shutil.copy(os.path.join(SRC, "research.json"), os.path.join(OUT, "research.json"))
a = json.load(open(os.path.join(SRC, "assets.json")))
os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
for k, v in a.items():
    for kind, f in v.items():
        dst = os.path.join(OUT, "assets", os.path.basename(f))
        shutil.copy(f, dst); v[kind] = dst
json.dump(a, open(os.path.join(OUT, "assets.json"), "w"))
print("wrote", OUT, sum(len(s["vo"].split()) for s in plan["scenes"]), "words")
