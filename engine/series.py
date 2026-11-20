"""Part 2 for winners ("Part 2 kal"; owner 17 Nov).
scan():     every day (called from stats.py / trends timer): for each page, a posted video whose views beat 1.5x the page median
            (and >= 300 views) and that has no Part 2 yet gets a Part 2 topic written by the planner: it continues the same
            story / goes one layer deeper, and ends by asking for Part 3. Saved in knowledge/series.json.
            ideas.py puts due Part 2 topics first in the page's queue (fit 10, +3 bonus).
announce(): comments.py posts "Part 2 kal aa raha hai" as a comment under the Part 1 post once its Part 2 is queued.
context():  plan.py gives the Part 2 planner the Part 1 script so the two parts connect ("Pichhle video mein...").
No video is edited after posting; the promise lives in the first comment, so Part 1 stays as approved.
  python engine/series.py [--print]"""
import json, os, statistics, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log

F = os.path.join(ROOT, "knowledge", "series.json")

ASK = """Our faceless Short on the page "{name}" did well ({views} views). Its script:
\"\"\"{vo}\"\"\"
Write PART 2 as a new video topic: the same subject one layer deeper, or what happened next, with a NEW fact or twist that part 1
did not give. It must work for someone who did not see part 1 (one line recap allowed) and end by asking for Part 3.
No claims we cannot source. JSON {{"topic": "Part 2: <specific, curiosity-first title in the page's language>", "search": "3-5 English words"}}"""


def scan():
    import plan as planner
    from core import channel
    data = load(F, {"items": []}) or {"items": []}
    have = {i["of_job"] for i in data["items"]}
    for cid in [c for c in os.listdir(os.path.join(ROOT, "channels")) if os.path.isdir(os.path.join(ROOT, "channels", c))]:
        done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
        rows = [(d, (d.get("stats") or {}).get("views") or 0) for d in done if d.get("status") == "posted" and (d.get("stats") or {}).get("views")]
        if len(rows) < 3:
            continue
        med = statistics.median(v for _, v in rows)
        for d, v in sorted(rows, key=lambda x: -x[1]):
            if v < max(300, 1.5 * med) or d["job"] in have or d["job"].endswith("-en") or str(d.get("topic", "")).lower().startswith("part "):
                continue
            plan = load(os.path.join(OUT, cid, d["job"], "plan.json"), {})
            vo = " ".join(s.get("vo", "") for s in plan.get("scenes", []))[:1500]
            r = planner.ask(ASK.format(name=channel(cid).get("name", cid), views=v, vo=vo), max_tokens=700) or {}
            if isinstance(r, dict) and r.get("topic"):
                data["items"].append({"page": cid, "of_job": d["job"], "of_title": d.get("title"), "topic": r["topic"], "search": r.get("search") or r["topic"],
                                      "due": time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400)), "announced": False, "used": False, "views": v})
                have.add(d["job"]); log("series: part 2 queued for", cid, d["job"], "->", r["topic"][:70])
            break                                                       # at most one new Part 2 per page per scan
    save(F, data)
    return data


def due(page):
    today = time.strftime("%Y-%m-%d")
    return [i for i in (load(F, {"items": []}) or {}).get("items", []) if i["page"] == page and not i["used"] and i["due"] <= today]


def mark_used(page, topic):
    data = load(F, {"items": []}) or {"items": []}
    for i in data["items"]:
        if i["page"] == page and i["topic"] == topic:
            i["used"] = time.strftime("%Y-%m-%d")
    save(F, data)


def announce(page, job):
    """Text for the 'Part 2 kal' comment if this job has a queued Part 2 not announced yet, else None."""
    for i in (load(F, {"items": []}) or {}).get("items", []):
        if i["page"] == page and i["of_job"] == job and not i["announced"] and not i["used"]:
            return "Part 2 kal aa raha hai. Follow kijiye taaki miss na ho."
    return None


def mark_announced(page, job):
    data = load(F, {"items": []}) or {"items": []}
    for i in data["items"]:
        if i["page"] == page and i["of_job"] == job:
            i["announced"] = True
    save(F, data)


def context(topic, page):
    """Part 1 script for a 'Part 2: ...' topic (plan.py adds it to the prompt)."""
    for i in (load(F, {"items": []}) or {}).get("items", []):
        if i["page"] == page and i["topic"] == topic:
            plan = load(os.path.join(OUT, page, i["of_job"], "plan.json"), {})
            vo = " ".join(s.get("vo", "") for s in plan.get("scenes", []))[:1600]
            return f"THIS IS PART 2 of the video \"{i.get('of_title')}\". Part 1 said:\n{vo}\nStart with a one-line recap, then give the NEW part, end by asking for Part 3."
    return ""


if __name__ == "__main__":
    d = scan()
    if "--print" in sys.argv:
        print(json.dumps(d, ensure_ascii=False, indent=1)[:2000])
