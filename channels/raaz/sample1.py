"""Builds the hand-written plan + research record for the first raaz sample (case 1, part 1).
The engine then does voice, assets, compose, mix, render and QC:  make.py raaz --job case1-p1 --from voice"""
import json, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/studio-out/raaz/case1-p1")
os.makedirs(OUT, exist_ok=True)

STYLE = ("Cinematic noir graphic-novel illustration, painterly with rich shadows, cold teal shadows and warm amber lamplight, "
         "subtle film grain, Rajasthani haveli, night, moody, vertical 9:16, one clear subject, empty space above and below")
INSP = ("Inspector Vikram Rathore seen from behind: tall Indian man in his 40s, long dark brown coat, steel wristwatch, "
        "holding a small brass torch")
MUNSHI = "Munshi Ramlal: thin elderly Indian man in his 60s, round wire glasses, white kurta and dhoti, ink-stained fingers, nervous eyes"
MEERA = "Bahu Meera: young Indian woman in her late 20s, maroon saree, long braid, flour on her forearms, tired but calm"
KALLU = "Driver Kallu: stocky Indian man in his 30s, grey driver uniform shirt, towel over his shoulder, oil-stained hands"
THAKUR = "Thakur Bhairav Singh: stern old Rajasthani nobleman in his 70s, big white moustache, red turban, cream angrakha"

S = [
    dict(vo="Ek haveli. Ek raat. Aur ek laal dibba... jo ab wahan nahi hai.", type="clip",
         prompt=f"{INSP}, walking slowly down a long candle-lit haveli corridor at night, torch beam sweeping the carved pillars. {STYLE}",
         motion="push", keywords=["laal", "dibba"], hud_right="PART 1"),
    dict(vo="Main Inspector Vikram Rathore. Aaj ka faisla, aapka hoga.", type="image",
         prompt=f"{INSP}, standing in a haveli courtyard on Diwali night, rows of glowing diyas, looking up at dark carved windows. {STYLE}",
         motion="pull", keywords=["faisla", "aapka"], hud_right="PART 1"),
    dict(vo="Jaipur ke paas, Thakur Bhairav Singh ki haveli. Diwali ki raat, almirah se laal dibba gayab.", type="image",
         prompt=f"Wide establishing shot of a grand old Rajasthani haveli at night, Diwali diyas along every wall, a single lit window glowing amber. {STYLE}",
         motion="push", keywords=["almirah", "laal", "dibba"], title="DIWALI KI RAAT", hud_right="PART 1"),
    dict(vo="Andar nau pushton ka sone ka haar tha. Taala toota nahi. Matlab, chabi se khula.", type="image",
         prompt=f"An open antique wooden almirah in a dim room with an empty velvet shelf, a brass padlock hanging open and unbroken, {THAKUR} standing beside it with a grim face. {STYLE}",
         motion="pan", keywords=["taala", "chabi"], title="TAALA TOOTA NAHI", hud_right="PART 1"),
    dict(vo="Chabi sirf teen logon ke paas thi. Teeno ne apni baat boli.", type="image",
         prompt=f"Three silhouettes standing in a row in a dim haveli hall, backlit by a lamp, faces hidden in shadow: a thin elderly man with glasses, a woman in a saree, a stocky man with a towel on his shoulder. {STYLE}",
         motion="push", keywords=["teen", "teeno"], hud_right="3 SUSPECT"),
    dict(vo="Pehla, Munshi Ramlal. Maine toh shaam se hisaab likha. Mujhe kya pata, kaale thaile mein dibba kab gaya.", type="clue",
         prompt=f"{MUNSHI}, sitting at a low wooden desk with a ledger under an oil lamp, looking sideways at the camera. {STYLE}",
         motion="push", label="SURAAG 1", who="Munshi Ramlal", quote="Main shaam se hisaab likh raha tha.",
         keywords=["hisaab", "kaale", "thaile"], hud_right="SURAAG 1/3"),
    dict(vo="Doosri, Bahu Meera. Main poori raat rasoi mein thi. Sau mehmaanon ka khaana banana tha.", type="clue",
         prompt=f"{MEERA}, in a steamy haveli kitchen with big brass pots, kneading dough, warm firelight. {STYLE}",
         motion="pan", label="SURAAG 2", who="Bahu Meera", quote="Main poori raat rasoi mein thi.",
         keywords=["rasoi", "mehmaanon"], hud_right="SURAAG 2/3"),
    dict(vo="Teesra, driver Kallu. Main toh gaadi dho raha tha, saab. Saara din gaadi ka kaam.", type="clue",
         prompt=f"{KALLU}, washing an old white Ambassador car in the haveli yard at night with a hose, lantern light. {STYLE}",
         motion="pull", label="SURAAG 3", who="Driver Kallu", quote="Main toh gaadi dho raha tha, saab.",
         keywords=["gaadi", "dho"], hud_right="SURAAG 3/3"),
    dict(vo="Ab dhyaan se suno. Almirah ke handle par na aata tha, na grease. Bilkul saaf.", type="image",
         prompt=f"Extreme close-up of an antique brass almirah handle, perfectly clean and shiny, soft amber side light, shallow depth of field. {STYLE}",
         motion="punch", keywords=["aata", "grease", "saaf"], title="HANDLE: BILKUL SAAF", hud_right="SURAAG 4"),
    dict(vo="Ek ne jhooth bola. Aur uski ek galti, aapne abhi sun li.", type="image",
         prompt=f"Close-up of a hand holding a small brass torch, its beam falling on a leather notebook on a dark table, a magnifying glass nearby. {STYLE}",
         motion="push", keywords=["jhooth", "galti"], hud_right="ZARA SOCHO"),
    dict(vo="Toh kaun hai chor? Munshi? Meera? Ya Kallu? Comment karo.", type="choice",
         prompt=f"{INSP}, standing at the end of a dark haveli corridor, torch beam pointing forward, deep shadows. {STYLE}",
         motion="push", options=["Munshi Ramlal", "Bahu Meera", "Driver Kallu"], keywords=["chor", "comment"], hud_right="TUMHARA FAISLA"),
    dict(vo="Sahi jawab, kal Part 2 mein. Dekhte hain, kitne log pakad paate hain.", type="card",
         prompt=f"The haveli at first light of dawn, mist in the courtyard, a single diya still burning, calm and ominous. {STYLE}",
         motion="pull", big="KAL: PART 2", small="Sahi jawab wahin", keywords=["kal", "part"], hud_right="PART 2 KAL"),
]

