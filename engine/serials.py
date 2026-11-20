"""Aage Suno = original fiction told as a SERIAL (owner 17 Nov: "a story that starts with something, then a 10-day series").
One story at a time per page. The whole arc is planned once, up front (story bible), so the parts connect and the cast
looks the same in every part; then one part is made per slot, ahead of posting.
  stories live in channels/<page>/stories/<slug>.json:
    {slug, title, genre, logline, cast: {name: fixed visual description}, setting, parts: [{n, title, beats, cliffhanger,
     status: todo|made}], made_jobs: {n: job}}
  next_topic(ch)   -> "<Story title> - Part n" for the next part not made yet (starts a new story when the last one is done)
  context(ch, topic) -> text for the planner: the bible, this part's beats, and what the earlier parts said
  mark_made(ch, topic, job)
Length: planned as 10 parts; if Part 1-3 are clearly weak once stats exist, the story is closed early (wrap-up part
replaces the remaining ones) so a weak story does not run for 10 days.
  python engine/serials.py <page> [new]"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save

# Owner 18 Nov: use his and his friends' names. Start with Mehul + Raghav, then rotate (never the same pair every story).
# Villains / culprits always get a MADE-UP name (never a friend, never "Rohan").
FRIENDS = ["Mehul", "Raghav", "Aditya", "Shobhit", "Shwetal", "Saumya", "Suhail", "Jahnvi", "Masood", "Animesh", "Jayesh",
           "Aaryan", "Dhruv", "Mudit", "Shruti"]
BANNED_VILLAIN = {"rohan"}


def _names_for_new_story(cid):
    """Hero + 1-3 friends for the next story: least used first, so everyone appears over time."""
    use = {}
    for s in stories(cid):
        for n in s.get("cast", {}):
            use[n] = use.get(n, 0) + 1
    order = sorted(FRIENDS, key=lambda n: (use.get(n, 0), FRIENDS.index(n)))
    return order[0], order[1:4]


GENRES = ["mystery thriller", "emotional family drama", "light horror", "fantasy (talking objects or animals, magic in a modern Indian town)",
          "karma and revenge twist", "love story with a secret", "survival / adventure", "sci-fi in a small Indian town"]

ARC = """You write ORIGINAL fiction serials for the Hindi faceless Shorts page "{name}". Tagline: "{tagline}".
Write ONE new story that runs exactly {n} parts, one 40-second part per day. Genre this time: {genre}.
Earlier stories (do not repeat their idea): {past}.
Rules: pure fiction, no real people, no real crimes, no religion or mythology, no gore, no politics; a modern, relatable Indian
setting (city flat, hostel, office, train, small town, village fair, hospital, wedding); 2-4 characters, the hero is ordinary.
Part 1 opens on the strangest, most specific moment (first line pulls you in) and ends on a hook. EVERY part ends on a
cliffhanger that makes people come back tomorrow. The middle keeps raising the stakes (a new clue, a betrayal, a twist every
2-3 parts); Part {n} pays everything off with a satisfying twist. Each part has a clear new event (no recap-only parts).
NAMES: the hero is {hero}; friends / side characters may use: {friends} (use 1-3 of them, good characters only).
The villain or culprit gets a made-up Indian name that is NOT in that list and is never "Rohan".
Cast: EVERY named character who appears in any part (hero, friends, villain, side characters) gets a fixed visual description (age, face, hair, clothes, one signature item) reused in every image; nobody appears who is not in the cast.
Return JSON {{"title": "<Hindi/Hinglish title, 2-5 words>", "slug": "ascii-slug", "genre": "...", "logline": "one sentence",
"setting": "...", "cast": {{"<name>": "fixed visual description"}},
"parts": [{{"n": 1, "title": "...", "beats": "3-5 sentences: what happens in this part", "cliffhanger": "the last moment"}}, ... {n} parts]}}"""


def _dir(cid):
    d = os.path.join(ROOT, "channels", cid, "stories"); os.makedirs(d, exist_ok=True); return d


def stories(cid):
    out = []
    for f in sorted(os.listdir(_dir(cid))):
        if f.endswith(".json"):
            s = load(os.path.join(_dir(cid), f), {})
            if s:
                out.append(s)
    return sorted(out, key=lambda s: s.get("started", ""))


def _save(cid, s):
    save(os.path.join(_dir(cid), s["slug"] + ".json"), s)


def new_story(ch):
    import plan as planner
    cid = ch["id"]
    past = [s.get("title") + ": " + s.get("logline", "") for s in stories(cid)][-12:]
    used = [s.get("genre", "") for s in stories(cid)][-3:]
    genre = next((g for g in GENRES if not any(g.split()[0] in u for u in used)), GENRES[len(past) % len(GENRES)])
    n = int((ch.get("serial") or {}).get("parts", 10))
    hero, friends = _names_for_new_story(cid)
    r = planner.ask(ARC.format(name=ch.get("name", cid), tagline=ch.get("tagline", ""), n=n, genre=genre, hero=hero,
                               friends=", ".join(friends), past="; ".join(past) or "none yet"), max_tokens=6000) or {}
    parts = [p for p in (r.get("parts") or []) if isinstance(p, dict) and p.get("beats")]
    if not r.get("title") or len(parts) < max(5, n - 2):
        log("serial: story planning failed for", cid); return None
    slug = re.sub(r"[^a-z0-9]+", "-", (r.get("slug") or r["title"]).lower()).strip("-")[:40] or time.strftime("story-%m%d")
    if os.path.exists(os.path.join(_dir(cid), slug + ".json")):
        slug += time.strftime("-%m%d")
    s = {"slug": slug, "title": r["title"], "genre": r.get("genre", genre), "logline": r.get("logline", ""), "setting": r.get("setting", ""),
         "cast": r.get("cast") or {}, "started": time.strftime("%Y-%m-%d %H:%M"),
         "parts": [dict(p, n=i + 1, status="todo") for i, p in enumerate(parts[:n])], "made_jobs": {}}
    _save(cid, s)
    log("serial: new story for", cid, repr(s["title"]), f"({s['genre']}, {len(s['parts'])} parts)")
    return s


def _current(ch):
    # 18 Nov: the story already on air (most parts made) first; an older story's lost Part 2 must not cut into it
    for s in sorted(stories(ch["id"]), key=lambda s: -sum(p["status"] == "made" for p in s["parts"])):
        if any(p["status"] == "todo" for p in s["parts"]) and not s.get("closed"):
            return s
    return new_story(ch)


def next_topic(ch):
    s = _current(ch)
    if not s:
        return None
    p = next(p for p in s["parts"] if p["status"] == "todo")
    return f"{s['title']} - Part {p['n']}"


def _find(ch, topic):
    m = re.match(r"(.+) - Part (\d+)$", str(topic or ""))
    if not m:
        return None, None
    for s in stories(ch["id"]):
        if s["title"] == m.group(1):
            return s, int(m.group(2))
    return None, None


def _complete_cast(ch, s, n):
    """Part n may bring in a named character who has no fixed look yet (Rohan in Part 8 of the first story): ask the planner
    for a description once, save it to the story, so every image of that character matches."""
    part = s["parts"][n - 1]
    txt = f"{part.get('title', '')}. {part.get('beats', '')} {part.get('cliffhanger', '')}"
    try:
        import plan as planner
        r = planner.ask("Our serial's cast so far: " + json.dumps(s["cast"], ensure_ascii=False) + ".\nThis part's text: " + txt[:900]
                        + '\nList every NAMED person in this part who is NOT in the cast, with a fixed visual description (age, face, hair, '
                        'clothes, one signature item), consistent with the story setting. JSON {"new": {"<name>": "<description>"}} '
                        '(empty if nobody is missing).', max_tokens=700) or {}
        new = {k: v for k, v in (r.get("new") or {}).items() if isinstance(v, str) and k not in s["cast"]} if isinstance(r, dict) else {}
        if new:
            s["cast"].update(new)
            _save(ch["id"], s)
            log("serial: added to the cast for part", n, ", ".join(new))
    except Exception as e:
        log("serial cast check failed", str(e)[:100])


def context(ch, topic):
    s, n = _find(ch, topic)
    if not s:
        return ""
    _complete_cast(ch, s, n)
    last = len(s["parts"])
    part = s["parts"][n - 1]
    prev = []
    for k in range(1, n):
        j = s["made_jobs"].get(str(k))
        pl = load(os.path.join(OUT, ch["id"], j, "plan.json"), {}) if j else {}
        said = " ".join(x.get("vo", "") for x in pl.get("scenes", []))
        prev.append(f"Part {k}: " + (said[:600] if said else s["parts"][k - 1]["beats"]))
    nxt = "THIS IS THE LAST PART: pay everything off with the twist; end with: 'Kal ek nayi kahani. Follow kijiye.'" if n == last \
        else f"End on this cliffhanger: {part.get('cliffhanger')}. Last spoken line: 'Part {n + 1} kal. Follow kijiye.'"
    return (f"THIS VIDEO IS PART {n} OF {last} of our original serial \"{s['title']}\" ({s['genre']}). Logline: {s['logline']}\n"
            f"Setting: {s['setting']}\nCAST (paste each description verbatim in every image prompt that shows them): "
            f"{json.dumps(s['cast'], ensure_ascii=False)}\nTHIS PART: {part.get('title')}: {part['beats']}\n"
            + ("Earlier parts (do not repeat them; one short recap line at most, then new events):\n" + "\n".join(prev[-4:]) + "\n" if prev else
               "Part 1: open on the strangest moment, no recap.\n")
            + nxt + f"\nOn screen: hud_left \"PART {n}\". Set \"end_line\" to " + ("\"Kal ek nayi kahani\"" if n == last else f"\"Part {n + 1} kal\"") + ".")


def mark_made(ch, topic, job):
    s, n = _find(ch, topic)
    if not s:
        return
    s["parts"][n - 1]["status"] = "made"; s["made_jobs"][str(n)] = job
    _save(ch["id"], s)


if __name__ == "__main__":
    from core import channel
    ch = channel(sys.argv[1])
    if sys.argv[2:3] == ["new"]:
        print(json.dumps(new_story(ch), ensure_ascii=False, indent=1)[:3000])
    else:
        t = next_topic(ch); print(t); print(context(ch, t)[:2500])
