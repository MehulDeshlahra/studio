"""Pick the best of 10 ideas before a video is made (owner, 17 Nov; idea from a creator who runs 8 pages: "it picks 1 idea
out of every 10"). Free: 1 planner call (Gemini free key) + YouTube search listings (yt-dlp), no paid API.
  1. Candidates: unused backlog topics + fresh ideas from the planner (told what is trending, what we did, what worked).
  2. Demand: for each idea, YouTube Shorts search -> median views of the top 5 results (what people already watch).
  3. Score = demand (log scale, 0-10) x 0.45 + fit (planner, 0-10) x 0.35 + freshness (not like our past videos) x 0.20.
  4. The top idea wins; all 10 with scores are saved to channels/<id>/ideas.json (the dashboard shows them).
  python engine/ideas.py <channel>          (prints the ranking, does not make a video)"""
import json, math, os, re, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, read

N = 10


def _words(s):
    return set(re.findall(r"[a-z0-9]{3,}", s.lower()))


def freshness(idea, done_topics):
    if not done_topics:
        return 10.0
    best = max(max(SequenceMatcher(None, idea.lower(), d.lower()).ratio(),
                   len(_words(idea) & _words(d)) / max(1, len(_words(idea)))) for d in done_topics)
    return round(10 * (1 - best), 1)


def demand(query):
    import research
    vids = research.search(query, n=8)[:5]
    views = [v["views"] for v in vids if v.get("views")]
    if not views:
        return None, 0                                       # no listing (yt-dlp timeout under load): unknown, not zero
    med = statistics.median(views)
    return round(min(10.0, max(0.0, (math.log10(max(med, 1)) - 3) * 2.5)), 1), int(med)   # 1k views -> 0, 100k -> 5, 10M -> 10


def candidates(ch, used):
    import plan as planner
    backlog = [t for t in ch.get("topics_backlog", []) if t.lower() not in used][:4]
    trends = read(os.path.join(ROOT, "knowledge", "playbook.md"), 2200) or ""
    if ch["id"] == "tech":                                   # the radar's ranked AI/tech news ideas (scout.py radar)
        tj = load(os.path.join(ROOT, "knowledge", "topics.json"), {}) or {}
        items = tj.get("topics", tj) if isinstance(tj, dict) else tj
        heads = [x.get("title") or x.get("topic") for x in (items if isinstance(items, list) else []) if isinstance(x, dict) and not x.get("used")][:12]
        if heads:
            trends += "\n\nFresh AI/tech news ideas from today's radar:\n- " + "\n- ".join(h for h in heads if h)
    results = read(os.path.join(ROOT, "knowledge", "results.md"), 2000) or ""
    p = (f"You plan short vertical videos (Reels/Shorts) for the page '{ch.get('name', ch['id'])}'.\n"
         f"Page format: {ch.get('format', '')}\nPillars/series: {json.dumps(ch.get('pillars') or ch.get('series') or [], ensure_ascii=False)}\n"
         f"Already made (do not repeat or rephrase): {sorted(used)[:60]}\n"
         f"What is trending now (scout notes):\n{trends}\n\nWhat worked for us so far:\n{results}\n\n"
         f"Write {N - len(backlog)} NEW video ideas. Each must be specific (one clear question or story), curiosity-first, "
         "safe (no politics, no real crimes, no medical or money advice), and fit the page.\n"
         'For each idea also write "search": 3-5 English words someone would type on YouTube to find this kind of Short, '
         'and "fit": 0-10, how well it fits this page and its audience.\n'
         'Return JSON {"ideas": [{"topic": "...", "search": "...", "fit": 0}]}')
    try:
        fresh = (planner.ask(p, max_tokens=2500) or {}).get("ideas", [])
    except Exception as e:
        log("ideas: planner failed", str(e)[:150]); fresh = []
    out = [{"topic": t, "search": t, "fit": 7, "from": "backlog"} for t in backlog]
    try:                                                     # Part 2 of a winner is due: first of all (engine/series.py)
        import series
        out = [{"topic": x["topic"], "search": x.get("search") or x["topic"], "fit": 10.0, "from": "series", "note": "Part 2 of " + str(x.get("of_title"))}
               for x in series.due(ch["id"])[:1]] + out
    except Exception as e:
        log("ideas: series unavailable", str(e)[:100])
    try:                                                     # 17 Nov: today's trends for this page (engine/trends.py), first
        import trends
        tr = [x for x in trends.fresh(ch["id"]) if x["topic"].lower() not in used][:3]
        out = [{"topic": x["topic"], "search": x.get("search") or x["topic"], "fit": float(x.get("fit") or 7), "from": "trend",
                "note": x.get("why", "")} for x in tr] + out
    except Exception as e:
        log("ideas: trends unavailable", str(e)[:100])
    for x in fresh:
        if isinstance(x, dict) and x.get("topic") and x["topic"].lower() not in used:
            t = re.split(r"\s*\((?:metaphor|example|analogy)\b", x["topic"], flags=re.I)[0].strip()
            out.append({"topic": t, "note": x["topic"][len(t):].strip(" ()"), "search": (x.get("search") or x["topic"]).strip(), "fit": float(x.get("fit") or 6), "from": "new"})
    return out[:N]


def pick(ch):
    done = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), []) or []
    used = {d["topic"].lower() for d in done if d.get("topic")}
    cands = candidates(ch, used)
    if not cands:
        return None
    with ThreadPoolExecutor(2) as ex:
        dem = list(ex.map(lambda c: demand(c["search"]), cands))
    dem = [d if d[0] is not None else demand(c["search"]) for c, d in zip(cands, dem)]   # one slow retry
    for c, (d, med) in zip(cands, dem):
        c["demand_known"] = d is not None
        c["demand"], c["median_views"] = (d if d is not None else 4.0), med
        c["fresh"] = freshness(c["topic"], list(used))
        c["score"] = round(0.45 * c["demand"] + 0.35 * min(10, c["fit"]) + 0.20 * c["fresh"] + (1.0 if c.get("from") == "trend" else 0) + (3.0 if c.get("from") == "series" else 0), 2)   # 17 Nov: used d (None when YouTube gave no data) -> crash -> plain backlog
    cands.sort(key=lambda c: -c["score"])
    hist = load(os.path.join(ROOT, "channels", ch["id"], "ideas.json"), []) or []
    hist.append({"t": time.strftime("%Y-%m-%d %H:%M"), "picked": cands[0]["topic"], "ideas": cands})
    save(os.path.join(ROOT, "channels", ch["id"], "ideas.json"), hist[-30:])
    if cands[0].get("from") == "series":
        try:
            import series; series.mark_used(ch["id"], cands[0]["topic"])
        except Exception:
            pass
    if cands[0].get("from") == "trend":
        try:
            import trends; trends.mark_used(ch["id"], cands[0]["topic"])
        except Exception:
            pass
    log("ideas", ch["id"], "picked", repr(cands[0]["topic"]), "score", cands[0]["score"], "of", len(cands),
        "| runner-up", repr(cands[1]["topic"]) if len(cands) > 1 else "-")
    return cands[0]["topic"]


if __name__ == "__main__":
    from core import channel
    ch = channel(sys.argv[1])
    t = pick(ch)
    for c in (load(os.path.join(ROOT, "channels", ch["id"], "ideas.json"), []) or [{}])[-1].get("ideas", []):
        print(f"{c['score']:5.2f}  demand {c['demand']:4.1f} ({c['median_views']:>9,} views)  fit {c['fit']:4.1f}  fresh {c['fresh']:4.1f}  {c['topic']}")
    print("PICKED:", t)
