"""Studio scout: finds what is working right now and keeps a living playbook. Runs on the Oracle server
(systemd timer studio-scout, twice a day). Read-only on every source; free models only (OmniRoute).

  radar  AI/tech news: Hacker News front page, GitHub trending, Hugging Face daily papers, AI blog feeds
         -> knowledge/topics.json (ranked story ideas for a Hinglish AI/tech channel, no repeats)
  style  latest Shorts of every watchlist channel with view counts -> outliers vs that channel's own median
         (>= 2x = winner, <= 0.4x = flop) -> Gemini watches them by URL -> knowledge/videos/<id>.json
  learn  all analyses of the last 45 days -> knowledge/playbook.md (what wins, what flops, hooks, techniques,
         banned) + channels to add to the watchlist
  python3 scout/scout.py [radar] [style] [learn] [--dry]      (no args = all three)
Never crawls sites whose robots.txt forbids AI use (e.g. prompt-motion.com: reference by a human only).
"""
import datetime, html, json, os, re, statistics, subprocess, sys, time, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "lib"))
import llm  # noqa: E402

K = os.path.join(ROOT, "knowledge")
VIDEOS = os.path.join(K, "videos")
SHORTS = os.path.join(K, "shorts.json")        # view snapshots per short
TOPICS = os.path.join(K, "topics.json")
PLAYBOOK = os.path.join(K, "playbook.md")
STATE = os.path.join(K, "scout-state.json")
WATCHLIST = os.path.join(ROOT, "scout", "watchlist.json")
YTDLP = os.environ.get("YTDLP", os.path.expanduser("~/studio-venv/bin/yt-dlp"))
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
WATCH_PER_RUN, PER_CHANNEL, SKIP_NEWEST, MAX_CHANNELS = 10, 15, 2, 40
UA = "Mozilla/5.0 (studio-scout; read-only research)"
DRY = "--dry" in sys.argv


def now():
    return datetime.datetime.now(IST)


def log(*a):
    print(now().strftime("%H:%M:%S"), *a, flush=True)


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def save(p, d):
    if DRY:
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def get(url, timeout=25):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout).read()


# ---------------------------------------------------------------- radar
FEEDS = {
    "Hugging Face blog": "https://huggingface.co/blog/feed.xml",
    "OpenAI": "https://openai.com/news/rss.xml",
    "Google AI": "https://blog.google/technology/ai/rss/",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
}


def src_hn():
    d = json.loads(get("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=40"))
    return [{"src": "Hacker News", "title": h["title"], "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
             "score": h.get("points", 0)} for h in d["hits"]]


def src_github():
    page = get("https://github.com/trending?since=daily").decode("utf-8", "ignore")
    out = []
    for art in re.findall(r'<article class="Box-row">(.*?)</article>', page, re.S)[:25]:
        m = re.search(r'href="/([^"/]+/[^"/]+)"', art)
        if not m:
            continue
        desc = re.search(r'<p class="[^"]*">(.*?)</p>', art, re.S)
        stars = re.search(r'([\d,]+) stars today', art)
        out.append({"src": "GitHub trending", "title": m.group(1) + (": " + html.unescape(re.sub(r"<[^>]+>|\s+", " ", desc.group(1))).strip() if desc else ""),
                    "url": "https://github.com/" + m.group(1), "score": int(stars.group(1).replace(",", "")) if stars else 0})
    return out


def src_hf_papers():
    d = json.loads(get("https://huggingface.co/api/daily_papers"))
    return [{"src": "HF papers", "title": p["paper"]["title"], "url": "https://huggingface.co/papers/" + p["paper"]["id"],
             "score": p["paper"].get("upvotes", 0)} for p in d[:20]]


def src_feeds():
    out = []
    for name, url in FEEDS.items():
        try:
            root = ET.fromstring(get(url))
        except Exception as e:
            log("feed fail", name, str(e)[:60]); continue
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for it in items[:8]:
            t = it.findtext("title") or it.findtext("{http://www.w3.org/2005/Atom}title") or ""
            link = it.findtext("link") or ""
            if not link:
                a = it.find("{http://www.w3.org/2005/Atom}link")
                link = a.get("href", "") if a is not None else ""
            date = it.findtext("pubDate") or it.findtext("{http://www.w3.org/2005/Atom}updated") or ""
            out.append({"src": name, "title": html.unescape(t.strip()), "url": link.strip(), "score": 0, "date": date[:25]})
    return out


