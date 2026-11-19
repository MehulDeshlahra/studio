"""Indian clipping platforms watcher (19 Nov, for Cut Capsule Hindi). On 19 Nov they had no paid campaigns: ClipConnect
1 XP-only challenge, Vyuzz "0 campaigns live now", Dashrize only samples. Daily: read each, count REAL paid campaigns
(rupee / dollar rate, not XP, not "Sample"), keep them in ~/studio-out/indiawatch.json and Telegram the owner the first
time a site has one ("sign up / join now"). ClipConnect needs the owner's login (the laptop's saved browser profile).
  python engine/indiawatch.py            (timer studio-indiawatch, daily 11:10)"""
import json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import OUT, log, load, save, telegram

STATE = os.path.join(OUT, "indiawatch.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"}


def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8", "ignore")


def vyuzz():
    t = re.sub(r"<[^>]+>", " ", _get("https://vyuzz.com/"))
    m = re.search(r"(\d+)\s+campaigns?\s+live\s+now", t)
    return {"live": int(m.group(1)) if m else None, "note": "public home page counter"}


def dashrize():
    t = _get("https://dashrize.com/")
    real = len(re.findall(r"₹[\d,]+\s*/\s*1[MK] views(?![^<]{0,80}Sample)", t))
    samples = len(re.findall(r"Sample\s*·", t))
    return {"live": max(0, real - samples), "samples": samples, "note": "home page cards marked Sample are not campaigns"}


def clipconnect():
    """Logged-in campaign marketplace through the laptop (owner's ClipConnect login in the saved profile)."""
    import laptop
    if not laptop.available():
        return {"live": None, "note": "laptop off"}
    d = laptop.job({"kind": "whop", "cmd": "look", "args": ["https://app.clipconnect.in/campaigns"]}, "india clipconnect", wait=600)
    r = load(os.path.join(d, "result.json"), {}) or {}
    t = r.get("text") or ""
    if re.search(r"\b(log ?in|sign ?in)\b", t[:600], re.I) and "MARKETPLACE" not in t.upper():
        return {"live": None, "note": "ClipConnect login expired: owner logs in once in the robot window"}
    blocks = re.split(r"\n(?=[A-Z0-9][A-Z0-9 &:—!'’-]{12,}\n)", t)
    paid = [b for b in blocks if re.search(r"PER 1K VIEWS\s*\n\s*(₹|\$|RS)", b, re.I)]
    xp = [b for b in blocks if re.search(r"PER 1K VIEWS\s*\n\s*[\d.]+\s*XP", b, re.I)]
    return {"live": len(paid), "xp_only": len(xp), "titles": [b.split("\n")[0][:80] for b in paid][:10]}


def run():
    st = load(STATE, {}) or {}
    now = time.strftime("%Y-%m-%d %H:%M")
    news = []
    for name, fn, url in (("ClipConnect", clipconnect, "https://app.clipconnect.in/campaigns"), ("Vyuzz", vyuzz, "https://vyuzz.com"),
                          ("Dashrize", dashrize, "https://dashrize.com")):
        try:
            r = fn()
        except Exception as e:
            r = {"live": None, "note": "read failed: " + str(e)[:100]}
        prev = (st.get(name) or {}).get("live") or 0
        r["at"] = now
        st[name] = r
        log("indiawatch:", name, r)
        if (r.get("live") or 0) > prev:
            news.append(f"• {name}: {r['live']} paid campaign(s) live" + (f" ({', '.join(r.get('titles') or [])[:200]})" if r.get("titles") else "")
                        + f"\n  {url}")
    save(STATE, st)
    if news:
        telegram("🇮🇳 Indian clipping campaigns for Cut Capsule Hindi:\n" + "\n".join(news)
                 + "\nTell Kiro to sign up / join (one click from you).")


if __name__ == "__main__":
    run()
