"""CutCapsule: long video -> the best short moments -> finished vertical clips (owner 19 Nov: "just provide a YT link,
it sees the best moments, suggests clips and auto-creates them"). Research: knowledge/clipping.md.

  python engine/clipper.py <cid> <youtube url> [--n 4] [--test] [--campaign KEY]

1 info      the laptop reads the video's title, chapters and YouTube's "most replayed" heatmap (yt-dlp -J; free crowd signal)
2 moments   Gemini watches the YouTube URL (no download) with the heatmap peaks, returns the best standalone moments
            (hook = who + action + twist, accurate; 30-45 s target, 58 s cap; start 1-3 s before the action)
3 clip      the laptop downloads once and builds each clip with engine/clipcore.py: whisper words, sentence-boundary cut,
            dead pauses removed, layout from faces (face crop / webcam-over-gameplay / blurred fill), pop captions, -14 LUFS
4 check     format + loudness + a vision check of the frame sheet against the transcript (hook honest, captions readable,
            nothing covers the face)
5 hand-off  each clip = its own job (plan.json, review.json, cover.jpg, done.json "made") -> Telegram for approval

PERMISSION GATE: clips are posted only from sources the page may use: channels/<cid>/sources.json (a paid clipping
campaign or a creator who allows clipping). Anything else runs only as a test (made, never posted)."""
import argparse, json, os, re, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, channel, telegram, note_problem
import llm

GENERIC_TAGS = ["fyp", "viral", "reels", "trending"]
PLUG = re.compile(r"\b(subscribe|subscribed|hit the bell|notification bell|sponsor(ed)? by|this video is sponsored|link in (the )?"
                  r"description|use (my )?code|discount code|merch|patreon|giveaway|smash (that )?like)\b", re.I)     # OpusClip 13.5M-clip study: niche + generic tags beat niche-only 2.5x

MOMENTS = """You are the best short-form clipper in the world. Watch this whole video and pick the {n} best moments to post
as standalone Reels / Shorts on the page "{page}" ({about}).
VIDEO: "{title}" by {creator}{chapters}
{heat}
A great moment:
- hooks in its FIRST 2 SECONDS: a bold claim, a shocking line, a laugh, a fight, a reveal, a question. Start 1-3 s before
  the action, never on dead air or an intro.
- makes sense with zero context, has ONE clear payoff, and ends right after it.
- LENGTH BY TYPE (19 Nov study of the top clip Shorts of the last 30 days, knowledge/clipping.md): a reaction, a shock
  or one funny moment = 15-25 s, ending ON the payoff so the loop restarts cleanly (MC Stan 13.6M at 19 s, Kohsa Edit
  12M at 22 s, Btalk Radar 17M at 15 s); a story, a stand-up bit or an argument = 30-55 s, only if every 5 s earns its
  place. Never pad: the shortest version that keeps the setup and the payoff wins. 12 s minimum, 58 s maximum.
- prefer reactions, quotable lines, conflict, surprises and "first time" moments over quiet stretches.
- NEVER the intro or outro, a "like and subscribe" / channel plug, a sponsor read, "link in the description", a giveaway
  or merch plug (19 Nov: the first pick was the intro with a Subscribe button). Don't start at 0:00 unless the very first
  line is itself the hook.
- moments must not overlap.
{rules}
HOOK TITLE (on screen from frame 1): who + action + twist, 3-7 words, in the video's language (Hinglish in Roman script
for Hindi), e.g. "DAD SMASHES SON'S CONSOLE, THEN REGRETS IT". It must be TRUE to what happens: no fake claims.
Write it the way a real fan would say it out loud: natural, grammatical, instantly clear, with curiosity or emotion.
Use real names spelled exactly as given. Never word salad (19 Nov rejects: "REBEL DENIES FALSE EQUALITY CLAIMS DREAM
POWER", "JO KOY ORDERS GET A DOG"; better: "SHE SAYS DREAMS CAN BEAT THE KING", "JO KOY'S CURE FOR THERAPY: GET A DOG").
CAPTION: the context the clip leaves out, naming the show / game / product and the person. Do NOT repeat required
campaign lines or tags (they are added after it).
NOTES (19 Nov, Instagram + YouTube originality rules: a clip page must ADD its own perspective, not only crop and
caption): 3 short on-screen notes in the page's voice, a witty fan watching along. One "context" note first (who /
what show or game / why this moment matters, with a fact the clip itself does not say) and 2 "react" notes, each tied
to the exact words it follows ("after": 3-6 words copied EXACTLY from the speech). Each note 3-8 words, says something
the viewer is thinking (a joke, an opinion, a "wait for it", a fact), NEVER repeats or describes what is being said,
never negative about the brand, show, game or person, never a lie, no emojis, no hashtags.
The CONTEXT note must name WHO (the person / show / game by name) plus one SPECIFIC fact: a year, a number, where it
aired, why it blew up ("Anjelah Johnson, 2007: this bit made her famous"). REACT notes are what a fan would type in
the comments at that exact second, about THAT exact thing (name it: "Not the free sanitizer 💀" is about the
moment; "This part never gets old" fits any clip, so it is banned) ("Bhai ye kya hai?" on MC Stan: 13.6M views; "her teary eyes say it all": 17M).
Good: "Cheaper than therapy, honestly" / "He did NOT see that coming" / "This scene took 9 months to film".
Bad: "Jo Koy talks about dogs" (describes) / "LOL" (empty) / "Worst show ever" (negative) / "The most famous part of
the set", "The pressure is real", "Iconic moment" (vague: says nothing a fan would say).
Return JSON:
{{"moments": [{{"start": "<MM:SS where the hook begins>", "end": "<MM:SS where the payoff ends>", "hook": "<hook title>",
   "why": "<why people will watch to the end, one line>",
   "score": {{"hook": <1-10>, "flow": <1-10>, "value": <1-10>, "trend": <1-10>}},
   "caption": "<Instagram caption: one or two short lines that add the context the clip leaves out, no hashtags>",
   "tags": ["<4-6 specific hashtags without # (people, game, topic)>"],
   "notes": [{{"after": "", "text": "<context note>", "kind": "context"}},
             {{"after": "<3-6 exact spoken words>", "text": "<react note>", "kind": "react"}},
             {{"after": "<3-6 exact spoken words>", "text": "<react note>", "kind": "react"}}]}}]}}"""

