"""How strict the gates are (owner 20 Nov: "we are getting too strict, nothing will ever be posted").
HARD problems stop a video: things a viewer or a devotee would see as wrong, or that hurt the page.
Everything else is SOFT: the video gets ONE automatic fix (the healer), then posts even if a soft problem is left; the
problem goes to the page's lessons so the next videos avoid it.
  is_hard(problem) -> True / False
  split(problems)  -> (hard, soft)
  allow_soft(jd, soft, gate) -> True when this video already had its one fix for soft problems at this gate"""
import os, re

# a wrong sacred form, a wrong place, or no dignity (picture checks, vision review, before-render FIT checks)
SACRED = re.compile(r"deit|\bgod|goddess|tirthankar|mahavir|bahubali|gommat|rishabh|parshva|neminath|idol|monk|\bnun\b|"
                    r"ascetic|robe|saffron|crown|tiara|tilak|jewel|necklace|beard|moustache|blue skin|grey skin|green skin|"
                    r"third eye|more than two arms|four-armed|emblem|weapon|trishul|peacock feather|flute|wrong (traditional )?"
                    r"form|wrong mount|wrong gender|hindu god|onion dome|minaret|mosque|mughal|islamic|taj mahal|immodest|"
                    r"dignity|living man|clothed|clothes|horned demon|demon on|vishnu-like|krishna-like|shiva-like", re.I)
HARD = [
    re.compile(r"informal '", re.I),                                           # "tu" (owner rule)
    re.compile(r"^STORY|invented|NUMBERS:|wrong (maths|number)|not found in .*(texts|sources)|fabricat", re.I),  # facts
    re.compile(r"brand-safe|brand-unsafe|unsafe|swear|abusive|gory|gore", re.I),
    re.compile(r"^format/loudness|no audio|true peak", re.I),                   # broken sound / format
    re.compile(r"spoken instructions|does not start with the first line|of the script was found", re.I),   # broken voice
    re.compile(r"not in Latin script|wrong language|japanese|devanagari", re.I),
]
SCORE = re.compile(r"visual score (\d+)", re.I)


def is_hard(p):
    t = str(p)
    if any(r.search(t) for r in HARD):
        return True
    m = SCORE.search(t)
    if m:
        return int(m.group(1)) < 5                     # 5-6 out of 10 is a soft problem, under 5 is not shown
    if re.search(r"picture check|^visual:|FIT:|before render", t, re.I) and SACRED.search(t):
        return True
    return False


def split(problems):
    hard = [p for p in problems if is_hard(p)]
    return hard, [p for p in problems if not is_hard(p)]


def allow_soft(jd, soft, gate):
    """gate 'review' / 'preflight'. The first time only soft problems are found the video is held (one fix); the next
    time they pass. Counted in meta.json so a rebuild does not reset it."""
    import json
    mp = os.path.join(jd, "meta.json")
    try:
        meta = json.load(open(mp, encoding="utf-8"))
    except Exception:
        meta = {}
    key = f"soft_{gate}"
    if meta.get(key, 0) >= 1:
        return True
    meta[key] = meta.get(key, 0) + 1
    tmp = mp + ".new"
    json.dump(meta, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, mp)
    return False


if __name__ == "__main__":
    for p in ["picture check: scene 1: Is the picture split into panels, a collage (yes 83%)",
              "picture check: scene 12: Does the main deity carry an emblem of a different god (yes 75%)",
              "before render, scene 3: FIT: split / collage picture shown instead of a single cohesive scene",
              "before render, scene 2: FIT: monk is wearing orange/saffron robes instead of plain white robes",
              "before render, scene 5: OVERLAP/CUT (layout audit): text_occluded on #s5",
              "visual: Scene 5: The caption 'SAANP' is cut off", "visual score 6/10", "visual score 4/10",
              "STORY scene 4: invented: 'Phir bhi Muni ne pucha'", "scene 2 vo: informal 'tu' in ...",
              "length 78.2 s is outside 25-75 s", "blank frame from 3.0 s to 4.0 s",
              "visual: Scene 1, 2, 6 clearly feature Mughal/Islamic architecture including large white onion domes"]:
        print("HARD" if is_hard(p) else "soft", "|", p[:90])
