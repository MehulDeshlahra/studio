"""tech-003 pilot: 'Phone ulta karte hi screen kaise ghoom jaati hai?' -> render/index.html
Sentence times come from whisper on the Gemini (Charon) VO; words inside a sentence are spread by length."""
import json, os, re, shutil, html

D = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(D, "render")
VO_END = 41.72
TOTAL = 42.6

S = [  # text, start, end
    ("Phone ulta kiya... aur screen khud ghoom gayi.", 0.00, 2.95),
    ("Par phone ko pata kaise chala?", 3.20, 4.95),
    ("Jaadu nahi hai.", 5.48, 6.60),
    ("Aapke phone ke andar ek chhota sa chip hai.", 6.82, 9.00),
    ("Naam hai... accelerometer.", 9.42, 11.25),
    ("Is chip ke andar ek bahut hi chhota sa wazan hai, jo patli patli springs pe latka hota hai.", 11.60, 15.50),
    ("Jaise hi aap phone terha karte ho, gravity us wazan ko neeche kheenchti hai,", 16.18, 19.95),
    ("aur woh thoda sa khisak jaata hai.", 20.54, 21.85),
    ("Wazan ke dono taraf metal ki plates hain.", 22.26, 24.50),
    ("Woh khiska, plates ke beech ka gap badla,", 24.60, 26.85),
    ("aur chip ne turant naap liya ki neeche kis taraf hai.", 27.02, 30.10),
    ("Phone samajh gaya ki aapne use terha pakda hai, aur screen ghuma di.", 30.58, 33.60),
    ("Ek second se bhi kam mein.", 33.96, 35.10),
    ("Aur mazedaar baat?", 35.70, 36.45),
    ("Yahi chip aapke kadam bhi ginta hai.", 36.58, 38.80),
    ("Agla sawaal aap batao, comment mein.", 39.18, 41.00),
]
KEY = {"ulta", "ghoom", "kaise", "jaadu", "chip", "accelerometer.", "wazan", "springs", "gravity", "khisak",
       "plates", "gap", "neeche", "turant", "ghuma", "second", "mazedaar", "kadam", "comment"}


def chunks():
    out = []
    for text, a, b in S:
        words = text.split()
        lens = [len(w) + 2 for w in words]
        tot, t, times = sum(lens), a, []
        for w, l in zip(words, lens):
            d = (b - a) * l / tot
            times.append((w, t, t + d)); t += d
        cur = []
        for i, (w, s, e) in enumerate(times):
            cur.append((w, s, e))
            last2 = i == len(times) - 2 and len(cur) < 3
            if (len(cur) == 3 and not (i == len(times) - 2)) or (w.endswith((",", ".", "?")) and len(cur) > 1) or i == len(times) - 1:
                out.append(cur); cur = []
    return out


def cap_html():
    groups, n = [], 0
    ch = chunks()
    for i, c in enumerate(ch):
        s = c[0][1]
        e = ch[i + 1][0][1] if i + 1 < len(ch) and ch[i + 1][0][1] - c[-1][2] < 0.45 else c[-1][2] + 0.25
        spans = []
        for w, ws, we in c:
            k = re.sub(r"[^a-z.]", "", w.lower())
            cls = "w key" if k in KEY or k.rstrip(".") in KEY else "w"
            spans.append(f'<span class="{cls}" data-t="{ws - s:.2f}">{html.escape(w.strip(".,").replace("...", "").upper())}</span>')
        groups.append(f'<div id="c{n}" class="clip cap" data-start="{s:.2f}" data-duration="{e - s:.2f}" data-track-index="9">{" ".join(spans)}</div>')
        n += 1
    return "\n".join(groups)