CHECK = """You check a finished vertical clip before it is posted on the clip page "{page}". The image is 6 frames sampled
across the clip, left to right (shrunk: judge the layout, not the font size).
The on-screen hook title is "{hook}". The full transcript of the clip: "{text}"
1) Is the hook TRUE to the transcript and the frames? (A short, punchy title is fine; only flag it if it claims something
   that does not happen.)
2) Look at the frames for real, clearly visible problems only: captions covering a face or mouth, a black or frozen frame,
   the main person cut out of the frame, a broken layout (a webcam box cut in half, two copies of the same person side by
   side), a watermark of another clip app, nudity, gore.
3) CHECKLIST (19 Nov: a stand-up clip showing the SAME comedian twice, top and bottom, scored 9): answer each, yes/no:
   a. Is the same person shown twice at once in two SHARP copies, top and bottom or side by side? (A heavily BLURRED
      enlarged copy of the frame behind the video is our intended background style: that is NOT a yes.)
   b. Is a caption word clearly misheard (nonsense next to the transcript, e.g. "CRYPTO JAIL" for "crystal gel")?
   c. Is any on-screen page note just describing what is said, vague ("iconic moment"), negative, or false?
   d. Is the picture blurry, very low resolution or pixelated for most of the clip?
   e. Is another account's big logo or watermark covering part of the picture?
Do not list guesses. Return JSON {{"score": <1-10 how good and postable>, "problems": ["<only clear, serious problems>"],
"minor": ["<small notes>"], "checklist": {{"a": true/false, "b": true/false, "c": true/false, "d": true/false, "e": true/false}}}}
Every checklist "true" must also be written in problems."""


def vision_check(prompt, img):
    """Gemini on our own keys first (the same as review.py), the OmniRoute vision combo second."""
    import base64, urllib.request, tts
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(img).decode()}},
                                    {"text": prompt + "\n\nReturn ONLY valid JSON."}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1, "maxOutputTokens": 1500}}
    for m in tts.usable(["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-3.5-flash-lite"]):
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                       data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(m)})
            d = json.load(urllib.request.urlopen(r, timeout=120))
            res = llm.parse_json(d["candidates"][0]["content"]["parts"][0]["text"])
            cl = res.get("checklist") if isinstance(res, dict) else None
            if isinstance(cl, dict):
                names = {"a": "same person shown twice", "b": "misheard caption", "c": "weak / vague / negative page note",
                         "d": "blurry or low-resolution picture", "e": "another account's watermark over the picture"}
                hits = [names.get(k, k) for k, v in cl.items() if v is True]
                if hits:
                    res.setdefault("problems", []).extend(f"checklist: {h}" for h in hits if f"checklist: {h}" not in res.get("problems", []))
                    res["score"] = min(int(res.get("score") or 10), 5)
            return res
        except Exception as e:
            log("clipper: vision", m, "failed", str(e)[:100])
    return llm.vision(prompt, img)


def ts(x):
    if isinstance(x, (int, float)):
        return float(x)
    parts = [float(p) for p in re.findall(r"\d+(?:\.\d+)?", str(x))][-3:]
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def permitted(cid, url, campaign=None):
    src = load(os.path.join(ROOT, "channels", cid, "sources.json"), {}) or {}
    for key, s in (src.get("sources") or {}).items():
        if campaign and key != campaign:
            continue
        if not s.get("active", True):
            continue
        if any(p and p.lower() in url.lower() for p in s.get("match") or []) or (campaign and key == campaign):
            return dict(s, key=key)
    return None


def heat_peaks(info, k=6):
    """The 'most replayed' peaks: local maxima of YouTube's 100-point curve, skipping the opening 3% (always high)."""
    hm = [h for h in (info or {}).get("heatmap") or [] if isinstance(h, dict)]
    if len(hm) < 10:
        return []
    dur = float(info.get("duration") or hm[-1].get("end_time") or 0)
    pts = [(float(h["start_time"]), float(h["end_time"]), float(h.get("value") or 0)) for h in hm]
    peaks = [p for i, p in enumerate(pts) if 0 < i < len(pts) - 1 and p[2] >= pts[i - 1][2] and p[2] >= pts[i + 1][2]
             and p[0] > 0.03 * dur]
    peaks.sort(key=lambda p: -p[2])
    out = []
    for p in peaks:
        if all(abs(p[0] - q[0]) > 45 for q in out):
            out.append(p)
        if len(out) >= k:
            break
    return [{"at": round(p[0]), "until": round(p[1]), "replay": round(p[2], 2)} for p in sorted(out)]


