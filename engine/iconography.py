"""Traditional forms of deities and sacred figures (owner rule: respectful, no controversy, correct forms).
Used twice (18 Nov): when a picture prompt is written (make.py) the matching forms are added, so the image model draws
the figure correctly; and the pre-render / final checkers get the same list, so a correct traditional form (Kartikeya
with six faces, Brahma with four heads) is never reported as a mistake. Keep descriptions short and neutral.
  iconography.notes(text) -> "" or "Kartikeya: ...; Shiva: ..." for the names found in text"""
import re

FORMS = {
    "Kartikeya": (r"kartikeya|kartikey|murugan|skanda|subrahmanya|shanmukha",
                  "youthful warrior god, one face or six faces (Shanmukha), holds a vel (spear), rides a peacock"),
    "Ganesha": (r"ganesh|ganesha|ganpati|ganapati|vinayak",
                "elephant head with one broken tusk, pot belly, four arms, modak, mouse (mooshak) as vehicle"),
    "Shiva": (r"\bshiv\b|shiva|mahadev|shankar|bholenath|neelkanth|rudra",
              "ash-grey or blue-grey skin, matted hair with crescent moon and Ganga, third eye, trident, damru, snake at the neck, tiger skin"),
    "Parvati": (r"parvati|gauri|uma\b", "graceful goddess in a red or green saree with jewellery, often beside Shiva"),
    "Durga": (r"durga|ambe|sherawali|mahishasura", "many-armed goddess holding weapons, rides a lion or tiger, red saree"),
    "Kali": (r"\bkali\b|kaali", "dark-skinned fierce goddess, many arms; always shown respectfully, never gory"),
    "Vishnu": (r"vishnu|narayan(?!a narayana)|hari\b", "blue skin, four arms holding conch, chakra, mace and lotus, yellow garments, crown"),
    "Lakshmi": (r"lakshmi|laxmi", "goddess on a lotus in a red saree, gold coins flowing from a hand, elephants beside her"),
    "Krishna": (r"krishna|kanha|govind|gopal|murari", "blue skin, peacock feather in the crown, flute, yellow garments"),
    "Rama": (r"\bram\b|\brama\b|shri ram|raghav", "blue-green skin, bow and arrows, prince's crown, calm face"),
    "Sita": (r"\bsita\b|janaki", "graceful princess in a simple saree, gentle and dignified"),
    "Hanuman": (r"hanuman|bajrang|maruti|pavanputra", "monkey face, strong body, mace (gada), often orange-red"),
    "Brahma": (r"brahma\b|brahmaji|brahma ji", "four bearded faces, four arms holding the Vedas and a water pot, seated on a lotus, swan"),
    "Saraswati": (r"saraswati|sarasvati", "white saree, plays the veena, seated on a white lotus with a swan"),
    "Yamraj": (r"yamraj|yama\b|yamaraj|dharmaraj", "dark-skinned king of death with a crown, mace and noose, rides a buffalo; stern, never scary-horror"),
    "Indra": (r"\bindra\b|devraj", "king of the gods with a crown and a vajra (thunderbolt), rides the white elephant Airavata"),
    "Surya": (r"surya|suryadev|sun god", "radiant golden god on a chariot pulled by seven horses"),
    "Ganga": (r"\bganga\b|gangaji|ganga maa", "goddess in white, seated on a makara (crocodile-like creature), flowing water"),
    "Narad": (r"narad|narada", "sage in white or saffron with a veena (tanpura), a tuft of hair, walks on clouds"),
    "Kuber": (r"kuber|kubera", "plump god of wealth with gold jewellery, a money pot, sometimes a mongoose"),
    # 18 Nov, Navkar Bhav (Jain page). Patterns never match the Hindu 'Mahavir' (a name of Hanuman) on its own.
    "Mahavir Swami": (r"mahavir swami|mahaveer swami|bhagwan mahavir|bhagwan mahaveer|vardhaman|tirthankar mahavir|mahavira\b",
                      "the 24th Tirthankara: serene meditating figure, seated padmasana or standing kayotsarga, eyes half closed, "
                      "calm face, curled hair, shrivatsa mark on the chest, lion emblem below; no weapons, no crown; often a "
                      "temple idol in white marble or gold"),
    "Rishabhdev": (r"rishabh ?dev|rishabhanatha|adinath|adinatha|aadinath", "the 1st Tirthankara: serene meditating figure with "
                   "locks of hair on the shoulders, bull emblem below, calm face, no weapons"),
    "Parshvanath": (r"parshvanath|parshwanath|parasnath|parshva\b", "the 23rd Tirthankara: serene meditating figure sheltered by "
                    "a seven-hooded serpent canopy over the head, calm face, no weapons"),
    "Neminath": (r"neminath|nemi ?nath|arishtanemi", "the 22nd Tirthankara: serene meditating figure, conch emblem below, dark "
                 "complexion, calm face"),
    "Bahubali": (r"bahubali|gommateshwara|gomateshwara", "a tall standing figure in kayotsarga meditation, creepers growing up "
                 "the arms and legs, anthills at the feet, perfectly calm (like the Shravanabelagola statue)"),
    "Jain monk": (r"\bmuni\b|sadhvi|jain monk|acharya|maharaj saheb|digambar|shwetambar|svetambar",
                  "Jain monk or nun in plain white robes with a rajoharan (soft whisk broom) and a mouth cloth (muhpatti), "
                  "calm and simple, no jewellery"),
}
# 18 Nov: the checkers held Kartikeya for "five faces instead of six" twice; in a turned head some faces are hidden.
NO_COUNT = (" Never count faces, heads or arms (in a painting at an angle some are hidden): report a deity only for a clearly "
            "wrong form (wrong gender, an animal head that does not belong, missing the defining weapon or mount) or a lack of dignity.")
DECENCY = "every figure fully and modestly dressed in traditional attire, correct gender and form, devotional and dignified"


def notes(text):
    t = (text or "").lower()
    hits = [f"{k}: {v}" for k, (rx, v) in FORMS.items() if re.search(rx, t)]
    return "; ".join(hits)


def prompt_addition(text):
    """Text to add to an image prompt that mentions a deity ('' when none is named)."""
    n = notes(text)
    return f" Traditional form: {n}. {DECENCY}." if n else ""