def svg_chip():
    zig = lambda x, y0, y1: "M{} {} ".format(x, y0) + " ".join(
        f"L{x + (34 if i % 2 else -34)} {y0 + (y1 - y0) * (i + 0.5) / 8:.0f}" for i in range(8)) + f" L{x} {y1}"
    return f'''
<svg id="dia" viewBox="0 0 1080 1100" width="1080" height="1100">
  <defs><linearGradient id="mg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffd84d"/><stop offset="1" stop-color="#ff9f1c"/></linearGradient></defs>
  <g id="tilt">
    <rect x="170" y="150" width="740" height="800" rx="46" fill="#0b1630" stroke="#3ec7ff" stroke-width="6"/>
    <rect id="plL" x="250" y="330" width="34" height="440" rx="8" fill="#9fb3c8"/>
    <rect id="plR" x="796" y="330" width="34" height="440" rx="8" fill="#9fb3c8"/>
    <rect x="440" y="200" width="200" height="22" rx="6" fill="#3ec7ff"/>
    <rect x="440" y="878" width="200" height="22" rx="6" fill="#3ec7ff"/>
    <g id="mass">
      <path d="{zig(540, 222, 420)}" stroke="#7fe0ff" stroke-width="9" fill="none" stroke-linejoin="round"/>
      <path d="{zig(540, 680, 878)}" stroke="#7fe0ff" stroke-width="9" fill="none" stroke-linejoin="round"/>
      <rect x="420" y="420" width="240" height="260" rx="22" fill="url(#mg)"/>
      <text x="540" y="565" text-anchor="middle" font-family="Archivo Black" font-size="46" fill="#1a1200">WAZAN</text>
    </g>
    <g id="gapL"><rect x="296" y="540" width="112" height="20" rx="10" fill="#38f28a"/></g>
    <g id="gapR"><rect x="672" y="540" width="112" height="20" rx="10" fill="#ff4d6d"/></g>
  </g>
  <g id="grav"><path d="M540 990 L540 1080 M505 1045 L540 1085 L575 1045" stroke="#ffd84d" stroke-width="14" fill="none" stroke-linecap="round"/></g>
</svg>'''


