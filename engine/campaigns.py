"""Campaign watcher (19 Nov, owner: "build everything, maximum money"). Reads the public Whop Content Rewards directory
(contentrewards.com/c/discover, data embedded in the page, no login, no paid scraper), ranks the clipping campaigns we
can run on Cut Capsule, tracks budget burn, and tells the owner which ones to join.

  python engine/campaigns.py [--report]      (timer studio-campaigns, every 6 h; --report = Telegram digest now)

Score (0-100) = money per clip we can expect x chance the budget lasts x fit:
  rate per 1K on Instagram/YouTube (our platforms), per-clip cap, budget left and days of runway at the current burn,
  competition (creators per $ left), fit (gaming / entertainment / podcast / streamer > software ads), no pre-approval.
Output: ~/studio-out/campaigns.json (all, with history), knowledge/campaigns.md (ranked table), Telegram digest of NEW
campaigns scoring >= 60 (once each) + a daily top 5. Joining = the owner's click (sign-up); then he adds the source in the
dashboard (Channels > Cut Capsule sources) and engine/clipwatch.py clips it automatically."""
import json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, telegram

BASE = "https://contentrewards.com"
PAGES = ["/c/discover/clipping", "/c/discover"]
STORE = os.path.join(OUT, "campaigns.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"}
OUR_PLATFORMS = ("instagram", "youtube")             # where Cut Capsule posts (Facebook is not paid by these campaigns)
FIT = {"gaming": 1.0, "entertainment": 1.0, "streaming": 1.0, "podcast": 0.95, "music": 0.8, "sports": 0.85, "comedy": 1.0,
       "lifestyle": 0.7, "education": 0.7, "business": 0.65, "finance": 0.6, "technology": 0.5, "crypto": 0.3, "betting": 0.0,
       "gambling": 0.0, "adult": 0.0}
BAD = re.compile(r"\b(casino|gambl|betting|bet365|stake\.com|onlyfans|nsfw|crypto pump|forex signal)\b", re.I)


def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8", "ignore")


