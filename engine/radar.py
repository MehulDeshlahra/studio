"""Daily tools radar (owner, 17 Nov: "an agent which checks new technologies, platforms that may be offered free, anything
beneficial; research Reddit, GitHub, Google; show what we can add").
Every morning (timer studio-radar 06:30 IST, low priority):
  collect  Reddit (RSS of ~14 subs), Hacker News (Show HN + front page), GitHub (new fast-rising repos), Hugging Face
           (trending models/spaces), Product Hunt, dev.to, Google News searches, and a Gemini Google-Search sweep for
           "new free API / free tier / free credits" launches. ~300 items a day, no paid API.
  filter   drop what we already looked at (radar-seen.json), keyword prefilter, then Gemini judges the best ~60 against
           knowledge/CAPABILITIES.md and the money rule (FREE only: free tier, free credits, open source, self-host).
  act      by itself: GitHub repos worth it -> learner queue (learn.py reads them into the brain or build list);
                      knowledge (tips, techniques) -> brain; buildable features -> knowledge/build-queue.md;
                      "needs a sign-up/account" -> listed as an option for the owner (never signs up by itself).
  report   dashboard "Radar" page (knowledge/radar.json, 60 days kept) + ONE short Telegram digest, only when something
           scored 7+/10. Nothing is ever paid for, installed system-wide or given our keys.
  python engine/radar.py [--dry]"""
import html, json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, read, telegram

DRY = "--dry" in sys.argv
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux aarch64) studio-radar/1.0"}
RADAR = os.path.join(ROOT, "knowledge", "radar.json")
SEEN = os.path.join(OUT, "radar-seen.json")
SUBS = ["LocalLLaMA", "StableDiffusion", "aivideo", "artificial", "singularity", "selfhosted", "SideProject", "NewTubers",
        "youtubers", "Instagram", "InstagramMarketing", "socialmedia", "ChatGPTPro", "comfyui", "VideoEditing", "opensource"]
NEWSQ = ["free AI API launch", "free tier AI video generation", "free credits developers AI", "open source text to speech model release",
         "free AI image generation API", "YouTube Shorts new feature", "Instagram Reels new feature creators", "open source video model release"]
KEYS = re.compile(r"\b(free|open[- ]source|self[- ]host|credits?|tier|api|launch|released?|new model|tts|voice|video|image|"
                  r"caption|subtitle|edit|shorts|reels|youtube|instagram|thumbnail|music|sfx|upscal|lip ?sync|avatar|diffusion|"
                  r"gemini|whisper|flux|wan|hunyuan|ltx|kokoro|f5|comfy|ffmpeg|remotion|hyperframes|agent|automation)\b", re.I)


def _get(url, raw=True, timeout=30):
    from core import github_headers
    b = urllib.request.urlopen(urllib.request.Request(url, headers=github_headers() if "api.github.com" in url else UA), timeout=timeout).read()
    return b if raw else json.loads(b)


def _text(s, n=300):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()[:n]


def rss(url, src, n=25):
    out = []
    for wait in (0, 20, 60):                                   # 17 Nov: Reddit and Google News answer 429 when asked too fast
        try:
            time.sleep(wait)
            root = ET.fromstring(_get(url))
            break
        except Exception as e:
            if "429" not in str(e) or wait == 60:
                log("radar:", src, "failed", str(e)[:80]); return out
    for it in list(root.iter("{http://www.w3.org/2005/Atom}entry"))[:n] + list(root.iter("item"))[:n]:
        g = lambda t: (it.find(t) if it.find(t) is not None else it.find("{http://www.w3.org/2005/Atom}" + t))
        t, l, d = g("title"), g("link"), g("description") if g("description") is not None else g("content")
        link = (l.get("href") if l is not None and l.get("href") else (l.text if l is not None else "")) or ""
        out.append({"src": src, "title": _text(t.text if t is not None else "", 160), "url": link.strip(),
                    "about": _text(d.text if d is not None else "", 400)})
    return out


