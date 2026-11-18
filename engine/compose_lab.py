"""'lab' look for Kaise Tech (channels/tech/style-lab.md): dark premium world, photoreal props, big numbers,
HTML UI cards, drawn charts and flows, mono HUD chrome, sentence captions with karaoke light-up.
page(plan, timed, total, theme, assets) -> (html, sfx cues). Scene types:
  object  {prompt, label}                      photoreal prop (Muse/Cloudflare image on black, blended 'lighten')
  clip    {prompt, label}                      generated video clip
  stat    {value, sub, label}                  big number that counts up
  ui      {title, rows:[{label,value,pct}]}    dark panel with rows and progress bars
  chart   {points:[..], end_label, label}      line chart that draws; red when it falls, green when it rises
  flow    {nodes:[..], label}                  vertical path, nodes light up, a dot travels
  compare {items:[{label,value,pct}] x2, label} two bars side by side
  title   {big, sub}                           kinetic statement"""
import html, math, os, re
from compose import chunks as _chunks, _split_dashes
import phone_scenes

W, H = 1080, 1920
MONO = "'JetBrains Mono','IBM Plex Mono',monospace"
SANS = "'Inter',sans-serif"   # 17 Nov: 'Inter Tight' is not in HyperFrames' font list -> rendered in a fallback font
CAP_Y = 1210


def esc(s):
    return html.escape(str(s or ""))


def _num(v):
    m = re.search(r"-?[\d,]*\.?\d+", str(v))
    if not m:
        return None
    raw = m.group(0)
    dec = len(raw.split(".")[1]) if "." in raw else 0
    return m.start(), m.end(), float(raw.replace(",", "")), dec, "," in raw


def cap_groups(words):
    words = _split_dashes(words)
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        letters = sum(len(x["w"]) for x in cur)
        brk = len(cur) >= 6 or letters >= 30 or w["w"].endswith((".", "?", "!")) or (nxt and nxt["s"] - w["e"] >= 0.25)
        left = len(words) - i - 1
        if nxt is None or (brk and (left > 2 or (left == 2 and w["w"].endswith((".", "?", "!"))))):   # no 1-2 word orphan caption at the end of a line
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def _stage_on(theme):
    """18 Nov pilot ("stage" layout, keynote grammar): the main visual is bigger and lower, captions are a toast pill
    nearer the bottom, a big number gets its screen without a caption, a faint hairline grid replaces film grain.
    On with theme {"stage": true} or STUDIO_LAB_STAGE=1; off by default until the owner approves the side-by-side."""
    return bool(theme.get("stage")) or os.environ.get("STUDIO_LAB_STAGE") == "1"


STAGE_DY, STAGE_S, STAGE_CAP_Y = 110, 1.15, 1395
STAGE_TEXT = ("title", "stat")        # text-only scenes move down but keep their size (150-200 px type would overflow)


SKINS = {   # 18 Nov (owner: "learn from the library and pick what template suits what"). Written from the Lemo-Opuscar
    # style grammars (blueprint, hologram-hud, ascii-crt, dark-keynote), in our own words; each = picture language + CSS.
    "keynote": {"use": "default premium dark look: products, apps, phones, money, everyday tech",
                "pic": "cinematic photoreal, dark low-key lighting, teal and amber accents, shallow depth of field, premium tech documentary"},
    "blueprint": {"use": "HOW something works inside: machines, chips, networks, signals, engines, any mechanism or process",
                  "pic": "technical engineering blueprint drawing, crisp white line art on deep Prussian blue cyanotype paper, "
                         "orthographic and isometric line drawing with centre lines, dimension lines and hatching, flat 2D, no 3D render, "
                         "no shading, no photo"},
    "hologram": {"use": "AI, future tech, space, scans, anything 'smart' or invisible made visible",
                 "pic": "glowing cyan wireframe hologram made of thin light lines floating above a round projector pad, near-black "
                        "stage, faint dot grid, depth fog, no solid surfaces, no photo"},
    "terminal": {"use": "hacking, passwords, internet, code, data, privacy, scams, anything 'inside the computer'",
                 "pic": "image made only of glowing amber monospace ASCII characters on dark CRT glass, scanlines, slight screen "
                        "curvature, monochrome amber phosphor, no photo"},
}


def _scope(css, k):
    """Scope a look's CSS to its own scenes (.scene.sk-k) and captions (.cap.sk-k); root and end-card rules stay shared."""
    out = []
    for rule in css.split("}"):
        if "{" not in rule:
            continue
        sel, body = rule.split("{", 1)
        sels = []
        for x in sel.split(","):
            x = x.strip()
            if not x or x.startswith(("#root", ".endc", ".endh", ".endf", ".vign", ".grain")):
                continue
            if x.startswith(".scene"):
                sels.append(f".scene.sk-{k}" + x[len(".scene"):])
            elif x.startswith(".cap"):
                sels.append(f".cap.sk-{k}" + x[len(".cap"):])
            else:
                sels.append(f".sk-{k} " + x)
        if sels:
            out.append(",".join(sels) + "{" + body + "}")
    return "\n".join(out) + "\n"