def _objs(html, key):
    """Every JSON object in the page's embedded data that contains `key`."""
    s = html.replace('\\"', '"').replace("\\\\", "\\")
    out = []
    for m in re.finditer(re.escape(f'"{key}"'), s):
        i, depth = m.start(), 0
        while i > 0:
            c = s[i]
            if c == "}":
                depth += 1
            elif c == "{":
                if depth == 0:
                    break
                depth -= 1
            i -= 1
        j, depth = i, 0
        while j < len(s):
            c = s[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        try:
            out.append(json.loads(s[i:j + 1]))
        except ValueError:
            pass
    return out


def listing():
    seen, rows = set(), []
    for p in PAGES:
        try:
            html = _get(BASE + p)
        except Exception as e:
            log("campaigns: fetch failed", p, str(e)[:100]); continue
        for d in _objs(html, "ratePer1kLabel"):
            if d.get("id") and d["id"] not in seen:
                seen.add(d["id"]); rows.append(d)
    return rows


def detail(cid):
    """Per-platform rate (cents per 1K) and payout cap, content types, categories, pre-approval."""
    try:
        html = _get(f"{BASE}/c/campaigns/{cid}")
    except Exception as e:
        return {"error": str(e)[:100]}
    d = next((o for o in _objs(html, "payoutModel") if o.get("payoutModel") is not None), {})
    pm = d.get("payoutModel") or []
    cats = [c.get("id") for c in (next((o for o in _objs(html, "categories") if o.get("categories")), {}).get("categories") or [])]
    types = [c.get("id") for c in (next((o for o in _objs(html, "contentTypes") if o.get("contentTypes")), {}).get("contentTypes") or [])]
    return {"payout": [{"platform": x.get("platform"), "rate_cents": x.get("rate"), "max_cents": x.get("maxPayout"),
                        "min_cents": x.get("minPayout")} for x in pm if isinstance(x, dict)],
            "pre_approval": bool((d.get("requirement") or {}).get("preApproval")), "categories": cats, "types": types}


def score(c):
    """0-100 and the reasons."""
    why = []
    pay = [p for p in (c.get("payout") or []) if p.get("platform") in OUR_PLATFORMS]
    if not pay:
        return 0, ["not paid on Instagram or YouTube"]
    rate = max((p.get("rate_cents") or 0) for p in pay) / 100.0                     # $ per 1K
    cap = max((p.get("max_cents") or 0) for p in pay) / 100.0 or None                 # $ per clip
    left = float(c.get("availableBudgetRaw") or 0)
    hist = c.get("hist") or []
    burn = 0.0
    if len(hist) >= 2 and hist[-1]["t"] > hist[0]["t"]:
        burn = max(0.0, (hist[-1]["spent"] - hist[0]["spent"]) / ((hist[-1]["t"] - hist[0]["t"]) / 86400))
    runway = left / burn if burn > 0 else (99 if left > 0 else 0)
    cats = [str(x).lower() for x in (c.get("categories") or [])] + [str(c.get("category") or "").lower()]
    fit = max([FIT.get(k, 0.6) for k in cats if k] or [0.6])
    text = f"{c.get('title', '')} {c.get('description', '')} {c.get('brand', '')}"
    if BAD.search(text):
        return 0, ["gambling / adult / pump content: never"]
    is_clip = "clipping" in (c.get("types") or []) or "clip" in text.lower()
    s_rate = min(1.0, rate / 2.0)                                 # $2/1K = full marks
    s_cap = 1.0 if not cap else min(1.0, cap / 100.0)             # a $35 cap limits what a hit can earn
    s_left = min(1.0, left / 3000.0) * min(1.0, runway / 7.0)    # $3K+ left and a week of runway
    comp = (c.get("creatorCountRaw") or 0) / max(1.0, left / 100.0)
    s_comp = 1.0 / (1.0 + comp / 3.0)
    sc = 100 * (0.35 * s_rate + 0.15 * s_cap + 0.3 * s_left + 0.2 * s_comp) * fit * (1.0 if is_clip else 0.6)
    if c.get("pre_approval") or c.get("requiresApplication"):
        sc *= 0.85; why.append("needs approval first")
    why = [f"${rate:.2f}/1K", f"cap ${cap:.0f}/clip" if cap else "no cap", f"${left:,.0f} left",
           f"~{runway:.0f} days runway" if burn else "no spend yet", f"{c.get('creatorCountRaw') or 0} creators",
           (c.get("category") or "?")] + why + ([] if is_clip else ["not a clipping campaign (UGC/other)"])
    return round(sc), why


def run(report=False):
    st = load(STORE, {}) or {}
    st.setdefault("c", {})
    rows = listing()
    if not rows:
        log("campaigns: nothing read (page changed or blocked)"); return st
    now = time.time()
    for r in rows:
        c = st["c"].setdefault(r["id"], {"first_seen": now, "hist": []})
        c.update({k: r.get(k) for k in ("title", "brand", "category", "description", "availableBudgetRaw", "budgetTotalRaw",
                                         "budgetSpentRaw", "creatorCountRaw", "submissionCountRaw", "platforms", "requiresApplication",
                                         "ratePer1kLabel", "type", "organizationProfileHandle", "launchedAtMs")})
        c["url"] = f"{BASE}/c/campaigns/{r['id']}"
        c["last_seen"] = now
        c["hist"] = ([h for h in c["hist"] if now - h["t"] < 7 * 86400] + [{"t": now, "spent": r.get("budgetSpentRaw") or 0,
                                                                            "left": r.get("availableBudgetRaw") or 0}])[-60:]
        if not c.get("detail_at") or now - c["detail_at"] > 86400:
            d = detail(r["id"])
            if "error" not in d:
                c.update(d); c["detail_at"] = now
            time.sleep(1.5)
        c["score"], c["why"] = score(c)
    live = {k: v for k, v in st["c"].items() if now - v.get("last_seen", 0) < 2 * 86400}
    ranked = sorted(live.items(), key=lambda kv: -kv[1].get("score", 0))
    joined = {s.get("campaign_id") for s in ((load(os.path.join(ROOT, "channels", "cutcapsule", "sources.json"), {}) or {})
                                             .get("sources") or {}).values()}
    new = [(k, v) for k, v in ranked if v.get("score", 0) >= 60 and not v.get("told") and k not in joined]
    if new:
        msg = ["💸 New clipping campaigns worth joining (Cut Capsule):"]
        for k, v in new[:6]:
            msg.append(f"• {v['score']}/100 {v.get('brand') or ''}: {v.get('title', '')[:70]}\n  {', '.join(v['why'][:5])}\n  {v['url']}")
            v["told"] = now
        msg.append("Join on Whop (your click), then paste the campaign link + source channel in the dashboard: I clip it automatically.")
        telegram("\n".join(msg)[:3900])
    if report:
        top = [f"{v['score']} · {v.get('brand') or ''} · {v.get('title', '')[:60]} · {', '.join(v['why'][:3])}" for k, v in ranked[:5]]
        telegram("📊 Top clipping campaigns today:\n" + "\n".join(top))
    lines = ["# Clipping campaigns (engine/campaigns.py, " + time.strftime("%Y-%m-%d %H:%M") + ")",
             f"{len(live)} live on contentrewards.com. Score = rate x cap x budget left/runway x competition x fit (our platforms: IG, YT).",
             "", "| score | brand | campaign | why | joined | link |", "|---|---|---|---|---|---|"]
    for k, v in ranked[:40]:
        lines.append(f"| {v.get('score', 0)} | {v.get('brand') or ''} | {str(v.get('title', ''))[:60]} | {'; '.join(v.get('why', [])[:6])} | "
                     f"{'yes' if k in joined else ''} | {v['url']} |")
    open(os.path.join(ROOT, "knowledge", "campaigns.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    st["updated"] = now
    save(STORE, st)
    log(f"campaigns: {len(rows)} read, {len(live)} live, {len(new)} new worth joining; top", [(v['score'], v.get('title', '')[:40]) for k, v in ranked[:3]])
    return st


if __name__ == "__main__":
    run("--report" in sys.argv)
