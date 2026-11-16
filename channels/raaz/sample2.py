"""raaz sample 2 (after owner feedback on sample 1: too long, boring story, double text, captions out of sync).
Case 2: "Shaadi ka lifafa" - second person (YOU are the detective), relatable Indian wedding, fast, fair-play, ~40 s,
3-second countdown before the answer. Then: make.py raaz --job case2-p1 --from voice"""
import json, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/studio-out/raaz/case2-p1")
os.makedirs(OUT, exist_ok=True)

STYLE = ("Cinematic graphic-novel illustration, vibrant Indian wedding at night, marigold garlands, fairy lights, "
         "warm saturated colours with deep shadows, dramatic rim light, subtle film grain, vertical 9:16, one clear subject, "
         "empty space at the top and bottom of the frame")
PHOTO = "Photographer Rohit: lean Indian man in his 20s, black t-shirt, big DSLR camera on a strap, cap turned backwards"
HALWAI = "Halwai Ramesh: plump cheerful Indian man in his 50s, white vest and dhoti, orange gamchha on his shoulder"
DOST = "Groom's friend Sunny: Indian man in his 20s, shiny maroon kurta, gold chain, gelled hair, smartphone in hand"

S = [
    dict(vo="Tum ho detective. Aur ye shaadi... ab crime scene hai.", type="clip",
         prompt=f"A grand Indian wedding stage at night, the bride and groom on the stage, guests dancing, then the music stops and everyone turns around shocked, slow camera push-in. {STYLE}",
         motion="push", keywords=["detective", "crime"], hud_right="CASE 2"),
    dict(vo="Dulhe ka paanch lakh ka lifafa, gayab!", type="card",
         prompt=f"An open, empty red-and-gold wedding gift bag lying on a velvet chair behind a stage curtain, a few torn shagun envelopes on the floor, spotlight. {STYLE}",
         motion="punch", big="₹5,00,000", small="GAYAB", keywords=["lakh", "gayab"], hud_right="CASE 2"),
    dict(vo="Bag stage ke peeche tha. Aur wahan sirf teen log gaye.", type="image",
         prompt=f"Backstage of a wedding stage: a heavy marigold curtain, three people seen from behind walking in, backlit, mysterious. {STYLE}",
         motion="push", keywords=["teen"], hud_right="3 SUSPECT"),
    dict(vo="Photographer bola: main toh poore time stage pe photo le raha tha.", type="clue",
         prompt=f"{PHOTO}, holding his camera, looking straight at the viewer, slightly annoyed, wedding lights behind. {STYLE}",
         motion="push", label="A", who="Photographer Rohit", quote="Poore time stage pe photo le raha tha.", hud_right="SUSPECT 1/3"),
    dict(vo="Halwai bola: main bhatti pe tha. Dekho, haath abhi bhi chashni mein hain.", type="clue",
         prompt=f"{HALWAI}, showing his sticky palms covered in sugar syrup, a big kadhai of jalebi frying behind him, steam. {STYLE}",
         motion="pan", label="B", who="Halwai Ramesh", quote="Haath abhi bhi chashni mein hain.", hud_right="SUSPECT 2/3"),
    dict(vo="Aur dulhe ka dost bola: main toh bas phone charge karne gaya tha.", type="clue",
         prompt=f"{DOST}, smiling too much, holding up his phone, sweat on his forehead, behind a stage curtain. {STYLE}",
         motion="pull", label="C", who="Dost Sunny", quote="Bas phone charge karne gaya tha.", hud_right="SUSPECT 3/3"),
    dict(vo="Ab suno. Bag pe chashni ka ek bhi nishaan nahi.", type="image",
         prompt=f"Extreme close-up of a clean red-and-gold silk wedding bag, no stains at all, a magnifying glass over it. {STYLE}",
         motion="punch", keywords=["chashni", "nishaan"], title="SURAAG 1", hud_right="SURAAG 1"),
    dict(vo="Aur stage ke peeche... ek bhi plug point nahi tha.", type="image",
         prompt=f"A plain backstage wall made of wooden boards and marigold strings, completely bare, no sockets, a torch beam scanning it. {STYLE}",
         motion="pan", keywords=["plug", "point"], title="SURAAG 2", hud_right="SURAAG 2"),
    dict(vo="Toh chor kaun? Teen second. Socho.", type="choice", hold=3,
         prompt=f"The wedding stage seen from far away, lights flickering, three silhouettes standing apart. {STYLE}",
         motion="push", options=["Photographer", "Halwai", "Dulhe ka dost"], hud_right="TUMHARA FAISLA"),
    dict(vo="Comment mein likho A, B ya C. Jawab kal.", type="card",
         prompt=f"The empty wedding hall at dawn, flower petals on the floor, one lamp still burning. {STYLE}",
         motion="pull", big="JAWAB KAL", small="PART 2", hud_right="PART 2 KAL"),
]

plan = {
    "slug": "case2-p1", "title": "Shaadi ka 5 lakh ka lifafa: chor kaun? (Part 1)", "hud_left": "PART 1",
    "hooks": ["Tum ho detective. Aur ye shaadi... ab crime scene hai.", "Shaadi mein 5 lakh gayab. Teen suspect. 3 second.",
              "Ek jhooth. Kya tum pakad paoge?"],
    "hook_choice": 0,
    "hook_why": "Second person (the viewer is the detective), a relatable Indian setting and a twist in the first line. The 3-second countdown makes people pause and rewatch.",
    "metaphor": "Fast fair-play whodunit; two spoken clues clear A and expose C (no plug point = no charging).",
    "scenes": S,
    "caption": "Shaadi mein 5 lakh ka lifafa gayab 😱 Tum detective ho. Chor kaun hai? A, B ya C, comment karo. Jawab kal Part 2 mein 🕵️",
    "hashtags": ["#RaazKaFaisla", "#HindiMystery", "#DetectiveStory", "#Paheli", "#Shaadi", "#WhoDidIt", "#Suspense"],
    "claims": [{"claim": "Fiction.", "basis": "original story"}],
    "answer_for_part2": "C, the groom's friend. There was no plug point behind the stage, so he could not have gone to charge his phone. The bag has no syrup, so it was not the halwai; the photographer's photos show him on stage the whole time.",
}
json.dump(plan, open(os.path.join(OUT, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"topic": "raaz case 2", "top": [], "watched": [], "note": "see RESEARCH.md round 6 + round 7"},
          open(os.path.join(OUT, "research.json"), "w", encoding="utf-8"))
print("wrote", OUT, sum(len(s["vo"].split()) for s in S), "words")