def what_worked(cid, k=5):
    """19 Nov learning loop: our posted clips with Instagram stats (engine/stats.py fills done.json "stats" daily), best and
    worst by views, with hook, layout, length and average watch time. Also written to channels/<cid>/results-clips.md."""
    rows = []
    for d in load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []:
        s = d.get("stats") or {}
        if d.get("status") != "posted" or s.get("views") is None:
            continue
        p = load(os.path.join(OUT, cid, d["job"], "plan.json"), {}) or {}
        q = (load(os.path.join(OUT, cid, d["job"], "qc.json"), {}) or {}).get("format") or {}
        c = p.get("clip") or {}
        rows.append({"hook": d.get("title"), "views": s.get("views") or 0, "watch": s.get("avg_watch") or s.get("ig_reels_avg_watch_time"),
                     "shares": s.get("shares"), "layout": c.get("layout"), "dur": q.get("dur"), "creator": c.get("creator"),
                     "replayed": c.get("replayed")})
    if len(rows) < 3:
        return ""
    rows.sort(key=lambda r: -r["views"])
    f = lambda r: (f"- {r['views']:,} views | hook \"{r['hook']}\" | {r['layout']} | {r['dur']} s | watch {r['watch']} | "
                   f"shares {r['shares']} | {r['creator']}{' | was most-replayed' if r['replayed'] else ''}")
    best, worst = rows[:k], rows[-3:] if len(rows) > k + 2 else []
    txt = "BEST:\n" + "\n".join(map(f, best)) + ("\nWORST:\n" + "\n".join(map(f, worst)) if worst else "")
    try:
        open(os.path.join(ROOT, "channels", cid, "results-clips.md"), "w", encoding="utf-8").write(
            f"# Cut Capsule clip results ({time.strftime('%Y-%m-%d')}, {len(rows)} posted clips with stats)\n\n" + txt + "\n")
    except OSError:
        pass
    return txt


