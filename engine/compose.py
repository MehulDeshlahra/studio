"""Plan + timings + assets -> HyperFrames page (render/index.html) + SFX cues. Generic for every channel.
Scene types: image (still + camera move), clip (generated video), flow (animated step diagram), card (big word)."""
import html, json, os, re

W, H = 1080, 1920
ENTER = ["zoom", "slide", "wipe", "spin", "zoom", "drop"]


def esc(s):
    return html.escape(s or "")


def chunks(words, keys):
    """3-word caption chunks; never a lone last word; break at punctuation."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        left = len(words) - i - 1
        if (len(cur) == 3 and left != 1) or (w["w"].endswith((",", ".", "?", "!")) and len(cur) > 1 and left != 1) or left == 0:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def page(plan, timed, total, theme, assets):
    acc, acc2, bg = theme.get("accent", "#ffd84d"), theme.get("accent2", "#3ec7ff"), theme.get("bg", "#050b1a")
    font = theme.get("font", "Archivo Black")
    scenes, top, caps, js, cues = [], [], [], [], []
    keys = set()
    for s in plan["scenes"]:
        for k in s.get("keywords") or []:
            keys.update(re.sub(r"[^a-z0-9 ]", "", k.lower()).split())
    n = len(timed)
    for i, (s, t) in enumerate(zip(plan["scenes"], timed)):
        a = 0.0 if i == 0 else t["start"] - 0.08
        b = (timed[i + 1]["start"] - 0.08) if i + 1 < n else total
        d = round(b - a, 3)
        sid = f"s{i}"
        kind, img = s["type"], assets.get(i, {}).get("image")
        inner = ""
        if kind == "clip" and assets.get(i, {}).get("video"):
            top.append(f'<video id="v{i}" class="clip bg" src="assets/{os.path.basename(assets[i]["video"])}" muted playsinline '
                       f'data-start="{a:.3f}" data-duration="{d:.3f}" data-media-start="0.2" data-track-index="0" style="z-index:1"></video>')
            js.append(f'tl.fromTo("#v{i}",{{scale:1.0}},{{scale:1.08,duration:{d:.3f},ease:"none"}},{a:.3f});')
        elif kind == "flow":
            inner += f'<div class="flowbg"></div>'
            if img:
                inner += f'<img id="{sid}i" class="bg dim" src="assets/{os.path.basename(img)}">'
            nodes = s["nodes"][:5]
            k = len(nodes)
            y0, gap = 420, min(190, 700 // max(1, k - 1)) if k > 1 else 0
            for j, lab in enumerate(nodes):
                y = y0 + j * gap
                inner += f'<div id="{sid}n{j}" class="node" style="top:{y}px">{esc(lab.upper())}</div>'
                if j:
                    inner += f'<div id="{sid}a{j}" class="arrow" style="top:{y - gap + 104}px;height:{gap - 112}px"></div>'
                t_in = a + 0.25 + j * min(0.9, (d * 0.6) / k)
                js.append(f'tl.fromTo("#{sid}n{j}",{{scale:0.4,opacity:0}},{{scale:1,opacity:1,duration:0.3,ease:"back.out(2.2)",immediateRender:false}},{t_in:.3f});')
                js.append(f'tl.set("#{sid}n{j}",{{opacity:0}},{a:.3f});')
                if j:
                    js.append(f'tl.fromTo("#{sid}a{j}",{{scaleY:0}},{{scaleY:1,duration:0.25,transformOrigin:"50% 0%",immediateRender:false}},{t_in - 0.2:.3f});')
                    js.append(f'tl.set("#{sid}a{j}",{{scaleY:0}},{a:.3f});')
                cues.append({"t": round(t_in, 3), "file": "sfx/click-ui.mp3", "gain_db": -19, "align": "onset"})
            inner += f'<div id="{sid}dot" class="dot" style="top:{y0 + 40}px"></div>'
            if k > 1:
                t_go = a + 0.25 + k * min(0.9, (d * 0.6) / k)
                js.append(f'tl.set("#{sid}dot",{{opacity:0}},{a:.3f});')
                js.append(f'tl.fromTo("#{sid}dot",{{y:0,opacity:1}},{{y:{(k - 1) * gap},duration:{max(0.6, b - t_go - 0.3):.3f},ease:"power1.inOut",immediateRender:false}},{t_go:.3f});')
        else:
            if img:
                inner += f'<img id="{sid}i" class="bg" src="assets/{os.path.basename(img)}">'
                m = s.get("motion", "push")
                frm, to = {"push": ("{scale:1.02}", "{scale:1.16}"), "pull": ("{scale:1.2}", "{scale:1.03}"),
                           "pan": ("{scale:1.15,x:-50}", "{scale:1.15,x:50}"), "tilt": ("{scale:1.12,rotation:-2.5}", "{scale:1.12,rotation:2.5}"),
                           "punch": ("{scale:1.04}", "{scale:1.14}")}[m]
                js.append(f'tl.fromTo("#{sid}i",{frm},{to[:-1]},duration:{d:.3f},ease:"none"}},{a:.3f});')
                if m == "punch":
                    mid = a + d * 0.5
                    js.append(f'tl.to("#{sid}i",{{scale:"+=0.08",duration:0.18,ease:"power4.out"}},{mid:.3f});')
            if kind == "card":
                bsz = int(min(190, 880 / max(4, len(s.get("big", ""))) / 0.60))
                inner += f'<div class="shade"></div><div id="{sid}b" class="big" style="font-size:{bsz}px">{esc(s.get("big", "").upper())}</div>'
                if s.get("small"):
                    inner += f'<div id="{sid}m" class="small">{esc(s["small"].upper())}</div>'
                    js.append(f'tl.fromTo("#{sid}m",{{y:40,opacity:0}},{{y:0,opacity:1,duration:0.3,immediateRender:false}},{a + 0.45:.3f});')
                    js.append(f'tl.set("#{sid}m",{{opacity:0}},{a:.3f});')
                js.append(f'tl.fromTo("#{sid}b",{{scale:2.6,opacity:0,rotation:-6}},{{scale:1,opacity:1,rotation:-2,duration:0.35,ease:"power4.out",immediateRender:false}},{a + 0.1:.3f});')
                js.append(f'tl.set("#{sid}b",{{opacity:0}},{a:.3f});')
                cues.append({"t": round(a + 0.12, 3), "file": "sfx/impact.mp3", "gain_db": -18, "align": "onset"})

            js.append(f'tl.fromTo("#{sid}k",{{y:140,rotation:4,opacity:0}},{{y:0,rotation:-1.5,opacity:1,duration:0.45,ease:"back.out(1.6)",immediateRender:false}},{a + 0.12:.3f});')
            js.append(f'tl.set("#{sid}k",{{opacity:0}},{a:.3f});')
            cues.append({"t": round(a + 0.12, 3), "file": "sfx/impact.mp3", "gain_db": -20, "align": "onset"})
        if kind == "choice":
            inner += '<div class="shade"></div>'
            for j, o in enumerate((s.get("options") or [])[:3]):
                inner += f'<div id="{sid}o{j}" class="opt"  style="top:{470 + j * 230}px"><span class="ab">{"ABC"[j]}</span>{esc(o.upper())}</div>'
                js.append(f'tl.fromTo("#{sid}o{j}",{{x:-700,opacity:0}},{{x:0,opacity:1,duration:0.4,ease:"power3.out",immediateRender:false}},{a + 0.2 + j * 0.28:.3f});')
                js.append(f'tl.set("#{sid}o{j}",{{opacity:0}},{a:.3f});')
                cues.append({"t": round(a + 0.2 + j * 0.28, 3), "file": "sfx/click-select.mp3", "gain_db": -18, "align": "onset"})
            inner += f'<div id="{sid}cm" class="cmt">COMMENT KARO: A, B YA C</div>'
            js.append(f'tl.fromTo("#{sid}cm",{{scale:0.7,opacity:0}},{{scale:1,opacity:1,duration:0.35,ease:"back.out(2)",immediateRender:false}},{a + 1.2:.3f});')
            js.append(f'tl.to("#{sid}cm",{{scale:1.06,duration:0.5,yoyo:true,repeat:5,ease:"sine.inOut"}},{a + 1.6:.3f});')
            js.append(f'tl.set("#{sid}cm",{{opacity:0}},{a:.3f});')
        if plan.get("hud_left"):
            inner += f'<div class="hud"><span>{esc(plan["hud_left"])}</span><span>{esc(s.get("hud_right", ""))}</span></div>'
        if kind == "clue":
            inner += (f'<div class="shade"></div><div id="{sid}k" class="paper"><div class="stamp">{esc(s.get("label", "SURAAG").upper())}</div>'
                      f'<div class="who">{esc(s.get("who", "").upper())}</div><div class="quote">&ldquo;{esc(s.get("quote", ""))}&rdquo;</div></div>')
            js.append(f'tl.fromTo("#{sid}k",{{y:140,rotation:4,opacity:0}},{{y:0,rotation:-1.5,opacity:1,duration:0.45,ease:"back.out(1.6)",immediateRender:false}},{a + 0.12:.3f});')
            js.append(f'tl.set("#{sid}k",{{opacity:0}},{a:.3f});')
            cues.append({"t": round(a + 0.12, 3), "file": "sfx/impact.mp3", "gain_db": -20, "align": "onset"})
        if kind == "choice":
            inner += '<div class="shade"></div>'
            for j, o in enumerate((s.get("options") or [])[:3]):
                inner += f'<div id="{sid}o{j}" class="opt" style="top:{470 + j * 230}px"><span class="ab">{"ABC"[j]}</span>{esc(o.upper())}</div>'
                js.append(f'tl.fromTo("#{sid}o{j}",{{x:-700,opacity:0}},{{x:0,opacity:1,duration:0.4,ease:"power3.out",immediateRender:false}},{a + 0.2 + j * 0.28:.3f});')
                js.append(f'tl.set("#{sid}o{j}",{{opacity:0}},{a:.3f});')
                cues.append({"t": round(a + 0.2 + j * 0.28, 3), "file": "sfx/click-select.mp3", "gain_db": -18, "align": "onset"})
            inner += f'<div id="{sid}cm" class="cmt">COMMENT KARO: A, B YA C</div>'
            js.append(f'tl.fromTo("#{sid}cm",{{scale:0.7,opacity:0}},{{scale:1,opacity:1,duration:0.35,ease:"back.out(2)",immediateRender:false}},{a + 1.2:.3f});')
            js.append(f'tl.to("#{sid}cm",{{scale:1.06,duration:0.5,yoyo:true,repeat:5,ease:"sine.inOut"}},{a + 1.6:.3f});')
            js.append(f'tl.set("#{sid}cm",{{opacity:0}},{a:.3f});')
        if plan.get("hud_left"):
            inner += f'<div class="hud"><span>{esc(plan["hud_left"])}</span><span>{esc(s.get("hud_right", ""))}</span></div>'
        if s.get("title"):
            inner += f'<div id="{sid}t" class="tag"><span class="pill">{esc(s["title"].upper())}</span></div>'
            js.append(f'tl.fromTo("#{sid}t",{{scale:0.3,opacity:0}},{{scale:1,opacity:1,duration:0.3,ease:"back.out(2.5)",immediateRender:false}},{a + 0.15:.3f});')
            js.append(f'tl.set("#{sid}t",{{opacity:0}},{a:.3f});')
            cues.append({"t": round(a + 0.15, 3), "file": "sfx/pop-light.mp3", "gain_db": -17, "align": "onset"})
        # scene entrance (varied)
        if i:
            e = ENTER[i % len(ENTER)]
            tgt = f"#{sid}" if kind != "clip" else f"#v{i}"
            if e == "zoom":
                js.append(f'tl.fromTo("{tgt}",{{scale:1.35,opacity:0.2}},{{scale:1,opacity:1,duration:0.3,ease:"power3.out",immediateRender:false}},{a:.3f});')
            elif e == "slide":
                js.append(f'tl.fromTo("{tgt}",{{yPercent:100}},{{yPercent:0,duration:0.32,ease:"power3.out",immediateRender:false}},{a:.3f});')
            elif e == "wipe":
                js.append(f'tl.fromTo("{tgt}",{{clipPath:"inset(0% 100% 0% 0%)"}},{{clipPath:"inset(0% 0% 0% 0%)",duration:0.3,ease:"power2.out",immediateRender:false}},{a:.3f});')
            elif e == "spin":
                js.append(f'tl.fromTo("{tgt}",{{rotation:-8,scale:1.25,opacity:0}},{{rotation:0,scale:1,opacity:1,duration:0.35,ease:"back.out(1.4)",immediateRender:false}},{a:.3f});')
            else:
                js.append(f'tl.fromTo("{tgt}",{{yPercent:-100}},{{yPercent:0,duration:0.3,ease:"power3.out",immediateRender:false}},{a:.3f});')
            cues.append({"t": round(a + 0.1, 3), "file": ["sfx/whoosh-fast.mp3", "sfx/air-zoom.mp3", "sfx/sweep-small.mp3"][i % 3],
                         "gain_db": -18, "align": "peak" if i % 3 == 0 else "onset"})
        if kind == "clip" and assets.get(i, {}).get("video"):
            scenes.append(f'<div id="{sid}" class="clip scene over" data-start="{a:.3f}" data-duration="{d:.3f}" data-track-index="1">{inner}</div>')
        else:
            scenes.append(f'<div id="{sid}" class="clip scene" data-start="{a:.3f}" data-duration="{d:.3f}" data-track-index="1">{inner}</div>')
        # captions
        for ci, c in enumerate(chunks(t["words"], keys)):
            cs = c[0]["s"] - (0.08 if ci == 0 else 0)
            ce = c[-1]["e"] + 0.12
            spans = []
            for w in c:
                k = re.sub(r"[^a-z0-9]", "", w["w"].lower())
                spans.append(f'<span class="w{" key" if k in keys else ""}" data-t="{max(0, w["s"] - cs):.2f}">{esc(w["w"].strip(".,!").replace("...", "").upper())}</span>')
            caps.append((cs, ce, " ".join(spans)))
    capdiv = []
    for j, (cs, ce, sp) in enumerate(caps):
        if j + 1 < len(caps) and caps[j + 1][0] - ce < 0.5:
            ce = caps[j + 1][0]
        capdiv.append(f'<div id="c{j}" class="clip cap" data-start="{cs:.3f}" data-duration="{max(0.3, ce - cs):.3f}" data-track-index="9">{sp}</div>')
    css = f"""