def skin_css(skin, acc):
    if skin == "blueprint":
        paper = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='540' height='960'><filter id='n'>"
                 "<feTurbulence type='fractalNoise' baseFrequency='.006 .012' numOctaves='4' seed='9'/><feColorMatrix values='0 0 0 0 .55 "
                 "0 0 0 0 .7  0 0 0 0 1  0 0 0 .22 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")
        return f"""
#root,.scene{{background:#1d3f80}}
.scene{{background:radial-gradient(ellipse 90% 70% at 50% 45%,#2a58a6 0%,#1d3f80 55%,#132e63 100%)}}
.scene:after{{content:"";position:absolute;inset:0;z-index:0;pointer-events:none;background:url("{paper}") 0 0/100% 100%,
  linear-gradient(#e7f0f914 1.5px,transparent 1.5px) 0 0/60px 60px,linear-gradient(90deg,#e7f0f914 1.5px,transparent 1.5px) 0 0/60px 60px,
  linear-gradient(#e7f0f926 2px,transparent 2px) 0 0/300px 300px,linear-gradient(90deg,#e7f0f926 2px,transparent 2px) 0 0/300px 300px}}
.bgimg{{mix-blend-mode:screen;opacity:.6;filter:saturate(.6)}}
.bgshade{{background:linear-gradient(180deg,#132e63cc 0%,#132e6300 25%,#132e6300 60%,#132e63d9 82%,#132e63 100%)}}
.glow,.vign,.grain{{display:none}}
.cam,.kin,.stat,.statsub,.node,.cl,.cv,.ptitle,.rl,.rv,.lpill,.hud span,.endh,.endf{{font-family:'Architects Daughter',cursive!important;color:#e7f0f9!important}}
.node,.cl,.cv,.rl,.rv{{text-shadow:0 0 10px #132e63,0 0 22px #132e63,0 0 4px #132e63!important}}
.cap{{color:#fff!important}}
.stat,.kin{{letter-spacing:0;text-shadow:none!important;font-weight:400}}
.kw.acc,.cap .key{{color:#e7f0f9!important;text-decoration:underline;text-decoration-thickness:4px;text-underline-offset:8px}}
.uline{{background:#e7f0f9;box-shadow:none}}
.panel,.chat,.term{{background:#132e6399!important;border:3px double #e7f0f9cc!important;border-radius:4px!important;box-shadow:none!important}}
.fill,.cbar{{background:repeating-linear-gradient(45deg,#e7f0f9 0 3px,transparent 3px 11px)!important;border:2px solid #e7f0f9}}
.bar{{background:transparent;border:1.5px dashed #e7f0f988}}
.nd{{background:transparent!important;border:3px solid #e7f0f9!important;box-shadow:none!important}}
.lpill{{background:transparent!important;border:2px solid #e7f0f9;border-radius:2px;color:#e7f0f9!important}}
.lpill i{{background:#e7f0f9}}
.cap{{background:#132e63e6;border:3px double #e7f0f9cc;border-radius:4px;padding:14px 26px;width:auto;left:70px;right:70px;text-shadow:none!important}}
.cap .w{{opacity:1}}
.endc{{background:#1d3f80}}
"""
    if skin == "hologram":
        h = "#5ef2ff"
        return f"""
#root,.scene{{background:#02070a}}
.scene{{background:radial-gradient(ellipse 70% 50% at 50% 46%,#0b2a33 0%,#02070a 70%)}}
.scene:after{{content:"";position:absolute;inset:0;z-index:0;pointer-events:none;
  background:radial-gradient(circle,{h}33 1.3px,transparent 1.6px) 0 0/40px 40px;-webkit-mask-image:radial-gradient(ellipse 70% 60% at 50% 50%,#000,transparent 85%)}}
.bgimg{{mix-blend-mode:screen}}
.bgshade{{background:linear-gradient(180deg,#02070acc 0%,#02070a00 25%,#02070a00 62%,#02070ae6 82%,#02070a 100%)}}
.glow,.grain{{display:none}}
.cam,.kin,.stat,.statsub,.node,.cl,.cv,.ptitle,.rl,.rv,.cap,.lpill,.hud span,.endh,.endf{{font-family:'Rajdhani',sans-serif!important;text-transform:uppercase}}
.stat,.kin{{font-weight:300;letter-spacing:6px;color:#eaffff;text-shadow:0 0 30px {h}aa!important}}
.kw.acc,.cap .key{{color:#ffb547!important}}
.panel,.chat,.term,.cap{{background:#02070ad9!important;border:1px solid {h}88!important;border-radius:2px!important;box-shadow:0 0 24px {h}22!important}}
.cap{{left:70px;right:70px;width:auto;padding:14px 26px;color:#eaffff;text-shadow:none!important;font-weight:600}}
.cap .w{{opacity:1}}
.fill,.cbar{{background:{h}!important;box-shadow:0 0 18px {h}}} .nd{{border-color:{h}!important}}
.lpill{{background:transparent!important;border:1px solid {h};color:{h}!important;letter-spacing:4px}} .lpill i{{background:{h}}}
.uline{{background:{h};box-shadow:0 0 20px {h}}}
"""
    if skin == "terminal":
        a = "#ffb000"
        return f"""
#root,.scene{{background:#0d0702}}
.scene{{background:radial-gradient(ellipse 85% 70% at 50% 46%,#1c1206 0%,#0d0702 75%)}}
.scene:after{{content:"";position:absolute;inset:0;z-index:4;pointer-events:none;
  background:repeating-linear-gradient(0deg,#00000055 0 2px,transparent 2px 4px),radial-gradient(ellipse 100% 90% at 50% 50%,transparent 60%,#000c 100%)}}
.bgimg{{mix-blend-mode:screen;filter:sepia(1) saturate(3) hue-rotate(-12deg) brightness(.9)}}
.bgshade{{background:linear-gradient(180deg,#0d0702d9 0%,#0d070200 25%,#0d070200 60%,#0d0702e6 82%,#0d0702 100%)}}
.glow,.grain{{display:none}}
.cam,.kin,.stat,.statsub,.node,.cl,.cv,.ptitle,.rl,.rv,.cap,.lpill,.hud span,.endh,.endf,.bub{{font-family:'VT323',monospace!important;color:{a}!important;text-shadow:0 0 12px {a}aa!important;text-transform:uppercase}}
.stat,.kin{{letter-spacing:4px;font-weight:400}}
.kw.acc,.cap .key{{color:#fff1c9!important}}
.panel,.chat,.term,.cap{{background:#0d0702e6!important;border:2px solid {a}88!important;border-radius:0!important;box-shadow:none!important}}
.cap{{left:60px;right:60px;width:auto;padding:12px 24px;font-size:66px}} .cap .w{{opacity:1}}
.cap:before{{content:"> ";color:{a}}}
.fill,.cbar{{background:{a}!important}} .nd{{border-color:{a}!important;border-radius:0!important}}
.lpill{{background:{a}!important;color:#0d0702!important;border-radius:0;text-shadow:none!important}}
.uline{{background:{a}}}
"""
    return ""


def _film_on(theme):
    """18 Nov v2 "film grammar" (owner: the stage pilot looked the same; use the skills). From the HyperFrames skill
    (references/motion.md, types/explainer.md, types/vertical.md): a deliberate camera move per scene instead of a breathing
    scale; transitions with a cause that change at every seam; no tag pill + HUD on every scene (reads as slides); bigger
    hero; per-word blur captions with the keyword larger; render-time motion blur. theme {"film": true} or STUDIO_LAB_FILM=1."""
    return bool(theme.get("film")) or os.environ.get("STUDIO_LAB_FILM") == "1"


def _camera(sid, kind, a, d):
    """One camera move per scene on the .cam wrapper (never on the timed clip). Titles land and hold dead still."""
    c = f"#{sid}cam"
    if kind in ("title", "stat"):                    # pull-back reveal: arrives close, settles, then still
        return [f'tl.fromTo("{c}",{{scale:1.32,filter:"blur(10px)"}},{{scale:1,filter:"blur(0px)",duration:0.8,ease:"expo.out",immediateRender:false}},{a:.3f});']
    if kind in ("ui", "chart", "compare", "chat", "code"):   # UI focus zoom: establish, then push toward the first rows
        t2 = a + max(0.9, d * 0.45)
        return [f'tl.set("{c}",{{scale:1,transformOrigin:"50% 36%"}},{a:.3f});',
                f'tl.to("{c}",{{scale:1.16,duration:{min(1.0, max(0.5, d * 0.35)):.2f},ease:"power2.inOut"}},{t2:.3f});']
    if kind == "flow":                               # camera travels down the path with the dot
        return [f'tl.fromTo("{c}",{{y:90}},{{y:-70,duration:{max(0.8, d - 0.2):.2f},ease:"power2.inOut",immediateRender:false}},{a:.3f});']
    # object / clip / image: slow push with a slight drift (the product is the subject)
    return [f'tl.fromTo("{c}",{{scale:1.0,x:-14}},{{scale:1.12,x:14,duration:{max(0.8, d):.2f},ease:"power1.inOut",immediateRender:false}},{a:.3f});']


def _seam(i, prev, sid, a, kind, cues):
    """Four transitions, each with a cause, never the same twice in a row (motion.md 'Transitions with a cause')."""
    p, n = f"#{prev}", f"#{sid}"
    k = i % 4
    if k == 1:      # whip: horizontal smear out, the next lands blurred and sharpens
        out = [f'tl.to("{p}",{{xPercent:-35,filter:"blur(16px)",duration:0.2,ease:"power3.in"}},{a - 0.2:.3f});',
               f'tl.fromTo("{n}",{{xPercent:35,filter:"blur(16px)"}},{{xPercent:0,filter:"blur(0px)",duration:0.32,ease:"expo.out",immediateRender:false}},{a:.3f});']
        snd = "sfx/whoosh-fast.mp3"
    elif k == 2:    # zoom through: the old frame flies into the lens, the new one grows out of it
        out = [f'tl.to("{p}",{{scale:1.6,opacity:0,filter:"blur(12px)",duration:0.25,ease:"power3.in"}},{a - 0.25:.3f});',
               f'tl.fromTo("{n}",{{scale:0.7,opacity:0,filter:"blur(12px)"}},{{scale:1,opacity:1,filter:"blur(0px)",duration:0.45,ease:"expo.out",immediateRender:false}},{a:.3f});']
        snd = "sfx/air-zoom.mp3"
    elif k == 3:    # blur swap on one stage
        out = [f'tl.to("{p}",{{opacity:0,filter:"blur(8px)",duration:0.16,ease:"power2.in"}},{a - 0.16:.3f});',
               f'tl.fromTo("{n}",{{opacity:0,filter:"blur(8px)"}},{{opacity:1,filter:"blur(0px)",duration:0.16,ease:"power2.out",immediateRender:false}},{a:.3f});']
        snd = "sfx/sweep-small.mp3"
    else:           # dip cut: the outgoing frame darkens before a hard cut, so the cut reads as meant
        out = [f'tl.to("{p}",{{filter:"brightness(0.55)",duration:0.1,ease:"none"}},{a - 0.1:.3f});',
               f'tl.fromTo("{n}",{{filter:"brightness(1.6)"}},{{filter:"brightness(1)",duration:0.25,ease:"power2.out",immediateRender:false}},{a:.3f});']
        snd = "sfx/impact.mp3"
    cues.append({"t": round(a - 0.05, 3), "file": snd, "gain_db": -24, "align": "onset"})
    return out


