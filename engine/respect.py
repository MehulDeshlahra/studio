"""Respectful address (owner, said again 20 Nov: "never say tu and all, give request to viewers always").
Every word the viewer hears or reads (voice lines, on-screen titles / cards, captions, post text, comments) speaks to
them as "aap", and asks as a request ("comment mein bataiye", "follow kijiye"), never "tu / tum / batao / likho / karo".
  find(text)  -> list of the informal words found ([] = clean)
  fix(text)   -> the same text with the common forms rewritten (words with no safe rewrite are left for find())
  fix_plan(p) -> rewrites every viewer-facing field of a plan in place, returns the number of changes
The plan writer gets the rule in its prompt; this module enforces it after (a prompt alone failed 5+ times)."""
import re

# informal word -> respectful form (Roman Hinglish, as our scripts are written)
MAP = {
    "tu": "aap", "tum": "aap", "tujhe": "aapko", "tumhe": "aapko", "tumhein": "aapko", "tujhko": "aapko", "tumko": "aapko",
    "tujhse": "aapse", "tumse": "aapse", "tera": "aapka", "teri": "aapki", "tere": "aapke", "tumhara": "aapka",
    "tumhari": "aapki", "tumhare": "aapke", "tumhaara": "aapka", "tumhaari": "aapki", "tumhaare": "aapke",
    "batao": "bataiye", "bata": "bataiye", "likho": "likhiye", "likh": "likhiye", "socho": "sochiye", "soch": "sochiye",
    "dekho": "dekhiye", "suno": "suniye", "sun": "suniye", "bolo": "boliye", "bol": "boliye", "jao": "jaiye", "aao": "aaiye",
    "ruko": "rukiye", "ruk": "rukiye", "rukho": "rukiye", "chalo": "chaliye", "samjho": "samjhiye", "yaad rakho": "yaad rakhiye",
    "karo": "kijiye", "kar": "kijiye", "do": "dijiye", "lo": "lijiye", "bhejo": "bhejiye", "pucho": "poochhiye", "poocho": "poochhiye",
    "karoge": "karenge", "dekhoge": "dekhenge", "sochoge": "sochenge", "jaoge": "jaayenge", "bologe": "bolenge",
    "doge": "denge", "loge": "lenge", "chunoge": "chunenge", "bataoge": "batayenge", "samjhoge": "samjhenge", "rahoge": "rahenge",
    "chuno": "chuniye", "dabao": "dabaiye", "bachao": "bachaiye", "padho": "padhiye", "jano": "jaaniye", "jaano": "jaaniye", "milao": "milaiye",
}
# words that are only informal when they address someone; "do" (two), "lo", "kar", "bata", "sun", "bol", "soch", "likh",
# "ruk" are common inside other phrases, so they are rewritten only right after a CTA word or at a line end
SOFT = {"do", "lo", "kar", "bata", "sun", "bol", "soch", "likh", "ruk"}
CTA = r"(?:comment|comments|share|follow|save|like|subscribe|dm|message|reply|tag|link|bio|neeche|mein|me|mujhe|humein|hume)"
HARD = re.compile(r"(?<![a-z])(" + "|".join(sorted((re.escape(k) for k in MAP if k not in SOFT), key=len, reverse=True)) + r")(?![a-z])", re.I)
# "DM kar dunga" / "bhej diya" (I will / I did) is not a request: a first-person ending after it keeps the word
SOFTRX = re.compile(r"(?<![a-z])(" + CTA + r")\s+(" + "|".join(SOFT) + r")(?![a-z])"
                    r"(?!\s+(?:dunga|dungi|denge|diya|liya|raha|rahi|rahe|chuka|chuki|sakta|sakti|payega))", re.I)
# "tum ... ho" / "tu ... hai" endings become "aap ... hain"
HO = re.compile(r"(?<![a-z])(aap\b[^.?!|]{0,40}?\b)(ho|hai|tha|thi)(?=[\s?!.,]|$)", re.I)


def _case(src, new):
    return new.upper() if src.isupper() else (new.capitalize() if src[:1].isupper() else new)


OGE = re.compile(r"(?<![a-z])([a-z]{2,})oge(?![a-z])", re.I)       # any "-oge" (you will ...) -> "-enge"


KEEP = re.compile(r"aage\s+suno|samjho\.exe", re.I)        # the page name "Aage Suno" and handles stay as they are


def find(text):
    t = KEEP.sub(" ", text or "")
    return [m.group(0) for m in HARD.finditer(t)] + [m.group(2) for m in SOFTRX.finditer(t)] + [m.group(0) for m in OGE.finditer(t)]


def fix(text):
    if not text or not isinstance(text, str):
        return text
    keep = {}

    def _hold(m):
        keep[f"\x00{len(keep)}\x00"] = m.group(0); return f"\x00{len(keep) - 1}\x00"
    text = KEEP.sub(_hold, text)
    had_tu = bool(re.search(r"(?<![a-z])(tu|tum)(?![a-z])", text, re.I))
    out = HARD.sub(lambda m: _case(m.group(1), MAP[m.group(1).lower()]), text)
    out = SOFTRX.sub(lambda m: m.group(1) + " " + _case(m.group(2), MAP[m.group(2).lower()]), out)
    out = OGE.sub(lambda m: m.group(1) + ("ENGE" if m.group(0).isupper() else "enge"), out)
    if had_tu:                        # "tum kya sochte ho" -> "aap kya sochte hain"
        out = HO.sub(lambda m: m.group(1) + _case(m.group(2), {"ho": "hain", "hai": "hain", "tha": "the", "thi": "thi"}[m.group(2).lower()]), out)
    for k, v in keep.items():
        out = out.replace(k, v)
    return out


FIELDS = ("vo", "title", "big", "small", "headline", "text", "label", "question", "cta", "caption", "line", "hook")


def fix_plan(p):
    """Rewrite every viewer-facing text field of a plan (scenes + post text). Returns the number of fields changed."""
    n = 0

    def walk(o):
        nonlocal n
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if isinstance(v, str) and (k in FIELDS or k.endswith("_text") or k in ("description", "pinned", "comment", "first_comment")):
                    f = fix(v)
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
                out.append(f"scene {i + 1} {k}: informal '{', '.join(find(v))}' in \"{v[:80]}\" (owner: always 'aap' and a request)")
    for k in ("caption", "description", "title", "first_comment", "pinned"):
        v = p.get(k)
        if isinstance(v, str) and find(v):
            out.append(f"post {k}: informal '{', '.join(find(v))}' (owner: always 'aap' and a request)")
    return out


if __name__ == "__main__":
    for t in ["Comment batao tum", "TUM HOTE TOH? COMMENT MEIN LIKHO", "COMMENT MEIN BATAO", "Tum kya sochte ho?",
              "Agla baar darr aaye - tum kya karoge? Dekhoge? Ya daboge?", "Do log aaye", "Follow karo aur share karo",
              "Kuber ne do baar socha", "Aap kya sochte hain? Comment kijiye", "Tera dost kaun hai?", "Mujhe batao"]:
        print(f"{t!r:60} -> {fix(t)!r:60} left: {find(fix(t))}")
