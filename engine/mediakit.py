"""Media kits + SEO for scrollhouse.in (MONEY.md "Brand readiness"; owner 19 Nov: automate everything).
Called at the end of site.py (daily 09:05). Writes:
  docs/kit/<page>.html   one brand-facing page per live page: logo, numbers (only once they exist), audience (measured
                         from Instagram once the page has 100 followers, else the stated target), formats, brand fit,
                         brand safety, best reels, how to book
  docs/sitemap.xml, docs/robots.txt
  knowledge/ratecard.md  INTERNAL draft rate card from real views (never published; Mehul approves before any quote)
  knowledge/audience.json  measured Instagram audience per page (age, gender, country, city)
No prices on the public site. Rates need >= 3 posted reels with views."""
import html, json, os, re, statistics, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, load, save, log

DOCS = os.path.join(ROOT, "docs")
DOMAIN = "scrollhouse.in"
FIT = {  # brand categories that sponsor each niche (MONEY.md section 2, checked against knowledge/brands.json)
    "tech": ["Phones and gadgets", "Apps: finance, edtech, VPN, AI tools", "Telecom and broadband", "Laptops and accessories"],
    "katha": ["Devotional and kundli apps", "Puja items and ayurveda", "Spiritual books and audio", "Pilgrim travel"],
    "raaz": ["Story and audio apps", "OTT thrillers and web series", "Mobile games", "Books and publishing"],
    "jain": ["Books and audio", "Pilgrim travel", "Food and wellness brands that respect Jain diet", "Devotional apps"],
    "finance": ["Banks and cards", "UPI and payment apps", "Insurance and tax apps", "Credit and savings tools"],
}
FORMATS = ["Sponsored reel: your product inside an original reel", "Series sponsor: your name on every episode",
           "Story frames with your link on the day the reel goes live", "Cross-post on Instagram, Facebook and YouTube Shorts"]


def esc(s):
    return html.escape(str(s or ""))


def fmt(n):
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.1f}K" if n >= 1e4 else f"{int(n):,}"


def _css():
    try:
        t = open(os.path.join(DOCS, "index.html"), encoding="utf-8").read()
        return re.search(r"<style>.*?</style>", t, re.S).group(0)
    except Exception:
        return "<style>body{background:#0b0c10;color:#e9ecf1;font:16px system-ui}</style>"


def audience(cid, followers):
    """Measured audience from the Instagram API; only once the page has 100 followers (Meta's own limit)."""
    store = load(os.path.join(ROOT, "knowledge", "audience.json"), {}) or {}
    if followers >= 100 and time.time() - store.get(cid, {}).get("t", 0) > 6 * 86400:
        try:
            import publish
            acc = publish.resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
            res = {"t": time.time()}
            for br in ("age", "gender", "country", "city"):
                d = publish._req(f"{publish.G}/{acc['ig_user_id']}/insights?metric=follower_demographics&period=lifetime"
                                 f"&metric_type=total_value&breakdown={br}&access_token={acc['page_token']}")
                rows = d["data"][0]["total_value"]["breakdowns"][0]["results"]
                tot = sum(r["value"] for r in rows) or 1
                res[br] = sorted(([r["dimension_values"][0], round(100 * r["value"] / tot)] for r in rows), key=lambda x: -x[1])[:5]
            store[cid] = res
            save(os.path.join(ROOT, "knowledge", "audience.json"), store)
        except Exception as e:
            log("mediakit: audience", cid, str(e)[:150])
    return store.get(cid)


