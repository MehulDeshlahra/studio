"""Offer reels: "Comment KEYWORD, get the freebie in DM" (owner 19 Nov: these reels pull followers because the link comes
only after a follow). Research + rules: knowledge/comment-dm.md.

1. decide(ch, plan, job): about 1 in channel.json offers.every videos becomes an offer reel. One planner call turns the
   video's OWN script into a freebie (a save-able cheat sheet, or for story pages the video's picture as a wallpaper),
   picks a unique keyword, and adds a closing scene "Comment KEYWORD". Every number on the sheet must already be in the
   script (checked in code); finance stays education only.
2. build(ch, plan, job, assets): after the pictures exist, draws the freebie (HTML -> Chrome screenshot, or the wallpaper
   with the page handle), publishes it to the public repo offhours-lab/studio-media (offers/<page>/), registers the
   keyword in ~/studio-out/offers.json. dm.py reads that registry: keyword comment -> follow gate -> link.
"""
import glob, html, json, os, re, shutil, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log
import plan as planner

REG = os.path.join(OUT, "offers.json")
MEDIA = os.path.expanduser("~/studio-media")
RAW = "https://raw.githubusercontent.com/offhours-lab/studio-media/main/"
CHROME = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux-*/chrome-headless-shell")))
TAKEN = {"PART2", "PART", "AAGE", "LINK", "TECH", "PAISA", "MONEY", "KATHA", "DONE", "HI", "HELLO", "JAI", "JINENDRA"}

DESIGN = """You turn a finished {lang} Reels script of the page "{name}" into a FREE GIFT the viewer gets in DM after
commenting a keyword (and following the page). The gift must feel worth a comment: specific, practical, save-able.
SCRIPT (the only source of facts):
{script}
Kinds allowed on this page: {kinds}
- "sheet": a one-page cheat sheet / checklist of THIS video: 4-7 points the viewer will want later (steps to follow,
  documents to keep, what to say to the bank, settings to change...). Every fact and number must be in the script above:
  no new numbers, no new rules, no names of funds/stocks/apps to buy. Short lines, Hinglish in Roman script.
- "wallpaper": the video's own picture as an HD phone wallpaper (story pages only).
- "none": when this video has nothing a viewer would really want to keep.
A GIFT IS SOMETHING THEY WILL USE LATER: steps to claim a refund, documents to keep, what to say to the bank, the settings
to change, a puja / vrat vidhi, an aarti, a wallpaper of the deity. A recap or summary of the story or of the facts is
NOT a gift: then choose "wallpaper" (story pages) or "none". On a story page prefer "wallpaper" unless the script itself
gives a ritual or prayer the viewer can follow.
Return JSON:
{{"kind": "sheet|wallpaper|none",
 "keyword": "<ONE common word everyone can spell, CAPITALS, 3-8 letters, about the gift (no abbreviations or tech jargon), e.g. CHECKLIST, REFUND, PAPERS, WALLPAPER, AARTI; never {taken}>",
 "gift": "<what they get, 2-5 words Hinglish, e.g. 'refund checklist PDF', 'Shiv ji HD wallpaper'>",
 "title": "<sheet title, 2-6 words>",
 "items": [{{"head": "<2-5 words>", "text": "<one line, under 16 words>"}}],
 "wallpaper_scene": <scene number whose picture is the best wallpaper, 1-based, for wallpaper only>,
 "say": "<the spoken closing line, Hinglish, under 14 words, e.g. 'Ye poori checklist chahiye? Comment karo REFUND, main DM kar dunga.'>"}}"""


CHECK = """You check a free cheat sheet before it is sent to viewers. SCRIPT of the video (the only source):
{script}
SHEET "{gift}":
{lines}
1) List the line numbers that say anything the script does not state (a new fact, number, rule, deadline, website, step or
claim). Rewording is fine; new information is not.
2) Score 1-10 how much a typical viewer of this page would want this sheet enough to comment for it (10 = a practical tool
they will use: steps to claim money, a checklist to follow; 3 = a recap of facts they just watched).
Return JSON {{"unsupported": [numbers], "worth": number, "why": "<one line>"}}"""


def _cfg(ch):
    o = ch.get("offers") or {}
    return o if o.get("on") else None


