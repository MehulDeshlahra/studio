"""scrollhouse.in: the parent brand site (owner 18 Nov: "a website where we showcase things"). Static, free (GitHub Pages
serves docs/ of this repo), rebuilt daily from live numbers: knowledge/money.json (followers/subs), channels/*/done.json
(posted reels + stats). Every channel with a handle and status pilot/active/live is listed automatically, so a new page
appears on the site the day it exists. Brands see: the network, each page's audience and reach, best reels, what we offer.
  python engine/site.py          writes docs/index.html + docs/CNAME (sync.py commits it)"""
import html, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, load

DOCS = os.path.join(ROOT, "docs")
DOMAIN = "scrollhouse.in"
BRAND = {"name": "Scroll House", "ig": "scrollhouse.in", "yt": "scrollhouse", "email": "",
         "line": "A network of original short-video pages. Every genre, every audience, one booking."}
YT = {"tech": "kaise.tech.official", "katha": "puraankikatha", "raaz": "aagesuno"}   # verified 18 Nov (publish launch check)
LIVE = ("pilot", "active", "live", "live (warm-up)")
GENRE = {"tech": "Tech explainers", "katha": "Mythology", "raaz": "Fiction serials",
    "jain": "Jain stories",
    "finance": "Money explainers",
}
BLURB = {   # what a viewer or a brand reads (channel.json "site_blurb" wins when set)
    "tech": "How everyday tech really works, in under a minute: phones, apps, AI, the internet. Clear visuals, real brands, no jargon.",
    "katha": "Stories from the Puranas and the epics, told the way grandparents tell them, with the source named in every reel.",
    "raaz": "Original mystery and drama serials, one part a day, every part ending on a cliffhanger. The audience comes back daily.",
    "jain": "Stories of the Tirthankaras, Jain saints and kings, with the source named in every reel. Calm, respectful, one story a day.",
    "finance": "Money made simple for young India: saving, credit, tax, UPI and scams, explained in under a minute with real numbers. Education, not advice.",
}


def esc(s):
    return html.escape(str(s or ""))


def pages():
    money = load(os.path.join(ROOT, "knowledge", "money.json"), {}) or {}
    out = []
    for cid in sorted(os.listdir(os.path.join(ROOT, "channels"))):
        c = load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}
        if not c.get("handle") or str(c.get("status", "")) not in LIVE:
            continue
        m = (money.get(cid) or [{}])[-1]
        done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
        posted = [d for d in done if d.get("status") == "posted"]
        views = sum(int((d.get("stats") or {}).get("views") or 0) for d in posted)
        best = sorted([d for d in posted if (d.get("stats") or {}).get("views")], key=lambda d: -d["stats"]["views"])[:3]
        name = str(c.get("name", cid)).split(" (")[0]
        out.append({"id": cid, "name": name, "genre": GENRE.get(cid, c.get("genre", "")), "tagline": c.get("tagline", ""),
                    "about": c.get("site_blurb") or BLURB.get(cid, ""),
                    "ig": str(c.get("handle_instagram") or c.get("handle") or "").lstrip("@"),
                    "yt": str(c.get("handle_youtube") or YT.get(cid, "")).lstrip("@"),
                    "lang": "English" if str(c.get("lang") or c.get("language") or "hi").lower().startswith("en") else "Hindi",
                    "followers": sum(int((m.get(p) or {}).get(k) or 0) for p, k in (("ig", "followers"), ("fb", "followers"), ("yt", "subs"))),
                    "posts": len(posted), "views": views,
                    "best": [{"title": d.get("title", ""), "views": d["stats"]["views"], "url": (d.get("posted") or {}).get("ig_url") or ""} for d in best]})
    return out


def fmt(n):
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.1f}K" if n >= 1e4 else f"{n:,}"


def nums(p):
    """Numbers only once they exist (a row of zeros tells a brand nothing good)."""
    if not (p["followers"] >= 100 or p["views"] >= 1000):      # 19 Nov: 3 followers on a brand-facing page does not help us
        return '<p class="soon">Launching 20 Nov 2026</p>'
    return (f'<div class="nums"><div><b>{fmt(p["followers"])}</b><span>followers</span></div><div><b>{fmt(p["views"])}</b>'
            f'<span>views</span></div><div><b>{p["posts"]}</b><span>reels</span></div></div>')


