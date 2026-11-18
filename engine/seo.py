"""Captions, titles and hashtags per platform, checked against what the top Shorts in each niche actually use
(owner 17 Nov). Two parts:
  study(page)   weekly (after hookstudy): for the videos hookstudy watched, read their real title, description and tags with
                yt-dlp (no download), count hashtags/keywords, keep title patterns -> knowledge/seo.json
  make(cid, plan) at publish time: one planner call writes the three packages from the plan and that page's seo.json:
        ig  {caption, hashtags (4-6)}      first line = the hook, 1-2 short lines, a question, then tags
        fb  {caption}                      slightly longer, conversational, a question, 2-3 tags
        yt  {title (<= 70 chars, keyword first), description (3 lines + keywords), tags[], hashtags (3)}
      Saved into plan.json "seo" (so publish never asks twice). Falls back to the plan's own caption on any failure.
  python engine/seo.py study|make <page> [job]"""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log
import research

OUTF = os.path.join(ROOT, "knowledge", "seo.json")

MAKE = """You write the posting text for one faceless Short on the page "{name}" ({fmt}). Audience: Hindi-speaking India.
Video title: {title}
Voice-over (what the video says):
{vo}
Language of the video: {lang}.
WHAT THE TOP SHORTS IN THIS NICHE USE (from their real titles/descriptions/tags):
{seo}
Rules: the first 90 characters of every caption must make a stranger want to watch (curiosity, no spoilers, no clickbait lie);
one clear question at the end that is easy to answer in a comment; Roman script Hinglish unless the video is English;
ig and fb captions also carry ONE natural send line naming who to send it to (2026: Instagram ranks sends per reach above
comments), specific to this video, e.g. "Us dost ko bhejo jo phone 24 ghante charge pe rakhta hai" (never "share karo");
no price/medical/political claims; no 'follow for follow'; hashtags only relevant ones (mix 2 big + 2-4 niche).
Return JSON {{"ig": {{"caption": "...", "hashtags": ["#..", ...4-6]}},
"fb": {{"caption": "...", "hashtags": ["#..", "#.."]}},
"yt": {{"title": "<=70 chars, main keyword first", "description": "3 short lines then a line of keywords", "tags": ["8-12 tags"], "hashtags": ["#..", "#..", "#.."]}},
"comment_q": "the one question to post as the first comment (<= 120 chars, answerable in one word)"}}"""


def _info(url):
    """Title, description and tags of a Short. yt-dlp is blocked for single videos from this server ("confirm you are not
    a bot", 17 Nov) but the public /shorts/<id> page still carries them, so read that page directly."""
    import urllib.request
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
         "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1; SOCS=CAI"}
    try:
        t = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40).read().decode("utf8", "ignore")
    except Exception:
        return None
    m = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', t)
    k = re.search(r'"keywords":\[(.*?)\]', t)
    ti = re.search(r'<meta property="og:title" content="([^"]*)"', t)
    if not (m or k or ti):
        return None
    try:
        desc = json.loads('"' + m.group(1) + '"') if m else ""
    except Exception:
        desc = ""
    import html as _h
    return {"title": _h.unescape(ti.group(1)) if ti else "", "description": desc, "view_count": None,
            "tags": [x.strip().strip('"') for x in (k.group(1).split('","') if k else [])]}


def study(page):
    notes = [x for x in (load(os.path.join(ROOT, "knowledge", "hooks.json"), {}) or {}).get(page, {}).get("notes", []) if x.get("on_niche") is not False]
    tags, hts, titles = {}, {}, []
    n = 0
    for x in notes[:12]:
        d = _info(x["url"])
        if not d:
            continue
        n += 1
        titles.append({"title": d.get("title"), "views": x.get("views")})
        for t in d.get("tags") or []:
            tags[t.lower()] = tags.get(t.lower(), 0) + 1
        for h in re.findall(r"#\w+", (d.get("description") or "") + " " + (d.get("title") or "")):
            hts[h.lower()] = hts.get(h.lower(), 0) + 1
    if n < 3:
        log("seo study: too few videos for", page, n); return
    r = research.llm.text("Titles of the most-viewed Shorts in our niche (with views): " + json.dumps(titles, ensure_ascii=False)
                          + ". Write the title patterns that win (length, first words, numbers, question vs statement, emoji use, language mix). "
                          'JSON {"title_patterns": ["5-7 concrete rules"], "avoid": ["3 things"]}', json_mode=True)
    data = load(OUTF, {}) or {}
    data[page] = {"day": time.strftime("%Y-%m-%d"), "videos": n,
                  "hashtags": sorted(hts, key=lambda k: -hts[k])[:15], "tags": sorted(tags, key=lambda k: -tags[k])[:20],
                  "title_patterns": (r or {}).get("title_patterns", []), "avoid": (r or {}).get("avoid", []), "titles": titles[:8]}
    save(OUTF, data)
    log("seo study", page, n, "videos, top hashtags:", " ".join(data[page]["hashtags"][:6]))