def _script(plan):
    out = []
    for i, s in enumerate(plan.get("scenes", [])):
        bits = [s.get("vo", "")]
        for k in ("big", "sub", "title", "value", "label"):
            if s.get(k):
                bits.append(str(s[k]))
        for k in ("rows", "lines", "messages", "items"):
            for x in s.get(k) or []:
                bits.append(json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else str(x))
        if isinstance(s.get("total"), dict):
            bits.append(json.dumps(s["total"], ensure_ascii=False))
        out.append(f"{i + 1}. [{s.get('type')}] " + " | ".join(b for b in bits if b))
    return "\n".join(out)


def _nums(t):
    return {re.sub(r"[,\s]", "", n) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", str(t))}


def due(ch):
    """True when this video should be an offer reel: no offer among the page's last (every-1) videos."""
    c = _cfg(ch)
    if not c:
        return False
    every = max(2, int(c.get("every", 4)))
    done = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), []) or []
    recent = [d for d in done if d.get("status") not in ("rejected", "removed")][-(every - 1):]
    known = {d["job"] for d in done}
    building = [k for k, v in ((load(REG, {}) or {}).get(ch["id"]) or {}).items()
                if v.get("job") not in known and time.time() - v.get("t", 0) < 86400]     # an offer video still being built
    return not any(d.get("offer") for d in recent) and not building


def _register(cid, kw, entry):
    reg = load(REG, {}) or {}
    cur = reg.setdefault(cid, {}).get(kw) or {"stats": {"comments": 0, "asked": 0, "delivered": 0, "new_follows": 0}}
    cur.update(entry)
    reg[cid][kw] = cur
    save(REG, reg)


def decide(ch, plan, job, force=False):
    """Adds plan["offer"] + a closing 'Comment KEYWORD' scene. Returns True when the plan changed."""
    c = _cfg(ch)
    if not c or plan.get("offer") or plan.get("no_offer") or not (force or due(ch)):
        return False
    kinds = [k for k in (c.get("kinds") or ["sheet"]) if k in ("sheet", "wallpaper")] or ["sheet"]
    reg = load(REG, {}) or {}
    taken = TAKEN | set((reg.get(ch["id"]) or {}).keys())
    script = _script(plan)
    try:
        o = planner.ask(DESIGN.format(lang="Hindi" if ch.get("lang", "hi") == "hi" else "English", name=ch.get("name") or ch["id"],
                                      script=script[:7000], kinds=", ".join(kinds), taken=", ".join(sorted(taken))), max_tokens=2500)
    except Exception as e:
        log("offer design failed:", str(e)[:120]); return False
    if o.get("kind") == "none":
        log("offer: no gift worth a comment in this video -> normal reel"); return False
    kind = o.get("kind") if o.get("kind") in kinds else kinds[0]
    kw = re.sub(r"[^A-Z0-9]", "", str(o.get("keyword") or "").upper())[:12]
    if len(kw) < 3 or kw in taken:
        kw = (re.sub(r"[^A-Z]", "", str(o.get("gift") or "").upper().split()[0] if o.get("gift") else "") or "GIFT")[:8]
        n = 2
        base = kw
        while kw in taken or len(kw) < 3:
            kw = f"{base}{n}"; n += 1
    have = _nums(script)
    items = []
    for it in o.get("items") or []:
        if not isinstance(it, dict) or not it.get("text"):
            continue
        bad = _nums(f"{it.get('head', '')} {it['text']}") - have
        if bad:
            log("offer: dropped a sheet line with numbers not in the script", bad, repr(it["text"][:60])); continue
        items.append({"head": str(it.get("head") or "")[:40], "text": str(it["text"])[:140]})
    if kind == "sheet" and items:
        # 19 Nov test: a finance line said "the bank gets 30 more days for lost papers", not checked against the script.
        # A second, separate call checks every line against the script and scores the gift; weak gifts are dropped.
        try:
            v = planner.ask(CHECK.format(script=script[:7000], gift=o.get("gift", ""),
                                         lines="\n".join(f"{i + 1}. {x['head']}: {x['text']}" for i, x in enumerate(items))), max_tokens=1200)
            bad = {int(x) for x in (v.get("unsupported") or []) if str(x).isdigit()}
            if bad:
                log("offer: dropped lines the script does not say:", sorted(bad))
            items = [x for i, x in enumerate(items) if i + 1 not in bad]
            score = float(v.get("worth") or 0)
            if score < 7:
                log("offer: gift scored", score, "/10 (", str(v.get("why", ""))[:100], ") -> no offer on this video"); return False
        except Exception as e:
            log("offer check failed -> no offer:", str(e)[:100]); return False
    if kind == "sheet" and len(items) < 3:
        log("offer: sheet has", len(items), "checked lines -> no offer on this video"); return False
    gift = str(o.get("gift") or ("checklist" if kind == "sheet" else "HD wallpaper"))[:40]
    say = str(o.get("say") or "").strip()
    if kw not in say.upper():
        say = f"Ye {gift} chahiye? Comment karo {kw}, DM mein bhej dunga."
    plan["offer"] = {"kind": kind, "keyword": kw, "gift": gift, "title": str(o.get("title") or gift)[:60], "items": items[:7],
                     "wallpaper_scene": int(o.get("wallpaper_scene") or 1) if str(o.get("wallpaper_scene") or "1").isdigit() else 1,
                     "job": os.path.basename(job)}
    lab = ch.get("theme", {}).get("style") == "lab"
    scene = {"type": "title" if lab else "card", "big": f"Comment {kw}", "sub": f"{gift} DM mein 📩", "small": f"{gift} DM mein",
             "vo": say, "offer_cta": True, "label": "FREE"}
    if not lab:
        scene["prompt"] = "a gift box with soft warm light, simple background"
    scenes = plan["scenes"]
    # before the page's own goodbye scene when it has one (save / follow line), else last
    at = len(scenes) - 1 if scenes and re.search(r"save|follow|share", str(scenes[-1].get("vo", "")), re.I) else len(scenes)
    scenes.insert(at, scene)
    _register(ch["id"], kw, {"url": None, "gift": gift, "job": os.path.basename(job), "kind": kind, "t": time.time(),
                             "made": time.strftime("%Y-%m-%d %H:%M")})
    log("offer reel:", kw, "->", gift, f"({kind}, {len(items)} lines)")
    return True


