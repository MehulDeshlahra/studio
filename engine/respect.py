"""Respectful address (owner 20 Nov: "never say tu"; then "tum is fine, only tu is bad").
Nobody on screen or in the voice is spoken to as "tu" (tu / tera / tujhe ... and the bare "tu" commands such as
"comment mein bata", "follow kar"). "tum" and "aap" are both fine; "tu" forms become "tum" forms.
  find(text)  -> list of the "tu" words found ([] = clean)
  fix(text)   -> the same text with the "tu" forms rewritten to "tum" forms
  fix_plan(p) -> rewrites every viewer-facing field of a plan in place, returns the number of changes
The plan writer gets the rule in its prompt; this module enforces it after (a prompt alone failed 5+ times)."""
import re

# "tu" word -> "tum" form (Roman Hinglish, as our scripts are written)
MAP = {
    "tu": "tum", "tujhe": "tumhe", "tujhko": "tumko", "tujhse": "tumse", "tujhme": "tumme", "tujhmein": "tummein",
    "tera": "tumhara", "teri": "tumhari", "tere": "tumhare", "tereko": "tumko", "terko": "tumko",
    "bata": "batao", "kar": "karo", "likh": "likho", "sun": "suno", "bol": "bolo", "soch": "socho", "dekh": "dekho",
    "ruk": "ruko", "chal": "chalo", "bhej": "bhejo", "le": "lo", "de": "do", "aaja": "aao", "ja": "jao",
}
# bare "tu" commands ("bata", "kar", "le", "de" ...) are also ordinary words ("kar diya", "le gaya"), so they count only
# right after a CTA word and at the end of a phrase ("comment mein bata.", "follow kar")
SOFT = {"bata", "kar", "likh", "sun", "bol", "soch", "dekh", "ruk", "chal", "bhej", "le", "de", "aaja", "ja"}
CTA = r"(?:comment|comments|share|follow|save|like|subscribe|dm|message|reply|tag|link|bio|neeche|mein|me|mujhe|humein|hume)"
HARD = re.compile(r"(?<![a-z])(" + "|".join(sorted((re.escape(k) for k in MAP if k not in SOFT), key=len, reverse=True)) + r")(?![a-z])", re.I)
SOFTRX = re.compile(r"(?<![a-z])(" + CTA + r")\s+(" + "|".join(SOFT) + r")(?![a-z])"
                    r"(?!\s+(?:dunga|dungi|denge|diya|liya|raha|rahi|rahe|chuka|chuki|sakta|sakti|payega))"
                    r"(?=\s*(?:$|[.,!?|:;\u2014-]|aur\b))", re.I)
# "tu ... hai / tha" endings become "tum ... ho / the"
HO = re.compile(r"(?<![a-z])(tum\b[^.?!|]{0,40}?\b)(hai|tha|thi)(?=\s*(?:[?!.,|]|$))", re.I)


def _case(src, new):
    return new.upper() if src.isupper() else (new.capitalize() if src[:1].isupper() else new)


KEEP = re.compile(r"aage\s+suno|samjho\.exe", re.I)        # the page name "Aage Suno" and handles stay as they are


def find(text):
    t = KEEP.sub(" ", text or "")
    return [m.group(0) for m in HARD.finditer(t)] + [m.group(2) for m in SOFTRX.finditer(t)]


def fix(text):
    if not text or not isinstance(text, str):
        return text
    keep = {}

    def _hold(m):
        keep[f"\x00{len(keep)}\x00"] = m.group(0); return f"\x00{len(keep) - 1}\x00"
    text = KEEP.sub(_hold, text)
    had_tu = bool(re.search(r"(?<![a-z])tu(?![a-z])", text, re.I))
    out = HARD.sub(lambda m: _case(m.group(1), MAP[m.group(1).lower()]), text)
    out = SOFTRX.sub(lambda m: m.group(1) + " " + _case(m.group(2), MAP[m.group(2).lower()]), out)
    if had_tu:                        # "tu kya sochta hai" -> "tum kya sochta ho"
        out = HO.sub(lambda m: m.group(1) + _case(m.group(2), {"hai": "ho", "tha": "the", "thi": "thi"}[m.group(2).lower()]), out)
    for k, v in keep.items():
        out = out.replace(k, v)
    return out


