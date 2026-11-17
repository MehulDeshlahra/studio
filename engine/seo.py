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
no price/medical/political claims; no 'follow for follow'; hashtags only relevant ones (mix 2 big + 2-4 niche).
Return JSON {{"ig": {{"caption": "...", "hashtags": ["#..", ...4-6]}},
"fb": {{"caption": "...", "hashtags": ["#..", "#.."]}},
"yt": {{"title": "<=70 chars, main keyword first", "description": "3 short lines then a line of keywords", "tags": ["8-12 tags"], "hashtags": ["#..", "#..", "#.."]}},
"comment_q": "the one question to post as the first comment (<= 120 chars, answerable in one word)"}}"""


def _info(url):
    try:
        out = subprocess.run([research.YTDLP if os.path.exists(research.YTDLP) else "yt-dlp", "-j", "--no-warnings", "--skip-download", url],
                             capture_output=True, text=True, timeout=120).stdout
        return json.loads(out) if out.strip() else None
    except Exception:
        return None


def study(page):
    notes = (load(os.path.join(ROOT, "knowledge", "hooks.json"), {}) or {}).get(page, {}).get("notes", [])
    tags, hts, titles = {}, {}, []
    n = 0
    for x in notes[:12]:
        d = _info(x["url"])
        if not d:
            continue
        n += 1
        titles.append({"title": d.get("title"), "views": d.get("view_count")})
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
            r[k]["hashtags"] = [h if h.startswith("#") else "#" + h for h in (r[k].get("hashtags") or [])][:8]
    plan["seo"] = r
    if job_dir:
        save(os.path.join(job_dir, "plan.json"), plan)
    return r


def text_for(plan, platform, music_credit=None):
    """Final text for 'ig' / 'fb' / 'yt' (falls back to the plan's own caption + hashtags)."""
    s = (plan.get("seo") or {}).get(platform) or {}
    credits = [c for c in ([music_credit] if music_credit else []) + ["Video: " + c for c in plan.get("credits", [])] if c]
    tail = ("\n\n" + "\n".join(credits)) if credits else ""
    if platform == "yt" and s.get("title"):
        d = s.get("description", "") + "\n\n" + " ".join(s.get("hashtags", [])[:3]) + tail
        return {"title": s["title"][:90], "description": d.strip(), "tags": s.get("tags", [])[:12]}
    if s.get("caption"):
        return (s["caption"].strip() + "\n\n" + " ".join(s.get("hashtags", [])) + tail).strip()
    base = (plan.get("caption", "") + "\n\n" + " ".join(plan.get("hashtags", [])[:8])).strip()
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