body{{margin:0;background:{bg}}}
#root{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:{bg};font-family:'{font}',sans-serif}}
.scene{{position:absolute;inset:0;overflow:hidden;z-index:1;background:{bg}}}
.scene.over{{background:transparent;z-index:2}}
.bg{{position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover}}
.bg.dim{{opacity:.28}}
.flowbg{{position:absolute;inset:0;background:radial-gradient(circle at 50% 40%,#10285a,{bg} 70%)}}
.shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.15),rgba(0,0,0,.55) 50%,rgba(0,0,0,.2))}}
.tag{{position:absolute;left:0;width:{W}px;top:300px;text-align:center;z-index:3}}
.pill{{display:inline-block;background:{acc};color:#0a0f20;font-size:64px;padding:16px 36px;border-radius:22px;box-shadow:0 10px 0 #000;max-width:820px}}
.node{{position:absolute;left:190px;width:700px;height:104px;line-height:104px;text-align:center;font-size:54px;color:#fff;
  background:#0b1630;border:5px solid {acc2};border-radius:28px;box-shadow:0 0 30px rgba(62,199,255,.35)}}
.arrow{{position:absolute;left:534px;width:12px;background:{acc};border-radius:6px}}
.dot{{position:absolute;left:510px;width:60px;height:60px;border-radius:30px;background:{acc};box-shadow:0 0 40px {acc};z-index:3}}
.big{{position:absolute;left:90px;width:900px;top:560px;text-align:center;font-size:190px;line-height:1;color:{acc};text-shadow:0 12px 0 #000}}
.small{{position:absolute;left:90px;width:900px;top:800px;text-align:center;font-size:66px;color:#fff;text-shadow:0 6px 0 #000}}
.cap{{position:absolute;left:90px;width:900px;top:1190px;z-index:5;text-align:center;font-size:80px;line-height:1.05;color:#fff;
  -webkit-text-stroke:4px #000;paint-order:stroke fill;text-shadow:0 7px 0 #000}}
.paper{{position:absolute;left:110px;width:860px;top:520px;background:#e9dcc0;color:#2a1a0a;border-radius:10px;padding:48px 44px 54px;box-shadow:0 24px 60px rgba(0,0,0,.65);transform:rotate(-1.5deg)}}
.paper .stamp{{position:absolute;top:-34px;left:34px;background:#b3261e;color:#fff;font-size:44px;padding:8px 24px;border-radius:8px;transform:rotate(-3deg)}}
.paper .who{{font-size:62px;line-height:1.05;margin-top:12px;color:#7a1a12}}
.paper .quote{{font-family:Inter,sans-serif;font-weight:700;font-size:46px;line-height:1.25;margin-top:22px}}
.opt{{position:absolute;left:100px;width:880px;height:180px;display:flex;align-items:center;font-size:62px;color:#fff;background:rgba(10,16,22,.88);border:5px solid {acc};border-radius:26px;box-shadow:0 12px 0 #000}}
.opt .ab{{display:inline-block;width:130px;text-align:center;font-size:96px;color:{acc};margin-right:10px}}
.cmt{{position:absolute;left:0;width:{W}px;top:1150px;text-align:center;font-size:58px;color:#fff;text-shadow:0 6px 0 #000;z-index:4}}
.hud{{position:absolute;left:70px;width:940px;top:200px;display:flex;justify-content:space-between;font-family:Inter,sans-serif;font-weight:800;font-size:34px;color:#fff;letter-spacing:3px;z-index:3;text-shadow:0 3px 0 #000}}
.hud span:first-child{{background:#b3261e;padding:6px 18px;border-radius:8px}}
.paper{{position:absolute;left:110px;width:860px;top:470px;background:#e9dcc0;color:#2a1a0a;border-radius:10px;padding:48px 44px 54px;box-shadow:0 24px 60px rgba(0,0,0,.65)}}
.paper .stamp{{position:absolute;top:-34px;left:34px;background:#b3261e;color:#fff;font-size:44px;padding:8px 24px;border-radius:8px;transform:rotate(-3deg)}}
.paper .who{{font-size:62px;line-height:1.05;margin-top:12px;color:#7a1a12}}
.paper .quote{{font-family:Inter,sans-serif;font-weight:700;font-size:46px;line-height:1.25;margin-top:22px}}
.opt{{position:absolute;left:100px;width:880px;height:180px;display:flex;align-items:center;font-size:62px;color:#fff;background:rgba(10,16,22,.88);border:5px solid {acc};border-radius:26px;box-shadow:0 12px 0 #000}}
.opt .ab{{display:inline-block;width:130px;text-align:center;font-size:96px;color:{acc};margin-right:10px}}
.cmt{{position:absolute;left:0;width:{W}px;top:1150px;text-align:center;font-size:58px;color:#fff;text-shadow:0 6px 0 #000;z-index:4}}
.hud{{position:absolute;left:70px;width:940px;top:200px;display:flex;justify-content:space-between;font-family:Inter,sans-serif;font-weight:800;font-size:34px;color:#fff;letter-spacing:3px;z-index:3;text-shadow:0 3px 0 #000}}
.hud span:first-child{{background:#b3261e;padding:6px 18px;border-radius:8px}}
.cap .w{{display:inline-block}} .cap .key{{color:{acc}}}
"""
    cap_js = """document.querySelectorAll(".cap").forEach(c=>{const s=parseFloat(c.dataset.start);
 c.querySelectorAll(".w").forEach(w=>{tl.fromTo(w,{opacity:0.8,scale:0.9},{opacity:1,scale:1,duration:0.12,ease:"back.out(3)",immediateRender:false},s+parseFloat(w.dataset.t));});
 tl.set(c.querySelectorAll(".w"),{opacity:0.8},s);});"""
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
<div id="root" data-composition-id="main" data-width="{W}" data-height="{H}" data-duration="{total:.3f}" data-start="0">
{chr(10).join(top)}
{chr(10).join(scenes)}
{chr(10).join(capdiv)}
<audio id="mix" class="clip" src="assets/mix.wav" data-start="0" data-duration="{total:.3f}" data-track-index="10"></audio>
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
<script>
const tl=gsap.timeline({{paused:true}});
{chr(10).join(js)}
{cap_js}
window.__timelines=window.__timelines||{{}};window.__timelines["main"]=tl;
</script></body></html>"""
    return doc, cues