def page(plan, timed, total, theme, assets):
    stage = _stage_on(theme)
    film = _film_on(theme)
    acc = theme.get("accent", "#ffd84d")
    cool = theme.get("accent2", "#3ec7ff")
    handle = theme.get("handle", "")
    series = (plan.get("hud_left") or theme.get("hud") or "KAISE.TECH").upper()     # 18 Nov: theme.hud per lab page
    endcard = 1.4 if handle else 0.0
    keys = set()
    for s in plan["scenes"]:
        for k in s.get("keywords") or []:
            keys.update(re.sub(r"[^a-z0-9 ]", "", k.lower()).split())
    scenes, top, js, cues, caps = [], [], [], [], []
    stat_win = []
    # 18 Nov (owner: "mix and match styles, choose what part suits what"): a look per SCENE (s["skin"], set by the creative
    # director in make.py); the plan-wide look is the fallback. Each look's CSS is scoped to its scenes and captions.
    sks = [str(s.get("skin") or plan.get("skin") or theme.get("skin") or "keynote") for s in plan["scenes"]]
    sks = [k if k in SKINS else "keynote" for k in sks]
    capscene = []
    n = len(timed)
    for i, (s, t) in enumerate(zip(plan["scenes"], timed)):
        a = 0.0 if i == 0 else t["start"] - 0.1
        b = (timed[i + 1]["start"] - 0.1) if i + 1 < n else total - endcard
        d = round(b - a, 3)
        sid = f"s{i}"
        js0 = len(js)
        kind = s.get("type", "object")
        glow = acc if i % 3 != 1 else cool
        inner = f'<div class="glow" data-layout-ignore style="background:radial-gradient(circle at 50% 44%,{glow}33 0%,{glow}14 28%,transparent 62%)"></div>'
        hero = ""
        img = (assets.get(i) or {}).get("image")
        vid = (assets.get(i) or {}).get("video")
        if kind in phone_scenes.KINDS:          # 19 Nov: phone-story scenes (engine/phone_scenes.py), exact HTML, no AI picture
            hero, pj, pc = phone_scenes.scene(kind, s, sid, a, d, assets.get(i) or {})
            js += pj; cues += pc
        elif kind == "clip" and vid:
            try:                                 # the video element ends with its clip, so the held image shows after it
                import subprocess as _sp
                vlen = float(_sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vid],
                                     capture_output=True, text=True, timeout=30).stdout.strip()) - 0.3
            except Exception:
                vlen = d
            vd = max(0.5, min(d, vlen))
            top.append(f'<video id="v{i}" class="clip vid" src="assets/{os.path.basename(vid)}" muted playsinline '
                       f'data-start="{a:.3f}" data-duration="{vd:.3f}" data-media-start="0.2" data-track-index="0"></video>')
            js.append(f'tl.fromTo("#v{i}",{{scale:1.08}},{{scale:1.0,duration:{vd:.3f},ease:"none"}},{a:.3f});')
        elif kind in ("object", "clip") and img:
            lg = (assets.get(i) or {}).get("logo")
            t_img = a
            # 18 Nov pilot: a REAL logo / photo (realmedia, s<i>r.jpg / s<i>rl.jpg) is a clean card, not a blended prop
            rc = lambda f: " real" if re.search(r"s\d+r[l]?\.jpg$", os.path.basename(f)) else ""
            if lg and d > 2.4:        # 17 Nov: the brand logo pops in (back.out), holds, shrinks away, THEN the photo/product arrives
                hero = f'<img id="{sid}L" class="prop{rc(lg)}" src="assets/{os.path.basename(lg)}">'
                js.append(f'tl.fromTo("#{sid}L",{{scale:0.35,opacity:0,rotation:-4}},{{scale:1,opacity:1,rotation:0,duration:0.45,ease:"back.out(2.4)",immediateRender:false}},{a + 0.05:.3f});')
                js.append(f'tl.to("#{sid}L",{{scale:0.8,opacity:0,y:-60,duration:0.35,ease:"power2.in"}},{a + 1.15:.3f});')
                js.append(f'tl.set("#{sid}L",{{opacity:0}},{a:.3f});')
                cues.append({"t": round(a + 0.08, 3), "file": "sfx/impact.mp3", "gain_db": -22, "align": "onset"})
                t_img = a + 1.3
            hero += f'<img id="{sid}h" class="prop{rc(img)}" src="assets/{os.path.basename(img)}">'
            js.append(f'tl.fromTo("#{sid}h",{{y:70,scale:0.92,opacity:0}},{{y:0,scale:1,opacity:1,duration:0.9,ease:"power4.out",immediateRender:false}},{t_img:.3f});')
            js.append(f'tl.to("#{sid}h",{{y:-18,rotation:0.6,duration:{max(0.5, d - 0.9 - (t_img - a)):.3f},ease:"sine.inOut"}},{t_img + 0.9:.3f});')
            js.append(f'tl.set("#{sid}h",{{opacity:0}},{a:.3f});')
        elif kind == "stat":
            # 19 Nov: plans put the number in "big" with "value": null -> the screen said 'None' (finance 1118-2334)
            v = str(s.get("value") or s.get("big") or "")
            nm = _num(v)
            # 18 Nov v2: one line always: the font fits the value in 940 px (bold glyphs ~0.62 em); "2 HOURS" wrapped at 250 px
            sty = (' style="font-size:%dpx;white-space:nowrap"' % int(min(250, 940 / (0.62 * max(3, len(v)))))) if film else ""
            if nm and (nm[2] < 10 or theme.get("phone")):   # 18 Nov: "1 HOURS"; 19 Nov: money must never show a wrong number (₹4,895)
                nm = None
            if nm:
                st, en, val, dec, comma = nm
                hero = (f'<div id="{sid}h" class="stat"{sty}>{esc(v[:st])}<span id="{sid}n" class="tab">{esc(v[st:en])}</span>{esc(v[en:])}</div>')
                js.append(f'(function(){{const o={{v:0}},el=document.getElementById("{sid}n");'
                          # 18 Nov: 1.4 s count -> the pre-render check's first still read '98+' for '100+' and held the video.
                          # 19 Nov: still read 98+ on SHORT scenes (still at 0.45 d, count ended 0.2 + 0.3 d): now 0.1 + 0.22 d, always done first
                          f'tl.to(o,{{v:{val},duration:{min(0.7, d * 0.22):.2f},ease:"power2.out",onUpdate:()=>{{el.textContent='
                          f'o.v.toLocaleString("{"en-IN" if comma else "en-US"}",{{minimumFractionDigits:{dec},maximumFractionDigits:{dec}}})}}}},{a + 0.1:.3f});'
                          f'tl.set(o,{{v:0}},{a:.3f});}})();')
            else:
                hero = f'<div id="{sid}h" class="stat"{sty}>{esc(v)}</div>'
            if s.get("sub"):
                hero += f'<div id="{sid}u" class="statsub">{esc(s["sub"])}</div>'
                js.append(f'tl.fromTo("#{sid}u",{{y:24,opacity:0}},{{y:0,opacity:1,duration:0.5,ease:"power3.out",immediateRender:false}},{a + 0.6:.3f});')
                js.append(f'tl.set("#{sid}u",{{opacity:0}},{a:.3f});')
            js.append(f'tl.fromTo("#{sid}h",{{scale:0.86,opacity:0}},{{scale:1,opacity:1,duration:0.7,ease:"power4.out",immediateRender:false}},{a + 0.05:.3f});')
            js.append(f'tl.set("#{sid}h",{{opacity:0}},{a:.3f});')
            cues.append({"t": round(a + 0.2, 3), "file": "sfx/type-soft.mp3", "gain_db": -24, "align": "onset", "dur": 1.2})
        elif kind == "ui":
            rows = (s.get("rows") or [])[:5]
            hero = f'<div id="{sid}h" class="panel"><div id="{sid}sh" class="shine" data-layout-ignore></div><div class="ptitle"><i></i>{esc(s.get("title", ""))}</div>'
            js.append(f'tl.fromTo("#{sid}sh",{{xPercent:-120}},{{xPercent:260,duration:1.1,ease:"power2.inOut",immediateRender:false}},{a + 0.5:.3f});')
            for j, r in enumerate(rows):
                pct = max(0, min(100, float(r.get("pct", 60) or 0)))
                hero += (f'<div class="row"><div class="rl">{esc(r.get("label"))}</div><div class="rv">{esc(r.get("value"))}</div>'
                         f'<div class="bar"><div id="{sid}b{j}" class="fill" style="width:{pct:.0f}%;background:{acc if j == 0 else "#d7dbe3"}"></div></div></div>')
                js.append(f'tl.fromTo("#{sid}b{j}",{{scaleX:0}},{{scaleX:1,transformOrigin:"0% 50%",duration:0.7,ease:"power3.out",immediateRender:false}},{a + 0.45 + j * 0.22:.3f});')
                js.append(f'tl.set("#{sid}b{j}",{{scaleX:0,transformOrigin:"0% 50%"}},{a:.3f});')
                cues.append({"t": round(a + 0.45 + j * 0.22, 3), "file": "sfx/click-select.mp3", "gain_db": -24, "align": "onset"})
            hero += "</div>"
            js.append(f'tl.fromTo("#{sid}h",{{y:60,opacity:0,rotationX:12}},{{y:0,opacity:1,rotationX:0,duration:0.8,ease:"power4.out",immediateRender:false}},{a:.3f});')
            js.append(f'tl.set("#{sid}h",{{opacity:0}},{a:.3f});')
        elif kind == "chart":
            pts = [float(x) for x in (s.get("points") or [3, 5, 4, 7, 6, 9])][:12]
            lo, hi = min(pts), max(pts)
            rng = (hi - lo) or 1
            cw, ch_ = 780, 420
            xy = [(i2 * cw / max(1, len(pts) - 1), ch_ - (p - lo) / rng * ch_) for i2, p in enumerate(pts)]
            path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in xy)
            area = path + f" L{cw} {ch_} L0 {ch_} Z"
            ln = sum(math.dist(xy[k], xy[k + 1]) for k in range(len(xy) - 1))
            col = "#ff4d5e" if pts[-1] < pts[0] else "#3ddc84"
            hero = (f'<div id="{sid}h" class="panel chartp"><div class="ptitle"><i></i>{esc(s.get("title", s.get("label", "")))}</div>'
                    f'<svg width="{cw}" height="{ch_ + 20}" viewBox="0 -10 {cw} {ch_ + 20}">'
                    + "".join(f'<line x1="0" x2="{cw}" y1="{g * ch_ / 4:.0f}" y2="{g * ch_ / 4:.0f}" stroke="#ffffff14"/>' for g in range(5))
                    + f'<path id="{sid}a" d="{area}" fill="{col}22"/>'
                    f'<path id="{sid}l" d="{path}" fill="none" stroke="{col}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round" '
                    f'stroke-dasharray="{ln:.0f}" stroke-dashoffset="{ln:.0f}"/>'
                    f'<circle id="{sid}c" cx="{xy[-1][0]:.1f}" cy="{xy[-1][1]:.1f}" r="13" fill="{col}"/></svg>'
                    f'<div id="{sid}e" class="endl" style="color:{col}">{esc(s.get("end_label", ""))}</div></div>')
            js.append(f'tl.fromTo("#{sid}h",{{y:60,opacity:0}},{{y:0,opacity:1,duration:0.7,ease:"power4.out",immediateRender:false}},{a:.3f});')
            js.append(f'tl.set("#{sid}h",{{opacity:0}},{a:.3f});')
            js.append(f'tl.fromTo("#{sid}l",{{strokeDashoffset:{ln:.0f}}},{{strokeDashoffset:0,duration:{min(1.8, d * 0.6):.2f},ease:"power1.inOut",immediateRender:false}},{a + 0.35:.3f});')
            js.append(f'tl.set("#{sid}l",{{strokeDashoffset:{ln:.0f}}},{a:.3f});')
            js.append(f'tl.fromTo("#{sid}a,#{sid}c,#{sid}e",{{opacity:0}},{{opacity:1,duration:0.4,immediateRender:false}},{a + 0.35 + min(1.8, d * 0.6):.3f});')
            js.append(f'tl.set("#{sid}a,#{sid}c,#{sid}e",{{opacity:0}},{a:.3f});')
            cues.append({"t": round(a + 0.35, 3), "file": "sfx/sweep-small.mp3", "gain_db": -22, "align": "onset"})
        elif kind == "flow":
            nodes = (s.get("nodes") or [])[:5]
            k = max(1, len(nodes))
            y0, gap = 0, (min(560, 150 * (k - 1)) / max(1, k - 1)) if k > 1 else 0   # last node ends above the captions
            hero = f'<div id="{sid}h" class="flowp"><svg class="fline" width="20" height="{int(gap * (k - 1)) + 2}"><line x1="10" x2="10" y1="0" y2="{gap * (k - 1):.0f}" stroke="#ffffff22" stroke-width="4"/>' \
                   f'<line id="{sid}ln" x1="10" x2="10" y1="0" y2="{gap * (k - 1):.0f}" stroke="{acc}" stroke-width="4" stroke-dasharray="{gap * (k - 1):.0f}" stroke-dashoffset="{gap * (k - 1):.0f}"/></svg>'
            step = min(0.8, (d * 0.4) / k)   # all nodes visible before mid-scene
            for j, lab in enumerate(nodes):
                tj = a + 0.3 + j * step
                hero += (f'<div id="{sid}n{j}" class="node" style="top:{y0 + j * gap:.0f}px"><span class="nd"></span>'
                         f'<span class="ni">{j + 1:02d}</span>{esc(lab)}</div>')
                js.append(f'tl.fromTo("#{sid}n{j}",{{x:-40,opacity:0}},{{x:0,opacity:1,duration:0.5,ease:"power3.out",immediateRender:false}},{tj:.3f});')
                js.append(f'tl.set("#{sid}n{j}",{{opacity:0}},{a:.3f});')
                js.append(f'tl.to("#{sid}n{j} .nd",{{backgroundColor:"{acc}",boxShadow:"0 0 26px {acc}",duration:0.2}},{tj + 0.1:.3f});')
                js.append(f'tl.set("#{sid}n{j} .nd",{{backgroundColor:"#2a2f3a",boxShadow:"none"}},{a:.3f});')
                cues.append({"t": round(tj, 3), "file": "sfx/click-ui.mp3", "gain_db": -22, "align": "onset"})
            if k > 1:
                js.append(f'tl.fromTo("#{sid}ln",{{strokeDashoffset:{gap * (k - 1):.0f}}},{{strokeDashoffset:0,duration:{step * (k - 1):.2f},ease:"none",immediateRender:false}},{a + 0.4:.3f});')
                js.append(f'tl.set("#{sid}ln",{{strokeDashoffset:{gap * (k - 1):.0f}}},{a:.3f});')
            hero += "</div>"
        elif kind == "compare":
            its = (s.get("items") or [])[:2]
            hero = f'<div id="{sid}h" class="cmp">'
            for j, it in enumerate(its):
                pct = max(4, min(100, float(it.get("pct", 50) or 0)))
                col = acc if j == 0 else "#d7dbe3"
                vtx = str(it.get("value") or "")
                vfs = 86 if len(vtx) <= 8 else 64 if len(vtx) <= 14 else 46       # fits in 2 lines, never climbs into the pill
                # 18 Nov: "Base+New" (8 chars, no space) at 86 px is ~410 px wide in a 360 px column -> clipped (lab-gpt-01 held).
                # The longest unbreakable word must fit the column width (bold glyphs ~0.66 em).
                vfs = min(vfs, int(350 / (0.66 * max([len(w) for w in vtx.split()] or [1]))))
                hero += (f'<div class="cc"><div class="cv" style="color:{col};font-size:{vfs}px">{esc(vtx)}</div>'
                         f'<div class="ctrack"><div id="{sid}c{j}" class="cbar" style="height:{pct * 4.0:.0f}px;background:{col}"></div></div>'
                         f'<div class="cl">{esc(it.get("label"))}</div></div>')
                js.append(f'tl.fromTo("#{sid}c{j}",{{scaleY:0}},{{scaleY:1,transformOrigin:"50% 100%",duration:0.8,ease:"power3.out",immediateRender:false}},{a + 0.35 + j * 0.35:.3f});')
                js.append(f'tl.set("#{sid}c{j}",{{scaleY:0,transformOrigin:"50% 100%"}},{a:.3f});')
                cues.append({"t": round(a + 0.35 + j * 0.35, 3), "file": "sfx/sweep-small.mp3", "gain_db": -22, "align": "onset"})
            hero += "</div>"
            js.append(f'tl.fromTo("#{sid}h",{{opacity:0}},{{opacity:1,duration:0.3,immediateRender:false}},{a:.3f});')
            js.append(f'tl.set("#{sid}h",{{opacity:0}},{a:.3f});')
        elif kind == "chat":
            msgs = [m for m in (s.get("messages") or []) if isinstance(m, dict) and m.get("text")][:3]
            cl = (assets.get(i) or {}).get("chatlogo")       # 18 Nov: the app's real logo in the header (engine/make.py _real_brands)
            head_ = (f'<img class="clogo" src="assets/{os.path.basename(cl)}">' if cl else '<i></i><i></i><i></i>')
            hero = f'<div id="{sid}h" class="chat"><div class="chead">{head_}<span>{esc(s.get("title") or "assistant")}</span></div>'
            tcur = a + 0.35
            for j, m in enumerate(msgs):
                ai = (m.get("role") or "ai") != "user"
                ws = esc(m["text"]).split()
                body = " ".join(f'<span id="{sid}m{j}w{q}" class="cw">{w}</span>' for q, w in enumerate(ws)) if ai else esc(m["text"])
                hero += f'<div id="{sid}m{j}" class="bub {"ai" if ai else "me"}">{"<b class=av></b>" if ai else ""}<div>{body}</div></div>'
                js.append(f'tl.set("#{sid}m{j}",{{opacity:0}},{a:.3f});')
                js.append(f'tl.fromTo("#{sid}m{j}",{{y:30,opacity:0}},{{y:0,opacity:1,duration:0.35,ease:"power3.out",immediateRender:false}},{tcur:.3f});')
                cues.append({"t": round(tcur, 3), "file": "sfx/pop-light.mp3" if not ai else "sfx/click-ui.mp3", "gain_db": -24, "align": "onset"})
                if ai and ws:
                    span = max(0.6, min(2.2, (d - (tcur - a)) * 0.7))
                    for q in range(len(ws)):
                        js.append(f'tl.set("#{sid}m{j}w{q}",{{opacity:0}},{a:.3f});')
                        js.append(f'tl.to("#{sid}m{j}w{q}",{{opacity:1,duration:0.05}},{tcur + 0.3 + q * span / len(ws):.3f});')
                    cues.append({"t": round(tcur + 0.3, 3), "file": "sfx/type-soft.mp3", "gain_db": -26, "align": "onset", "dur": round(span, 2)})
                    tcur += 0.3 + span + 0.2
                else:
                    tcur += 0.7
            hero += "</div>"
            js.append(f'tl.fromTo("#{sid}h",{{y:50,opacity:0}},{{y:0,opacity:1,duration:0.6,ease:"power4.out",immediateRender:false}},{a:.3f});')
            js.append(f'tl.set("#{sid}h",{{opacity:0}},{a:.3f});')
        elif kind == "code":
            lines = [str(x) for x in (s.get("lines") or [])][:6]
            hl = s.get("highlight")
            hero = f'<div id="{sid}h" class="term"><div class="chead"><i></i><i></i><i></i><span>{esc(s.get("title") or "terminal")}</span></div><div class="tbody">'
            step = max(0.25, min(0.7, (d * 0.6) / max(1, len(lines))))
            for j, ln in enumerate(lines):
                tj = a + 0.4 + j * step
                hero += f'<div id="{sid}l{j}" class="tl{" hl" if hl == j else ""}"><span class="tp">{"$" if j == 0 else ">"}</span>{esc(ln)}</div>'
                js.append(f'tl.set("#{sid}l{j}",{{clipPath:"inset(0 100% 0 0)"}},{a:.3f});')
                js.append(f'tl.to("#{sid}l{j}",{{clipPath:"inset(0 0% 0 0)",duration:{step * 0.8:.2f},ease:"steps({max(4, min(28, len(ln)))})"}},{tj:.3f});')
            hero += '<span class="cur"></span></div></div>'
            js.append(f'tl.fromTo("#{sid}h",{{y:50,opacity:0}},{{y:0,opacity:1,duration:0.6,ease:"power4.out",immediateRender:false}},{a:.3f});')
            js.append(f'tl.set("#{sid}h",{{opacity:0}},{a:.3f});')
            cues.append({"t": round(a + 0.4, 3), "file": "sfx/type-soft.mp3", "gain_db": -24, "align": "onset", "dur": round(step * len(lines), 2)})
        else:  # title
            words = esc(s.get("big", "")).split()
            sub = f'<div id="{sid}u" class="kinsub">{esc(s["sub"])}</div>' if s.get("sub") else ""   # in the flow: never overlaps a 2-line title
            spans = []
            for j, w in enumerate(words):
                last = j == len(words) - 1 and len(words) > 1
                spans.append(f'<span class="kwm"><span class="kw{" acc" if last else ""}" id="{sid}w{j}">{w}</span></span>')
            # 19 Nov: a long word ('CMS.RBI.ORG.IN') ran off the frame at 168 px; the size fits the longest word in 940 px
            lw = max([len(w_) for w_ in words] + [1])
            ksty = f' style="font-size:{int(min(168, 940 / (0.62 * lw)))}px"' if lw > 8 else ""
            hero = '<div id="%sh" class="kin"%s>%s<div id="%sul" class="uline"></div>%s</div>' % (sid, ksty, " ".join(spans), sid, sub)
            js.append(f'tl.set("#{sid}ul",{{scaleX:0}},{a:.3f});')
            js.append(f'tl.to("#{sid}ul",{{scaleX:1,duration:0.5,ease:"power3.inOut"}},{a + 0.2 + len(words) * 0.09:.3f});')
            for j in range(len(words)):
                js.append(f'tl.fromTo("#{sid}w{j}",{{yPercent:105,opacity:1}},{{yPercent:0,opacity:1,duration:0.65,ease:"expo.out",immediateRender:false}},{a + 0.08 + j * 0.09:.3f});')
                js.append(f'tl.set("#{sid}w{j}",{{opacity:0}},{a:.3f});')
            if s.get("sub"):
                js.append(f'tl.fromTo("#{sid}u",{{opacity:0}},{{opacity:1,duration:0.4,immediateRender:false}},{a + 0.5:.3f});')
                js.append(f'tl.set("#{sid}u",{{opacity:0}},{a:.3f});')
        if s.get("label") and (not film or kind in ("object", "clip")):     # v2: a tag pill on every scene reads as slides
            inner += f'<div id="{sid}p" class="lpill"><i></i>{esc(s["label"].upper())}</div>'
            js.append(f'tl.fromTo("#{sid}p",{{y:-14,opacity:0}},{{y:0,opacity:1,duration:0.45,ease:"power3.out",immediateRender:false}},{a + 0.15:.3f});')
            js.append(f'tl.set("#{sid}p",{{opacity:0}},{a:.3f});')
        if stage:
            sc = 1.0 if kind in STAGE_TEXT else STAGE_S
            inner = inner.replace('<div class="glow"', '<div class="hgrid" data-layout-ignore></div><div class="glow"', 1)
            inner += (f'<div class="stg" style="transform:translateY({STAGE_DY}px) scale({sc})">'
                      f'<div id="{sid}cam" class="cam">{hero}</div></div>')
            if kind == "stat":
                stat_win.append((a, b))
        else:
            inner += f'<div id="{sid}cam" class="cam">{hero}</div>'
        if (not film or i == 0) and kind not in phone_scenes.KINDS:   # 19 Nov: the tag overlapped the phone's header
            inner += (f'<div class="hud"><span class="hl"><b></b>{esc(series)}</span>'
                      f'<span class="hr">{esc("" if (s.get("hud_right") or "").upper() in ("", (s.get("label") or "").upper()) else s["hud_right"].upper())}</span></div>')   # no duplicate of the pill
        bgp = (assets.get(i) or {}).get("bg")
        if film and bgp:                                # v2: the world behind the card: full frame, it moves, the type stays still
            inner = (f'<img id="{sid}bg" class="bgimg" src="assets/{os.path.basename(bgp)}"><div class="bgshade" data-layout-ignore></div>'
                     + inner.replace('<div class="glow"', '<div class="glow" style="display:none"', 1))
            dx = 24 if i % 2 else -24
            real_bg = bool(re.search(r"s\d+rb\.jpg$", os.path.basename(bgp)))
            if real_bg and kind not in ("object", "clip") and d > 2.2:
                # 18 Nov pilot: the real Google Assistant screen sat behind the AUDIO BUFFER panel and nobody could see it.
                # Establish, then overlay: the real screen / photo plays alone first, then the card arrives and it dims.
                est = round(min(1.8, max(1.0, d * 0.35)), 2)
                dx = 10 if i % 2 else -10
                js.append(f'tl.fromTo("#{sid}cam",{{opacity:0}},{{opacity:1,duration:0.35,ease:"power2.out",immediateRender:false}},{a + est:.3f});')
                js.append(f'tl.set("#{sid}cam",{{opacity:0}},{a:.3f});')
                js.append(f'tl.fromTo("#{sid}bg",{{filter:"brightness(1) blur(0px)"}},{{filter:"brightness(0.42) blur(6px)",duration:0.45,ease:"power2.out",immediateRender:false}},{a + est:.3f});')
                js.append(f'tl.set("#{sid}bg",{{filter:"brightness(1) blur(0px)"}},{a:.3f});')
                inner = inner.replace('<div class="bgshade" data-layout-ignore></div>', '<div class="bgshade real" data-layout-ignore></div>', 1)
            end_sc = 1.08 if real_bg else 1.14              # a real screen must stay readable: gentler push
            js.append(f'tl.fromTo("#{sid}bg",{{scale:1.04,x:{-dx}}},{{scale:{end_sc},x:{dx},duration:{max(0.8, d):.2f},ease:"power1.inOut",immediateRender:false}},{a:.3f});')
        if film:
            js += _camera(sid, kind, a, d)
        else:
            js.append(f'tl.fromTo("#{sid}cam",{{scale:1.05}},{{scale:1.0,duration:0.9,ease:"power3.out",immediateRender:false}},{a:.3f});')
            js.append(f'tl.to("#{sid}cam",{{scale:1.03,duration:{max(0.4, d - 0.9):.3f},ease:"sine.inOut"}},{a + 0.9:.3f});')
        if i and film:
            js += _seam(i if sks[i] == sks[i - 1] else 2, f"s{i - 1}", sid, a, kind, cues)   # a new look enters by zooming through
        elif i:
            tr = i % 3
            if tr == 1:      # push up with motion blur
                js.append(f'tl.fromTo("#{sid}",{{yPercent:7,opacity:0,filter:"blur(14px)"}},{{yPercent:0,opacity:1,filter:"blur(0px)",duration:0.38,ease:"power3.out",immediateRender:false}},{a:.3f});')
            elif tr == 2:    # zoom through
                js.append(f'tl.fromTo("#{sid}",{{scale:1.14,opacity:0,filter:"blur(10px)"}},{{scale:1,opacity:1,filter:"blur(0px)",duration:0.42,ease:"expo.out",immediateRender:false}},{a:.3f});')
            else:            # flash cut
                js.append(f'tl.fromTo("#{sid}",{{opacity:0,filter:"brightness(2.2)"}},{{opacity:1,filter:"brightness(1)",duration:0.26,ease:"power2.out",immediateRender:false}},{a:.3f});')
            cues.append({"t": round(a + 0.05, 3), "file": ["sfx/air-zoom.mp3", "sfx/whoosh-fast.mp3"][i % 2], "gain_db": -26, "align": "onset"})
        # 17 Nov fix: a tl.set(opacity:0) at the SAME time as the entrance fromTo, added after it, won on every seek ->
        # props, UI panels, stats and compares rendered invisible. Resets go first, so the entrance tween wins.
        mine = js[js0:]
        js[js0:] = [x for x in mine if x.startswith("tl.set(")] + [x for x in mine if not x.startswith("tl.set(")]
        scenes.append(f'<div id="{sid}" class="clip scene{" over" if kind == "clip" and vid else ""}{(" sk-" + sks[i]) if film else ""}" data-start="{a:.3f}" '
                      f'data-duration="{d:.3f}" data-track-index="1">{inner}</div>')
        for c in cap_groups(t["words"]):
            caps.append(c); capscene.append(i)
    # captions: one sentence chunk at a time, words light up as spoken
    capdiv, cap_js = [], []
    for j, c in enumerate(caps):
        st = max(0.05, c[0]["s"] - 0.08)
        en = c[-1]["e"] + 0.3
        if j + 1 < len(caps):
            en = min(en, caps[j + 1][0]["s"] - 0.06)
        en = max(en, st + 0.3)
        if stage and any(sa - 0.05 <= (st + en) / 2 < sb for sa, sb in stat_win):
            continue                                  # the big number is the message: no caption over it
        if endcard:                                   # 17 Nov: captions bled into the end card (review HOLD)
            if st >= total - endcard - 0.2:
                continue
            en = min(en, total - endcard - 0.05)
        spans = []
        for k, w in enumerate(c):
            kk = re.sub(r"[^a-z0-9]", "", w["w"].lower())
            word = esc(re.sub(r"[,]+$", "", w["w"]).replace("...", ""))
            spans.append(f'<span id="c{j}w{k}" class="w{" key" if kk in keys else ""}">{word}</span>')
            if film:                                  # v2: each word blurs in when it is spoken (motion.md), keyword larger
                cap_js.append(f'tl.fromTo("#c{j}w{k}",{{opacity:0,filter:"blur(6px)"}},{{opacity:1,filter:"blur(0px)",duration:0.13,ease:"power2.out",immediateRender:false}},{max(st, w["s"] - 0.05):.3f});')
                cap_js.append(f'tl.set("#c{j}w{k}",{{opacity:0}},{st:.3f});')
            else:
                cap_js.append(f'tl.to("#c{j}w{k}",{{opacity:1,duration:0.08}},{max(st, w["s"] - 0.03):.3f});')
                cap_js.append(f'tl.set("#c{j}w{k}",{{opacity:0.55}},{st:.3f});')
        capdiv.append(f'<div id="c{j}" class="clip cap{(" sk-" + sks[capscene[j]]) if film else ""}" data-start="{st:.3f}" data-duration="{en - st:.3f}" data-track-index="9">{" ".join(spans)}</div>')
        cap_js.append(f'tl.fromTo("#c{j}",{{y:16,opacity:0}},{{y:0,opacity:1,duration:0.18,ease:"power2.out",immediateRender:false}},{st:.3f});')
    brand = []
    if handle:
        e0 = total - endcard
        brand.append(f'<div id="endc" class="clip endc" data-start="{e0:.3f}" data-duration="{endcard:.3f}" data-track-index="8">'
                     f'<div class="glow" data-layout-ignore style="background:radial-gradient(circle at 50% 46%,{acc}30,transparent 60%)"></div>'
                     f'<div id="endh" class="endh">{esc(handle)}</div><div id="endf" class="endf">{"FOLLOW FOR MORE" if theme.get("lang") == "en" else "FOLLOW KARO"}</div></div>')
        js.append(f'tl.fromTo("#endh",{{y:40,opacity:0}},{{y:0,opacity:1,duration:0.6,ease:"power4.out",immediateRender:false}},{e0 + 0.05:.3f});')
        js.append(f'tl.fromTo("#endf",{{opacity:0}},{{opacity:1,duration:0.4,immediateRender:false}},{e0 + 0.3:.3f});')
        cues.append({"t": round(e0 + 0.05, 3), "file": "sfx/whoosh-cine.mp3", "gain_db": -20, "align": "peak"})
    grain = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>"
             "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/>"
             "<feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .55 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")
    css = f"""
body{{margin:0;background:#07080b}}
#root{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:#07080b;font-family:{SANS};color:#fff}}
.scene{{position:absolute;inset:0;overflow:hidden;z-index:1;background:#07080b}}
.scene.over{{background:transparent;z-index:2}}
.vid{{position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover;z-index:1}}
.glow{{position:absolute;inset:0}}
.cam{{position:absolute;inset:0}}
.prop{{position:absolute;left:40px;top:330px;width:1000px;height:900px;object-fit:contain;mix-blend-mode:lighten;
  -webkit-mask-image:radial-gradient(ellipse 62% 58% at 50% 50%,#000 60%,transparent 100%)}}
.prop.real{{left:0;right:0;top:250px;bottom:690px;margin:auto;width:auto;height:auto;max-width:860px;max-height:800px;object-fit:fill;
  mix-blend-mode:normal;-webkit-mask-image:none!important;mask-image:none!important;border-radius:32px;
  box-shadow:0 40px 90px #000c,0 0 0 1.5px #ffffff22}}
.hud{{position:absolute;left:64px;right:64px;top:196px;display:flex;justify-content:space-between;font-family:{MONO};font-size:30px;
  letter-spacing:2px;color:#c9ced8;z-index:6}}
.hud span{{border:1.5px solid #ffffff30;border-radius:10px;padding:8px 16px;background:#0b0d12cc}}
.hud span:empty{{display:none}}
.hud b{{display:inline-block;width:14px;height:14px;border-radius:4px;background:{acc};margin-right:12px;vertical-align:1px}}
.lpill{{position:absolute;left:0;right:0;margin:auto;top:340px;width:max-content;font-family:{MONO};font-size:32px;letter-spacing:2px;
  color:#0b0d12;background:{acc};padding:8px 20px;border-radius:10px;z-index:5}}
.lpill i{{display:inline-block;width:10px;height:10px;border-radius:50%;background:#0b0d12;margin-right:12px;vertical-align:4px}}
.stat{{position:absolute;left:40px;right:40px;top:560px;text-align:center;font-weight:800;font-size:200px;letter-spacing:-6px;line-height:1;
  color:#fff;text-shadow:0 0 60px {acc}40}}
.tab{{font-variant-numeric:tabular-nums}}
.statsub{{position:absolute;left:80px;right:80px;top:800px;text-align:center;font-family:{SANS};font-weight:700;font-size:48px;letter-spacing:0;line-height:1.15;color:#e6e9ef}}
.panel{{position:absolute;left:100px;width:880px;top:470px;background:linear-gradient(180deg,#151922,#0e1117);border:1.5px solid #ffffff1f;
  border-radius:28px;padding:40px 44px 46px;box-shadow:0 40px 80px #000a, inset 0 1px 0 #ffffff14;box-sizing:border-box}}
.ptitle{{font-family:{MONO};font-size:30px;letter-spacing:2px;color:#9aa3b2;margin-bottom:26px;text-transform:uppercase}}
.ptitle i{{display:inline-block;width:12px;height:12px;border-radius:50%;background:#3ddc84;margin-right:14px;vertical-align:3px;box-shadow:0 0 12px #3ddc84}}
.row{{display:grid;grid-template-columns:1fr auto;row-gap:12px;margin-top:26px}}
.rl{{font-size:42px;font-weight:600;color:#e8ebf0}} .rv{{font-size:42px;font-weight:800;color:#fff;font-variant-numeric:tabular-nums}}
.bar{{grid-column:1/3;height:16px;border-radius:8px;background:#ffffff12;overflow:hidden}}
.fill{{height:100%;border-radius:8px}}
.chartp svg{{display:block;margin-top:10px}}
.endl{{font-weight:800;font-size:64px;text-align:right;margin-top:6px}}
.flowp{{position:absolute;left:150px;top:450px;width:780px;height:660px}}
.fline{{position:absolute;left:28px;top:44px}}
.node{{position:absolute;left:0;width:780px;height:92px;display:flex;align-items:center;font-size:46px;font-weight:700;color:#fff}}
.nd{{width:56px;height:56px;border-radius:50%;background:#2a2f3a;border:4px solid #07080b;margin-right:28px;flex:none}}
.ni{{font-family:{MONO};font-size:28px;color:#7d8696;margin-right:20px}}
.cmp{{position:absolute;left:120px;right:120px;top:470px;height:660px;display:flex;justify-content:space-around;align-items:flex-end}}
.cc{{width:360px;text-align:center}} .cv{{font-weight:800;font-size:86px;line-height:1.05;margin-bottom:18px;letter-spacing:-1px;max-height:2.2em;overflow:hidden}}
.ctrack{{height:400px;display:flex;align-items:flex-end;justify-content:center}} .cbar{{width:180px;border-radius:22px 22px 6px 6px}}
.cl{{font-family:{MONO};font-size:34px;color:#c9ced8;margin-top:20px;letter-spacing:1px}}
.kinsub{{display:block;margin-top:36px;font-family:{SANS};font-weight:700;font-size:48px;letter-spacing:0;line-height:1.2;color:#e6e9ef}}
.kin{{position:absolute;left:70px;right:70px;top:500px;text-align:center;font-weight:800;font-size:150px;line-height:1.02;letter-spacing:-4px}}
.kwm{{display:inline-block;overflow:hidden;vertical-align:bottom;padding:0 12px 6px}} .kw{{display:inline-block}} .kw.acc{{color:{acc}}}
.uline{{width:260px;height:12px;margin:26px auto 0;border-radius:6px;background:{acc};transform-origin:0 50%;box-shadow:0 0 24px {acc}88}}
.shine{{position:absolute;top:0;bottom:0;left:0;width:40%;background:linear-gradient(100deg,transparent,#ffffff14,transparent);pointer-events:none}}
.panel{{overflow:hidden}}
.chat,.term{{position:absolute;left:90px;width:900px;top:440px;background:linear-gradient(180deg,#141821,#0c0f15);border:1.5px solid #ffffff1f;
  border-radius:30px;box-shadow:0 40px 90px #000b, inset 0 1px 0 #ffffff14;overflow:hidden}}
.chead{{display:flex;align-items:center;gap:12px;padding:22px 30px;border-bottom:1.5px solid #ffffff12;font-family:{MONO};font-size:26px;color:#8b93a3;letter-spacing:1px}}
.chead i{{width:16px;height:16px;border-radius:50%;background:#ffffff22}} .chead i:first-child{{background:#ff5f57}} .chead i:nth-child(2){{background:#febc2e}} .chead i:nth-child(3){{background:#28c840}}
.chead span{{margin-left:14px}}
.clogo{{width:56px;height:56px;border-radius:14px;background:#fff;object-fit:contain;padding:6px;box-sizing:border-box}}
.chead:has(.clogo) span{{font-family:{SANS};font-weight:700;font-size:34px;color:#eef1f6;letter-spacing:0}}
.bub{{margin:26px 30px;font-size:42px;line-height:1.3;font-weight:600;display:flex;gap:18px;align-items:flex-start}}
.bub.me{{justify-content:flex-end}} .bub.me div{{background:{acc};color:#0b0d12;border-radius:26px 26px 6px 26px;padding:18px 26px;max-width:640px}}
.bub.ai div{{background:#1d2230;color:#eef1f6;border-radius:26px 26px 26px 6px;padding:18px 26px;max-width:680px}}
.bub .av{{width:44px;height:44px;border-radius:12px;flex:none;margin-top:8px;background:conic-gradient({acc},{cool},{acc})}}
.tbody{{padding:26px 34px 34px;font-family:{MONO};font-size:36px;line-height:1.55;color:#d6dbe4;position:relative}}
.tl{{white-space:pre;overflow:hidden}} .tl.hl{{color:{acc};background:#ffffff0c;border-radius:8px;margin:0 -12px;padding:0 12px}}
.tp{{color:#5d6677;margin-right:18px}}
.cur{{display:inline-block;width:20px;height:40px;background:{acc};vertical-align:-6px;animation:none}}
.cap{{position:absolute;left:80px;width:{W - 160}px;top:{CAP_Y}px;z-index:7;text-align:center;font-family:{SANS};font-weight:700;font-size:58px;
  line-height:1.18;letter-spacing:-0.5px;color:#fff;text-shadow:0 4px 18px #000c}}
.cap .w{{opacity:0.55}} .cap .key{{color:{acc}}}
.grain{{position:absolute;inset:-50px;z-index:30;pointer-events:none;opacity:.07;background-image:url("{grain}");mix-blend-mode:overlay}}
.vign{{position:absolute;inset:0;z-index:29;pointer-events:none;background:radial-gradient(ellipse 80% 70% at 50% 48%,transparent 55%,#000c 100%)}}
.endc{{position:absolute;inset:0;z-index:20;background:#07080b}}
""" + (f"""
.stg{{position:absolute;inset:0;transform-origin:50% 730px}}
.hgrid{{position:absolute;inset:0;opacity:1;background-image:linear-gradient(#ffffff08 1px,transparent 1px),linear-gradient(90deg,#ffffff08 1px,transparent 1px),
  linear-gradient(#ffffff0f 1px,transparent 1px),linear-gradient(90deg,#ffffff0f 1px,transparent 1px);
  background-size:48px 48px,48px 48px,192px 192px,192px 192px;-webkit-mask-image:radial-gradient(ellipse 75% 60% at 50% 45%,#000 30%,transparent 85%)}}
.grain{{display:none}}
.cap{{left:0;right:0;margin:auto;width:fit-content;max-width:960px;top:{STAGE_CAP_Y}px;font-size:52px;line-height:1.2;padding:18px 34px 20px 64px;
  background:#0b0d12e0;border:1.5px solid #ffffff24;border-radius:30px;box-shadow:0 18px 40px #0009;text-shadow:none;box-sizing:border-box}}
.cap:before{{content:"";position:absolute;left:28px;top:38px;width:14px;height:14px;border-radius:50%;background:{acc};box-shadow:0 0 12px {acc}}}
""" if stage else "") + (f"""
.prop{{left:0;top:250px;width:1080px;height:980px;-webkit-mask-image:radial-gradient(ellipse 72% 66% at 50% 50%,#000 62%,transparent 100%)}}
.cap .key{{font-size:1.22em;color:{acc}}}
.grain{{opacity:.04}}
.bgimg{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover;z-index:0}}
.bgshade{{position:absolute;inset:0;z-index:0;background:linear-gradient(180deg,#07080bd9 0%,#07080b66 18%,#07080b33 42%,#07080b8c 62%,#07080bf2 80%,#07080b 100%)}}
.cam{{z-index:1}} .scene .hud,.scene .lpill{{z-index:3}}
.cam:has(.prop:not(.real)){{mix-blend-mode:lighten}}
.bgshade.real{{background:linear-gradient(180deg,#07080b99 0%,#07080b00 16%,#07080b00 70%,#07080bcc 88%,#07080b 100%)}}
.stat{{font-size:250px;top:520px;text-shadow:0 8px 40px #000e,0 0 70px {acc}55}}
.statsub{{font-size:58px;top:800px;text-shadow:0 4px 24px #000}}
.kin{{font-size:168px;text-shadow:0 10px 50px #000e}} .kinsub{{font-size:56px}}
.panel,.chat,.term{{left:60px;width:960px;background:linear-gradient(180deg,#151922f0,#0e1117f2)}}
.rl,.rv{{font-size:50px}} .ptitle{{font-size:34px}}
.node{{font-size:56px;text-shadow:0 4px 22px #000}} .nd{{width:64px;height:64px}}
.cv{{text-shadow:0 6px 28px #000}} .cl{{font-size:40px;color:#fff;text-shadow:0 3px 14px #000}}
.bub{{font-size:46px}}
.cap{{font-size:62px;text-shadow:0 4px 22px #000,0 0 3px #000}}
""" if film else "") + ("".join(_scope(skin_css(k, acc), k) for k in sorted(set(sks))) if film else "") + phone_scenes.css(acc, bool(theme.get("phone"))) + f"""
.endh{{position:absolute;left:0;width:{W}px;top:800px;text-align:center;font-weight:800;font-size:110px;letter-spacing:-3px}}
.endf{{position:absolute;left:0;width:{W}px;top:950px;text-align:center;font-family:{MONO};font-size:36px;letter-spacing:6px;color:{acc}}}
"""
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<style>{css}</style></head><body>
<div id="root"{' data-motion-blur="on"' if film else ''} data-composition-id="main" data-width="{W}" data-height="{H}" data-duration="{total:.3f}" data-start="0">
{chr(10).join(top)}
{chr(10).join(scenes)}
{chr(10).join(capdiv)}
{chr(10).join(brand)}
<div class="vign" data-layout-ignore></div><div class="grain" data-layout-ignore></div>
<audio id="mix" class="clip" src="assets/mix.wav" data-start="0" data-duration="{total:.3f}" data-track-index="10"></audio>
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
<script>
const tl=gsap.timeline({{paused:true}});
{chr(10).join(js)}
{chr(10).join(cap_js)}
window.__timelines=window.__timelines||{{}};window.__timelines["main"]=tl;
</script></body></html>"""
    return doc, cues