SHEET = """<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#151a24;font-family:'Noto Sans',sans-serif;color:#111}}
.pg{{width:1080px;min-height:1920px;box-sizing:border-box;padding:90px 70px;background:linear-gradient(180deg,#0b0d12,#151a24)}}
.hd{{color:#fff;font-size:34px;letter-spacing:6px;opacity:.75}}
.t{{color:#fff;font-size:86px;font-weight:800;line-height:1.05;margin:24px 0 50px}}
.t b{{color:{acc}}}
.it{{background:#f6f4ef;border-radius:28px;padding:34px 40px;margin-bottom:26px;display:flex;gap:28px}}
.n{{flex:0 0 74px;height:74px;border-radius:50%;background:{acc};color:#111;font-size:40px;font-weight:800;display:flex;align-items:center;justify-content:center}}
.h{{font-size:40px;font-weight:800}} .x{{font-size:36px;line-height:1.35;margin-top:6px;color:#2a2d33}}
.ft{{color:#fff;font-size:34px;margin-top:50px;opacity:.8;line-height:1.5}} .ft b{{color:{acc}}}
</style></head><body><div class="pg"><div class="hd">{hud}</div><div class="t">{title}</div>{items}
<div class="ft">{foot}</div></div></body></html>"""


def _shot(html_doc, out):
    if not CHROME:
        raise RuntimeError("no headless chrome")
    tmp = out + ".html"
    open(tmp, "w", encoding="utf-8").write(html_doc)
    h = 1920 + max(0, html_doc.count('class="it"') - 5) * 260
    subprocess.run([CHROME[-1], "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", f"--window-size=1080,{h}",
                    f"--screenshot={out}", "file://" + tmp], capture_output=True, timeout=90)
    os.remove(tmp)
    if not os.path.exists(out) or os.path.getsize(out) < 5000:
        raise RuntimeError("screenshot failed")
    return out


def _sheet(ch, o, out):
    th = ch.get("theme") or {}
    acc = th.get("accent") or "#ffd84d"
    handle = ch.get("handle") or th.get("handle") or ""
    items = "".join(f'<div class="it"><div class="n">{i + 1}</div><div><div class="h">{html.escape(x["head"])}</div>'
                    f'<div class="x">{html.escape(x["text"])}</div></div></div>' for i, x in enumerate(o["items"]))
    foot = f"Save karo, kaam aayega. Aise aur ke liye follow karo <b>{html.escape(handle)}</b>"
    if ch.get("caption_footer"):
        foot += "<br>" + html.escape(ch["caption_footer"])
    return _shot(SHEET.format(acc=acc, hud=html.escape((th.get("hud") or ch.get("name") or "").upper()),
                              title=html.escape(o["title"]), items=items, foot=foot), out)