def page():
    return f'''<!doctype html><html><head><meta charset="utf-8">
<style>
body{{margin:0;background:#050b1a}}
#root{{position:relative;width:1080px;height:1920px;overflow:hidden;background:#050b1a;font-family:'Archivo Black',sans-serif}}
.scene{{position:absolute;inset:0;overflow:hidden;z-index:1}}
.bg{{position:absolute;inset:0;width:1080px;height:1920px;object-fit:cover}}
.title{{position:absolute;left:130px;width:820px;top:310px;text-align:center;color:#fff;font-size:80px;line-height:1.02;
  text-shadow:0 8px 0 #000,0 0 40px rgba(0,0,0,.7)}}
.title b{{color:#ffd84d;font-weight:400}}
.tag{{position:absolute;left:50%;top:330px;transform:translateX(-50%);}}
.pill{{background:#ffd84d;color:#0a0f20;font-size:70px;padding:18px 40px;border-radius:24px;white-space:nowrap;box-shadow:0 12px 0 #000}}
.cap{{position:absolute;left:90px;width:900px;top:1190px;z-index:5;text-align:center;font-size:80px;line-height:1.05;color:#fff;
  -webkit-text-stroke:3px #000;paint-order:stroke fill;text-shadow:0 7px 0 #000}}
.cap .key{{color:#ffd84d}} .cap .w{{display:inline-block}}
.ai{{position:absolute;left:60px;top:230px;z-index:5;font-family:Inter,sans-serif;font-size:30px;color:rgba(255,255,255,.75);
  background:rgba(0,0,0,.45);padding:8px 16px;border-radius:12px}}
#dia{{position:absolute;left:0;top:260px}}
.lbl{{position:absolute;left:0;width:1080px;text-align:center;color:#fff;font-size:66px;text-shadow:0 6px 0 #000}}
.cnt{{position:absolute;left:0;width:1080px;top:330px;text-align:center;font-size:170px;color:#ffd84d;text-shadow:0 10px 0 #000}}
</style></head><body>
<div id="root" data-composition-id="main" data-width="1080" data-height="1920" data-duration="{TOTAL}" data-start="0">

<video id="bVid" class="clip bg" src="assets/talk.mp4" muted playsinline data-start="3.1" data-duration="2.3" data-media-start="0.3" data-track-index="0" style="z-index:0"></video>
<div id="sA" class="clip scene" data-start="0" data-duration="3.1" data-track-index="1">
  <img id="aDizzy" class="bg" src="assets/dizzy.webp">
  <img id="aUp" class="bg" src="assets/mascot.webp" style="opacity:0">
  <div id="aT" class="title">PHONE KO <b>PATA</b><br>KAISE CHALA?</div>
</div>
<div id="sB" class="clip scene" data-start="3.1" data-duration="2.3" data-track-index="1">
  <div id="bQ" class="title" style="font-size:240px;top:260px">?</div>
</div>
<div id="sC" class="clip scene" data-start="5.4" data-duration="6.1" data-track-index="1">
  <img id="cImg" class="bg" src="assets/chip.webp">
  <div id="cT" class="tag"><div class="pill">ACCELEROMETER</div></div>
</div>
<div id="sD" class="clip scene" data-start="11.5" data-duration="10.7" data-track-index="1" style="background:radial-gradient(circle at 50% 40%,#10285a,#050b1a 70%)">
  {svg_chip()}
  <div id="dL" class="lbl" style="top:300px">CHIP KE ANDAR</div>
</div>
<div id="sE" class="clip scene" data-start="22.2" data-duration="8.3" data-track-index="1" style="background:radial-gradient(circle at 50% 40%,#10285a,#050b1a 70%)">
  <div id="eZoom" style="position:absolute;inset:0">{svg_chip().replace('id="', 'id="e')}</div>
  <div id="eL" class="lbl" style="top:300px">GAP BADLA = <span style="color:#ffd84d">SIGNAL</span></div>
</div>
<div id="sF" class="clip scene" data-start="30.5" data-duration="5.1" data-track-index="1">
  <img id="fImg" class="bg" src="assets/sideways.webp">
  <div id="fT" class="tag" style="top:300px"><div class="pill">&lt; 1 SECOND</div></div>
</div>
<div id="sG" class="clip scene" data-start="35.6" data-duration="3.5" data-track-index="1">
  <img id="gImg" class="bg" src="assets/walk.webp">
  <div id="gN" class="cnt">1</div>
  <div id="gL" class="lbl" style="top:530px">KADAM BHI GINTA HAI</div>
</div>
<div id="sH" class="clip scene" data-start="39.1" data-duration="{TOTAL - 39.1:.2f}" data-track-index="1">
  <img id="hImg" class="bg" src="assets/mascot.webp">
  <div id="hT" class="title">AGLA <b>SAWAAL?</b><br>COMMENT KARO</div>
</div>

<div id="aiTag" data-layout-ignore class="clip ai" data-start="0" data-duration="{TOTAL}" data-track-index="8">AI visuals</div>
{cap_html()}
<audio id="mix" src="assets/mix.wav" data-start="0" data-duration="{VO_END}" class="clip" data-track-index="10"></audio>
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
<script>
const tl = gsap.timeline({{paused:true}});
const P = (sel,o,t)=>tl.fromTo(sel,o[0],Object.assign({{immediateRender:false}},o[1]),t);
// A hook: upside-down phone flips upright
tl.fromTo("#aDizzy",{{scale:1.08}},{{scale:1.0,duration:1.5,ease:"power2.out"}},0);
tl.fromTo("#aT",{{scale:1.25,opacity:0}},{{scale:1,opacity:1,duration:0.25,ease:"back.out(2)"}},0);
tl.to("#aDizzy",{{rotation:180,scale:1.25,opacity:0,duration:0.35,ease:"power3.in"}},1.55);
P("#aUp",[{{rotation:-180,scale:1.25,opacity:0}},{{rotation:0,scale:1,opacity:1,duration:0.4,ease:"back.out(1.6)"}}],1.75);
// B question
P("#bQ",[{{scale:0,rotation:-30}},{{scale:1,rotation:0,duration:0.35,ease:"back.out(3)"}}],3.35);
tl.to("#bQ",{{rotation:12,duration:0.5,yoyo:true,repeat:2,ease:"sine.inOut"}},3.7);
// C chip push-in, label
tl.fromTo("#cImg",{{scale:1.0}},{{scale:1.35,duration:6.1,ease:"none"}},5.4);
P("#cT",[{{scale:0,opacity:0}},{{scale:1,opacity:1,duration:0.35,ease:"back.out(2.5)"}}],9.95);
tl.set("#cT",{{opacity:0}},5.4);
// D diagram: mass on springs, phone tilts, gravity pulls
P("#dia",[{{scale:0.6,opacity:0}},{{scale:1,opacity:1,duration:0.5,ease:"power3.out"}}],11.5);
tl.fromTo("#mass",{{y:-30}},{{y:0,duration:0.9,ease:"elastic.out(1,0.35)"}},12.6);
tl.set("#grav",{{opacity:0}},11.5);
tl.to("#tilt",{{rotation:-28,svgOrigin:"540 550",duration:0.8,ease:"power2.inOut"}},16.4);
tl.to("#grav",{{opacity:1,duration:0.2}},18.3);
tl.fromTo("#grav",{{y:-30}},{{y:0,duration:0.5,repeat:3,ease:"power1.in",immediateRender:false}},18.3);
tl.to("#mass",{{x:70,duration:0.7,ease:"back.out(1.4)"}},20.6);
tl.to("#gapL",{{scaleX:2.2,svgOrigin:"296 550",duration:0.7}},20.6);
tl.to("#gapR",{{scaleX:0.35,svgOrigin:"784 550",duration:0.7}},20.6);
P("#dL",[{{y:-40,opacity:0}},{{y:0,opacity:1,duration:0.3}}],11.7);
// E plates close-up
tl.fromTo("#eZoom",{{scale:1}},{{scale:1.12,duration:1.2,ease:"power2.inOut"}},22.4);
tl.to("#eplL,#eplR",{{fill:"#3ec7ff",duration:0.25,yoyo:true,repeat:3}},22.6);
tl.fromTo("#emass",{{x:0}},{{x:70,duration:0.5,ease:"back.out(2)",immediateRender:false}},24.9);
tl.fromTo("#egapR",{{scaleX:1}},{{scaleX:0.35,svgOrigin:"784 550",duration:0.5,immediateRender:false}},24.9);
tl.fromTo("#egapL",{{scaleX:1}},{{scaleX:2.2,svgOrigin:"296 550",duration:0.5,immediateRender:false}},24.9);
P("#eL",[{{scale:0.5,opacity:0}},{{scale:1,opacity:1,duration:0.3,ease:"back.out(2)"}}],25.4);
tl.set("#eL",{{opacity:0}},22.2);
tl.to("#eZoom",{{scale:1,x:0,y:0,duration:0.8,ease:"power2.inOut"}},27.1);
tl.to("#etilt",{{rotation:-28,svgOrigin:"540 550",duration:0.6}},27.1);
tl.set("#emass",{{x:70}},27.1);
tl.fromTo("#egrav",{{y:-40,scale:1}},{{y:0,scale:1.25,svgOrigin:"540 1040",duration:0.4,repeat:3,yoyo:true,immediateRender:false}},28.2);
// F sideways
P("#fImg",[{{rotation:90,scale:1.6}},{{rotation:0,scale:1.08,duration:0.55,ease:"back.out(1.3)"}}],30.5);
tl.to("#fImg",{{scale:1.18,duration:4.5,ease:"none"}},31.05);
tl.set("#fT",{{opacity:0}},30.5);
P("#fT",[{{scale:2.5,opacity:0,rotation:-8}},{{scale:1,opacity:1,rotation:-4,duration:0.3,ease:"power4.out"}}],33.95);
// G steps
tl.fromTo("#gImg",{{scale:1.05,x:0}},{{scale:1.18,x:-40,duration:3.5,ease:"none"}},35.6);
tl.set("#gN,#gL",{{opacity:0}},35.6);
[["1",36.6],["2",37.1],["3",37.6],["4",38.1]].forEach(([n,t])=>{{
  tl.set("#gN",{{opacity:1,textContent:n}},t);
  tl.fromTo("#gN",{{scale:1.6}},{{scale:1,duration:0.25,ease:"back.out(3)",immediateRender:false}},t);
}});
P("#gL",[{{y:30,opacity:0}},{{y:0,opacity:1,duration:0.3}}],36.7);
// H CTA
tl.fromTo("#hImg",{{scale:1.15}},{{scale:1.0,duration:3.5,ease:"power2.out"}},39.1);
P("#hT",[{{y:60,opacity:0}},{{y:0,opacity:1,duration:0.4,ease:"back.out(2)"}}],39.2);
// captions: pop each word
document.querySelectorAll(".cap").forEach(c=>{{
  const s=parseFloat(c.dataset.start);
  c.querySelectorAll(".w").forEach(w=>{{
    tl.fromTo(w,{{opacity:0.4,scale:0.85}},{{opacity:1,scale:1,duration:0.12,ease:"back.out(3)",immediateRender:false}},s+parseFloat(w.dataset.t));
  }});
  tl.set(c.querySelectorAll(".w"),{{opacity:0.4}},s);
}});
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
</script></body></html>'''


if __name__ == "__main__":
    os.makedirs(os.path.join(R, "assets"), exist_ok=True)
    for f in os.listdir(os.path.join(D, "assets")):
        shutil.copy(os.path.join(D, "assets", f), os.path.join(R, "assets", f))
    open(os.path.join(R, "index.html"), "w", encoding="utf-8").write(page())
    print("ok", len(chunks()), "caption groups")