def build():
    ps = pages()
    tf, tv, tp = sum(p["followers"] for p in ps), sum(p["views"] for p in ps), sum(p["posts"] for p in ps)
    cards = []
    for p in ps:
        links = f'<a href="https://instagram.com/{esc(p["ig"])}">Instagram @{esc(p["ig"])}</a>'
        if p["yt"]:
            links += f' · <a href="https://youtube.com/@{esc(p["yt"])}">YouTube</a>'
        best = "".join(f'<li>{esc(b["title"][:70])} <b>{fmt(b["views"])} views</b></li>' for b in p["best"])
        logo = f'<img src="img/{p["id"]}.webp" alt="" width="64" height="64" style="border-radius:50%;float:right;margin-left:12px">' if os.path.exists(os.path.join(DOCS, "img", p["id"] + ".webp")) else ""
        cards.append(f"""<article class="card">{logo}<div class="tag">{esc(p['genre'])} · {esc(p['lang'])}</div>
<h3>{esc(p['name'])}</h3><p class="tl">{esc(p['tagline'])}</p><p>{esc(p['about'])}</p>
{nums(p)}
{('<ul class="best">' + best + '</ul>') if best else ''}<p class="links">{links} · <a href="kit/{p["id"]}.html">Media kit</a></p></article>""")
    contact = (f'<a class="btn" href="mailto:{esc(BRAND["email"])}">{esc(BRAND["email"])}</a>' if BRAND["email"] else
               f'<a class="btn" href="https://instagram.com/{BRAND["ig"]}">Message @{BRAND["ig"]}</a>')
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scroll House: original short-video pages for every audience</title>
<meta name="description" content="{esc(BRAND['line'])}">
<meta property="og:title" content="Scroll House"><meta property="og:description" content="{esc(BRAND['line'])}">
<meta property="og:image" content="https://{DOMAIN}/og.png"><meta property="og:type" content="website"><meta property="og:url" content="https://{DOMAIN}/">
<meta name="twitter:card" content="summary_large_image"><link rel="canonical" href="https://{DOMAIN}/"><link rel="icon" href="img/scrollhouse.webp">
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#0b0c10;color:#e9ecf1;font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
a{{color:#ffd84d;text-decoration:none}}a:hover{{text-decoration:underline}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 22px}}
header{{padding:72px 0 40px;border-bottom:1px solid #ffffff14}}
.logo{{font-weight:800;letter-spacing:-1px;font-size:20px}}.logo i{{display:inline-block;width:12px;height:12px;border-radius:3px;background:#ffd84d;margin-right:10px}}
h1{{font-size:clamp(34px,6vw,60px);line-height:1.05;letter-spacing:-2px;margin:28px 0 14px}}h1 span{{color:#ffd84d}}
.lead{{font-size:19px;color:#b9c0cc;max-width:640px}}
.stats{{display:flex;gap:40px;flex-wrap:wrap;margin-top:34px}}.stats b{{display:block;font-size:34px;letter-spacing:-1px}}.stats span{{color:#8b93a3;font-size:14px}}
h2{{font-size:28px;letter-spacing:-1px;margin:56px 0 18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}}
.card{{background:#13151b;border:1px solid #ffffff14;border-radius:18px;padding:24px}}
.tag{{display:inline-block;font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#0b0c10;background:#ffd84d;border-radius:6px;padding:3px 9px}}
.card h3{{font-size:22px;margin:14px 0 2px}}.tl{{color:#ffd84d;margin:0 0 8px}}.card p{{color:#b9c0cc;margin:6px 0}}
.nums{{display:flex;gap:22px;margin:16px 0 8px}}.nums b{{display:block;font-size:22px}}.nums span{{font-size:12px;color:#8b93a3}}
.soon{{color:#ffd84d!important;font-weight:600;margin:16px 0 8px!important}}.best{{padding-left:18px;color:#b9c0cc;font-size:14px}}.links{{font-size:14px}}
.offer{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}}
.offer div{{background:#13151b;border:1px solid #ffffff14;border-radius:14px;padding:18px}}.offer b{{display:block;margin-bottom:4px}}.offer p{{margin:0;color:#b9c0cc;font-size:14px}}
.btn{{display:inline-block;background:#ffd84d;color:#0b0c10;font-weight:700;border-radius:10px;padding:12px 20px;margin-top:6px}}
footer{{margin:70px 0 40px;color:#6d7586;font-size:13px}}
</style></head><body><div class="wrap">
<header><div class="logo"><i></i>Scroll House</div>
<h1>Original short-video pages for <span>every audience</span>.</h1>
<p class="lead">{esc(BRAND['line'])} Daily, original Reels and Shorts in Hindi and English: tech, mythology, fiction serials, and more genres every month.</p>
<div class="stats"><div><b>{len(ps)}</b><span>pages</span></div>{(f'<div><b>{fmt(tf)}</b><span>followers across platforms</span></div><div><b>{fmt(tv)}</b><span>views</span></div><div><b>{tp}</b><span>reels published</span></div>') if (tf >= 100 or tv >= 1000) else '<div><b>3</b><span>platforms each: Instagram, YouTube, Facebook</span></div><div><b>Daily</b><span>new reels on every page</span></div>'}</div>
</header>
<h2>Our pages</h2><div class="grid">{''.join(cards)}</div>
<h2>Work with us</h2><div class="offer">
<div><b>Sponsored reel</b><p>Your product inside an original reel on the page that fits your audience.</p></div>
<div><b>Network bundle</b><p>One booking, several pages: reach different audiences at once.</p></div>
<div><b>Series partner</b><p>Present a whole story serial or explainer series, every episode.</p></div>
<div><b>Stories + link</b><p>Story frames with your link the day the reel goes live.</p></div>
</div><p>{contact}</p>
<footer>Scroll House · {DOMAIN} · numbers updated {time.strftime('%d %b %Y')}</footer>
</div></body></html>"""
    os.makedirs(DOCS, exist_ok=True)
    open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8", newline="\n").write(doc)
    open(os.path.join(DOCS, "CNAME"), "w", encoding="utf-8", newline="\n").write(DOMAIN + "\n")
    open(os.path.join(DOCS, ".nojekyll"), "w").write("")
    try:                                   # 19 Nov: per-page media kits, sitemap, internal rate card
        import mediakit
        mediakit.run(ps)
    except Exception as e:
        print("mediakit failed:", e)
    return len(ps)


if __name__ == "__main__":
    print("pages on the site:", build())