def collect():
    items = []
    for s in SUBS:
        items += rss(f"https://www.reddit.com/r/{s}/top/.rss?t=day", f"reddit r/{s}", 12); time.sleep(7)
    day = int(time.time()) - 86400
    for q in (f"tags=show_hn&numericFilters=created_at_i>{day}", f"tags=front_page"):
        try:
            for h in _get("https://hn.algolia.com/api/v1/search?" + q.replace(">", "%3E"), raw=False).get("hits", [])[:40]:
                items.append({"src": "hacker news", "title": h.get("title") or "", "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                              "about": f"{h.get('points', 0)} points"})
        except Exception as e:
            log("radar: hn failed", str(e)[:80])
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))
    for q in (f"created:>{since} stars:>80", f"created:>{since} stars:>25 topic:ai", f"created:>{since} stars:>20 video"):
        try:
            for r in _get("https://api.github.com/search/repositories?sort=stars&order=desc&per_page=30&q=" + urllib.parse.quote(q), raw=False).get("items", []):
                items.append({"src": "github", "title": r["full_name"], "url": r["html_url"],
                              "about": f"{r.get('description') or ''} · {r['stargazers_count']} stars in a week · licence {(r.get('license') or {}).get('spdx_id', 'none')}"})
        except Exception as e:
            log("radar: github failed", str(e)[:80])
        time.sleep(7)
    for kind in ("models", "spaces"):
        try:
            for m in _get(f"https://huggingface.co/api/{kind}?sort=trendingScore&limit=20", raw=False):
                items.append({"src": f"hugging face {kind}", "title": m.get("id", ""), "url": f"https://huggingface.co/{'spaces/' if kind == 'spaces' else ''}{m.get('id', '')}",
                              "about": f"{m.get('pipeline_tag') or m.get('sdk') or ''} · {m.get('likes', 0)} likes"})
        except Exception as e:
            log("radar: hf failed", str(e)[:80])
    items += rss("https://www.producthunt.com/feed", "product hunt", 30)
    try:
        for a in _get("https://dev.to/api/articles?top=1&per_page=30&tag=ai", raw=False):
            items.append({"src": "dev.to", "title": a["title"], "url": a["url"], "about": a.get("description") or ""})
    except Exception as e:
        log("radar: devto failed", str(e)[:80])
    for q in NEWSQ:
        items += rss(f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}+when:2d&hl=en-IN&gl=IN&ceid=IN:en", "google news", 8)
        time.sleep(6)
    items += google_sweep()
    return items


def google_sweep():
    """Gemini with Google Search: free AI launches of the last few days that fit a faceless short-video studio."""
    import tts
    q = ("Search the web for things launched or announced in the LAST 7 DAYS that a small automated faceless short-video studio could use "
         "for FREE: new free AI APIs or free tiers, free credits programs, open-source models for video, voice/TTS, music, image, "
         "captions or upscaling, new free features for YouTube Shorts / Instagram Reels creators, and new free automation tools. "
         "Return up to 15 items as JSON list [{\"title\",\"url\",\"about\"}] with the real source URL. Only real, verifiable items.")
    import core
    body = {"contents": [{"parts": [{"text": core.dated(q)}]}], "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.2}}
    for m in ("gemini-3.8-flash", "gemini-3.5-flash-lite"):
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key()})
            d = json.load(urllib.request.urlopen(r, timeout=180))
            txt = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
            mm = re.search(r"\[.*\]", txt, re.S)
            got = json.loads(mm.group(0)) if mm else []
            return [{"src": "google (gemini search)", "title": str(g.get("title", ""))[:160], "url": str(g.get("url", "")), "about": str(g.get("about", ""))[:400]}
                    for g in got if isinstance(g, dict) and g.get("title")]
        except Exception as e:
            log("radar: google sweep failed", m, str(e)[:100])
    return []


JUDGE = """You are the R&D scout of a small, fully automated studio that makes faceless vertical short videos (Hinglish tech
explainers, mythology stories, general stories) and posts them to Instagram, Facebook and YouTube. Everything must be FREE:
free tier, free credits, open source or self-hostable on a 2-core ARM server with 12 GB RAM and no GPU. Never paid.

WHAT THE STUDIO ALREADY HAS:
{caps}

CANDIDATES (today's Reddit, Hacker News, GitHub, Hugging Face, Product Hunt, news and web search):
{items}

Pick ONLY the ones that would truly help us: better or cheaper video/voice/image/music/captions, more reach (platform features),
more reliability, or less work. Skip hype, paid-only products, things we already do as well, things that need a GPU we lack
(unless offered free in the cloud), and anything unsafe or against platform rules.
Return JSON {{"picks": [{{
  "n": <candidate number>, "name": "short name", "what": "what it is, one plain sentence",
  "why": "what it would improve for US, concrete", "free": "exactly what is free (tier limits, credits, licence)",
  "action": "learn_repo" | "add_to_brain" | "build" | "owner_signup" | "watch",
  "how": "the concrete next step for our pipeline", "effort": "small" | "medium" | "large",
  "score": 1-10, "risk": "anything to be careful about"}}]}}
Look across ALL sources (not only GitHub): free services and credits, new open models, platform features and creator tips count too.
Skip repos we already read: {known}
Max 8 picks, best first. Be strict: most days only 0-3 deserve a 7 or more."""