RANK = """You pick stories for a faceless Hinglish Instagram/YouTube Shorts channel about AI and tech for Indian
viewers (students, young professionals, small business owners). Today's raw items are below (source, title, url).
Pick the {n} best for a 30-60 s short. A good pick is: genuinely new (this week), useful or surprising to an
ordinary Indian phone user, explainable with real screenshots of the source, and not political or financial advice.
Skip anything in ALREADY USED. Never invent facts; the angle must follow from the title/source.
For each pick return: {{"title": "...", "url": "...", "src": "...", "angle": "why an Indian viewer cares, 1 line",
"hook": "first spoken line in Hinglish, max 9 words, does NOT explain itself", "format": "evidence | how-it-works |
tool-demo | comparison | story", "freshness": "today|this week", "score": 1-10}}
JSON: {{"picks": [...]}}

ALREADY USED:
{used}

ITEMS:
{items}"""


def radar():
    items = []
    for f in (src_hn, src_github, src_hf_papers, src_feeds):
        try:
            got = f(); items += got; log("radar", f.__name__, len(got))
        except Exception as e:
            log("radar fail", f.__name__, str(e)[:80])
    if not items:
        return
    t = load(TOPICS, {"picks": [], "history": []})
    used = [h["url"] for h in t.get("history", [])][-300:]
    seen, uniq = set(used), []
    for i in items:
        if i["url"] and i["url"] not in seen:
            seen.add(i["url"]); uniq.append(i)
    lines = "\n".join(f"- [{i['src']}] {i['title'][:160]} | {i['url']}" for i in uniq[:120])
    r = llm.text(RANK.format(n=12, used="\n".join(used[-60:]) or "none", items=lines), json_mode=True)
    picks = [p for p in r.get("picks", []) if p.get("url") and p["url"] not in used]
    stamp = now().isoformat(timespec="minutes")
    for p in picks:
        p["found"] = stamp
    t["picks"] = sorted(picks, key=lambda p: -int(p.get("score", 0)))
    t["updated"] = stamp
    t["history"] = (t.get("history", []) + [{"url": p["url"], "title": p["title"], "found": stamp} for p in picks])[-600:]
    save(TOPICS, t)
    log("radar picks", len(picks), "|", " / ".join(p["title"][:50] for p in t["picks"][:3]))


# ---------------------------------------------------------------- style
def list_shorts(handle):
    r = subprocess.run([YTDLP, f"https://www.youtube.com/@{handle}/shorts", "--flat-playlist", "--playlist-end",
                        str(PER_CHANNEL), "--print", "%(id)s\t%(view_count)s\t%(title)s"],
                       capture_output=True, text=True, timeout=180)
    out = []
    for line in r.stdout.splitlines():
        p = line.split("\t")
        if len(p) == 3 and p[1].isdigit():
            out.append({"id": p[0], "views": int(p[1]), "title": p[2]})
    return out


WATCH = """You are a senior short-form video editor studying a YouTube Short to learn what makes it perform.
Channel: @{handle} ({niche}). Title: "{title}". It got {views:,} views = {ratio:.1f}x this channel's median
({label}). Watch the whole video, sound included, and report precisely what you see and hear. No guessing: if
unsure, say so.
JSON:
{{"hook_first_words": "exact first spoken words", "first_frame": "what is on screen at 0 s",
"hook_type": "question | bold claim | interruption | in-the-middle | visual surprise | other",
"format": "e.g. evidence/news, 3D how-it-works, talking head + graphics, meme-cut explainer, animation",
"length_s": 0, "cuts_estimate": 0, "avg_shot_s": 0.0, "words_per_s_estimate": 0.0,
"beats": ["0-3 s: ...", "..."],
"visual_techniques": ["each concrete editing/motion technique seen, with when"],
"captions": "style, words per chunk, position, highlight colour",
"sound": "voice type, music, sound effects, silences",
"recurring_element": "anything the video keeps returning to, or none",
"ending": "how it ends: loop, twist, CTA, punchline",
"why": "why it {verdict}, concrete, tied to moments",
"reusable_faceless": ["techniques a faceless motion-graphics/AI channel could copy"]}}"""


