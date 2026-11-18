"""Phone-story scenes for the lab compositor (19 Nov; owner on the first Finance Fuel video: "similar to tech, not catchy,
random logo/image placement, generated image not matching (euro was showing): it loses relatability").

A finance reel now lives on the viewer's own phone, drawn in HTML so every word and number is exact:
  wa    a WhatsApp-style chat between friends   {"title": "Raghav", "messages": [{"from": "Raghav", "text": ".."}, {"from": "me", "text": ".."}]}
  sms   lock screen with bank SMS / app alerts  {"time": "10:42", "messages": [{"from": "VM-HDFCBK", "text": "Rs 500 debited ..."}]}
  pay   payment app status screen               {"status": "failed|pending|success", "value": "₹500", "to": "Aditya", "sub": "..."}
  bill  receipt / bill breakdown                {"title": "..", "rows": [{"label": "..", "value": ".."}], "total": {"label": "..", "value": ".."}, "tone": "bad|good"}
  rule  official rule card (real logo letterhead) {"title": "RBI circular", "sub": "20 Sep 2019", "lines": ["..", ".."], "stamp": "ASLI NIYAM"}
No AI pictures: the real logo (rule) is the only fetched image, placed on purpose. compose_lab.page() calls scene() for these kinds.
"""
import html, os

KINDS = ("wa", "sms", "pay", "bill", "rule", "table", "list")
#  table comparison grid {"title": "..", "cols": ["", "Prop", "LLP", "Pvt Ltd"], "rows": [{"label": "Risk", "cells": ["..", "..", ".."]}], "best": 2}
#  list  checklist card  {"title": "..", "sub": "..", "lines": ["..", ".."]}
SANS = "'Inter',sans-serif"
MONO = "'JetBrains Mono','IBM Plex Mono',monospace"


def esc(x):
    return html.escape(str(x or ""))


def _rev(sel, t, a, y=26, dur=0.38, ease="power3.out", extra=""):
    """reset to hidden at the scene start, then reveal at t (resets first: compose_lab reorders tl.set lines)."""
    return [f'tl.set("{sel}",{{opacity:0}},{a:.3f});',
            f'tl.fromTo("{sel}",{{y:{y},opacity:0{extra}}},{{y:0,opacity:1,scale:1,duration:{dur},ease:"{ease}",immediateRender:false}},{t:.3f});']


def _phone(sid, cls, inner, time_="10:42"):
    return (f'<div id="{sid}ph" class="pq-ph"><div class="pq-scr {cls}"><div class="pq-isl"></div>'
            f'<div class="pq-sb"><span>{esc(time_)}</span><span>5G&nbsp;&nbsp;▮▮▮&nbsp;&nbsp;82%</span></div>{inner}</div></div>')