FIELDS = ("vo", "title", "big", "small", "headline", "text", "label", "question", "cta", "caption", "line", "hook")


REWRITE = """You fix ONE line of a Hindi short-video script (Roman Hinglish). Owner rule: nobody is spoken to as "tu".
Change every "tu" form (tu, tera, teri, tere, tujhe, tujhse and the bare commands like "bata", "kar", "le") to the
"tum" form with the matching verbs. "tum" and "aap" stay as they are. Do not add, drop or move anything else: same
names, same keywords in capitals, same punctuation, same meaning.
Examples:
"bhai tu tension mat le, sab theek ho jayega." -> "bhai tum tension mat lo, sab theek ho jayega."
"Tu hota to kya karta? Comment mein bata" -> "Tum hote to kya karte? Comment mein batao"
"aur usse nikalta hai tera processor." -> "aur usse nikalta hai tumhara processor."
"Proprietorship: tu hi maalik, unlimited risk." -> "Proprietorship: tum hi maalik, unlimited risk."
Line: {line}
Return JSON {{"line": "..."}}"""


def rewrite_line(line):
    """A spoken line: the text model rewrites it into natural respectful Hindi (word swaps break the grammar:
    "bhai tu tension mat le" -> "aap tension mat le"); checked, else the word-level fix."""
    if not find(line):
        return line
    try:
        import llm
        r = llm.text(REWRITE.format(line=line), json_mode=True, max_tokens=400) or {}
        new = str(r.get("line") or "").strip()
        wo, wn = re.findall(r"[a-z0-9]+", line.lower()), re.findall(r"[a-z0-9]+", new.lower())
        kept_caps = all(w in new for w in re.findall(r"\b[A-Z0-9]{3,}\b", line))     # keywords like MAHAKAL / PART2
        if new and not find(new) and abs(len(wn) - len(wo)) <= 2 and kept_caps and not re.search(r"[\u0900-\u097f]", new):
            return new
    except Exception:
        pass
    return fix(line)


def fix_plan(p):
    """Rewrite every viewer-facing text field of a plan (scenes + post text). Returns the number of fields changed."""
    n = 0

    def walk(o):
        nonlocal n
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if isinstance(v, str) and (k in FIELDS or k.endswith("_text") or k in ("description", "pinned", "comment", "first_comment")):
                    f = rewrite_line(v) if k == "vo" else fix(v)
                    if f != v:
                        o[k] = f; n += 1
                elif isinstance(v, (dict, list)) and k not in ("bible", "pic", "credits", "research", "sources"):
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(p)
    return n


def problems(p):
    """Viewer-facing informal words still in a plan (for the review)."""
    out = []
    for i, s in enumerate(p.get("scenes") or []):
        for k in FIELDS:
            v = s.get(k)
            if isinstance(v, str) and find(v):
                out.append(f"scene {i + 1} {k}: informal '{', '.join(find(v))}' in \"{v[:80]}\" (owner: never 'tu')")
    for k in ("caption", "description", "title", "first_comment", "pinned"):
        v = p.get(k)
        if isinstance(v, str) and find(v):
            out.append(f"post {k}: informal '{', '.join(find(v))}' (owner: never 'tu')")
    return out


if __name__ == "__main__":
    for t, want in [("Comment batao tum", "Comment batao tum"), ("Tum kya sochte ho?", "Tum kya sochte ho?"), ("Follow karo", "Follow karo"),
                    ("Tu hota to kya karta? Comment mein bata", None), ("Tera dost kaun hai?", "Tumhara dost kaun hai?"),
                    ("bhai tu tension mat le", None), ("Raghav le gaya", "Raghav le gaya"), ("main DM kar dunga", "main DM kar dunga"),
                    ("Aage Suno pe follow kar", "Aage Suno pe follow karo"), ("Tu kya sochta hai?", "Tum kya sochta ho?")]:
        got = fix(t)
        print("OK " if (want is None or got == want) else "BAD", repr(t), "->", repr(got), "| left", find(got))