def _seo_text(page):
    d = (load(OUTF, {}) or {}).get(page)
    if not d:
        return "no study yet: use common sense for Hindi Shorts (hook first, one question, 4-6 relevant hashtags)"
    return ("Top hashtags: " + " ".join(d["hashtags"][:12]) + "\nTop tags: " + ", ".join(d["tags"][:15]) + "\nTitle patterns: "
            + "; ".join(d["title_patterns"]) + "\nAvoid: " + "; ".join(d["avoid"]) + "\nExample titles: " + " | ".join(t["title"] for t in d["titles"][:5] if t.get("title")))


def make(cid, plan, job_dir=None):
    if plan.get("seo", {}).get("ig"):
        return plan["seo"]
    import plan as planner
    from core import channel
    ch = channel(cid)
    vo = " ".join(s.get("vo", "") for s in plan.get("scenes", []))[:1400]
    r = planner.ask(MAKE.format(name=ch.get("name", cid), fmt=ch.get("format", ""), title=plan.get("title", ""), vo=vo,
                                lang="English" if plan.get("lang") == "en" else "Hinglish", seo=_seo_text(cid)), max_tokens=2500) or {}
    if not isinstance(r, dict) or not (r.get("ig") or {}).get("caption"):
        log("seo: planner gave nothing for", cid); return {}
    for k in ("ig", "fb"):
        if isinstance(r.get(k), dict):
            r[k]["hashtags"] = [h if h.startswith("#") else "#" + h for h in (r[k].get("hashtags") or [])][:12]
            r[k]["hashtags"] = clamp_tags(r[k]["hashtags"])
    plan["seo"] = r
    if job_dir:
        save(os.path.join(job_dir, "plan.json"), plan)
    return r


GENERIC = {"#viral", "#trending", "#reels", "#reel", "#fyp", "#foryou", "#foryoupage", "#explore", "#instagood", "#instareels",
           "#explorepage", "#trend", "#shorts", "#follow", "#like", "#love"}


def clamp_tags(tags, n=5):
    """19 Nov: Instagram allows at most 5 hashtags per post (announced Dec 2025; source in knowledge/build-queue.md) and
    ranks Reels by topic. Keep the first n specific tags, drop broad reach tags, no duplicates."""
    out, seen = [], set()
    for h in tags or []:
        h = h if str(h).startswith("#") else "#" + str(h)
        k = h.lower()
        if k in GENERIC or k in seen or len(h) < 3:
            continue
        seen.add(k)
        out.append(h)
    return out[:n]


def text_for(plan, platform, music_credit=None, cid=None):
    """Final text for 'ig' / 'fb' / 'yt' (falls back to the plan's own caption + hashtags).
    18 Nov: with cid, ig/fb get the channel's comment-to-DM line (engine/dm.py cta) before the hashtags."""
    s = (plan.get("seo") or {}).get(platform) or {}
    line = ""
    if cid and platform in ("ig", "fb"):
        try:
            import dm, offers
            line = offers.caption_line(plan) if (plan.get("offer") or {}).get("url") else dm.cta(cid)   # 19 Nov: offer reels
        except Exception:
            line = ""
    if line:
        if s.get("caption"):
            s = dict(s, caption=s["caption"].strip() + "\n\n" + line)
        else:
            plan = dict(plan, caption=(plan.get("caption", "").strip() + "\n\n" + line).strip())
    credits = [c for c in ([music_credit] if music_credit else []) + ["Video: " + c for c in plan.get("credits", [])] if c]
    # 18 Nov: a fixed line from channel.json "caption_footer" on every platform (Finance Fuel: the not-advice line that
    # SEBI's finfluencer rules expect), never left to the model
    foot = ""
    if cid:
        try:
            from core import ROOT as _R, load as _ld
            foot = str((_ld(os.path.join(_R, "channels", cid, "channel.json"), {}) or {}).get("caption_footer") or "").strip()
        except Exception:
            foot = ""
    if foot:
        credits = [foot] + credits
    tail = ("\n\n" + "\n".join(credits)) if credits else ""
    if platform == "yt" and s.get("title"):
        d = s.get("description", "") + "\n\n" + " ".join(s.get("hashtags", [])[:3]) + tail
        return {"title": s["title"][:90], "description": d.strip(), "tags": s.get("tags", [])[:12]}
    if s.get("caption"):
        tags = s.get("hashtags", [])
        return (s["caption"].strip() + "\n\n" + " ".join(clamp_tags(tags) if platform in ("ig", "fb") else tags) + tail).strip()
    base = (plan.get("caption", "") + "\n\n" + " ".join(clamp_tags(plan.get("hashtags", [])) if platform in ("ig", "fb") else plan.get("hashtags", [])[:8]) + tail).strip()   # 18 Nov: + footer/credits
    if platform == "yt":
        return {"title": plan.get("title", "")[:90], "description": base, "tags": []}
    return base


if __name__ == "__main__":
    cmd, page = sys.argv[1], sys.argv[2]
    if cmd == "study":
        study(page)
    else:
        jd = os.path.join(OUT, page, sys.argv[3]); p = load(os.path.join(jd, "plan.json"))
        print(json.dumps(make(page, p, jd), ensure_ascii=False, indent=1))