def style():
    wl = load(WATCHLIST, {"channels": []})
    snap = load(SHORTS, {})
    os.makedirs(VIDEOS, exist_ok=True)
    done = {f[:-5] for f in os.listdir(VIDEOS)} if os.path.isdir(VIDEOS) else set()
    queue = []
    for ch in wl["channels"]:
        try:
            shorts = list_shorts(ch["handle"])
        except Exception as e:
            log("list fail", ch["handle"], str(e)[:60]); continue
        if len(shorts) < 6:
            log("too few shorts", ch["handle"], len(shorts)); continue
        for s in shorts:
            snap.setdefault(s["id"], {"channel": ch["handle"], "title": s["title"], "views": []})
            snap[s["id"]]["views"] = (snap[s["id"]]["views"] + [[now().date().isoformat(), s["views"]]])[-10:]
        mature = shorts[SKIP_NEWEST:]                      # the newest ones haven't collected views yet
        med = statistics.median(s["views"] for s in mature) or 1
        for s in mature:
            ratio = s["views"] / med
            if s["id"] in done:
                continue
            if ratio >= 2:
                queue.append((ratio, "winner", ch, s, med))
            elif ratio <= 0.4:
                queue.append((ratio, "flop", ch, s, med))
        time.sleep(2)
    save(SHORTS, snap)
    winners = sorted((q for q in queue if q[1] == "winner"), key=lambda q: -q[0])
    flops = sorted((q for q in queue if q[1] == "flop"), key=lambda q: q[0])
    pick = winners[:WATCH_PER_RUN - 2] + flops[:2]          # mostly winners, a couple of flops for contrast
    log("style queue", len(winners), "winners", len(flops), "flops; watching", len(pick))
    for ratio, label, ch, s, med in pick:
        url = f"https://www.youtube.com/watch?v={s['id']}"
        try:
            a = llm.watch(url, WATCH.format(handle=ch["handle"], niche=ch.get("niche", ""), title=s["title"],
                                            views=s["views"], ratio=ratio, label=label,
                                            verdict="beat the channel's usual" if label == "winner" else "did worse than usual"))
        except Exception as e:
            log("watch fail", s["id"], str(e)[:100]); continue
        if not isinstance(a, dict) or not a.get("hook_first_words"):
            log("watch: unusable answer", s["id"]); continue
        a.update(id=s["id"], url=url, channel=ch["handle"], niche=ch.get("niche", ""), title=s["title"],
                 views=s["views"], channel_median=int(med), ratio=round(ratio, 2), label=label,
                 watched=now().isoformat(timespec="minutes"))
        save(os.path.join(VIDEOS, s["id"] + ".json"), a)
        log("watched", label, f"{ratio:.1f}x", ch["handle"], s["title"][:50])
        time.sleep(4)


# ---------------------------------------------------------------- learn
LEARN = """You maintain the editing playbook for an automated faceless Shorts studio (first channel: Hinglish AI/tech
explainers for Indian viewers; videos are motion graphics + real screenshots + AI visuals + TTS voice). Below are
analyses of real Shorts, each with how it performed against its own channel's median (ratio), plus the current
playbook. Rewrite the playbook in Markdown so it reflects what the EVIDENCE shows right now. Rules:
- Every claim cites the video ids it comes from, e.g. (Q3FcCNXUoU8 3.1x). No claim without evidence.
- Separate what winners do from what flops do. Prefer patterns seen in 2+ winners.
- Keep it practical: things a video builder can do (timings, caption styles, hook shapes, transitions, sound).
- Keep the 'Never' list from the current playbook unless evidence contradicts it.
- Max ~900 words. Sections: ## Updated, ## Hooks that win (quote real first lines), ## Editing that wins,
  ## Sound, ## Pacing numbers, ## What flops, ## Never, ## Try next (3 experiments for our channel).
Then, separately, suggest up to 3 YouTube channel handles (Shorts-heavy, 2025-2026 active, relevant to AI/tech/
explainers/Hindi) that we are NOT watching yet and would teach us something new.
JSON: {{"playbook_md": "...", "add_channels": [{{"handle": "...", "niche": "...", "why": "..."}}]}}

WATCHING: {watching}

CURRENT PLAYBOOK:
{playbook}

ANALYSES:
{analyses}"""


