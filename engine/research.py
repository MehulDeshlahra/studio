"""Research before every video (knowledge/PREFLIGHT.md step 2, automatic part):
YouTube Shorts on the topic (yt-dlp search listing; works from the server), top ones by views are WATCHED by
Gemini through OmniRoute (by URL, no download). Result: <job>/research.json + a short text for the planner."""
import json, os, re, subprocess
from core import log, save, PY
import llm

YTDLP = os.path.expanduser("~/studio-venv/bin/yt-dlp")

WATCH_PROMPT = """You are a senior short-form video editor. Watch this Short about "{topic}".
Return JSON: {{"hook_line": "first spoken/written words", "frame0": "what the first frame shows",
"visual_metaphor": "the one visual idea that explains it", "structure": ["beat 1", "beat 2", "..."],
"editing": "cuts, captions, motion graphics, sfx", "length_s": number, "why_it_works": "...",
"weak_points": "...", "facts_claimed": ["..."]}}"""


def search(query, n=12):
    try:
        out = subprocess.run([YTDLP if os.path.exists(YTDLP) else "yt-dlp", f"ytsearch{n}:{query}", "--flat-playlist",
                              "-j", "--no-warnings"], capture_output=True, text=True, timeout=120).stdout
    except Exception as e:
        log("research search fail", e); return []
    vids = []
    for line in out.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if (d.get("duration") or 0) <= 180:
            vids.append({"id": d.get("id"), "title": d.get("title"), "views": d.get("view_count") or 0,
                         "dur": d.get("duration"), "channel": d.get("channel") or d.get("uploader"),
                         "url": f"https://www.youtube.com/shorts/{d.get('id')}"})
    return sorted(vids, key=lambda v: -v["views"])


def run(topic, queries, job, watch_n=3):
    found, seen = [], set()
    for q in queries:
        for v in search(q):
            if v["id"] not in seen:
                seen.add(v["id"]); found.append(v)
    found.sort(key=lambda v: -v["views"])
    watched = []
    for v in found[:watch_n]:
        try:
            a = llm.watch(v["url"], WATCH_PROMPT.format(topic=topic))
            a.update({k: v[k] for k in ("url", "title", "views", "channel")})
            watched.append(a); log("watched", v["url"], v["views"])
        except Exception as e:
            log("watch fail", v["url"], str(e)[:120])
    try:                                     # 18 Nov: Instagram reels under the topic's own hashtags (smaller pages too)
        import hookstudy, re as _re
        page = os.path.basename(os.path.dirname(job))
        tags = []
        for q in (queries or [topic])[:2]:
            words = [w for w in _re.sub(r"[^a-z0-9 ]", "", q.lower()).split() if len(w) > 2 and w not in ("kaise", "kya", "how", "the", "and", "hai", "hindi", "shorts")]
            if words:
                tags.append("".join(words[:2]))
        ht = hookstudy.hashtag_top(page, tags=list(dict.fromkeys(tags))[:2], per=3, min_likes=300) if tags else []
        for v in ht[:2]:
            try:
                a = hookstudy.watch_file(v["video"], WATCH_PROMPT.format(topic=topic))
                a.update({k: v[k] for k in ("url", "title", "views", "channel")})
                watched.append(a); log("watched", v["channel"], v["url"], v.get("likes"), "likes")
            except Exception as e:
                log("watch fail", v["url"], str(e)[:100])
    except Exception as e:
        log("research hashtags skipped", str(e)[:100])
    r = {"topic": topic, "queries": queries, "top": found[:10], "watched": watched}
    try:                                     # 18 Nov: real articles too, so facts come from sources, not from memory
        import web
        r["web"] = web.facts(queries[0] if queries else topic, n=3)
        if len(r.get("web") or "") < 500:
            # 18 Nov: a 30-word idea full of '₹' found nothing (finance 1118-2228: 0 chars). Retry short and plain:
            # the first words before any '?', '₹' and digits removed, then the other planned queries.
            short = re.sub(r"[₹\d,.+%'\"]+", " ", re.split(r"[?:(]", str(topic))[0])
            short = " ".join(short.split()[:7])
            for q in [short] + list(queries[1:3]):
                if q and len(r.get("web") or "") < 500:
                    r["web"] = web.facts(q, n=3) or r.get("web") or ""
        log("research web:", len(r["web"]), "chars from articles")
    except Exception as e:
        log("research web fail", str(e)[:120])
    save(os.path.join(job, "research.json"), r)
    return r


def summary(r):
    lines = [f"Research on '{r['topic']}': {len(r['top'])} Shorts found, top views: "
             + ", ".join(f"{v['views']:,}" for v in r["top"][:5])]
    for w in r["watched"]:
        lines.append(f"- {w.get('views', 0):,} views '{w.get('title')}': hook '{w.get('hook_line')}'; frame0 {w.get('frame0')}; "
                     f"metaphor {w.get('visual_metaphor')}; works because {w.get('why_it_works')}; weak: {w.get('weak_points')}")
    if r.get("web"):
        lines.append("\nWEB SOURCES (use these for facts; every claim must agree with them; prefer their concrete details "
                     "and numbers over generic lines):\n" + r["web"][:9000])
    return "\n".join(lines)