plan = {
    "slug": "case1-p1", "title": "Haveli ka laal dibba: kaun hai chor? (Part 1)",
    "hud_left": "PART 1",
    "hooks": ["Ek haveli. Ek raat. Aur ek laal dibba... jo ab wahan nahi hai.",
              "Teen log. Teen bahane. Ek jhooth.", "Chor ne khud apni galti bol di. Aapne suni?"],
    "hook_choice": 0,
    "hook_why": "Starts mid-mystery with an object (the red box) and a loss, no greeting; the lost object is the question.",
    "metaphor": "A fair-play whodunit: the culprit slips by mentioning a detail nobody told him (the black bag); viewers who listen can solve it.",
    "scenes": S,
    "caption": "Chor ne khud apni galti bol di. Aapne suni? 🕵️ Teen suspect, teen bahane, ek jhooth. Comment mein A, B ya C likho. Sahi jawab kal Part 2 mein.",
    "hashtags": ["#RaazKaFaisla", "#HindiMystery", "#DetectiveStory", "#Paheli", "#Suspense", "#WhoDidIt", "#YouDecide"],
    "claims": [{"claim": "Fiction. Inspector, haveli, and suspects are invented.", "basis": "original story"}],
    "answer_for_part2": ("Munshi Ramlal. Only the Inspector, Thakur and the thief knew the red box was carried in a black bag; "
                         "nobody had mentioned a bag before Munshi did. Clean handle: Meera (flour) and Kallu (grease) would have left marks; "
                         "Munshi wore gloves of his ledger cloth. Part 2 reveals the black bag in his room."),
}
json.dump(plan, open(os.path.join(OUT, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

research = {
    "top": [], "watched": [],
    "topic": "interactive suspense / who-did-it Reels in Hindi (Instagram, Nov 2026)",
    "method": "Apify hashtag reels scrape (#youdecide #hindimystery #suspensestory #mysterystory #detectivestory #kahanihindi, 90 reels), top reels downloaded and studied frame by frame; web research on interactive reels.",
    "findings": [
        "pahelikaraz (9.0M plays, 4.5k comments, 97 s): 2D vector story, pilot Captain Lena, game HUD (time, fuel), cockpit panels, notebook card, ends 'WHAT DID SHE FORGET? Comment your answer' + 'PART 2 COMING SOON'.",
        "paheli.x (1.14M plays, 23.7k comments, 46 s): detective puzzle 'chor ne khud apna raaz khola, kya aapne pakda?' fair-play slip clue; comment-answer CTA. Most comments per play in the set.",
        "thebankhesit (2.7M, 3.2k comments, 58 s): 'YOU JUST ROBBED A BANK', HUD (HEAT bar, CASH counter), phone message UI, A/B cards 'YOUR CALL', 'COMMENTS DECIDE WHAT HAPPENS IN PART 2'.",
        "oddhourtales (4.3M, 96 s): rules-of-the-keeper paper cards, clock, radio UI, ends with ANSWER / STAY SILENT card, 'Comment ANSWER or SILENT'.",
        "your.calltv (1.7M, 2.8k comments, 88 s): 'LET GO or HOLD ON? The majority writes Part 4'.",
        "All winners: speech from frame 0, one clear situation, game-like UI (HUD, phone messages, paper clues, A/B/C cards), a 'Part N' tag, the final frame is the question + the promise of the next part. Loudness -14 LUFS. Lengths 46-98 s.",
        "Most winners are flat 2D vector animation with simple characters. Our edge: cinematic noir stills + the same UI language, a fair-play clue the viewer can really solve, a recurring Inspector, and answers revealed in Part 2 (comment-to-know)."
    ],
    "sources": ["https://typito.com/blog/quiz-reels-trend-report-boost-engagement/", "https://postflow.app/blog/instagram-reel-polls-and-comment-prompts"],
}
json.dump(research, open(os.path.join(OUT, "research.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", OUT, sum(len(s["vo"].split()) for s in S), "words")
