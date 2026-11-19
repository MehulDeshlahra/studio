"""Free web search + reading for research, fact checks, news and the learner (18 Nov, owner: "search scrapers, crawlers
which will help you, set it up"). No keys, no sign-ups.
  search(q, n)      -> [{title, url, snippet}]       DuckDuckGo/Bing/Brave meta-search (ddgs)
  news(q, n, days)  -> [{title, url, source, date}]  recent news
  read(url)         -> clean article text             trafilatura; fallback r.jina.ai reader (renders JS pages)
  facts(topic, n)   -> text block for the planner     top articles read and trimmed
  python engine/web.py search "<q>" | news "<q>" | read <url> | facts "<topic>" """
import json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import log

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"}
SKIP = re.compile(r"(linkedin\.com|facebook\.com|instagram\.com|tiktok\.com|pinterest\.|quora\.com/profile|x\.com|twitter\.com)", re.I)


def search(q, n=8, region="in-en"):
    from ddgs import DDGS
    # the India region sometimes answers "No results found". 19 Nov: "wt-wt" made ddgs's Wikipedia backend call
    # wt.wikipedia.org (DNS error), so the fallback is us-en; a long, sentence-like query then gets a 5-word retry
    short = " ".join(q.split()[:5])
    tries = [(q, region), (q, "us-en")] + ([(short, "us-en")] if short != q else [])
    for qq, reg in tries:
        try:
            got = [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                   for r in DDGS().text(qq, region=reg, max_results=n) or []]
            if got:
                return got
        except Exception as e:
            log("web search fail", reg, qq[:60], str(e)[:100])
    return []


def news(q, n=8, days=7, region="in-en"):
    try:
        from ddgs import DDGS
        lim = {1: "d", 7: "w", 30: "m"}.get(days, "w")
        return [{"title": r.get("title", ""), "url": r.get("url", ""), "source": r.get("source", ""), "date": (r.get("date") or "")[:10],
                 "snippet": r.get("body", "")} for r in DDGS().news(q, region=region, timelimit=lim, max_results=n) or []]
    except Exception as e:
        log("web news fail", q[:60], str(e)[:100]); return []


def read(url, maxc=12000):
    """Main text of a page ('' when nothing readable)."""
    txt = ""
    try:
        import trafilatura
        html = trafilatura.fetch_url(url)
        if html:
            txt = trafilatura.extract(html, include_comments=False, include_tables=True, favor_precision=True) or ""
    except Exception as e:
        log("web read fail", url[:80], str(e)[:80])
    if len(txt) < 400:                                   # JS pages, odd markup: the free Jina reader renders them
        try:
            r = urllib.request.urlopen(urllib.request.Request("https://r.jina.ai/" + url, headers=dict(UA, Accept="text/plain")), timeout=40)
            t2 = r.read(400_000).decode("utf-8", "ignore")
            t2 = re.sub(r"^(Title|URL Source|Published Time|Markdown Content):.*\n", "", t2, flags=re.M)
            if len(t2) > len(txt):
                txt = t2
        except Exception as e:
            log("web jina fail", url[:80], str(e)[:80])
    return re.sub(r"\n{3,}", "\n\n", txt).strip()[:maxc]


def facts(topic, n=3, per=3500):
    """The planner's evidence: top web articles on the topic, read and trimmed, with their sources."""
    out, seen = [], set()
    for r in search(topic, n=10):
        u = r["url"]
        dom = re.sub(r"^www\.", "", urllib.parse.urlparse(u).netloc) if u else ""
        if not u or SKIP.search(u) or dom in seen:
            continue
        t = read(u, per)
        if len(t) < 400:
            continue
        seen.add(dom)
        out.append(f"SOURCE {dom} ({r['title'][:90]}):\n{t}")
        if len(out) >= n:
            break
    return "\n\n".join(out)


import urllib.parse  # noqa: E402  (used in facts)

if __name__ == "__main__":
    cmd, arg = sys.argv[1], " ".join(sys.argv[2:])
    if cmd == "search":
        print(json.dumps(search(arg), ensure_ascii=False, indent=1))
    elif cmd == "news":
        print(json.dumps(news(arg), ensure_ascii=False, indent=1))
    elif cmd == "read":
        print(read(arg))
    elif cmd == "facts":
        t0 = time.time(); f = facts(arg); print(f[:3000]); print(f"\n[{len(f)} chars in {time.time() - t0:.0f} s]")
