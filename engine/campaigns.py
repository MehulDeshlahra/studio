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
BAD = re.compile(r"(casino|gambl|betting|\bbet\b|bet365|1win|1xbet|melbet|parimatch|stake\.com|\bstake\b|roobet|rollbit|"
                 r"onlyfans|nsfw|crypto pump|forex signal|sportsbook|candy\.?ai|ai girlfriend|ai companion|\bspicy\b|"
                 r"\b18\+ chat|adult chat|sugar daddy|poker|slot machine|roulette|blackjack|lottery|fantasy (sports|cricket) cash|"
                 r"rummy|teen patti|aviator game)", re.I)
# Cut Capsule speaks English / Hinglish: campaigns that require another language get no score
LANG = re.compile(r"(french|fran[cç]ais|arabic|عربي|espa[nñ]ol|spanish|portugu|brasil|deutsch|german|italian|italiano|"
                  r"turkish|t[uü]rk|japanese|korean|russian|polski|polish|vietnam|indonesia)", re.I)


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


API = BASE + "/api/campaign/campaigns/discover?collapseGroups=true&limit=50&view=summary"


def listing_api(max_pages=120):
    """19 Nov: the site's own JSON API (public, no login) pages through EVERY live campaign (1,500+), where the old page
    scrape saw 120. Rows are mapped to the fields the rest of this file uses; payouts come with it (no detail fetch)."""
    import urllib.parse
    seen, rows, url = set(), [], API
    for _ in range(max_pages):
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA, Accept="application/json")),
                                                  timeout=60).read().decode("utf-8", "ignore"))
        except Exception as e:
            log("campaigns: api page failed", str(e)[:100]); break
        for r in d.get("data") or []:
            if not r.get("id") or r["id"] in seen or r.get("status") not in (None, "active"):
                continue
            seen.add(r["id"])
            m = r.get("metrics") or {}
            spent = (m.get("budgetSpentCents") or 0) / 100.0
            total = (r.get("budgetCents") or 0) / 100.0
            lo, hi = (r.get("cpmMinRateCents") or 0) / 100.0, (r.get("cpmMaxRateCents") or 0) / 100.0
            rows.append({
                "id": r["id"], "title": r.get("name"), "brand": r.get("organizationName"),
                "category": ((r.get("categories") or [{}])[0] or {}).get("id"),
                "categories": [c.get("id") for c in r.get("categories") or [] if isinstance(c, dict)],
                "description": r.get("description"), "availableBudgetRaw": max(0.0, total - spent), "budgetTotalRaw": total,
                "budgetSpentRaw": spent, "creatorCountRaw": m.get("creatorCount"), "submissionCountRaw": m.get("approvedSubmissionCount"),
                "paidOutRaw": (m.get("paidOutCents") or 0) / 100.0, "totalViews": m.get("totalViews"),
                "platforms": r.get("platforms") or [], "requiresApplication": bool(r.get("requiresApplication")),
                "geoPriced": bool(r.get("geoPriced")), "type": r.get("payoutType"),
                "ratePer1kLabel": f"${lo:.2f}" + (f"-{hi:.2f}" if hi > lo else ""),
                "organizationProfileHandle": r.get("organizationProfileHandle"),
                "launchedAtMs": r.get("launchDate"),
                # country-priced campaigns (geoPriced, SEGA) leave the per-platform rate empty: use the campaign's top rate
                "payout": [{"platform": p.get("platform"), "rate_cents": p.get("rateCents") or r.get("cpmMaxRateCents") or r.get("primaryPayoutCents"),
                            "max_cents": p.get("maxPayoutCents"), "min_cents": p.get("minPayoutCents")}
                           for p in r.get("payouts") or [] if isinstance(p, dict)]
                          or [{"platform": pl, "rate_cents": r.get("cpmMaxRateCents") or r.get("primaryPayoutCents"), "max_cents": None,
                               "min_cents": None} for pl in r.get("platforms") or []],
                "detail_at": time.time(),
            })
        cur = (d.get("pagination") or {}).get("nextCursor")
        if not cur or not d.get("data"):
            break
        url = API + "&cursor=" + urllib.parse.quote(cur)
        time.sleep(0.5)
    return rows


def listing():
    rows = listing_api()
    if len(rows) >= 50:
        return rows
    seen, rows = set(), []                         # fallback: the old page scrape (120 campaigns)
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
    ids = lambda xs: [x.get("id") if isinstance(x, dict) else str(x) for x in (xs or []) if x]
    cats = ids(next((o["categories"] for o in _objs(html, "categories") if isinstance(o.get("categories"), list) and o["categories"]
                     and isinstance(o["categories"][0], dict)), []))
    types = ids(next((o["contentTypes"] for o in _objs(html, "contentTypes") if isinstance(o.get("contentTypes"), list)), []))
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
    if LANG.search(f"{c.get('title', '')} {c.get('brand', '')}"):
        return 0, ["needs another language (French/Arabic/...)"]
    if rate <= 0:
        return 0, ["no pay per view (flat / influencer deal)"]
    is_clip = "clipping" in (c.get("types") or []) or "clip" in text.lower()
    s_rate = min(1.0, rate / 2.0)                                 # $2/1K = full marks
    s_cap = 1.0 if not cap else min(1.0, cap / 100.0)             # a $35 cap limits what a hit can earn
    s_left = min(1.0, left / 3000.0) * min(1.0, runway / 7.0)    # $3K+ left and a week of runway
    comp = (c.get("creatorCountRaw") or 0) / max(1.0, left / 100.0)
    s_comp = 1.0 / (1.0 + comp / 3.0)
    sc = 100 * (0.35 * s_rate + 0.15 * s_cap + 0.3 * s_left + 0.2 * s_comp) * fit * (1.0 if is_clip else 0.6)
    # 19 Nov: money actually paid out to clippers = the campaign approves and pays (ClippingAlpha's best signal)
    paid = float(c.get("paidOutRaw") or 0)
    if len(hist) >= 2 and hist[-1].get("paid", 0) > hist[0].get("paid", 0):
        sc *= 1.1; why.append(f"paying now (+${hist[-1].get('paid', 0) - hist[0].get('paid', 0):,.0f})")
    elif paid > 0:
        why.append(f"${paid:,.0f} paid out so far")
    sc = min(100, sc)
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
        for k in ("payout", "categories", "geoPriced", "paidOutRaw", "totalViews", "detail_at"):   # API rows carry these
            if r.get(k) is not None:
                c[k] = r[k]
        c["url"] = f"{BASE}/c/campaigns/{r['id']}"
        c["last_seen"] = now
        c["hist"] = ([h for h in c["hist"] if now - h["t"] < 7 * 86400] + [{"t": now, "spent": r.get("budgetSpentRaw") or 0,
                                                                            "left": r.get("availableBudgetRaw") or 0,
                                                                            "paid": r.get("paidOutRaw") or 0}])[-60:]
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
    # 19 Nov: 1,500 campaigns now (was 120): first run marks them all as seen, digests only list really new ones (>= 75)
    first_full = not st.get("api_seeded")
    if first_full:
        for k, v in live.items():
            v["told"] = v.get("told") or now
        st["api_seeded"] = now
    new = [(k, v) for k, v in ranked if v.get("score", 0) >= 75 and not v.get("told") and k not in joined]
    if new:
        msg = ["💸 New clipping campaigns (whopbot joins the best ones itself, nothing to do):"]
        for k, v in new[:6]:
            msg.append(f"• {v['score']}/100 {v.get('brand') or ''}: {v.get('title', '')[:70]}\n  {', '.join(v['why'][:5])}\n  {v['url']}")
            v["told"] = now

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