def judge(items):
    import plan as planner
    caps = read(os.path.join(ROOT, "knowledge", "CAPABILITIES.md"), 5000)
    lines = "\n".join(f"{i}. [{c['src']}] {c['title']} | {c['about'][:220]} | {c['url']}" for i, c in enumerate(items))
    known = ", ".join(d["name"] for d in (load(os.path.join(ROOT, "knowledge", "learned.json"), []) or [])[-80:]) or "none"
    r = planner.ask(JUDGE.format(caps=caps, items=lines, known=known), max_tokens=6000) or {}
    picks = r.get("picks", []) if isinstance(r, dict) else []
    out = []
    for p in picks:
        try:
            c = items[int(p["n"])]
        except Exception:
            continue
        out.append({**{k: p.get(k) for k in ("name", "what", "why", "free", "action", "how", "effort", "score", "risk")},
                    "src": c["src"], "url": c["url"], "title": c["title"]})
    return sorted(out, key=lambda x: -(x.get("score") or 0))


def act(picks):
    done = []
    for p in picks:
        if (p.get("score") or 0) < 7:
            continue
        a = p.get("action")
        if a == "learn_repo" and "github.com/" in (p.get("url") or ""):
            q = load(os.path.join(OUT, "learn-queue.json"), []) or []
            q.append({"kind": "github", "url": p["url"], "from": "radar"}); save(os.path.join(OUT, "learn-queue.json"), q)
            p["done"] = "queued for the learner"; done.append(p)
        elif a == "add_to_brain":
            import brain
            brain.add([{"title": p["name"], "text": f"{p['what']} {p['why']}", "how": p.get("how", ""), "area": "growth", "kind": "knowledge"}], p["url"])
            p["done"] = "added to the brain"; done.append(p)
        elif a == "build":
            with open(os.path.join(ROOT, "knowledge", "build-queue.md"), "a", encoding="utf-8", newline="\n") as f:
                f.write(f"\n- [ ] [radar] {p['name']} ({p['url']}, {time.strftime('%Y-%m-%d')}): {p['why']} FREE: {p.get('free', '')} HOW: {p.get('how', '')}\n")
            p["done"] = "added to the build list"; done.append(p)
        elif a == "owner_signup":
            p["done"] = "needs a free sign-up by the owner (optional)"; done.append(p)
    if any(p.get("done") == "queued for the learner" for p in done) and not DRY:
        import subprocess
        subprocess.Popen([sys.executable, os.path.join(ROOT, "engine", "learn.py")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return done


def main():
    seen = load(SEEN, {}) or {}
    items = collect()
    fresh, keys = [], set()
    for c in items:
        k = (c.get("url") or c["title"]).split("?")[0].rstrip("/").lower()
        if not k or k in seen or k in keys:
            continue
        keys.add(k)
        if c["src"] in ("github", "google (gemini search)") or KEYS.search(c["title"] + " " + c["about"]):
            fresh.append(c)
    log("radar: collected", len(items), "items,", len(fresh), "new and relevant")
    for k in keys:
        seen[k] = time.strftime("%Y-%m-%d")
    cut = time.strftime("%Y-%m-%d", time.localtime(time.time() - 45 * 86400))
    seen = {k: v for k, v in seen.items() if v >= cut}
    picks = judge(fresh[:140]) if fresh else []
    done = act(picks) if not DRY else []
    rec = load(RADAR, []) or []
    rec.append({"day": time.strftime("%Y-%m-%d"), "t": time.strftime("%H:%M"), "scanned": len(items), "new": len(fresh),
                "sources": sorted({c["src"].split(" r/")[0] for c in items}), "picks": picks})
    rec = [r for r in rec if r["day"] >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 60 * 86400))]
    if not DRY:
        save(RADAR, rec[-60:]); save(SEEN, seen)
    good = [p for p in picks if (p.get("score") or 0) >= 7]
    log("radar:", len(picks), "picks,", len(good), "worth acting on,", len(done), "acted on")
    if good and not DRY:
        lines = [f"• {p['name']} ({p.get('score')}/10): {p['why'][:110]}" + (f" → {p['done']}" if p.get("done") else "") for p in good[:4]]
        telegram("📡 Tools radar: " + str(len(good)) + " new free thing" + ("s" if len(good) > 1 else "") + " worth it for Studio\n" + "\n".join(lines) + "\nDetails: dashboard → Radar")
        import subprocess
        subprocess.run([sys.executable, os.path.join(ROOT, "engine", "sync.py")], timeout=300)
    print(json.dumps({"scanned": len(items), "new": len(fresh), "picks": [{k: p.get(k) for k in ("name", "score", "action", "done")} for p in picks]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