def scene(kind, s, sid, a, d, asset):
    js, cues = [], []
    T = lambda f: a + min(d * f, d - 0.3)
    if kind == "wa":
        msgs = [m for m in (s.get("messages") or []) if isinstance(m, dict) and m.get("text")][:4]
        who = s.get("title") or next((m.get("from") for m in msgs if str(m.get("from", "")).lower() not in ("me", "")), "Dost")
        rows = ""
        step = max(0.3, min(0.9, d * 0.4 / max(1, len(msgs))))
        for j, m in enumerate(msgs):
            me = str(m.get("from", "")).lower() == "me" or m.get("role") == "user"
            tick = '<b class="pq-tk">✓✓</b>' if me else ""
            rows += (f'<div id="{sid}w{j}" class="pq-wb {"me" if me else "them"}"><span>{esc(m["text"])}</span>'
                     f'<i>10:4{min(9, 1 + j)} {tick}</i></div>')
            t = a + 0.25 + j * step
            js += _rev(f"#{sid}w{j}", t, a, y=24, dur=0.3, ease="back.out(1.6)", extra=",scale:0.92")
            cues.append({"t": round(t, 3), "file": "sfx/pop-light.mp3" if me else "sfx/click-ui.mp3", "gain_db": -22, "align": "onset"})
        inner = (f'<div class="pq-wh"><b class="pq-bk">‹</b><div class="pq-av">{esc(str(who)[:1].upper())}</div>'
                 f'<div><div class="pq-wn">{esc(who)}</div><div class="pq-ws">online</div></div></div>'
                 f'<div class="pq-wl">{rows}</div><div class="pq-wi">Message</div>')
        hero = _phone(sid, "wa", inner)
    elif kind == "sms":
        msgs = [m for m in (s.get("messages") or []) if isinstance(m, dict) and m.get("text")][:3]
        cards = ""
        for j, m in enumerate(msgs):
            app = esc(m.get("app") or "Messages")
            cards += (f'<div id="{sid}n{j}" class="pq-nc"><div class="pq-nh"><b class="pq-ic">{app[:1]}</b>{app}<em>now</em></div>'
                      f'<div class="pq-nf">{esc(m.get("from") or "Bank")}</div><div class="pq-nt">{esc(m["text"])}</div></div>')
            t = a + 0.3 + j * max(0.3, min(0.8, d * 0.35 / max(1, len(msgs))))
            js += _rev(f"#{sid}n{j}", t, a, y=-60, dur=0.45, ease="back.out(1.4)")
            cues.append({"t": round(t, 3), "file": "sfx/pop-light.mp3", "gain_db": -20, "align": "onset"})
        inner = (f'<div class="pq-ld">{esc(s.get("date") or "Wednesday, 19 November")}</div>'
                 f'<div class="pq-lt">{esc(s.get("time") or "10:42")}</div><div class="pq-nl">{cards}</div>')
        hero = _phone(sid, "lk", inner, s.get("time") or "10:42")
    elif kind == "pay":
        st = str(s.get("status") or "failed").lower()
        st = st if st in ("failed", "pending", "success") else "failed"
        word = {"failed": "Payment Failed", "pending": "Payment Pending", "success": "Payment Successful"}[st]
        rows = [("To", s.get("to") or "Aditya"), ("From", s.get("from") or "Your bank a/c XX4821"),
                ("UPI Ref No.", s.get("ref") or "4321 8765 1290"), ("Date", s.get("date") or "19 Nov, 10:42 AM")]
        rws = "".join(f'<div class="pq-pr"><span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in rows)
        note = f'<div id="{sid}pn" class="pq-pn">{esc(s["sub"])}</div>' if s.get("sub") else ""
        inner = (f'<div class="pq-ph2"><b class="pq-bk">‹</b>Transaction details</div>'
                 f'<div id="{sid}pi" class="pq-pi {st}"></div><div id="{sid}ps" class="pq-ps {st}">{word}</div>'
                 f'<div id="{sid}pa" class="pq-pa">{esc(s.get("value") or s.get("big") or "")}</div>'
                 f'<div id="{sid}pc" class="pq-pc">{rws}</div>{note}')
        hero = _phone(sid, "py", inner)
        js += [f'tl.set("#{sid}pi",{{opacity:0}},{a:.3f});',
               f'tl.fromTo("#{sid}pi",{{scale:0.3,opacity:0}},{{scale:1,opacity:1,duration:0.5,ease:"back.out(2.6)",immediateRender:false}},{a + 0.3:.3f});']
        cues.append({"t": round(a + 0.32, 3), "file": "sfx/impact.mp3", "gain_db": -20, "align": "onset"})
        js += _rev(f"#{sid}ps", a + 0.5, a) + _rev(f"#{sid}pa", a + 0.62, a) + _rev(f"#{sid}pc", T(0.25), a)
        if note:
            js += _rev(f"#{sid}pn", T(0.38), a)
    elif kind == "bill":
        rows = [r for r in (s.get("rows") or []) if isinstance(r, dict)][:6]
        if isinstance(s.get("total"), dict) and s["total"].get("value"):
            rows = [r for r in rows if "total" not in str(r.get("label", "")).lower()]
        tone = "bad" if str(s.get("tone") or "bad") == "bad" else "good"
        tot = s.get("total") if isinstance(s.get("total"), dict) else {}
        body = "".join(f'<div id="{sid}b{j}" class="pq-br"><span>{esc(r.get("label"))}</span><b>{esc(r.get("value"))}</b></div>'
                       for j, r in enumerate(rows))
        tl_ = (f'<div id="{sid}bx" class="pq-bx {tone}"><span>{esc(tot.get("label") or "Total")}</span><b>{esc(tot.get("value"))}</b></div>'
               if tot.get("value") else "")
        hero = (f'<div id="{sid}bl" class="pq-bill"><div class="pq-bt">{esc(s.get("title") or "BILL")}</div>'
                f'<div class="pq-bs">{esc(s.get("sub") or "")}</div><div class="pq-bh"></div>{body}{tl_}</div>')
        js += _rev(f"#{sid}bl", a + 0.05, a, y=60, dur=0.5, ease="power4.out")
        step = max(0.22, min(0.55, (d * 0.3) / max(1, len(rows))))
        for j in range(len(rows)):
            js += _rev(f"#{sid}b{j}", a + 0.4 + j * step, a, y=12, dur=0.25)
            cues.append({"t": round(a + 0.4 + j * step, 3), "file": "sfx/click-ui.mp3", "gain_db": -26, "align": "onset"})
        if tl_:
            tt = min(a + 0.4 + len(rows) * step + 0.15, T(0.45))
            js += [f'tl.set("#{sid}bx",{{opacity:0}},{a:.3f});',
                   f'tl.fromTo("#{sid}bx",{{scale:1.25,opacity:0}},{{scale:1,opacity:1,duration:0.45,ease:"back.out(2)",immediateRender:false}},{tt:.3f});']
            cues.append({"t": round(tt, 3), "file": "sfx/impact.mp3", "gain_db": -20, "align": "onset"})
    elif kind == "rule":
        lines = [str(x) for x in (s.get("lines") or []) if str(x).strip()][:4]
        lg = asset.get("logo") or asset.get("image")
        head = (f'<img class="pq-rl" src="assets/{os.path.basename(lg)}">' if lg else
                f'<b class="pq-rf">{esc("".join(w[:1] for w in str(s.get("title") or "RBI").split()[:3]).upper())}</b>')
        li = "".join(f'<div id="{sid}r{j}" class="pq-rli">{esc(x)}</div>' for j, x in enumerate(lines))
        hero = (f'<div id="{sid}rc" class="pq-rule"><div class="pq-rh">{head}<div><div class="pq-rt">{esc(s.get("title") or "")}</div>'
                f'<div class="pq-rd">{esc(s.get("sub") or "")}</div></div></div>{li}'
                f'<div id="{sid}rs" class="pq-rs">{esc(s.get("stamp") or "ASLI NIYAM")}</div></div>')
        js += _rev(f"#{sid}rc", a + 0.05, a, y=70, dur=0.55, ease="power4.out")
        for j in range(len(lines)):
            js += _rev(f"#{sid}r{j}", a + 0.45 + j * max(0.25, min(0.7, d * 0.3 / max(1, len(lines)))), a, y=14, dur=0.3)
        ts = T(0.45)
        js += [f'tl.set("#{sid}rs",{{opacity:0}},{a:.3f});',
               f'tl.fromTo("#{sid}rs",{{scale:2.2,opacity:0,rotation:-20}},{{scale:1,opacity:1,rotation:-8,duration:0.35,ease:"power4.in",immediateRender:false}},{ts:.3f});']
        cues.append({"t": round(ts + 0.33, 3), "file": "sfx/impact.mp3", "gain_db": -18, "align": "onset"})
    elif kind == "table":
        # 19 Nov (owner on the LLP vs Pvt Ltd reel: "table form comparing each"): rows reveal one by one with the voice
        cols = [str(c) for c in (s.get("cols") or [])][:4]
        rows = [r for r in (s.get("rows") or []) if isinstance(r, dict)][:6]
        best = s.get("best")
        hd = "".join(f'<div class="pq-tc pq-th{" best" if best == j else ""}">{esc(c)}</div>' for j, c in enumerate(cols))
        body = ""
        for j, r in enumerate(rows):
            cells = [r.get("label", "")] + [str(x) for x in (r.get("cells") or [])][:len(cols) - 1]
            cells += [""] * (len(cols) - len(cells))
            body += (f'<div id="{sid}t{j}" class="pq-tr">' + "".join(
                f'<div class="pq-tc{" lab" if k == 0 else ""}{" best" if best == k else ""}">{esc(c)}</div>' for k, c in enumerate(cells))
                + "</div>")
        hero = (f'<div id="{sid}tb" class="pq-tab" style="--n:{max(2, len(cols))}"><div class="pq-tt">{esc(s.get("title") or "")}</div>'
                f'<div class="pq-tr pq-thr">{hd}</div>{body}</div>')
        js += _rev(f"#{sid}tb", a + 0.05, a, y=60, dur=0.5, ease="power4.out")
        step = max(0.3, min(0.9, (d * 0.6) / max(1, len(rows))))
        for j in range(len(rows)):
            js += _rev(f"#{sid}t{j}", a + 0.45 + j * step, a, y=14, dur=0.28)
            cues.append({"t": round(a + 0.45 + j * step, 3), "file": "sfx/click-ui.mp3", "gain_db": -26, "align": "onset"})
    elif kind == "list":
        lines = [str(x) for x in (s.get("lines") or []) if str(x).strip()][:5]
        li = "".join(f'<div id="{sid}l{j}" class="pq-rli">{esc(x)}</div>' for j, x in enumerate(lines))
        hero = (f'<div id="{sid}lc" class="pq-rule pq-list"><div class="pq-rt">{esc(s.get("title") or s.get("big") or "")}</div>'
                f'<div class="pq-rd">{esc(s.get("sub") or "")}</div>{li}</div>')
        js += _rev(f"#{sid}lc", a + 0.05, a, y=70, dur=0.5, ease="power4.out")
        for j in range(len(lines)):
            js += _rev(f"#{sid}l{j}", a + 0.4 + j * max(0.3, min(0.9, d * 0.55 / max(1, len(lines)))), a, y=14, dur=0.3)
    else:
        return "", [], []
    if a < 0.4:
        # 19 Nov: the hook scene is on screen from frame 0 (the first frame decides the swipe): no entrance fades, and the
        # first message / card is already there; later items still arrive with the voice.
        first = {"wa": f"#{sid}w0", "sms": f"#{sid}n0", "pay": f"#{sid}pi", "bill": f"#{sid}bl", "rule": f"#{sid}rc",
                 "table": f"#{sid}tb", "list": f"#{sid}lc"}.get(kind)
        js = [x for x in js if not (first and f'"{first}"' in x)]
        js = [x.replace("opacity:0,", "opacity:1,", 1) if ("fromTo" in x and first and f'"{first}"' in x) else x for x in js]
        return hero, js, cues
    if kind in ("wa", "sms", "pay"):
        js += [f'tl.set("#{sid}ph",{{opacity:0}},{a:.3f});',
               f'tl.fromTo("#{sid}ph",{{y:90,opacity:0,rotation:-2}},{{y:0,opacity:1,rotation:0,duration:0.55,ease:"power4.out",immediateRender:false}},{a:.3f});']
    return hero, js, cues


def css(acc, phone_page=False):
    return ("""
.pq-ph{position:absolute;zoom:1.2;left:130px;top:80px;width:640px;height:1030px;border-radius:72px;background:#05070a;padding:14px;box-sizing:border-box;
  box-shadow:0 60px 120px #000d,0 0 0 2px #2c313a,inset 0 0 0 2px #15181e;z-index:2}
.pq-scr{position:relative;width:100%;height:100%;border-radius:58px;overflow:hidden;font-family:SANS;color:#fff}
.pq-isl{position:absolute;left:50%;top:18px;width:150px;height:42px;margin-left:-75px;border-radius:21px;background:#000;z-index:6}
.pq-sb{position:absolute;left:46px;right:40px;top:24px;display:flex;justify-content:space-between;font-size:24px;font-weight:600;z-index:5}
.pq-bk{font-size:56px;font-weight:300;line-height:1;margin-right:6px}
.pq-scr.wa{background:radial-gradient(#ffffff08 1.5px,transparent 2px) 0 0/34px 34px,#0b141a}
.pq-wh{position:absolute;top:0;left:0;right:0;height:170px;background:#1f2c34;display:flex;align-items:flex-end;gap:18px;padding:0 28px 22px;box-sizing:border-box;color:#e9edef}
.pq-av{width:68px;height:68px;border-radius:50%;background:linear-gradient(135deg,#6a8a96,#3f5560);font-size:32px;font-weight:700;display:flex;align-items:center;justify-content:center}
.pq-wn{font-size:32px;font-weight:600}.pq-ws{font-size:22px;color:#8696a0;margin-top:2px}
.pq-wl{position:absolute;top:200px;left:22px;right:22px;display:flex;flex-direction:column;gap:20px}
.pq-wb{max-width:480px;padding:16px 22px 10px;border-radius:24px;font-size:31px;line-height:1.3;color:#e9edef;box-shadow:0 2px 0 #0004}
.pq-wb.them{align-self:flex-start;background:#202c33;border-top-left-radius:6px}
.pq-wb.me{align-self:flex-end;background:#005c4b;border-top-right-radius:6px}
.pq-wb i{display:block;text-align:right;font-style:normal;font-size:19px;color:#ffffff8c;margin-top:6px}
.pq-tk{color:#53bdeb;font-weight:700;margin-left:4px}
.pq-wi{position:absolute;bottom:28px;left:22px;right:22px;height:78px;border-radius:39px;background:#202c33;color:#8696a0;font-size:27px;display:flex;align-items:center;padding-left:32px}
.pq-scr.lk{background:radial-gradient(ellipse 130% 70% at 50% 0%,#24493f 0%,#0c1916 55%,#05080a 100%)}
.pq-ld{position:absolute;top:110px;left:0;right:0;text-align:center;font-size:28px;font-weight:500;color:#ffffffd9}
.pq-lt{position:absolute;top:150px;left:0;right:0;text-align:center;font-size:160px;font-weight:300;letter-spacing:-5px;line-height:1}
.pq-nl{position:absolute;top:400px;left:22px;right:22px;display:flex;flex-direction:column;gap:16px}
.pq-nc{background:#2b3532f2;border-radius:32px;padding:22px 26px 24px;box-shadow:0 10px 30px #0007}
.pq-nh{display:flex;align-items:center;gap:12px;font-size:21px;color:#ffffffb3;letter-spacing:.5px;text-transform:uppercase}
.pq-nh em{margin-left:auto;font-style:normal;text-transform:none}
.pq-ic{width:42px;height:42px;border-radius:11px;background:#34c759;color:#fff;font-size:22px;font-weight:800;display:flex;align-items:center;justify-content:center}
.pq-nf{font-size:29px;font-weight:700;margin-top:12px}.pq-nt{font-size:28px;line-height:1.32;margin-top:4px;color:#ffffffeb}
.pq-scr.py{background:#0e1116}
.pq-ph2{position:absolute;top:84px;left:30px;right:30px;display:flex;align-items:center;gap:10px;font-size:30px;font-weight:600;color:#e6e9ef}
.pq-pi{position:absolute;top:230px;left:50%;width:170px;height:170px;margin-left:-85px;border-radius:50%}
.pq-pi.failed{background:#e5484d;box-shadow:0 0 70px #e5484d77}.pq-pi.success{background:#30a46c;box-shadow:0 0 70px #30a46c77}
.pq-pi.pending{background:#f5a524;box-shadow:0 0 70px #f5a52477}
.pq-pi.failed:before,.pq-pi.failed:after{content:"";position:absolute;left:43px;top:78px;width:84px;height:14px;border-radius:7px;background:#fff;transform:rotate(45deg)}
.pq-pi.failed:after{transform:rotate(-45deg)}
.pq-pi.success:before{content:"";position:absolute;left:52px;top:44px;width:40px;height:72px;border:solid #fff;border-width:0 15px 15px 0;transform:rotate(45deg)}
.pq-pi.pending:before{content:"!";position:absolute;inset:0;text-align:center;font-size:120px;font-weight:900;line-height:170px;color:#fff}
.pq-ps{position:absolute;top:430px;left:0;right:0;text-align:center;font-size:42px;font-weight:800}
.pq-ps.failed{color:#ff6b6f}.pq-ps.success{color:#4cc38a}.pq-ps.pending{color:#f5b342}
.pq-pa{position:absolute;top:490px;left:0;right:0;text-align:center;font-size:104px;font-weight:800;letter-spacing:-2px}
.pq-pc{position:absolute;top:610px;left:28px;right:28px;background:#171b22;border-radius:30px;padding:10px 30px}
.pq-pr{display:flex;justify-content:space-between;padding:15px 0;border-bottom:1.5px solid #ffffff10;font-size:26px}
.pq-pr:last-child{border-bottom:none}.pq-pr span{color:#8b93a3}.pq-pr b{font-weight:600;color:#eef1f6}
.pq-pn{position:absolute;top:905px;left:28px;right:28px;background:#f5a5241f;border:1.5px solid #f5a52466;color:#f8c56a;border-radius:24px;padding:20px 24px;font-size:26px;line-height:1.3;text-align:center}
.pq-bill{position:absolute;left:130px;width:820px;top:330px;background:#f4f1ea;color:#15171a;border-radius:20px 20px 0 0;padding:46px 54px 56px;box-sizing:border-box;
  font-family:MONO;box-shadow:0 50px 100px #000c;z-index:2}
.pq-bill:after{content:"";position:absolute;left:0;right:0;bottom:-22px;height:22px;background:linear-gradient(-45deg,transparent 16px,#f4f1ea 0) 0 0/32px 22px,linear-gradient(45deg,transparent 16px,#f4f1ea 0) 0 0/32px 22px}
.pq-bt{font-family:SANS;font-weight:800;font-size:42px;text-align:center;letter-spacing:1px}
.pq-bs{font-size:24px;text-align:center;color:#6b6f76;margin-top:6px}
.pq-bh{border-top:3px dashed #15171a55;margin:26px 0 12px}
.pq-br{display:flex;justify-content:space-between;font-size:34px;padding:12px 0}.pq-br b{font-weight:700}
.pq-bx{display:flex;justify-content:space-between;border-top:3px dashed #15171a;margin-top:18px;padding-top:20px;font-size:46px;font-weight:800;font-family:SANS}
.pq-bx.bad b{color:#d92d20}.pq-bx.good b{color:#12805c}
.pq-rule{position:absolute;left:80px;width:920px;top:430px;background:#fbfaf7;color:#14161a;border-radius:28px;padding:46px 52px 70px;box-sizing:border-box;
  box-shadow:0 50px 100px #000c;font-family:SANS;z-index:2}
.pq-rh{display:flex;flex-wrap:wrap;gap:12px 26px;align-items:center;border-bottom:2px solid #e4e0d7;padding-bottom:28px;margin-bottom:12px}
.pq-rl{width:360px;height:130px;object-fit:contain;object-position:left center}
.pq-rf{width:110px;height:110px;border-radius:50%;background:#1f3a5f;color:#fff;font-size:38px;font-weight:900;display:flex;align-items:center;justify-content:center}
.pq-rt{font-size:42px;font-weight:800;line-height:1.1}.pq-rd{font-size:26px;color:#6b6b6b;margin-top:8px;font-family:MONO}
.pq-rli{font-size:38px;line-height:1.3;padding:18px 0 18px 54px;position:relative;font-weight:600;border-bottom:1.5px solid #efece5}
.pq-rli:last-of-type{border-bottom:none}
.pq-rli:before{content:"";position:absolute;left:4px;top:30px;width:26px;height:26px;border-radius:8px;background:ACC}
.pq-rs{position:absolute;right:44px;bottom:-34px;transform:rotate(-8deg);border:5px solid #12805c;color:#12805c;background:#fbfaf7;font-weight:900;
  font-size:32px;letter-spacing:2px;padding:12px 24px;border-radius:14px}
.pq-list{padding-bottom:40px}.pq-list .pq-rt{font-size:52px;margin-bottom:6px}.pq-list .pq-rd{margin-bottom:16px}
.pq-tab{position:absolute;left:80px;width:920px;top:360px;background:#fbfaf7;color:#14161a;border-radius:28px;padding:36px 28px 30px;box-sizing:border-box;
  box-shadow:0 50px 100px #000c;font-family:SANS;z-index:2}
.pq-tt{font-size:46px;font-weight:800;text-align:center;margin-bottom:22px}
.pq-tr{display:grid;grid-template-columns:1.05fr repeat(calc(var(--n) - 1),1fr);border-top:1.5px solid #e6e2d9}
.pq-thr{border-top:none}
.pq-tc{padding:22px 10px;font-size:33px;line-height:1.2;font-weight:600;text-align:center;display:flex;align-items:center;justify-content:center}
.pq-tc.lab{justify-content:flex-start;text-align:left;font-weight:800;color:#55595f;font-size:28px}
.pq-th{font-size:33px;font-weight:900;color:#fff;background:#1f2a37;border-radius:14px;margin:0 4px;padding:16px 8px}
.pq-th:first-child{background:none}
.pq-th.best{background:ACC;color:#111}.pq-tc.best:not(.pq-th){background:ACC22}
""" + (
        # a phone page: the phone fills the frame (zoom 1.2 -> 768 x 1236 px, ends y 1332); captions sit below it
        ".cap{top:1395px!important}"
        # 19 Nov: the real-life picture / clip behind the phone (plans with phone_bg) stays atmosphere: dim, soft, normal blend
        "#root .scene .bgimg,#root .vid.pbg{mix-blend-mode:normal!important;opacity:1;filter:brightness(.78) saturate(1) blur(2px)!important}"
        # first test (brightness .5 + the film shade) hid the pictures: only a dark band behind the captions now
        "#root .scene .bgshade{background:linear-gradient(180deg,#07080b73 0%,#07080b26 30%,#07080b26 62%,#07080bb3 74%,#07080bd9 86%,#07080bf2 100%)!important}"
        if phone_page else "")).replace("SANS", SANS).replace("MONO", MONO).replace("ACC", acc)
