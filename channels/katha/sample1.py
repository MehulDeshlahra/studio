"""katha pilot 1: "Kuber ka ghamand aur Ganesh ji ki bhookh" (lok-katha). Hand-written plan from research round 9.
Then: make.py katha --job kuber-01 --from voice"""
import json, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/studio-out/katha/kuber-01")
os.makedirs(OUT, exist_ok=True)

STYLE = ("Painterly cinematic Indian epic illustration, rich warm gold and deep maroon, soft divine rim light, "
         "ornate but uncluttered, vertical 9:16, one clear subject centred, empty space at the top and bottom")
KUBER = "Kuber: plump Indian god of wealth, golden crown, heavy gold jewellery, rich silk dhoti, proud smile"
GANESH = "Bal Ganesh: young child Lord Ganesha with elephant head, small and cute, red dhoti, gentle calm eyes"
SHIVA = "Lord Shiva: calm, blue skin, crescent moon in matted hair, serpent around neck, sitting on Mount Kailash"

S = [
    dict(vo="Teeno lok ka sabse ameer devta... ek bachche ko khaana khila nahi paaya.", type="clip",
         prompt=f"{KUBER} standing shocked in a huge golden palace hall, empty golden plates everywhere, slow camera push-in. {STYLE}",
         motion="push", keywords=["ameer", "bachche"], hud_right="LOK KATHA"),
    dict(vo="Kuber ke paas itna sona tha, ki wo use dikhane ke liye ek bhoj rakhte hain.", type="image",
         prompt=f"{KUBER} proudly showing an endless palace full of gold coins and jewels, servants carrying golden trays. {STYLE}",
         motion="pan", keywords=["sona", "bhoj"]),
    dict(vo="Wo Kailash jaate hain, aur Mahadev ko nyota dete hain.", type="image",
         prompt=f"{KUBER} bowing with folded hands before {SHIVA} on snowy Mount Kailash, golden invitation scroll in his hand. {STYLE}",
         motion="push", keywords=["kailash", "mahadev"]),
    dict(vo="Mahadev muskura kar kehte hain... main nahi aa sakta. Mera beta Ganesh aayega.", type="image",
         prompt=f"{SHIVA} smiling softly and pointing to {GANESH} sitting beside him on Kailash. {STYLE}",
         motion="pull", keywords=["ganesh"]),
    dict(vo="Ganesh ji khaane baithte hain. Pehli thaali, khatam. Dusri, khatam.", type="image",
         prompt=f"{GANESH} sitting on a golden seat eating happily from a big golden thali in a grand dining hall, servants amazed. {STYLE}",
         motion="punch", keywords=["khatam"]),
    dict(vo="Rasoi khaali ho gayi. Bhandaar khaali ho gaya.", type="card",
         prompt=f"A grand palace kitchen with huge empty copper pots and empty storerooms, cooks looking scared. {STYLE}",
         motion="push", big="SAB KHAALI", small="phir bhi bhookh", keywords=["khaali"]),
    dict(vo="Ganesh ji bole... mujhe abhi bhi bhookh lagi hai.", type="image",
         prompt=f"{GANESH} looking up innocently with an empty thali, while {KUBER} sweats nervously behind. {STYLE}",
         motion="push", keywords=["bhookh"]),
    dict(vo="Ghabraaye Kuber, bhaag kar Mahadev ke paas pahunche.", type="image",
         prompt=f"{KUBER} running in panic up the snowy path of Mount Kailash, crown slipping. {STYLE}",
         motion="pan", keywords=["mahadev"]),
    dict(vo="Mahadev ne bas ek mutthi chaawal diye, aur kaha: ise prem se khilao.", type="image",
         prompt=f"{SHIVA} placing a small handful of rice into the hands of {KUBER}, soft divine light. {STYLE}",
         motion="push", keywords=["mutthi", "prem"]),
    dict(vo="Ek mutthi chaawal. Aur Ganesh ji ka pet bhar gaya.", type="clip",
         prompt=f"{GANESH} happily eating a small handful of rice from a simple leaf plate, glowing contentment, warm light. {STYLE}",
         motion="push", keywords=["mutthi", "bhar"]),
    dict(vo="Bhagwan ko sona nahi chahiye. Bas bhaav chahiye.", type="card",
         prompt=f"A single humble leaf plate with a little rice in front of a small diya, golden light, temple background. {STYLE}",
         motion="pull", big="BHAAV", small="sona nahi", keywords=["bhaav"]),
    dict(vo="Aap ne kabhi dikhaave ke liye kuch kiya hai? Comment mein batao.", type="image",
         prompt=f"{GANESH} smiling warmly at the viewer, hands in blessing, soft golden background. {STYLE}",
         motion="pull", keywords=["comment"]),
]

plan = {
    "slug": "kuber-01", "title": "Kuber ka ghamand aur Ganesh ji ki bhookh",
    "hud_left": "PURAAN KI KATHA",
    "hooks": ["Teeno lok ka sabse ameer devta... ek bachche ko khaana khila nahi paaya.",
              "Ek mutthi chaawal ne Kuber ka ghamand tod diya.", "Ganesh ji ki bhookh kisi se nahi mitti thi... ek ko chhod kar."],
    "hook_choice": 0,
    "hook_why": "Paradox in line 1 (richest god fails to feed a child), the pattern of the 12-13M winners: a twist the viewer hasn't heard.",
    "metaphor": "Endless gold cannot fill a child's stomach; one handful given with love can.",
    "scenes": S,
    "caption": "Teeno lok ka sabse ameer devta ek bachche ka pet nahi bhar paaya 🙏 Ek mutthi chaawal ne sab badal diya. (Lok katha) Aap ne kabhi dikhaave ke liye kuch kiya hai?",
    "hashtags": ["#Ganesh", "#Kuber", "#PauranikKatha", "#Mahadev", "#SanatanDharma", "#HindiKahani", "#Bhakti"],
    "claims": [{"claim": "Kuber's feast and Ganesha's hunger", "basis": "popular Indian lok-katha (folk tale) about Kuber's pride; not from a single Purana chapter, so the video says 'lok katha'."}],
}
json.dump(plan, open(os.path.join(OUT, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"topic": "katha pilot", "top": [], "watched": [], "note": "RESEARCH.md round 9"},
          open(os.path.join(OUT, "research.json"), "w", encoding="utf-8"))
print("wrote", OUT, sum(len(s["vo"].split()) for s in S), "words")