def _wallpaper(ch, plan, o, assets, out):
    i = max(0, min(len(plan["scenes"]) - 1, int(o.get("wallpaper_scene", 1)) - 1))
    order = [i] + [k for k in range(len(plan["scenes"])) if k != i]
    src = None
    for k in order:
        a = assets.get(k) or assets.get(str(k)) or {}
        if plan["scenes"][k].get("offer_cta"):
            continue
        for key in ("image", "bg"):
            if a.get(key) and os.path.exists(a[key]) and not re.search(r"r[lbv]?\.jpg$|rl\.jpg$", a[key]):
                src = a[key]; break
        if src:
            break
    if not src:
        raise RuntimeError("no picture for the wallpaper")
    handle = ch.get("handle") or (ch.get("theme") or {}).get("handle") or ""
    vf = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
          + (f",drawtext=text='{handle}':fontcolor=white@0.55:fontsize=34:x=(w-text_w)/2:y=h-90:"
             "fontfile=/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if handle and re.fullmatch(r"[@\w.]+", handle) else ""))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", vf, "-q:v", "2", out], check=True, timeout=60)
    return out


def _publish(cid, f):
    d = os.path.join(MEDIA, "offers", cid)
    subprocess.run(["git", "-C", MEDIA, "pull", "-q", "--rebase"], timeout=120)
    os.makedirs(d, exist_ok=True)
    n = os.path.basename(f)
    shutil.copy(f, os.path.join(d, n))
    for c in (["git", "-C", MEDIA, "add", "-A"], ["git", "-C", MEDIA, "commit", "-qm", f"offer {cid} {n}"], ["git", "-C", MEDIA, "push", "-q"]):
        subprocess.run(c, check=True, timeout=180)
    u = RAW + f"offers/{cid}/{n}"
    for _ in range(20):
        try:
            if urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=20).status == 200:
                return u
        except Exception:
            pass
        time.sleep(6)
    return u                                     # raw.githubusercontent may take a minute more; the DM goes out much later


def build(ch, plan, job, assets):
    """Draw + publish the freebie once; registers the keyword. Never fails the video (a failed gift = no offer scene
    problem: the keyword then gets the page's normal 'jaldi aa raha hai' DM)."""
    o = plan.get("offer")
    if not o:
        return None
    if o.get("url"):
        return o["url"]
    jid = os.path.basename(job)
    out = os.path.join(job, f"offer-{o['keyword'].lower()}.jpg")
    try:
        if o["kind"] == "wallpaper":
            _wallpaper(ch, plan, o, assets, out)
        else:
            _sheet(ch, o, out)
        shutil.copy(out, os.path.join(job, "offer.jpg"))
        o["url"] = _publish(ch["id"], out)
    except Exception as e:
        log("offer build failed:", str(e)[:160]); return None
    _register(ch["id"], o["keyword"], {"url": o["url"], "gift": o["gift"], "job": jid, "kind": o["kind"], "t": time.time(),
                                       "made": time.strftime("%Y-%m-%d %H:%M")})
    save(os.path.join(job, "plan.json"), plan)
    log("offer ready:", o["keyword"], o["url"])
    return o["url"]


def caption_line(plan):
    o = plan.get("offer") or {}
    if not o.get("keyword"):
        return ""
    return f"🎁 Comment \"{o['keyword']}\" aur {o['gift']} seedha DM mein 📩 (follow zaroor karna, link followers ko jaata hai)"


if __name__ == "__main__":       # python engine/offers.py <cid> <job>  -> make the offer for an existing video (test)
    from core import channel
    cid, jid = sys.argv[1], sys.argv[2]
    ch = channel(cid); job = os.path.join(OUT, cid, jid)
    if not _cfg(ch):
        ch["offers"] = {"on": True, "kinds": ["sheet"] if (ch.get("theme") or {}).get("style") == "lab" else ["wallpaper", "sheet"]}
    p = load(os.path.join(job, "plan.json"))
    REG = os.path.join(OUT, "offers-test.json")          # a test never registers a real keyword
    if decide(ch, p, job, force=True):
        save(f"/tmp/offer-test-{cid}-{jid}.json", p)
        print(json.dumps(p["offer"], ensure_ascii=False, indent=1))
        print("closing scene:", json.dumps([s for s in p["scenes"] if s.get("offer_cta")], ensure_ascii=False))
        a = {int(k): v for k, v in (load(os.path.join(job, "assets.json"), {}) or {}).items()}
        p2 = json.loads(json.dumps(p))
        out = f"/tmp/offer-test-{cid}-{jid}.jpg"
        (_wallpaper(ch, p2, p2["offer"], a, out) if p2["offer"]["kind"] == "wallpaper" else _sheet(ch, p2["offer"], out))
        print("drawn", out)
