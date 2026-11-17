"""Daily trend scout (owner 17 Nov: "what's trending in India per page; score with ideas.py; best ones first").
Free sources, no keys: Google Trends daily RSS (India), Google News RSS (top + per-page searches), Reddit RSS (r/india,
r/IndiaTech, r/hinduism, r/TrueCrimeIndia..., spaced out because Reddit rate-limits). YouTube's trending page is gone
(yt-dlp: "redirected to home page", 17 Nov), so YouTube demand is measured later by ideas.py for each idea.
One planner call per page turns today's headlines into page-fit video ideas (or says none fit).
Output: knowledge/trends.json {page: [{topic, search, fit, why, source, day}]}; ideas.py adds them to the 10 candidates
with a trend bonus, so a fitting trend wins over an evergreen idea of the same score.
  python engine/trends.py            (timer studio-trends, daily 06:00 IST)"""
import html, json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux aarch64) StudioBot/1.0 (trend scout)"}
OUTF = os.path.join(ROOT, "knowledge", "trends.json")
GN = "https://news.google.com/rss/search?hl=en-IN&gl=IN&ceid=IN:en&q="
COMMON = [("google trends", "https://trends.google.com/trending/rss?geo=IN"),
          ("google news", "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"),
          ("reddit r/india", "https://www.reddit.com/r/india/top/.rss?t=day")]
PAGE = {
    "tech": [("news: tech", GN + "technology+smartphone+AI+india+when:2d"), ("news: gadgets", GN + "launch+phone+app+update+when:2d"),
             ("reddit r/IndiaTech", "https://www.reddit.com/r/IndiaTech/top/.rss?t=day"),
             ("reddit r/technology", "https://www.reddit.com/r/technology/top/.rss?t=day")],
    "katha": [("news: festivals", GN + "festival+puja+vrat+mandir+when:7d"), ("news: temples", GN + "temple+mythology+ramayan+mahabharat+when:7d"),
              ("reddit r/hinduism", "https://www.reddit.com/r/hinduism/top/.rss?t=week")],
    "raaz": [("news: mystery", GN + "mystery+unsolved+strange+india+when:7d"), ("news: history", GN + "history+secret+discovered+when:7d"),
             ("reddit r/UnresolvedMysteries", "https://www.reddit.com/r/UnresolvedMysteries/top/.rss?t=week")],
}
FIT = """You pick TRENDING topics for the faceless Shorts page "{name}" (format: {fmt}). Audience: Hindi-speaking India, 16-35.
Today's headlines and trending searches (India):
{heads}
Turn ONLY the ones that really fit this page into video ideas a viewer would click TODAY. The idea explains or tells a
story around the trend (how it works / the real story / the old legend behind it), curiosity first. Skip politics,
elections, communal topics, anything that questions the purity or character of deities or sacred figures or could hurt
religious feelings (Katha must stay respectful), celebrity gossip, deaths of real people, medical or money advice. Fit 0-10 (be strict:
8+ only if it fits the page AND is clearly trending). Return at most 6; return none if nothing fits.
JSON {{"ideas": [{{"topic": "...", "search": "3-5 English words people type on YouTube", "fit": 0, "why": "which headline + why now"}}]}}"""


def rss(url, n=25):
    try:
        x = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf8", "ignore")
    except Exception as e:
        log("trends fetch fail", url[:60], str(e)[:60]); return []
    items = re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", x, re.S)
    out = []
    for it in items[:n]:
        t = re.search(r"<title[^>]*>(.*?)</title>", it, re.S)
        if t:
            s = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>|<[^>]+>", "", t.group(1))).strip()
            traffic = re.search(r"<ht:approx_traffic>([^<]+)", it)
            out.append(s + (f" ({traffic.group(1)} searches)" if traffic else ""))
    return out


def run():
    import plan as planner
    from core import channel
    common = []
    for name, url in COMMON:
        common += [f"[{name}] {h}" for h in rss(url, 20)]; time.sleep(3)
    data = load(OUTF, {}) or {}
    day = time.strftime("%Y-%m-%d")
    for page, srcs in PAGE.items():
        heads = list(common)
        for name, url in srcs:
            heads += [f"[{name}] {h}" for h in rss(url, 15)]; time.sleep(4)
        try:
            ch = channel(page)
        except Exception:
            continue
        r = planner.ask(FIT.format(name=ch.get("name", page), fmt=ch.get("format", ""), heads="\n".join(heads[:110])), max_tokens=2000) or {}
        ideas = [dict(x, day=day, source="trend") for x in (r.get("ideas") or []) if isinstance(x, dict) and x.get("topic")]
        keep = [x for x in data.get(page, []) if x.get("day", "") >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))
                and not x.get("used") and x["topic"] not in {i["topic"] for i in ideas}]
        data[page] = sorted(ideas + keep, key=lambda x: -float(x.get("fit") or 0))[:12]
        log("trends", page, len(heads), "headlines ->", len(ideas), "ideas:", "; ".join(f"{x['topic'][:50]} ({x.get('fit')})" for x in ideas[:4]))
    save(OUTF, data)
    return data


def fresh(page):
    """Unused trend ideas from the last 3 days, best fit first (ideas.py)."""
    lim = time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))
    return [x for x in (load(OUTF, {}) or {}).get(page, []) if x.get("day", "") >= lim and not x.get("used") and float(x.get("fit") or 0) >= 6]


def mark_used(page, topic):
    data = load(OUTF, {}) or {}
    for x in data.get(page, []):
        if x.get("topic") == topic:
            x["used"] = time.strftime("%Y-%m-%d")
    save(OUTF, data)


if __name__ == "__main__":
    for p, v in run().items():
        print(p, [(x["topic"], x.get("fit")) for x in v[:5]])