def mmss(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


_COMMON = set("""the and for with this that from your you our are was were will have has not but all any can new one out
post posts clip clips caption captions video videos must only use used never every each more most best top show shows
official trailer trailers content folder brief rules campaign campaigns views view budget platform tiktok instagram
youtube shorts reels facebook twitter keep make made add like follow watch link links free trial season launch date
english example examples note genuine true write what when where how why who which they them their there then than
read full minimum maximum length seconds audience requirement required allowed background music voice voices""".split())


def glossary(src):
    """Names to spell right in subtitles and captions: the source's "names" (whopbot reads them from the brief) plus
    capitalised words of the title + brief that never appear in lower case there (so they are names, not words)."""
    if not src:
        return []
    names = [str(x) for x in src.get("names") or []]
    text = (src.get("title") or "") + "\n" + (src.get("brief") or "")[:6000]
    low = set(re.findall(r"\b[a-z][a-z']{3,}\b", text))
    for w in re.findall(r"\b[A-Z][a-zA-Z']{3,}\b", text):
        if w.lower() not in low and w.lower() not in _COMMON and not w.isupper():
            names.append(w)
    return list(dict.fromkeys(names))[:40]


def campaign_guide(src):
    if not src:
        return ""
    b = src.get("brief") or ""
    i = b.find("Back\n")
    names = glossary(src)
    return (f"\nCAMPAIGN: {src.get('title')}. Use only facts from it; the caption names the show / game / product."
            + (f"\nNAMES (spell exactly): {', '.join(names)}" if names else "")
            + (f"\nBRIEF (excerpt):\n{b[max(0, i):max(0, i) + 1800]}" if b else "") + "\n")


def find_moments(ch, url, n, info, source=None):
    rules = ""
    if source:
        rules = (campaign_guide(source) + "CAMPAIGN RULES (every clip must follow them):\n- "
                 + "\n- ".join(source.get("rules") or []) + "\n")
    rules += "- " + "\n- ".join((ch.get("clip") or {}).get("rules") or [])
    learned = what_worked(ch["id"])
    if learned:
        rules += "\nWHAT WORKED ON OUR PAGE (real views; pick moments and hooks like the winners, avoid the losers):\n" + learned
    pk = heat_peaks(info)
    heat = ("MOST REPLAYED by viewers (YouTube's own heatmap, strongest crowd signal; look here first, the moment usually "
            "starts 5-20 s before the peak): " + ", ".join(f"{mmss(p['at'])} ({p['replay']})" for p in pk)) if pk else ""
    chap = info.get("chapters") or []
    chapters = ("\nCHAPTERS: " + "; ".join(f"{mmss(c.get('start_time', 0))} {c.get('title', '')}" for c in chap[:20])) if chap else ""
    p = MOMENTS.format(n=n + 2, page=ch.get("name", ch["id"]), about=ch.get("format", ""), rules=rules, heat=heat,
                       title=info.get("title") or "?", creator=info.get("channel") or info.get("uploader") or "?", chapters=chapters)
    d = llm.watch(url, p, max_tokens=5000)
    ms = []
    for m in d.get("moments") or []:
        try:
            a, b = ts(m["start"]), ts(m["end"])
        except Exception:
            continue
        if b - a < 12:                    # 19 Nov: was "< 20 -> 32 s", which stretched every short reaction moment
            b = a + 15
        if b - a > 60:
            b = a + 55
        if any(not (b <= x["a"] or a >= x["b"]) for x in ms):
            continue
        sc = m.get("score") if isinstance(m.get("score"), dict) else {"hook": m.get("score") or 5}
        total = round(sum(float(sc.get(k) or 0) for k in ("hook", "flow", "value", "trend")) / max(1, len(sc)), 2)
        hits = [x["replay"] for x in pk if x["at"] - 25 <= b and a <= x["until"] + 5]
        near = bool(hits)
        top = max([x["replay"] for x in pk] or [1]) or 1
        ms.append({"a": a, "b": b, "hook": str(m.get("hook") or "")[:70], "why": str(m.get("why") or "")[:200], "score": total,
                   "scores": sc, "replayed": near, "heat": round(max(hits or [0]) / top, 2), "caption": str(m.get("caption") or "")[:300],
                   "tags": [re.sub(r"[^\w]", "", str(t)) for t in (m.get("tags") or [])][:6], "notes": _notes(m)})
    # a replayed moment gets a bonus by HOW replayed (19 Nov: a 0.91 peak lost to 0.27 ones, the flat +1 treated them alike)
    ms.sort(key=lambda m: -(m["score"] + 2.0 * m.get("heat", 0)))
    log("clipper: proposed", [(mmss(m["a"]), m["score"], m.get("heat")) for m in ms])
    return ms[:n], pk


MOMENTS_TEXT = """You are the best short-form clipper in the world. Below is the timed transcript of "{title}" (each line starts
with its time in seconds). Pick the {n} best moments to post as standalone Reels / Shorts on the page "{page}" ({about}).
{guide}
TRANSCRIPT:
{lines}
Return JSON {{"moments": [{{"start": <seconds where the hook line begins>, "end": <seconds where the payoff ends>, "hook": "<hook title>",
 "why": "<one line>", "score": {{"hook": <1-10>, "flow": <1-10>, "value": <1-10>, "trend": <1-10>}},
 "caption": "<one or two short lines adding the missing context, no hashtags>", "tags": ["<4-6 hashtags without #>"],
 "notes": [{{"after": "", "text": "<context note>", "kind": "context"}},
           {{"after": "<3-6 words copied exactly from the transcript>", "text": "<react note>", "kind": "react"}},
           {{"after": "<3-6 words copied exactly from the transcript>", "text": "<react note>", "kind": "react"}}]}}]}}"""


NOTES_ONLY = """You write the on-screen notes for ONE clip on the clip page "{page}" ({about}).
CLIP hook title: "{hook}". Why it works: {why}
{guide}
VIDEO FACTS (the ONLY facts you may state; never a name, show, special, year or number from memory: 19 Nov a model
wrote "Ali Wong, Baby Cobra 2016" on a Jo Koy clip):
{facts}
EXACT TRANSCRIPT of the clip (what is said, in order):
"{text}"
Write 3 notes: 1 "context" (who / which show or game by name + one specific fact the clip does not say, both taken
from VIDEO FACTS or the transcript; "after": "")
and 2 "react" notes, each placed right after DIFFERENT words: "after" = 3-6 words copied EXACTLY from the transcript
above, in order, and the two react notes must follow different parts (one early-middle, one near the payoff).
Each note 3-9 words, in the clip's language (Hinglish in Roman script for Hindi), no emojis, no hashtags.
Return JSON {{"notes": [{{"after": "", "text": "...", "kind": "context"}}, {{"after": "...", "text": "...", "kind": "react"}},
 {{"after": "...", "text": "...", "kind": "react"}}]}}"""


def video_facts(info):
    """What a context note may say: the video's own title, channel, upload date, chapters and description."""
    info = info or {}
    ud = str(info.get("upload_date") or "")
    out = [f"Title: {info.get('title') or '?'}", f"Channel: {info.get('channel') or info.get('uploader') or '?'}"]
    if len(ud) == 8:
        out.append(f"Uploaded to YouTube: {ud[:4]}-{ud[4:6]}-{ud[6:]} (the show itself may be older: say 'posted {ud[:4]}', "
                   "never 'filmed' or 'aired' in that year unless the description says so)")
    if info.get("view_count"):
        v = int(info["view_count"])
        out.append(f"YouTube views: {v:,} ({v / 1e6:.1f}M)" if v >= 1e6 else f"YouTube views: {v:,} ({v / 1e3:.0f}K)")
    chap = "; ".join(str(c.get("title", "")) for c in (info.get("chapters") or [])[:12])
    if chap:
        out.append("Chapters: " + chap)
    desc = re.sub(r"https?://\S+", "", str(info.get("description") or ""))
    desc = re.sub(r"\n{2,}", "\n", desc).strip()[:900]
    if desc:
        out.append("Description: " + desc)
    return "\n".join(out)
COMMON = set("""a an the this that these those his her he she him they them their its it i me my we our you your who what
when where why how and or but so if then than not no yes is are was were be been being has have had do does did will
would can could should just only even still also very too more most less least all any every some each one two three
first last next new old big little wait watch look see when bro bhai yaar ye wo kya hai mom dad mother father brother
sister wife husband son daughter friend kid kids family home school lunch man woman guy girl boy people crowd audience
nobody everyone somebody best worst funny classic legend legendary story bit joke set special show clip moment part
real true honestly literally actually never always nothing everything here there now today ok okay oh""".split())
def ungrounded(note, known):
    """The first name or number in a context note that the video facts / transcript never mention ('' = grounded)."""
    k = known.lower()
    for w in re.findall(r"\d[\d,.]*|[A-Z][\w'’&.-]+", note):
        lw = w.lower().strip("'’.,-")
        if not lw or lw in COMMON or lw.rstrip("s") in COMMON:
            continue
        if re.fullmatch(r"\d[\d,.]*", lw):
            if lw.replace(",", "") not in k.replace(",", ""):
                return w
        elif lw.rstrip("'’s") not in k and lw not in k:
            return w
    return ""
def exact_notes(ch, src, url, vid_id, ms, label, info=None):
    """19 Nov: on the YouTube path the moment-picker WATCHES the video and cannot quote the speech exactly (3 notes on
    the same anchor, 1 of 3 placed). Ask the laptop for the exact words of each moment (no render), then write the
    notes from them. Keeps the old notes when anything fails. The context note may only use names / numbers that the
    video facts or the transcript contain (ungrounded() checks it in code)."""
    import laptop
    try:
        out = laptop.job({"kind": "clip", "url": url, "id": vid_id, "pad": 4, "words_only": True, "glossary": glossary(src),
                          **_lang_spec(ch), "clips": [{"a": m["a"], "b": m["b"]} for m in ms]}, f"{ch['id']} {label} words", wait=1800)
    except Exception as e:
        log("clipper: exact words failed, keeping the first notes", str(e)[:150]); return ms
    guide = MOMENTS.split("NOTES (19 Nov")[1].split("Return JSON")[0]
    for i, m in enumerate(ms):
        r = load(os.path.join(out, f"c{i}", "result.json"), {}) or {}
        text = " ".join(w[2] for w in r.get("words") or [])
        if len(text.split()) < 8:
            continue
        facts = video_facts(info)
        ask = NOTES_ONLY.format(page=ch.get("name", ch["id"]), about=ch.get("format", "")[:200], hook=m["hook"],
                                why=m.get("why", ""), guide=guide + campaign_guide(src), facts=facts, text=text[:2500])
        known = facts + " " + text + " " + campaign_guide(src)
        try:
            for tries in range(2):
                d = llm.text(ask, json_mode=True, max_tokens=700)
                new = _notes({"notes": (d or {}).get("notes")})
                bad = [(n["text"], w) for n in new if n.get("kind") == "context" for w in [ungrounded(n["text"], known)] if w]
                if not bad:
                    break
                log("clipper: context note not in the video facts, asking again" if not tries else
                    "clipper: context note still not in the video facts, dropped", bad)
                ask += (f"\nYOUR LAST CONTEXT NOTE \"{bad[0][0]}\" used {bad[0][1]}, which is NOT in VIDEO FACTS or the "
                        "transcript. Use only names and numbers that appear there.")
                if tries:
                    new = [n for n in new if n.get("kind") != "context"]
            if len(new) >= 2:
                for n in new:
                    n["grounded"] = True              # checked against facts + transcript above
                m["notes"] = new
        except Exception as e:
            log("clipper: notes from words failed", str(e)[:120])
    shutil.rmtree(os.path.dirname(out), ignore_errors=True)
    log("clipper: exact-word notes", [[n["text"] for n in m.get("notes") or []] for m in ms])
    return ms


def _lang_spec(ch):
    """Clip job language: a Hindi page transcribes in Hindi and writes Roman Hinglish (channel.json clip.whisper_prompt)."""
    c = ch.get("clip") or {}
    out = {}
    if c.get("lang"):
        out["lang"] = c["lang"]
    if c.get("whisper_prompt"):
        out["wprompt"] = c["whisper_prompt"]
    return out


VAGUE = re.compile(r"\b(iconic|legendary|famous part|best part|classic moment|the moment|pressure is real|so relatable|"
                   r"this is (it|gold)|must watch|amazing|incredible|never gets old|is unmatched|the sass|so true|"
                   r"we all know|can'?t stop laughing|too funny)\b", re.I)


def _notes(m):
    """19 Nov test: 'The most famous part of the set' got through. A context note needs a real name (a capitalised word
    after the first one) or a number; a vague phrase anywhere drops the note."""
    out = []
    for n in (m.get("notes") or [])[:4]:
        if isinstance(n, dict) and str(n.get("text") or "").strip():
            t = str(n["text"])
            if VAGUE.search(t):
                continue
            if n.get("kind") == "context" and not (re.search(r"\d", t) or re.search(r"\s[A-Z][a-z]", t)):
                continue
            out.append({"after": str(n.get("after") or "")[:80], "text": re.sub(r"[#\U0001F000-\U0001FFFF]", "", str(n["text"])).strip()[:80],
                        "kind": "context" if n.get("kind") == "context" else "react"})
    return out


def find_moments_text(ch, item, n, source=None):
    """19 Nov: moments from a whisper transcript (Drive / non-YouTube footage Gemini cannot watch by URL)."""
    guide = MOMENTS.split("A great moment:")[1].split("Return JSON")[0]
    rules = ""
    if source:
        rules = (campaign_guide(source) + "CAMPAIGN RULES (every clip must follow them):\n- "
                 + "\n- ".join(source.get("rules") or []) + "\n")
    rules += "- " + "\n- ".join((ch.get("clip") or {}).get("rules") or [])
    learned = what_worked(ch["id"])
    guide = guide.replace("{rules}", rules + (("\nWHAT WORKED ON OUR PAGE:\n" + learned) if learned else ""))
    lines = "\n".join(f"{t} {s}" for t, s in item.get("lines") or [])
    if len(lines) > 60000:                              # very long footage: the model reads the first ~60K characters
        lines = lines[:60000]
    d = llm.text(MOMENTS_TEXT.format(title=item.get("name", "video"), n=n + 2, page=ch.get("name", ch["id"]), about=ch.get("format", ""),
                                     guide=guide, lines=lines), json_mode=True, max_tokens=5000)
    ms = []
    for m in d.get("moments") or []:
        try:
            a, b = float(m["start"]), float(m["end"])
        except Exception:
            continue
        b = a + 15 if b - a < 12 else (a + 55 if b - a > 60 else b)
        if any(not (b <= x["a"] or a >= x["b"]) for x in ms):
            continue
        sc = m.get("score") if isinstance(m.get("score"), dict) else {"hook": m.get("score") or 5}
        ms.append({"a": a, "b": b, "hook": str(m.get("hook") or "")[:70], "why": str(m.get("why") or "")[:200],
                   "score": round(sum(float(sc.get(k) or 0) for k in ("hook", "flow", "value", "trend")) / max(1, len(sc)), 2),
                   "scores": sc, "replayed": False, "caption": str(m.get("caption") or "")[:300],
                   "tags": [re.sub(r"[^\w]", "", str(t)) for t in (m.get("tags") or [])][:6], "notes": _notes(m)})
    ms.sort(key=lambda m: -m["score"])
    return ms[:n]


def make_files(cid, url, n=4, test=False, campaign=None):
    """Non-YouTube footage (a Drive file or folder): transcribe on the laptop, pick moments from the text, clip each file."""
    import laptop
    ch = channel(cid)
    src = permitted(cid, url, campaign)
    test = test or not src
    base = time.strftime("%m%d-%H%M")
    log("clipper (files):", cid, url, "test" if test else f"source {src['key']}")
    d = laptop.job({"kind": "transcribe", "url": url, "max_files": 6}, f"{cid} {base} transcribe", wait=7200)
    items = (load(os.path.join(d, "transcript.json"), {}) or {}).get("items") or []
    shutil.rmtree(os.path.dirname(d), ignore_errors=True)
    made = []
    per = max(1, n // max(1, len(items))) if len(items) > 1 else n
    for k, it in enumerate(items):
        if len(it.get("lines") or []) < 5:
            log("clipper (files): almost no speech in", it.get("name")); continue
        ms = find_moments_text(ch, it, per, src)
        if not ms:
            continue
        b2 = f"{base}{chr(97 + k)}"
        os.makedirs(os.path.join(OUT, cid, "sources", b2), exist_ok=True)
        save(os.path.join(OUT, cid, "sources", b2, "moments.json"), {"url": url, "file": it.get("name"), "moments": ms, "source": src, "test": test})
        log("clipper (files): moments", it.get("name"), [(round(m["a"]), round(m["b"]), m["hook"], m["score"]) for m in ms])
        brand = "" if (src or {}).get("no_watermark") else (ch.get("handle") or "")
        out = laptop.job({"kind": "clip", "url": url, "id": it["id"], "pad": 4, "brand": brand, "glossary": glossary(src), **_lang_spec(ch),
                          "clips": [{"a": m["a"], "b": m["b"], "hook": m["hook"], "notes": m.get("notes") or []} for m in ms]}, f"{cid} {b2}", wait=3600)
        info = {"title": it.get("name"), "channel": (src or {}).get("title") or "", "webpage_url": url}
        made += ingest(ch, cid, url, info, src, test, ms, out, b2)
        shutil.rmtree(os.path.dirname(out), ignore_errors=True)
    return made


def is_youtube(url):
    return bool(re.search(r"(youtube\.com/(watch|live|shorts)|youtu\.be/)", url or ""))


def vision(ch, jd, hook, text):
    try:
        import base64
        img = open(os.path.join(jd, "sheet.jpg"), "rb").read()
        return vision_check(CHECK.format(page=ch.get("name", ch["id"]), hook=hook, text=text[:2500]), img)
    except Exception as e:
        log("clipper: vision check failed", str(e)[:120])
        return {"score": None, "problems": [], "minor": ["vision check unavailable"]}


def make(cid, url, n=4, test=False, campaign=None):
    ch = channel(cid)
    if not ch:
        raise SystemExit(f"no page {cid}")
    if not is_youtube(url):                       # Drive / other footage: transcript path
        return make_files(cid, url, n, test, campaign)
    src = permitted(cid, url, campaign)
    if not src and not test:
        log(f"{cid}: {url} is not in channels/{cid}/sources.json (no campaign / creator permission): TEST only, never posted")
        test = True
    base = time.strftime("%m%d-%H%M")
    sdir = os.path.join(OUT, cid, "sources", base)
    os.makedirs(sdir, exist_ok=True)
    log("clipper:", cid, url, "n", n, "test" if test else f"source {src['key']}")
    import laptop
    try:
        info = laptop.info(url, f"{cid} {base}")
    except Exception as e:
        log("clipper: no video info (", str(e)[:120], ")"); info = {}
    ms, pk = find_moments(ch, url, n, info, src)
    save(os.path.join(sdir, "moments.json"), {"url": url, "info": {k: v for k, v in info.items() if k != "heatmap"}, "peaks": pk,
                                              "moments": ms, "source": src, "test": test})
    if not ms:
        raise RuntimeError("no moments found")
    log("clipper: replay peaks", [(mmss(p["at"]), p["replay"]) for p in pk])
    log("clipper: moments", [(mmss(m["a"]), mmss(m["b"]), m["hook"], m["score"], "replayed" if m["replayed"] else "") for m in ms])
    brand = "" if (src or {}).get("no_watermark") else (ch.get("handle") or "")    # campaigns that say "no watermark"
    if ch.get("kind") == "clips":
        ms = exact_notes(ch, src, url, info.get("id"), ms, base, info)
        # every path (also when the exact-words pass failed): a context note naming something the video facts do not hold
        # is dropped (the react notes stay; fewer than 2 notes -> the clip is held later)
        vf = video_facts(info) + " " + campaign_guide(src)
        for m in ms:
            keep = [n for n in m.get("notes") or [] if n.get("kind") != "context" or n.get("grounded")
                    or not ungrounded(n["text"], vf + " " + m.get("why", ""))]
            if len(keep) < len(m.get("notes") or []):
                log("clipper: ungrounded context note dropped", [n["text"] for n in m["notes"] if n not in keep])
            m["notes"] = keep
    out = laptop.job({"kind": "clip", "url": url, "id": info.get("id"), "pad": 4, "brand": brand, "glossary": glossary(src), **_lang_spec(ch),
                      "clips": [{"a": m["a"], "b": m["b"], "hook": m["hook"], "notes": m.get("notes") or []} for m in ms]}, f"{cid} {base}", wait=3600)
    made = ingest(ch, cid, url, info, src, test, ms, out, base)
    shutil.rmtree(os.path.dirname(out), ignore_errors=True)
    if test and made:
        telegram(f"✂️ {cid} TEST clips from {url} (not for posting, no permission entry): "
                 + ", ".join(f"{j} ({lay}, {sc}/10)" for j, _, _, lay, sc in made))
    return made


def ingest(ch, cid, url, info, src, test, ms, out, base, only=None):
    """Turn what the laptop sent back (out/c0, c1 ...) into jobs: checks, plan, review, done.json, Telegram."""
    done_p = os.path.join(ROOT, "channels", cid, "done.json")
    made = []
    who = info.get("channel") or info.get("uploader") or ""
    for i, m in enumerate(ms):
        if only is not None and i not in only:
            continue
        cd = os.path.join(out, f"c{i}")
        res = load(os.path.join(cd, "result.json"), {}) or {}
        if res.get("error") or not os.path.exists(os.path.join(cd, "final.mp4")):
            log("clipper: clip", i + 1, "failed on the laptop:", res.get("error", "no file")[:200]); continue
        jid = f"{base}-c{i + 1}"
        jd = os.path.join(OUT, cid, jid)
        os.makedirs(jd, exist_ok=True)
        mp4 = os.path.join(jd, f"{cid}-{jid}.mp4")
        shutil.move(os.path.join(cd, "final.mp4"), mp4)
        for f in ("cover.jpg", "sheet.jpg", "clip.json", "captions.ass"):
            if os.path.exists(os.path.join(cd, f)):
                shutil.move(os.path.join(cd, f), os.path.join(jd, f))
        q = res.get("format") or {}
        probs = []
        if not (12 <= (q.get("dur") or 0) <= 60):
            probs.append(f"length {q.get('dur')} s")
        if (q.get("w"), q.get("h")) != (1080, 1920):
            probs.append(f"size {q.get('w')}x{q.get('h')}")
        if not q.get("audio"):
            probs.append("no audio")
        if q.get("lufs") is not None and abs(q["lufs"] + 14) > 2:
            probs.append(f"loudness {q['lufs']} LUFS")
        if (res.get("words") or 0) < 12:
            probs.append("almost no speech (captions nearly empty)")
        if (res.get("lost") or 0) > 0.1:             # 19 Nov: vision scored 10 with the comedian walked out of the crop
            probs.append(f"speaker out of the crop for {res['lost']:.0%} of the time (crop did not follow him)")
        plug = PLUG.search(res.get("text", ""))
        if plug:
            probs.append(f"self-promotion inside the clip ('{plug.group(0)}'): someone else's channel plug, never post")
        # 19 Nov golden rule + originality (Instagram/YouTube stop recommending re-uploads without material edits):
        # every clip must carry at least 2 of our own notes, actually placed on screen
        placed = res.get("notes") or []
        if (ch.get("kind") == "clips") and len(placed) < 2:
            probs.append(f"not original enough: {len(placed)} of {res.get('notes_asked', 0)} page notes placed (need 2+)")
        v = vision(ch, jd, m["hook"], res.get("text", "") + ("\nPAGE NOTES SHOWN ON SCREEN (must be true to the clip, "
                   "never negative, never just repeating the speech): " + " | ".join(n["text"] for n in placed) if placed else ""))
        probs += [str(x)[:200] for x in v.get("problems") or []]
        credit = f"🎥 Credit: {who}" + (f" ({info.get('webpage_url') or url})" if (not src or src.get("credit_link", True)) else "")
        tags = list(dict.fromkeys([t for t in m["tags"] if t] + [t.lstrip("#") for t in (ch.get("hashtags_base") or [])]
                                  + GENERIC_TAGS))[:12]
        yt_title = m["hook"]
        if (src or {}).get("campaign_id"):
            # 19 Nov campaign briefs (CoD, SEGA): the disclosure (#Ad) must be the FIRST hashtag, on its own line right after
            # the caption, and at most 3 more hashtags. So: no hashtags inside the caption text, required lines next,
            # 3 topic tags, and no credit line (official footage, given to us to post).
            body = re.sub(r"\s*#\w+", "", m["caption"]).strip()
            # 19 Nov: the model wrote the required line ("Blue in the Face, on Netflix", "@callofduty") into the body and
            # caption_add added it again: drop every required line / tag from the body before appending them once
            for req in re.split(r"\n+", src.get("caption_add") or ""):
                req = req.strip()
                if req and not req.startswith("#"):
                    body = re.sub(r"\s*" + re.escape(req.rstrip(".")) + r"\.?", "", body, flags=re.I).strip()
            for tag in re.findall(r"@[\w.]+", src.get("caption_add") or ""):
                body = re.sub(r"\s*" + re.escape(tag) + r"\b", "", body, flags=re.I).strip()
            body = re.sub(r"\s{2,}", " ", body).strip(" ,")
            caption = "\n".join(x for x in [body, src.get("caption_add") or ""] if x)
            yt_title = body if 12 <= len(body) <= 95 else m["hook"]       # the caption sentence reads better on YouTube
            tags = [t for t in tags if t.lower() not in ("ad", "advertisement", "sponsored")][:3]
        else:
            caption = "\n\n".join(x for x in [m["caption"], (src or {}).get("caption_add") or "", credit] if x)
        start = round(res.get("offset", 0) + res["cut"][0], 2)
        plan = {"title": m["hook"], "topic": m["hook"], "caption": caption, "hashtags": ["#" + t for t in tags], "lang": res.get("lang", ""),
                "clip": {"url": url, "start": start, "end": round(res.get("offset", 0) + res["cut"][1], 2), "layout": res.get("layout"),
                         "removed_s": res.get("removed_s"), "why": m["why"], "scores": m["scores"], "replayed": m["replayed"],
                         "notes": res.get("notes") or [],
                         "source": (src or {}).get("key"), "test": test, "creator": who},
                "seo": {"ig": {"caption": caption, "hashtags": ["#" + t for t in tags]},
                        "fb": {"caption": caption, "hashtags": ["#" + t for t in tags]},
                        "yt": {"title": yt_title[:90], "description": caption, "tags": tags}},
                "scenes": []}
        save(os.path.join(jd, "plan.json"), plan)
        save(os.path.join(jd, "qc.json"), {"format": q, "ok": not probs})
        rv = {"ok": not probs and not test, "problems": probs + (["TEST: no clipping permission for this source, never post"] if test else []),
              "minor": [str(x)[:200] for x in v.get("minor") or []],
              "checks": {"format": q, "vision": {"score": v.get("score")}, "layout": res.get("layout")}}
        save(os.path.join(jd, "review.json"), rv)
        save(os.path.join(jd, "meta.json"), {"channel": cid, "job": jid, "topic": m["hook"], "stage": "done", "source_url": url,
                                             "kind": "clip", "test": test})
        done = load(done_p, []) or []
        if not any(d["job"] == jid for d in done):
            done.append({"job": jid, "topic": m["hook"], "title": m["hook"], "status": "held" if (probs or test) else "made",
                         "review": rv["problems"][:4], "clip": {"url": url, "start": start, "layout": res.get("layout")}})
            save(done_p, done)
        if probs:
            note_problem(cid, jid, probs, "clipper")
        made.append((jid, q, probs, res.get("layout"), v.get("score")))
        log("clipper: made", jid, res.get("layout"), q, "vision", v.get("score"), probs or "ok")
        if rv["ok"]:
            import send
            send.send(cid, jid)
    return made


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cid"); ap.add_argument("url")
    ap.add_argument("--n", type=int, default=4); ap.add_argument("--test", action="store_true"); ap.add_argument("--campaign")
    a = ap.parse_args()
    r = make(a.cid, a.url, a.n, a.test, a.campaign)
    print(json.dumps([{"job": j, "format": q, "problems": p, "layout": lay, "vision": sc} for j, q, p, lay, sc in r]))