def learn():
    if not os.path.isdir(VIDEOS):
        return
    cut = (now() - datetime.timedelta(days=45)).isoformat()
    rows = [load(os.path.join(VIDEOS, f), {}) for f in sorted(os.listdir(VIDEOS))]
    rows = [r for r in rows if r.get("watched", "") >= cut]
    st = load(STATE, {})
    if len(rows) < 3 or len(rows) == st.get("learned_on", -1):
        log("learn: nothing new", len(rows)); return
    keep = ("id", "channel", "label", "ratio", "hook_first_words", "first_frame", "hook_type", "format", "avg_shot_s",
            "words_per_s_estimate", "visual_techniques", "captions", "sound", "recurring_element", "ending", "why")
    compact = json.dumps([{k: r.get(k) for k in keep} for r in rows[-60:]], ensure_ascii=False)
    wl = load(WATCHLIST, {"channels": []})
    cur = open(PLAYBOOK, encoding="utf-8").read() if os.path.exists(PLAYBOOK) else "(none yet)"
    r = llm.text(LEARN.format(watching=", ".join(c["handle"] for c in wl["channels"]), playbook=cur[:6000],
                              analyses=compact[:60000]), json_mode=True, max_tokens=6000)
    md = (r.get("playbook_md") or "").strip()
    if len(md) > 300 and not DRY:
        open(PLAYBOOK, "w", encoding="utf-8").write(md + f"\n\n_Written by the scout on {now():%d %b %Y %H:%M} IST "
                                                    f"from {len(rows)} analysed Shorts._\n")
    have = {c["handle"].lower() for c in wl["channels"]}
    for c in (r.get("add_channels") or [])[:3]:
        h = str(c.get("handle", "")).lstrip("@").strip()
        if not h or h.lower() in have or len(wl["channels"]) >= MAX_CHANNELS:
            continue
        try:
            ok = len(list_shorts(h)) >= 6
        except Exception:
            ok = False
        if ok:
            wl["channels"].append({"handle": h, "niche": c.get("niche", ""), "why": c.get("why", ""),
                                   "added_by": "scout", "added": now().date().isoformat()})
            have.add(h.lower()); log("watchlist +", h)
    save(WATCHLIST, wl)
    st["learned_on"] = len(rows); st["learned_at"] = now().isoformat(timespec="minutes")
    save(STATE, st)
    log("learn: playbook from", len(rows), "analyses")


def push():
    if DRY or subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "knowledge", "scout/watchlist.json"],
                             capture_output=True, text=True).stdout.strip() == "":
        return
    subprocess.run(["git", "-C", ROOT, "add", "knowledge", "scout/watchlist.json"], check=True)
    subprocess.run(["git", "-C", ROOT, "commit", "-qm", f"scout: knowledge {now():%Y-%m-%d %H:%M}"], check=True)
    for i in range(4):
        if subprocess.run(["git", "-C", ROOT, "pull", "--rebase", "-q"]).returncode == 0 and \
           subprocess.run(["git", "-C", ROOT, "push", "-q"]).returncode == 0:
            return
        subprocess.run(["git", "-C", ROOT, "rebase", "--abort"], capture_output=True); time.sleep(10)
    log("push failed")


if __name__ == "__main__":
    steps = [a for a in sys.argv[1:] if not a.startswith("--")] or ["radar", "style", "learn"]
    for s in steps:
        try:
            {"radar": radar, "style": style, "learn": learn}[s]()
        except Exception as e:
            log(s, "FAILED", str(e)[:200])
    push()
