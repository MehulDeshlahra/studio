"""raaz case 2 PART 2 (20 Nov, owner: "where is part 2?"). Part 1 (case2-p1, posted 20 Nov 20:25) ended with
"Comment mein likho A, B ya C. Jawab kal." This is the promised answer: same cast, same look, same voice; it walks
back through the two clues so a viewer who missed Part 1 still follows, then reveals C. ~30 s.
Then: make.py raaz --job case2-p2 --from voice"""
import json, os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/studio-out/raaz/case2-p2")
os.makedirs(OUT, exist_ok=True)
STYLE = ("Cinematic graphic-novel illustration, vibrant Indian wedding at night, marigold garlands, fairy lights, "
         "warm saturated colours with deep shadows, dramatic rim light, subtle film grain, vertical 9:16, one clear subject, "
         "empty space at the top and bottom of the frame")
PHOTO = "Photographer Rohit: lean Indian man in his 20s, black t-shirt, big DSLR camera on a strap, cap turned backwards"
HALWAI = "Halwai Ramesh: plump cheerful Indian man in his 50s, white vest and dhoti, orange gamchha on his shoulder"
DOST = "Groom's friend Sunny: Indian man in his 20s, shiny maroon kurta, gold chain, gelled hair, smartphone in hand"
S = [
    dict(vo="Kal ka case: shaadi mein paanch lakh ka lifafa gayab. Aaj jawab.", type="card",
         prompt=f"An open, empty red-and-gold wedding gift bag on a velvet chair behind a stage curtain, spotlight. {STYLE}",
         motion="punch", big="JAWAB", small="PART 2", hud_right="CASE 2"),
    dict(vo="Teen suspect the: photographer, halwai, aur dulhe ka dost.", type="image",
         prompt=f"Three people standing apart backstage at a wedding, seen in silhouette against warm fairy lights: a man with a camera, a plump cook with a gamchha, a young man in a shiny kurta. {STYLE}",
         motion="push", keywords=["teen", "suspect"], hud_right="3 SUSPECT"),
    dict(vo="Photographer ki har photo mein wahi stage hai. Woh wahan se hila hi nahi.", type="clue",
         prompt=f"{PHOTO}, on the wedding stage, camera raised, flash going off, the couple behind him. {STYLE}",
         motion="pan", label="A", who="Photographer Rohit", quote="Har photo stage ki.", hud_right="A: CLEAR"),
    dict(vo="Halwai ke haath chashni mein the. Par bag pe chashni ka ek bhi nishaan nahi.", type="clue",
         prompt=f"{HALWAI}, frying jalebi at a big kadhai, sticky syrup on his hands, steam rising. {STYLE}",
         motion="push", label="B", who="Halwai Ramesh", quote="Bag bilkul saaf.", hud_right="B: CLEAR"),
    dict(vo="Aur dost ne kaha, main phone charge karne gaya tha.", type="clue",
         prompt=f"{DOST}, holding up his phone with a nervous smile, behind a stage curtain. {STYLE}",
         motion="pull", label="C", who="Dost Sunny", quote="Phone charge karne gaya tha.", hud_right="SUSPECT C"),
    dict(vo="Par stage ke peeche ek bhi plug point tha hi nahi.", type="image",
         prompt=f"A bare backstage wall of wooden boards and marigold strings, no sockets at all, a torch beam scanning it. {STYLE}",
         motion="pan", keywords=["plug", "point"], title="JHOOTH", hud_right="SURAAG"),
    dict(vo="Toh chor... dulhe ka dost, Sunny!", type="card",
         prompt=f"{DOST}, caught in a spotlight, frozen, eyes wide, guests turning to look at him. {STYLE}",
         motion="punch", big="C", small="DOST SUNNY", hud_right="CHOR"),
    dict(vo="Lifafa uske kurte ki andar wali jeb se mila.", type="image",
         prompt=f"Close-up of a red-and-gold wedding envelope being pulled out of the inside pocket of a shiny maroon kurta, gold chain visible. {STYLE}",
         motion="push", keywords=["lifafa", "jeb"], hud_right="CASE CLOSED"),
    dict(vo="Tumne kya socha tha, A, B ya C? Comment mein batao. Naya case jaldi.", type="card",
         prompt=f"The empty wedding hall at dawn, flower petals on the floor, one lamp still burning. {STYLE}",
         motion="pull", big="CASE CLOSED", small="NAYA CASE JALDI", hud_right="CASE 2"),
]
plan = {
    "slug": "case2-p2", "title": "Shaadi ka 5 lakh ka lifafa: chor kaun? (Part 2, jawab)", "hud_left": "PART 2",
    "hooks": ["Kal ka case: shaadi mein paanch lakh ka lifafa gayab. Aaj jawab."], "hook_choice": 0,
    "hook_why": "Answers the cliffhanger viewers commented on; recaps the two clues so it works without Part 1.",
    "metaphor": "Fair-play reveal: A cleared by his photos, B by the clean bag, C caught by the missing plug point.",
    "scenes": S,
    "caption": "Jawab aa gaya 🕵 Shaadi ke 5 lakh ka chor kaun tha? Do suraag, ek jhooth. Tumne sahi pakda? A, B ya C, comment mein batao. Part 1 profile pe 👆",
    "hashtags": ["#RaazKaFaisla", "#HindiMystery", "#DetectiveStory", "#Paheli", "#Shaadi", "#WhoDidIt", "#Suspense"],
    "claims": [{"claim": "Fiction.", "basis": "original story"}],
    "part_of": "case2-p1",
}
json.dump(plan, open(os.path.join(OUT, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"topic": "raaz case 2 part 2", "top": [], "watched": [], "note": "answer to case2-p1"},
          open(os.path.join(OUT, "research.json"), "w", encoding="utf-8"))
json.dump({"channel": "raaz", "job": "case2-p2", "topic": "Shaadi ka 5 lakh ka lifafa (Part 2, jawab)"},
          open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8"))
print("wrote", OUT, sum(len(s["vo"].split()) for s in S), "words")