def ratecard(ps):
    lines = ["# Rate card (INTERNAL draft, auto-written by engine/mediakit.py; Mehul approves every quote)",
             f"Updated {time.strftime('%d %b %Y %H:%M')}. Rule of thumb from MONEY.md: Rs 0.3 to 1 per expected view; expected views = "
             "median views of the page's posted reels. Needs >= 3 posted reels with views.", ""]
    for p in ps:
        v = p["vs"]
        if len(v) < 3:
            lines.append(f"- {p['name']}: not enough reels with views yet ({len(v)}/3)")
            continue
        med = statistics.median(v)
        lo, hi = max(500, round(med * .3 / 500) * 500), max(1000, round(med * 1.0 / 500) * 500)
        lines.append(f"- {p['name']}: median {fmt(med)} views over {len(v)} reels -> one sponsored reel Rs {lo:,} to Rs {hi:,}"
                     f"; series sponsor (5 parts) about 4x the low end; network bundle: sum minus 15%")
    open(os.path.join(ROOT, "knowledge", "ratecard.md"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")


def kit(p, css, aud, logo):
    cid = p["id"]
    nums = ('<p class="soon">Launching 20 Nov 2026: numbers appear here the day they exist.</p>' if not (p["followers"] or p["views"] or p["posts"])
            else f'<div class="nums"><div><b>{fmt(p["followers"])}</b><span>followers</span></div><div><b>{fmt(p["views"])}</b><span>views</span></div>'
                 f'<div><b>{p["posts"]}</b><span>reels</span></div></div>')
    if aud:
        ar = "".join(f"<li><b>{esc(k.title())}</b>: " + ", ".join(f"{esc(n)} {v}%" for n, v in aud[k]) + "</li>"
                     for k in ("age", "gender", "country", "city") if aud.get(k))
        audhtml = f'<p>Measured from Instagram follower data:</p><ul class="best">{ar}</ul>'
    else:
        audhtml = (f'<p>Target audience: India, {esc(p["lang"])}-speaking, ages 16 to 35. Measured age, gender and city data '
                   f'is added here automatically once the page passes 100 followers.</p>')
    best = "".join(f'<li>{esc(b["title"][:80])} <b>{fmt(b["views"])} views</b></li>' for b in p["best"]) or "<li>Best reels appear here once they have views.</li>"
    safe = "".join(f"<li>{esc(r)}</li>" for r in p["rules"][:6])
    fit = "".join(f"<li>{esc(x)}</li>" for x in FIT.get(cid, []))
    fm = "".join(f"<li>{esc(x)}</li>" for x in FORMATS)
    img = f'<img src="../img/{cid}.webp" alt="{esc(p["name"])}" width="96" height="96" style="border-radius:50%;float:right;margin:0 0 12px 18px">' if logo else ""
    ld = json.dumps({"@context": "https://schema.org", "@type": "Organization", "name": p["name"], "url": f"https://{DOMAIN}/kit/{cid}.html",
                     "sameAs": [f"https://instagram.com/{p['ig']}"] + ([f"https://youtube.com/@{p['yt']}"] if p["yt"] else []),
                     "parentOrganization": {"@type": "Organization", "name": "Scroll House", "url": f"https://{DOMAIN}"}})
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(p['name'])}: media kit | Scroll House</title><meta name="description" content="{esc(p['about'])}">
<meta property="og:title" content="{esc(p['name'])}: media kit"><meta property="og:description" content="{esc(p['about'])}">
{('<meta property="og:image" content="https://' + DOMAIN + '/img/' + cid + '.webp">') if logo else ''}
<script type="application/ld+json">{ld}</script>{css}</head><body><div class="wrap">
<header><div class="logo"><i></i><a href="../">Scroll House</a></div>{img}
<h1 style="font-size:clamp(30px,5vw,48px)">{esc(p['name'])} <span>media kit</span></h1>
<p class="lead">{esc(p['tagline'])} {esc(p['about'])}</p>{nums}
<p class="links"><a href="https://instagram.com/{esc(p['ig'])}">Instagram @{esc(p['ig'])}</a>{(' · <a href="https://youtube.com/@' + esc(p['yt']) + '">YouTube</a>') if p['yt'] else ''}</p></header>
<h2>Audience</h2>{audhtml}
<h2>Best reels</h2><ul class="best">{best}</ul>
<h2>Brands that fit</h2><ul class="best">{fit}</ul>
<h2>What we offer</h2><ul class="best">{fm}</ul>
<h2>Brand safety</h2><ul class="best">{safe}<li>Original content only, no reposts, no fake engagement.</li></ul>
<h2>Book</h2><p>Rates depend on the page's real views and are shared on request.</p>
<p><a class="btn" href="{esc('mailto:' + p['email']) if p.get('email') else 'https://instagram.com/scrollhouse.in'}">Message Scroll House</a></p>
<footer>Scroll House · {DOMAIN} · updated {time.strftime('%d %b %Y')}</footer></div></body></html>"""


def run(ps_site):
    """ps_site: the list from site.pages(). Adds the rule list + per-reel views the kit and ratecard need."""
    css = _css()
    os.makedirs(os.path.join(DOCS, "kit"), exist_ok=True)
    ps = []
    for p in ps_site:
        ch = load(os.path.join(ROOT, "channels", p["id"], "channel.json"), {}) or {}
        done = load(os.path.join(ROOT, "channels", p["id"], "done.json"), []) or []
        vs = [int((d.get("stats") or {}).get("views") or 0) for d in done if d.get("status") == "posted" and (d.get("stats") or {}).get("views")]
        ps.append(dict(p, rules=ch.get("rules") or [], vs=vs))
    for p in ps:
        logo = os.path.exists(os.path.join(DOCS, "img", p["id"] + ".webp"))
        open(os.path.join(DOCS, "kit", p["id"] + ".html"), "w", encoding="utf-8", newline="\n").write(kit(p, css, audience(p["id"], p["followers"]), logo))
    urls = [f"https://{DOMAIN}/"] + [f"https://{DOMAIN}/kit/{p['id']}.html" for p in ps]
    open(os.path.join(DOCS, "sitemap.xml"), "w", encoding="utf-8", newline="\n").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join(f"<url><loc>{u}</loc><lastmod>{time.strftime('%Y-%m-%d')}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    open(os.path.join(DOCS, "robots.txt"), "w", encoding="utf-8", newline="\n").write(f"User-agent: *\nAllow: /\nSitemap: https://{DOMAIN}/sitemap.xml\n")
    ratecard(ps)
    linkpages(ps, css)
    return len(ps)


def linkpages(ps, css):
    """scrollhouse.in/go/<page>: the link-in-bio / website for each page (viewer-facing): follow buttons and the sister pages
    (cross-promotion inside the network). One URL per page for IG bio, FB website, YouTube description."""
    os.makedirs(os.path.join(DOCS, "go"), exist_ok=True)
    for p in ps:
        acc = load(os.path.expanduser(f"~/.studio-accounts/{p['id']}.json"), {}) or {}
        btn = [("Instagram", f"https://instagram.com/{p['ig']}")]
        if acc.get("page_id"):
            btn.append(("Facebook", f"https://facebook.com/{acc['page_id']}"))
        if p["yt"]:
            btn.append(("YouTube", f"https://youtube.com/@{p['yt']}"))
        b = "".join(f'<p><a class="btn" style="display:block;text-align:center" href="{esc(u)}">{esc(n)}</a></p>' for n, u in btn)
        sis = "".join(f'<li><a href="{q["id"]}.html">{esc(q["name"])}</a>: {esc(q["genre"])}</li>' for q in ps if q["id"] != p["id"])
        logo = (f'<img src="../img/{p["id"]}.webp" alt="" width="96" height="96" style="border-radius:50%;display:block;margin:0 auto 12px">'
                if os.path.exists(os.path.join(DOCS, "img", p["id"] + ".webp")) else "")
        doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
               f'<title>{esc(p["name"])}</title><meta name="robots" content="noindex">{css}</head><body><div class="wrap" style="max-width:480px;text-align:center">'
               f'<header style="padding:40px 0 10px;border:0">{logo}<h1 style="font-size:30px;margin:8px 0">{esc(p["name"])}</h1>'
               f'<p class="lead" style="font-size:16px">{esc(p["tagline"])}</p></header>{b}'
               f'<h2 style="font-size:18px;margin-top:34px">More from Scroll House</h2><ul class="best" style="text-align:left">{sis}</ul>'
               f'<footer>A Scroll House page · {DOMAIN}</footer></div></body></html>')
        open(os.path.join(DOCS, "go", p["id"] + ".html"), "w", encoding="utf-8", newline="\n").write(doc)
