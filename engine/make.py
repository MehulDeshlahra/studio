"""Make one video for a channel, end to end:
  python engine/make.py <channel> ["topic"] [--job ID] [--from STAGE]
Stages: research -> plan -> voice -> assets -> compose -> mix -> render -> qc -> send.
Each stage writes into ~/studio-out/<channel>/<job>/ and is skipped when its output already exists (rerun-safe)."""
import argparse, json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, ASSETS, OUT, PY, log, sh, load, save, channel, telegram, dur, read
import research, plan as planner, tts, align, muse, compose, qc

# chrome-headless-shell enables HyperFrames' fast BeginFrame capture (full Chromium falls back to screenshots).
# Benchmark 16 Nov (6 s clip, busy server): full chromium 1 worker 239 s, headless shell 1 worker 182 s, 2 workers 133 s.
CHROME = os.environ.get("PUPPETEER_EXECUTABLE_PATH", next((p for p in [
    os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-1255/chrome-headless-shell-linux-arm64/chrome-headless-shell"),
    os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux-arm64/chrome-headless-shell"),
    os.path.expanduser("~/.cache/ms-playwright/chromium-1248/chrome-linux-arm64/chrome")] if os.path.exists(p)), ""))
WORKERS = os.environ.get("STUDIO_RENDER_WORKERS", "")


def render_workers():
    """17 Nov: 2 workers only help on a quiet server; with the job bot busy they double the CPU fight (load 11).
    Sample /proc/stat for 3 s: if normal-priority (not niced) work uses >= 35% of the cores, use 1 worker."""
    if WORKERS:
        return WORKERS
    def snap():
        with open("/proc/stat") as f:
            v = list(map(int, f.readline().split()[1:]))
        return v[0] + v[2], sum(v)                     # user + system (niced work excluded), total
    try:
        a = snap(); time.sleep(3); b = snap()
        busy = (b[0] - a[0]) / max(1, b[1] - a[1])
    except Exception:
        return "1"
    w = "1" if busy >= 0.35 else "2"
    log(f"render workers {w} (normal-priority CPU {busy:.0%})")
    return w


def pick_topic(ch):
    try:                                                 # 17 Nov owner-approved extras (engine/extras.py)
        import extras
        done_ = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), []) or []
        made = {str(d.get("topic", "")).lower() for d in done_}
        if ch["id"] == "katha":
            day, fest = extras.festival_today(1)
            if fest and f"festival {day}: {fest}".lower() not in made:
                return f"Festival {day}: {fest} - iski asli katha aur mahatva"
            last = str((done_[-1] if done_ else {}).get("topic", ""))
            if " - Part " not in last:                   # every other Katha video is the next part of a 5-7 part series
                return extras.katha_next(ch)
        if ch["id"] == "tech":
            m = extras.mythbust_due(ch)
            if m:
                return m
    except Exception as e:
        log("extras topic skipped", str(e)[:120])
    if ch.get("serial"):                                 # Aage Suno: the next part of the running serial (engine/serials.py)
        try:
            import serials
            t = serials.next_topic(ch)
            if t:
                return t
        except Exception as e:
            log("serial failed, using ideas", str(e)[:150])
    try:                                                 # best of 10 scored ideas (engine/ideas.py); old way as fallback
        import ideas
        t = ideas.pick(ch)
        if t:
            return t
    except Exception as e:
        log("ideas failed, using the backlog", str(e)[:150])
    done = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), [])
    used = {d["topic"].lower() for d in done}
    for t in ch.get("topics_backlog", []):
        if t.lower() not in used:
            return t
    import llm
    t = llm.text(f"Suggest ONE new topic for this channel, not in this list. Channel: {ch['format']}. "
                 f"Done: {sorted(used)}. Return JSON {{\"topic\": \"...\"}}", json_mode=True)["topic"]
    return t


def _muse_awake(on):
    """~/musebridge*/STUDIO-AWAKE: the bridge skips its 20-min idle stop while this file is fresh (< 45 min)."""
    for d in ("~/musebridge", "~/musebridge2"):
        f = os.path.join(os.path.expanduser(d), "STUDIO-AWAKE")
        try:
            if on:
                open(f, "w").write(str(int(time.time())))
            elif os.path.exists(f):
                os.remove(f)
        except Exception:
            pass


def _brand_guard(ch, p):
    """17 Nov: katha plans ended 'Follow @aagesuno' (another page's lesson leaked). Replace any other page's handle / page
    name in the spoken lines, cards, caption and hashtags with this page's own (or drop it). Returns True if changed."""
    import re as _re
    own = ch.get("handle") or ""
    bad = []
    for cid in os.listdir(os.path.join(ROOT, "channels")):
        if cid == ch["id"]:
            continue
        c = load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}
        for h in (c.get("handle"), c.get("handle_instagram")):
            if h:
                bad += [h, h.lstrip("@")]
    bad = sorted({b for b in bad if b and len(b) > 3}, key=len, reverse=True)
    if not bad:
        return False
    rx = _re.compile("|".join(_re.escape(b) for b in bad), _re.I)
    hit = False

    def fix(t):
        nonlocal hit
        if isinstance(t, str) and rx.search(t):
            hit = True
            return _re.sub(r"\s{2,}", " ", rx.sub(own, t)).strip()
        return t
    for s in p.get("scenes", []):
        for k in ("vo", "big", "small", "title"):
            s[k] = fix(s.get(k))
    p["caption"] = fix(p.get("caption"))
    p["hashtags"] = [h for h in (p.get("hashtags") or []) if not rx.search(h)]
    if hit:
        log("brand guard: removed another page's handle from the plan of", ch["id"])
    return hit


BRANDS = ["ChatGPT", "OpenAI", "Gemini", "Google", "YouTube", "Android", "Chrome", "Gmail", "Google Maps", "Google Pay", "WhatsApp",
          "Instagram", "Facebook", "Meta", "Threads", "Apple", "iPhone", "iPad", "Mac", "Siri", "Alexa", "Amazon", "Flipkart", "Samsung",
          "OnePlus", "Xiaomi", "Redmi", "Realme", "Vivo", "Oppo", "Microsoft", "Windows", "Copilot", "Claude", "Anthropic", "Netflix",
          "Spotify", "Telegram", "Snapchat", "Twitter", "LinkedIn", "Uber", "Ola", "Rapido", "Zomato", "Swiggy", "Blinkit", "Zepto",
          "Paytm", "PhonePe", "UPI", "BHIM", "Jio", "Airtel", "BSNL", "Tesla", "Nvidia", "Intel", "Qualcomm", "Snapdragon",
          "MediaTek", "Bluetooth", "Wi-Fi", "USB", "Aadhaar", "DigiLocker", "IRCTC", "Starlink", "ISRO", "NASA", "SpaceX", "Hotstar",
          "JioCinema", "Truecaller", "Canva", "Perplexity", "DeepSeek", "Grok", "Midjourney"]


def _real_brands(ch, p):
    """18 Nov (owner): "for the ChatGPT reel you could have added ChatGPT's logo". The tech guide once banned logos, so the
    planner stopped asking for them. On the tech page every reel that names a brand now gets its real logo, whatever the
    plan says: a chat scene shows the app's logo in its header, and the first object scene that names a brand (else the
    first scene that does) gets "real" {kind logo}. Returns True when the plan changed."""
    if ch.get("theme", {}).get("style") != "lab":
        return False
    import re as _re

    def found(text):
        for b in sorted(BRANDS, key=len, reverse=True):
            if len(b) <= 2:                      # "X", "Vi": only as a whole word in capitals
                if _re.search(rf"(?<![\w@]){_re.escape(b)}(?![\w])", text or ""):
                    return b
            elif _re.search(rf"(?<![\w@]){_re.escape(b)}(?![\w])", text or "", _re.I):
                return b
        return None
    changed = False
    for s in p.get("scenes", []):
        if s.get("type") == "chat" and not s.get("logo_q"):
            b = found(s.get("title", "")) or found(s.get("vo", ""))
            if b:
                s["logo_q"] = f"{b} logo"; s["title"] = s.get("title") or b; changed = True
    # 18 Nov (owner): "why are we not using the Google logo?" then "not necessarily all of them, you decide where it suits,
    # check related reels". The old rule gave ONE logo per video and none if the plan had any real picture. Now a visual
    # director decides scene by scene, using the rules learnt from top tech reels (channels/tech/visual-rules.md).
    film = bool(ch.get("theme", {}).get("film")) or os.environ.get("STUDIO_LAB_FILM") == "1"
    hits = [(i, s, found(s.get("vo", "") + " " + str(s.get("label", "")) + " " + str(s.get("title", ""))))
            for i, s in enumerate(p.get("scenes", []))]
    if not any(b for _, _, b in hits):
        return changed
    if _visual_director(ch, p, film):
        return True
    # fallback (director failed): the official logo at the brand's first mention only
    for i, s, b in hits:
        if b and s.get("type") not in ("chat", "code", "clip", "flow") and not (isinstance(s.get("real"), dict) and s["real"].get("q")):
            s["real"] = {"q": f"{b} logo", "kind": "logo", "subject": f"the official {b} logo"}
            if not film and s.get("type") not in ("object", "image", "card"):
                s["type"] = "object"; s.setdefault("prompt", f"{b} official logo")
            log("real brands (fallback): scene", i + 1, "gets the real", b, "logo")
            return True
    return changed


DIRECTOR = """You are the art director of a Hindi tech-explainer Reels page (vertical, about 10 scenes, a full-frame picture
behind every scene). Decide for each scene whether its picture should be REAL and which kind, so the reel feels real and
relatable (like the viewer's own phone) without stamping a logo on every line.
RULES LEARNT FROM THE TOP TECH REELS ON INSTAGRAM:
{rules}
SCENES (n | type | spoken line | on-screen label):
{scenes}
Kinds: "logo" (the brand's official logo, big), "app_screen" (a real screenshot of the app / feature on a phone, e.g. the
Google Assistant listening screen), "product" (a real photo of the product / device / hardware), "real_photo" (a real photo of
a real place or event), "none" (keep the generated cinematic picture). Only real things: never invent a screen that does
not exist. A chat, code or clip scene stays "none".
Return JSON {{"scenes": [{{"n": <scene number>, "kind": "...", "q": "the image search query a person would type",
"subject": "what the picture must show", "why": "short"}}]}} listing ONLY the scenes that get something real."""


def _quick_ask(prompt, max_tokens=800):
    """18 Nov: small creative decisions go to the fast free models first (Groq via OmniRoute studio-fast, ~1 s); the
    planner (Gemini, which hung up to 5 min a try today) only if they fail."""
    import llm, plan as planner
    try:
        r = llm.text(prompt, json_mode=True, max_tokens=max_tokens, fast=True)
        r = llm.parse_json(r) if isinstance(r, str) else r
        if isinstance(r, dict) and r:
            return r
    except Exception as e:
        log("quick ask fell back to the planner:", str(e)[:100])
    return planner.ask(prompt, max_tokens=max_tokens) or {}


def _pick_skin(ch, p):
    """18 Nov (owner: "use your brain and pick what template suits what; take ownership"). Chooses the look of THIS
    video from compose_lab.SKINS (styles learnt from the Lemo-Opuscar library), by topic, and rotates so two videos in a
    row rarely share a look. Writes p["skin"]. Every other system (pictures, layout, captions) follows it."""
    # 18 Nov (owner: "mix and match styles, not one style throughout; choose what part suits what"): the look is chosen
    # PER SCENE, in runs (a look holds 2+ scenes so the video does not flicker), at most 3 looks per video.
    import compose_lab, plan as planner
    sc_ = p.get("scenes", [])
    if sc_ and all(s.get("skin") in compose_lab.SKINS for s in sc_):
        return False
    recent = []
    for d in (load(os.path.join(ROOT, "channels", ch["id"], "done.json"), []) or [])[-6:]:
        pj = load(os.path.join(OUT, ch["id"], d["job"], "plan.json"), {}) or {}
        recent.append(sorted({s.get("skin") or pj.get("skin") or "keynote" for s in pj.get("scenes", [])}) or ["keynote"])
    menu = "\n".join(f'- {k}: for {v["use"]}' for k, v in compose_lab.SKINS.items())
    rows = "\n".join(f"{i + 1} | {s.get('type')} | {'REAL ' + s['real'].get('kind', '') if isinstance(s.get('real'), dict) else ''} | "
                     f"{s.get('vo', '')}" for i, s in enumerate(sc_))
    r = {}
    try:
        r = _quick_ask(
            "You are the creative director of a Hindi tech-explainer Reels page. Choose a LOOK for EACH scene, like a film "
            "editor who changes the visual world when the story changes (the real world -> inside the machine -> the smart "
            "part -> back to the real world).\nLooks:\n" + menu + "\n"
            f"Topic: {p.get('title') or p.get('topic')}\nSCENES (n | type | real picture? | spoken line):\n{rows}\n"
            "Rules: use 2 or 3 looks (a video of 6+ scenes is never all one look); scene 1 (the hook) and the last scene are "
            "in the real world (keynote) unless the topic itself lives inside a screen; a scene with a REAL logo or REAL "
            "app_screen is keynote; a REAL product photo may sit in any look; a diagram scene (flow, compare, ui, chart) may "
            "switch look on its own, like a cutaway; other looks hold 2+ scenes. Pick the look that makes THAT part easiest "
            "to understand.\n"
            f"Our last videos used: {recent[-3:]} - vary the mix.\n"
            f'Return JSON {{"looks": [exactly {len(sc_)} look names, one per scene in order], "why": "short"}}', 600)
    except Exception as e:
        log("look pick failed:", str(e)[:100])
    looks = [str(x).strip().lower() for x in (r.get("looks") or [])]
    if len(looks) != len(sc_) or any(x not in compose_lab.SKINS for x in looks):
        log("look pick: unusable answer", str(r)[:160])
        looks = ["keynote"] * len(sc_)
    for i, s in enumerate(sc_):                        # hard rules the model may forget
        if isinstance(s.get("real"), dict) and s["real"].get("q") and s["real"].get("kind") == "logo":
            looks[i] = "keynote"
        if isinstance(s.get("real"), dict) and "screen" in str(s["real"].get("q", "")).lower():
            looks[i] = "keynote"
    diagram = ("flow", "compare", "ui", "chart", "stat")
    for i in range(1, len(looks) - 1):                 # no single-scene flicker, except a diagram cutaway
        if looks[i] != looks[i - 1] and looks[i] != looks[i + 1] and sc_[i].get("type") not in diagram:
            looks[i] = looks[i - 1]
    if len(sc_) >= 6 and len(set(looks)) == 1:         # never one look for a whole 6+ scene video (owner: mix and match)
        pick = next((k for k in ("blueprint", "hologram", "terminal") if k != looks[0]), "blueprint")
        for i, s in enumerate(sc_):
            if s.get("type") in diagram and not (isinstance(s.get("real"), dict) and s["real"].get("kind") == "logo"):
                looks[i] = pick
        log("look pick: one look only -> diagrams in", pick)
    for s, k in zip(sc_, looks):
        s["skin"] = k
    p["skin"] = max(set(looks), key=looks.count) if looks else "keynote"
    log("creative director: looks", " ".join(f"{i + 1}:{k}" for i, k in enumerate(looks)), "-", str(r.get("why", ""))[:100])
    return True


def _story_looks_on(ch):
    return bool(ch.get("looks")) and (bool(ch.get("looks_on")) or os.environ.get("STUDIO_LOOKS") == "1")


def _pick_story_looks(ch, p):
    """18 Nov (owner: "mix and match styles, choose what part suits what"), for the picture pages (katha, raaz): the main
    story stays in the page's base picture style (the first entry of channel.json "looks", so characters stay
    recognisable); a part that is a different KIND of moment (a story inside the story, a memory, a camera watching,
    the cosmic big picture) cuts away to the look made for it. Writes scene["skin"]. Overlay textures were rejected
    (lemo.md), so a look here is only the picture language."""
    looks = ch.get("looks") or {}
    sc_ = p.get("scenes", [])
    if not _story_looks_on(ch) or not sc_ or all(s.get("skin") in looks for s in sc_):
        return False
    base = next(iter(looks))
    menu = "\n".join(f'- {k}: {v["use"]}' for k, v in looks.items())
    rows = "\n".join(f"{i + 1} | {s.get('type')} | {s.get('vo', '')}" for i, s in enumerate(sc_))
    r = {}
    try:
        r = _quick_ask(
            f"You are the creative director of the Instagram page {ch.get('name', ch['id'])}. Pick the picture LOOK of EACH "
            "scene, like a film editor who cuts to another visual world only when the KIND of moment changes.\nLooks:\n" + menu +
            f"\nTitle: {p.get('title') or p.get('topic')}\nSCENES (n | type | spoken line):\n{rows}\n"
            f"Rules: '{base}' is the main story and holds most scenes (at least 60%), always scene 1 and the last scene; use "
            "another look only where the line really is that kind of moment, as a cutaway of 1-3 scenes in a row; at most 2 "
            "other looks in one video; zero other looks is fine when nothing fits.\n"
            f'Return JSON {{"looks": [exactly {len(sc_)} look names in order], "why": "short"}}', 600)
    except Exception as e:
        log("story looks failed:", str(e)[:100])
    got = [str(x).strip().lower() for x in (r.get("looks") or [])]
    if len(got) != len(sc_) or any(x not in looks for x in got):
        log("story looks: unusable answer", str(r)[:160])
        got = [base] * len(sc_)
    got[0] = got[-1] = base
    extra = [k for k in dict.fromkeys(got) if k != base]
    for k in extra[2:]:                                 # at most 2 cutaway looks
        got = [base if x == k else x for x in got]
    if got.count(base) < 0.6 * len(got):                # the main story must stay recognisable
        log("story looks: too few base scenes", got)
        got = [base] * len(got)
    for s, k in zip(sc_, got):
        s["skin"] = k
    p["skin"] = base
    log("story looks", " ".join(f"{i + 1}:{k}" for i, k in enumerate(got)), "-", str(r.get("why", ""))[:100])
    return True


def _look_prompt(ch, s, prompt, look):
    """The scene's picture prompt in its own look: the planner pasted the base look into every prompt, so a cutaway
    swaps it out (and leads with its own style, image models weight the start)."""
    looks = ch.get("looks") or {}
    k = s.get("skin")
    if not _story_looks_on(ch) or k not in looks or k == next(iter(looks)):
        return prompt + (". " + look if look and look.lower()[:20] not in prompt.lower() else "")
    pic = looks[k]["pic"]
    for old in (look, looks[next(iter(looks))].get("pic", "")):
        if old:
            prompt = re.sub(re.escape(old), "", prompt, flags=re.I)
    return f"{pic}. {prompt.strip(' .,')}. Style: {pic}"


def _visual_director(ch, p, film):
    """One planner call: which scenes get a real logo / app screen / product photo. Writes scene["real"]. True if any."""
    try:
        import plan as planner
        rules = read(os.path.join(ROOT, "channels", ch["id"], "visual-rules.md"), 3500) or \
            "- a brand's official logo once, at its first mention or the reveal; the real app screen when the line shows what the app does"
        sc = "\n".join(f"{i + 1} | {s.get('type')} | {s.get('vo', '')} | {s.get('label') or s.get('title') or ''}"
                       for i, s in enumerate(p.get("scenes", [])))
        r = _quick_ask(DIRECTOR.format(rules=rules, scenes=sc), 2000)
    except Exception as e:
        log("visual director failed:", str(e)[:120]); return False
    did = 0
    for x in r.get("scenes") or []:
        try:
            i = int(x.get("n")) - 1
            s = p["scenes"][i]
        except (TypeError, ValueError, IndexError):
            continue
        kind = str(x.get("kind", "none")).lower()
        if kind == "none" or not x.get("q") or s.get("type") in ("chat", "code", "clip"):
            continue
        if not film and s.get("type") in ("flow", "compare", "ui", "chart", "stat", "title"):
            continue                                     # classic look: no picture slot in these scenes
        s["real"] = {"q": x["q"], "kind": "logo" if kind == "logo" else "photo", "subject": x.get("subject") or x["q"]}
        did += 1
        log("visual director: scene", i + 1, kind, repr(x["q"]), "-", str(x.get("why", ""))[:80])
    # 18 Nov (owner: "why are we not using the Google logo?"): a reel about a brand always shows its real logo once. The
    # learnt rule says not in the first ~5 s, so it goes on the brand's first mention from scene 3 on (the reveal), or on
    # its last mention if all mentions are earlier.
    if film and not any(isinstance(s.get("real"), dict) and s["real"].get("kind") == "logo" for s in p.get("scenes", [])):
        ms = [(i, b) for i, s in enumerate(p.get("scenes", []))
              for b in [_brand_in(s.get("vo", "") + " " + str(s.get("label", "")) + " " + str(s.get("title", "")))]
              if b and s.get("type") not in ("chat", "code", "clip")]
        if ms:
            i, b = next((m for m in ms if m[0] >= 2), ms[-1])
            p["scenes"][i]["real"] = {"q": f"{b} logo", "kind": "logo", "subject": f"the official {b} logo"}
            did += 1
            log("visual director: scene", i + 1, "logo", repr(b), "- the brand's logo once, at its reveal")
    return did > 0


def _brand_in(text):
    import re as _re
    for b in sorted(BRANDS, key=len, reverse=True):
        if _re.search(rf"(?<![\w@]){_re.escape(b)}(?![\w])", text or "", _re.I if len(b) > 2 else 0):
            return b
    return None


def stage_assets(ch, p, job):
    _muse_awake(True)
    try:
        return _stage_assets(ch, p, job)
    finally:
        _muse_awake(False)


def _stage_assets(ch, p, job):
    look = ch.get("visuals", {}).get("look", "")
    theme = ch.get("theme", {})
    film = theme.get("style") == "lab" and (bool(theme.get("film")) or os.environ.get("STUDIO_LAB_FILM") == "1")
    adir = os.path.join(job, "assets"); os.makedirs(adir, exist_ok=True)
    got = load(os.path.join(job, "assets.json"), {})
    last_img = None
    for i, s in enumerate(p["scenes"]):
        k = str(i)
        if k in got and all(os.path.exists(v) for v in got[k].values()):
            last_img = got[k].get("image", last_img); continue
        a = {}
        real = s.get("real")
        if film and isinstance(real, dict) and real.get("q") and s.get("type") not in ("object", "clip", "chat", "code"):
            import realmedia                                     # v2: a real photo/logo/screen as the scene's full-frame picture
            r = realmedia.fetch(real, os.path.join(adir, f"s{i}rb.jpg"), lab=False)
            if r:
                a["bg"] = r
        elif isinstance(real, dict) and real.get("q") and s.get("type") in ("image", "card", "object"):
            import realmedia
            if str(real.get("kind", "")).lower() == "clip":      # a real video clip (Wikimedia Commons)
                vc = realmedia.video_clip(real["q"], os.path.join(adir, f"s{i}rv.mp4"), real.get("subject"))
                if vc:
                    a["video"] = vc["path"]; a["image"] = vc["frame"] if os.path.exists(vc["frame"]) else None
                    if not a["image"]:
                        a.pop("image")
                    else:
                        keep = os.path.join(adir, f"s{i}rv.jpg"); shutil.copy(vc["frame"], keep); a["image"] = keep
                    s["type"] = "clip"
                    p.setdefault("credits", []).append(vc["credit"])
            else:
                r = realmedia.fetch(real, os.path.join(adir, f"s{i}r.jpg"), lab=theme.get("style") == "lab")
                if r:
                    a["image"] = r
                if r and real.get("logo") and theme.get("style") == "lab":      # logo pops in first, then the photo
                    lg = realmedia.fetch({"q": real["logo"], "kind": "logo", "subject": real["logo"]}, os.path.join(adir, f"s{i}rl.jpg"), lab=True)
                    if lg:
                        a["logo"] = lg
        if s.get("logo_q") and theme.get("style") == "lab":       # chat header: the app's real logo
            import realmedia
            lg = realmedia.fetch({"q": s["logo_q"], "kind": "logo", "subject": s["logo_q"]}, os.path.join(adir, f"s{i}cl.jpg"), lab=False, raw=True)
            if lg:
                a["chatlogo"] = lg
        if film and not a and s.get("type") not in ("object", "clip"):
            # 18 Nov v2 (owner: "same only, no improvement"): every tech scene gets a full-frame real picture behind its
            # card/number/flow, instead of a small element on black. Prompt from the plan, else built from the spoken line.
            s.setdefault("prompt", "")
            # never quote the spoken line: image models then paint its words into the picture (pilot 18 Nov, scene 6)
            subj = ", ".join(x for x in [str(s.get("label") or ""), str(s.get("title") or ""), " ".join(s.get("keywords") or []),
                                          str(p.get("topic") or p.get("title") or "")] if x).lower()
            import compose_lab
            pic = compose_lab.SKINS.get(s.get("skin") or p.get("skin") or "keynote", compose_lab.SKINS["keynote"])["pic"]
            s["bg_prompt"] = s.get("bg_prompt") or (
                f"Vertical scene for a technology explainer about: {subj}. Style: {pic}. One clear subject in the middle third, "
                "empty dark space at the top and bottom, no people's faces, no text, no letters, no logos, no watermark, vertical 9:16.")
            f = os.path.join(adir, f"s{i}bg.webp")
            img = (muse.image(s["bg_prompt"], f) or muse.omni_image(s["bg_prompt"], os.path.join(adir, f"s{i}bgo.jpg"))
                   or muse.cloudflare(s["bg_prompt"], os.path.join(adir, f"s{i}bg.jpg"))
                   or muse.pollinations(s["bg_prompt"], os.path.join(adir, f"s{i}bgp.jpg")))
            if img:
                a["bg"] = img
        if not a and s.get("prompt") and s["type"] in ("image", "clip", "card", "flow", "clue", "choice", "object") and (theme.get("style") != "lab" or s["type"] in ("object", "clip")):
            prompt = _look_prompt(ch, s, s["prompt"], look) + \
                ". Vertical 9:16, no text, no letters, no logos, no watermark."
            # 18 Nov: split / collage pictures and deities in the wrong form were the top picture holds. One scene per
            # frame, and the traditional form of every deity the scene names (engine/iconography.py).
            prompt += " One single scene in one frame: no split screen, no panels, no collage, no side-by-side copies."
            try:
                import iconography
                prompt += iconography.prompt_addition(s["prompt"] + " " + s.get("vo", ""))
            except Exception as e:
                log("iconography skipped", str(e)[:80])
            if theme.get("style") == "lab":
                prompt = (s["prompt"] + ". Photorealistic studio product render, single object centred, isolated on a pure black "
                          "background, dramatic soft rim light, subtle reflections, shallow depth of field, premium Apple-style "
                          "product photography, no people, no faces, no cartoon, no text, no logos, no watermark, vertical 9:16.")
            if s["type"] == "flow":
                prompt = "Soft, simple, uncluttered background for a diagram: " + prompt
            f = os.path.join(adir, f"s{i}.webp")
            img = (muse.image(prompt, f) or muse.omni_image(prompt, os.path.join(adir, f"s{i}o.jpg"))
                   or muse.cloudflare(prompt, os.path.join(adir, f"s{i}.jpg"))
                   or muse.pollinations(prompt, os.path.join(adir, f"s{i}p.jpg")))
            if img:
                a["image"] = img
            elif last_img:
                a["image"] = last_img; log("scene", i, "reuses the previous image")
            if s["type"] == "clip" and a.get("image"):
                v = muse.video(s["prompt"] + ". Smooth natural motion, no text, no subtitles, no speech.", a["image"],
                               os.path.join(adir, f"s{i}.mp4"))
                if v:
                    a["video"] = prep_clip(v)
                else:
                    s["type"] = "image"; s["motion"] = "push"; log("scene", i, "clip failed -> still image")
        got[k] = a
        last_img = a.get("image", last_img)
        save(os.path.join(job, "assets.json"), got)
    save(os.path.join(job, "plan.json"), p)
    return {int(k): v for k, v in got.items()}


def _loud(f):
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", o)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", o)[-1])


def prep_clip(src):
    """Muse clips are 704x1248 with a 10 s keyframe gap: upscale once (lanczos + light sharpen) to 1080x1920 and
    re-encode with a keyframe every second, so they look sharper and the renderer seeks fast. Keeps the original on error."""
    out = os.path.splitext(src)[0] + "-hd.mp4"
    try:
        sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,unsharp=5:5:0.6:5:5:0.0",
            "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-g", "30", "-keyint_min", "30",
            "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", out], timeout=600)
        return out
    except Exception as e:
        log("clip prep failed, using original:", str(e)[:120])
        return src


def remux(raw, mix, total, out):
    """Master to -14 LUFS with true peak <= -1.5 AFTER the AAC encode (the encoder adds 2-3 dB overshoot):
    gain + brickwall limiter at -4.4 dBFS, measured on the encoded file, corrected once."""
    lim = mix.replace(".wav", "-tp.wav")
    L0, _ = _loud(mix)
    gain = -14 - L0 + 2.8
    # 18 Nov: raaz 1118-1328 went -0.8, -1.3, then +0.3 dB TP and the LAST (worst) try was kept -> held for loudness.
    # The AAC overshoot is not monotonic in gain, so every try is kept and the best one wins; tries 3-4 also lower the
    # limiter ceiling (0.6 -> 0.5 -> 0.42) instead of only the gain.
    best, ceil = None, 0.6
    for k in range(4):
        sh(["ffmpeg", "-v", "error", "-y", "-i", mix, "-af",
            f"apad=whole_dur={total:.3f},volume={gain:.2f}dB,alimiter=limit={ceil}:level=false:attack=1:release=40,aresample=48000",
            "-c:a", "pcm_s16le", lim])
        tryf = out + f".try{k}.mp4"
        sh(["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", lim, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", "-movflags", "+faststart", tryf])
        L, tp = _loud(tryf)
        log("master", f"gain {gain:+.1f} dB, ceiling {ceil} -> {L} LUFS, TP {tp}")
        score = (0 if tp <= -1.5 else 1, abs(L + 14) if tp <= -1.5 else tp)
        if best is None or score < best[0]:
            if best:
                os.remove(best[1])
            best = (score, tryf)
        else:
            os.remove(tryf)
        if abs(L + 14) <= 0.6 and tp <= -1.5:
            break
        if tp > -1.5:
            gain -= 1.0; ceil = round(max(0.42, ceil - 0.08), 2)
        else:
            gain += (-14 - L)
    os.replace(best[1], out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel"); ap.add_argument("topic", nargs="?")
    ap.add_argument("--job"); ap.add_argument("--from", dest="frm", default="")
    ap.add_argument("--no-send", action="store_true")
    ap.add_argument("--lang", default="", help="en = English page version (voice, captions, handle_en)")
    ap.add_argument("--until", default="", help="assets = stop after voice + images (prep lane); the render lane finishes it")
    a = ap.parse_args()
    ch = channel(a.channel)
    if a.lang == "en":
        ch["lang"] = "en"
        ch["handle"] = ch.get("handle_en") or ch.get("handle", "")
        ch["voice"] = dict(ch["voice"], style=ch["voice"].get("style_en", ch["voice"].get("style", "")))
    theme = dict(ch.get("theme", {}))
    theme["lang"] = ch.get("lang", "hi")
    if ch.get("handle") and not ch["handle"].startswith("TBD"):
        theme["handle"] = ch["handle"]
    job_id = a.job or time.strftime("%m%d-%H%M")
    job = os.path.join(OUT, ch["id"], job_id); os.makedirs(job, exist_ok=True)
    # 18 Nov: one build per job, whoever starts it (lanes, healer, owner agent, a manual run). The lock is held for the
    # whole process and survives the os.execv re-voice restart (same process, inherited file descriptor).
    try:
        import fcntl
    except ImportError:                               # laptop (Windows) test runs: no lock
        fcntl = None
    if fcntl and os.environ.get("STUDIO_JOB_LOCKED") != job_id:
        _lk = open(os.path.join(job, ".build.lock"), "w")
        try:
            fcntl.flock(_lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log("job", ch["id"], job_id, "is already being built by another process; not starting a second build")
            return
        os.set_inheritable(_lk.fileno(), True)
        os.environ["STUDIO_JOB_LOCKED"] = job_id
    order = ["research", "plan", "voice", "assets", "compose", "mix", "render", "qc", "send"]
    redo = set(order[order.index(a.frm):]) if a.frm in order else set()
    meta = load(os.path.join(job, "meta.json"), {})
    topic = a.topic or meta.get("topic") or pick_topic(ch)
    meta.update({"channel": ch["id"], "job": job_id, "topic": topic}); save(os.path.join(job, "meta.json"), meta)
    if ch.get("serial") and " - Part " in str(topic):
        try:
            import serials; serials.mark_made(ch, topic, job_id)
        except Exception as e:
            log("serial mark failed", str(e)[:100])
    log("job", ch["id"], job_id, topic)

    # 1 research
    rp = os.path.join(job, "research.json")
    if "research" in redo or not os.path.exists(rp):
        qs = [topic, topic + " shorts", topic + " explained"]
        r = research.run(topic, qs, job)
    r = load(rp)
    rtext = research.summary(r)
    # 2 plan
    pp = os.path.join(job, "plan.json")
    if "plan" in redo or not os.path.exists(pp):
        p = planner.make(ch, topic, rtext); save(pp, p)
    p = load(pp)
    if _brand_guard(ch, p):
        save(pp, p)
    try:                                     # real pictures first, then the looks (a REAL scene stays keynote)
        if _real_brands(ch, p):
            save(pp, p)
    except Exception as e:
        log("real brands skipped", str(e)[:100])
    try:
        th_ = ch.get("theme", {})
        if th_.get("style") == "lab" and (th_.get("film") or os.environ.get("STUDIO_LAB_FILM") == "1") and _pick_skin(ch, p):
            save(pp, p)
        elif th_.get("style") != "lab" and _pick_story_looks(ch, p):
            save(pp, p)
    except Exception as e:
        log("look pick skipped", str(e)[:100])
    if ch.get("serial") and " - Part " in str(topic) and not p.get("cliff_done"):
        try:
            import extras
            ln = extras.cliffhanger_line(ch, topic, p)
            last = (p.get("scenes") or [{}])[-1]
            if ln and "kal" in last.get("vo", "").lower():
                last["vo"] = ln.rstrip(".") + ". Follow karo."
                log("serial teaser line:", ln)
            p["cliff_done"] = True; save(pp, p)
        except Exception as e:
            log("teaser line skipped", str(e)[:100])
    # 3 voice (one request)
    vo = os.path.join(job, "vo-raw.wav")
    if "voice" in redo or not os.path.exists(vo):
        script = "\n".join(s["vo"] for s in p["scenes"])
        lang_ = p.get("lang") or ch.get("lang", "hi")
        tts.speak(script, vo, ch["voice"].get("voice", "Charon"), ch["voice"].get("style", ""), lang_)
        try:
            tts.strip_preamble(vo, p["scenes"][0]["vo"], lang_, ch["voice"].get("style", ""))
        except Exception as e:
            log("preamble check failed:", str(e)[:120])
    import pace
    paced = os.path.join(job, "vo-paced.wav")
    if "voice" in redo or not os.path.exists(paced):
        nw = sum(len(s["vo"].split()) for s in p["scenes"])
        _, f, d0 = pace.fit(vo, paced, nw, ch.get("edit", {}).get("wps", 2.6))
        log("paced voice: pauses squeezed, speed x", f, "from", d0, "s")
        redo.add("voice")
    vo = paced
    tp = os.path.join(job, "timing.json")
    check_only = os.environ.get("STUDIO_STOP_AFTER_PREFLIGHT") == "1"    # healer check: never re-align or re-voice
    if "voice" in redo or not os.path.exists(tp) or (load(tp, {}).get("method") != "whisper" and not check_only):
        cover = 0.0
        try:
            timed, vdur, cover = align.words_by_line(vo, [s["vo"] for s in p["scenes"]], p.get("lang") or ch.get("lang", "hi"))
            method = "whisper"; log("aligned words with whisper, matched", f"{cover:.0%}", "by", align.LAST_ENGINE[0])
        except Exception as e:
            log("whisper alignment failed, pause estimate:", str(e)[:150])
            timed, vdur = align.lines(vo, [s["vo"] for s in p["scenes"]]); method = "pauses"
        save(tp, {"method": method, "dur": vdur, "lines": timed, "cover": cover if method == "whisper" else 0.0})
    tj = load(tp)
    timed, vdur = tj["lines"], tj["dur"]
    w0 = next((L["words"][0]["s"] for L in timed if L.get("words")), 0.0)
    vbad = []
    if tj.get("method") == "whisper" and (tj.get("cover") or 0) < 0.75:
        vbad.append(f"only {tj.get('cover', 0):.0%} of the script matched the voice")
    nwords = sum(len(s["vo"].split()) for s in p["scenes"])
    if vdur and nwords and vdur < nwords / 4.3:          # too short for the script (17 Nov: was 3.6 and rejected good 3.7 words/s voices after pause squeezing; the whisper match below catches real gaps)
        vbad.append(f"voice is {vdur:.0f} s for {nwords} words (part of the script is missing)")
    if w0 > 1.3:
        vbad.append(f"first word starts at {w0:.1f} s (something is said before the script)")
    if vbad and meta.get("voice_gate", 0) < 2 and not check_only:
        meta["voice_gate"] = meta.get("voice_gate", 0) + 1; save(os.path.join(job, "meta.json"), meta)
        log("voice gate:", "; ".join(vbad), "-> new voice now, before visuals and render")
        for f_ in ("vo-raw.wav", "vo-paced.wav", "timing.json"):
            if os.path.exists(os.path.join(job, f_)):
                os.remove(os.path.join(job, f_))
        av, skip = [], False
        for x in sys.argv:
            if skip:
                skip = False; continue
            if x == "--from":
                skip = True; continue
            av.append(x)
        os.execv(sys.executable, [sys.executable] + av + ["--from", "voice"])
    # holds: silence after a line (e.g. a countdown before the answer); words after it move later
    vo_use = vo
    holds = [(i, float(s["hold"])) for i, s in enumerate(p["scenes"]) if s.get("hold")]
    if holds:
        import numpy as np, soundfile as sf
        a_, sr = sf.read(vo, dtype="float32")
        shift, pieces, last = 0.0, [], 0
        for i, h in holds:
            if i + 1 >= len(timed):
                continue
            cut = (timed[i]["end"] + timed[i + 1]["start"]) / 2
            pieces += [a_[last:int(cut * sr)], np.zeros(int(h * sr), dtype="float32")]
            last = int(cut * sr)
            for L in timed[i + 1:]:
                L["start"] += h; L["end"] += h
                for w in L["words"]:
                    w["s"] += h; w["e"] += h
            shift += h
        pieces.append(a_[last:])
        vo_use = os.path.join(job, "vo-held.wav")
        sf.write(vo_use, np.concatenate(pieces), sr)
        vdur += shift
    total = round(vdur + 0.7 + (1.4 if theme.get("handle") else 0.0), 3)
    # 4 assets
    assets = stage_assets(ch, p, job)
    if a.until == "assets":
        meta.update({"stage": "prepped", "lang": p.get("lang") or ch.get("lang", "hi"), "prepped_at": time.strftime("%Y-%m-%d %H:%M")})
        save(os.path.join(job, "meta.json"), meta)
        log("prepped", ch["id"], job_id, "(voice + images ready; render lane finishes it)")
        print(json.dumps({"prepped": job}))
        return
    # 5 compose
    rdir = os.path.join(job, "render")
    if "compose" in redo or not os.path.exists(os.path.join(rdir, "index.html")):
        os.makedirs(os.path.join(rdir, "assets"), exist_ok=True)
        if theme.get("style") == "lab":
            import compose_lab
            doc, cues = compose_lab.page(p, timed, total, theme, assets)
        else:
            doc, cues = compose.page(p, timed, total, theme, assets)
        open(os.path.join(rdir, "index.html"), "w", encoding="utf-8").write(doc)
        for v in assets.values():
            for f in v.values():
                shutil.copy(f, os.path.join(rdir, "assets", os.path.basename(f)))
        mtrack = None
        try:                                              # 17 Nov: mood-picked track from the free library (engine/musiclib.py)
            import musiclib
            mtrack = musiclib.pick(ch["id"], p.get("music_mood"), job_id)
            if mtrack:
                p["music_credit"] = musiclib.CREDIT; save(os.path.join(job, "plan.json"), p)
                if musiclib.CREDIT not in (p.get("caption") or ""):
                    p["caption"] = (p.get("caption") or "").rstrip() + "\n\n" + musiclib.CREDIT; save(os.path.join(job, "plan.json"), p)
        except Exception as e:
            log("music library pick failed:", str(e)[:120])
        for cr in p.get("credits", []):                 # CC BY clips: the credit line goes into the caption
            if cr not in (p.get("caption") or ""):
                p["caption"] = (p.get("caption") or "").rstrip() + "\nVideo: " + cr
        save(os.path.join(job, "plan.json"), p)
        try:                                              # 17 Nov: the page's signature sound on frame 0 (engine/extras.py STING)
            import extras
            st_ = extras.STING.get(ch["id"])
            if st_ and os.path.exists(os.path.join(ASSETS, "audio", st_)) and not any(c.get("t", 9) < 0.3 for c in cues):
                cues = [{"t": 0.0, "file": st_, "gain_db": -15, "align": "onset"}] + list(cues)
        except Exception as e:
            log("sting skipped", str(e)[:80])
        save(os.path.join(job, "cues.json"), {"lufs": -14, "music": {"file": mtrack["file"] if mtrack else theme.get("music", "music/digital-clouds.mp3"),
              "offset": mtrack.get("offset", 2.0) if mtrack else theme.get("music_offset", 8.0), "gain_db": -22, "fade_out": 1.5}, "sfx": cues})
        redo.add("mix")
    # 5b preflight: check the composed page with stills BEFORE the slow render; repair bad scenes (visual fields only)
    lang_p = p.get("lang") or ch.get("lang", "hi")
    if "mix" in redo and os.environ.get("STUDIO_NO_PREFLIGHT") != "1":
        import preflight
        pr = {"ok": True}
        tries = max(1, int(os.environ.get("STUDIO_PREFLIGHT_TRIES", "3")))   # healer checks use 1: judge the code, not repairs
        for attempt in range(tries):
            pr = preflight.run(job, p, timed, total, lang_p)
            if pr["ok"] or attempt == tries - 1:
                break
            if theme.get("style") == "lab":
                if not preflight.repair(p, pr["bad"], lang_p):
                    break
                save(pp, p)
                import compose_lab
                doc, cues = compose_lab.page(p, timed, total, theme, assets)
            else:                                         # 17 Nov: classic pages rendered known-bad scenes (no repair) -> held after render
                again = preflight.repair_classic(p, pr["bad"], lang_p, ch.get("name", ch["id"]))
                if not again and not pr["bad"]:
                    break
                save(pp, p)
                got = load(os.path.join(job, "assets.json"), {})
                for k in again:
                    got.pop(str(k), None)
                save(os.path.join(job, "assets.json"), got)
                assets = stage_assets(ch, p, job)
                for v in assets.values():
                    for f in v.values():
                        shutil.copy(f, os.path.join(rdir, "assets", os.path.basename(f)))
                doc, cues = compose.page(p, timed, total, theme, assets)
            open(os.path.join(rdir, "index.html"), "w", encoding="utf-8").write(doc)
            cj = load(os.path.join(job, "cues.json"), {}); cj["sfx"] = cues; save(os.path.join(job, "cues.json"), cj)
            log("preflight: repaired", len(pr["bad"]), "scene(s), checking again")
        if not pr["ok"]:
            done = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), [])
            row = next((d for d in done if d["job"] == job_id), None)
            if not row:
                row = {"job": job_id, "topic": topic, "title": p.get("title")}; done.append(row)
            row.update(status="held", review=[f"before render, scene {int(k) + 1}: {v[0]}" for k, v in pr["bad"].items()][:6])
            save(os.path.join(ROOT, "channels", ch["id"], "done.json"), done)
            # 18 Nov: stage stayed "prepped", so the render lane rebuilt this same held job every 10 min (7 times 03:20-04:20)
            # and nothing else got rendered or prepped. "held" = the healer (engine/healer.py) owns it now.
            meta = load(os.path.join(job, "meta.json"), {}) or meta
            meta.update(stage="held", held_at=time.strftime("%Y-%m-%d %H:%M")); save(os.path.join(job, "meta.json"), meta)
            log("preflight: still failing after repairs, held BEFORE render (no render time spent)", ch["id"], job_id)
            return
    if os.environ.get("STUDIO_STOP_AFTER_PREFLIGHT") == "1":     # healer check (engine/healer.py): compose + preflight, no render
        print(json.dumps({"preflight_ok": True, "job": job_id}))
        return
    # 6 mix
    mix = os.path.join(job, "mix.wav")
    if "mix" in redo or not os.path.exists(mix):
        sh(["ffmpeg", "-v", "error", "-y", "-i", vo_use, "-ar", "48000", os.path.join(job, "vo.wav")])
        sh([PY, os.path.join(ROOT, "lib", "mix.py"), job, os.path.join(ASSETS, "audio")])
        shutil.copy(mix, os.path.join(rdir, "assets", "mix.wav"))
        redo.add("render")
    # 7 render
    raw, final = os.path.join(job, "raw.mp4"), os.path.join(job, f"{ch['id']}-{job_id}.mp4")
    if "render" in redo or not os.path.exists(final):
        env = dict(os.environ, PUPPETEER_EXECUTABLE_PATH=CHROME)
        t0 = time.time()
        off = False
        try:                                              # 18 Nov: the laptop renders 3x faster when it is on (engine/laptop.py)
            import laptop
            off = os.name != "nt" and laptop.available() and laptop.render(rdir, raw, total, f"{ch['id']} {job_id}")
        except Exception as e:
            log("laptop render skipped:", str(e)[:120])
        if not off:
            sh(["nice", "-n", "15", "npx", "-y", "hyperframes@latest", "render", "--workers", render_workers(), "--no-low-memory-mode", "--output", raw],
               env=env, timeout=7200, cwd=rdir) if os.name != "nt" else sh(["npx.cmd", "-y", "hyperframes@latest", "render", "--output", raw], cwd=rdir)
        log("rendered in", round(time.time() - t0), "s", "(laptop)" if off else "")
        remux(raw, mix, total, final)
        for junk in (raw, os.path.join(job, "mix-tp.wav")):         # ~120 MB per video; rebuilt if ever needed
            try:
                os.remove(junk)
            except OSError:
                pass
    # 8 qc
    rep = {"topic": topic, "title": p.get("title"), "format": qc.fmt(final)}
    mids = [((t["start"] + t["end"]) / 2) for t in timed]
    sheet = qc.sheet(final, mids, os.path.join(job, "sheet.jpg"))
    rep["vision"] = qc.vision(sheet, p)
    tj2 = load(os.path.join(job, "timing.json"), {})
    words = [w for L in tj2.get("lines", []) for w in L.get("words", [])]
    cover = tj2.get("cover")
    if cover is None and tj2.get("method") == "whisper":
        cover = 1.0
    rep["voice"] = {"ok": (cover or 0) >= 0.7, "method": tj2.get("method"), "matched": cover, "words": len(words),
                    "problems": [] if (cover or 0) >= 0.7 else [f"only {cover or 0:.0%} of the script was found in the voice"]}
    rep["ok"] = bool(rep["format"]["ok"] and rep["vision"].get("ok") is not False and rep["voice"].get("ok") is not False)
    save(os.path.join(job, "qc.json"), rep)
    # auto-lessons: every problem the gate found is kept for the next plans
    probs = (rep["vision"].get("problems") or []) + (rep["voice"].get("problems") or [])
    if probs:
        with open(os.path.join(ROOT, "channels", ch["id"], "lessons-auto.md"), "a", encoding="utf-8") as f:
            f.write(f"\n## {job_id} {topic}\n" + "\n".join("- " + str(x) for x in probs) + "\n")
    log("qc", "OK" if rep["ok"] else "PROBLEMS", json.dumps(rep["format"]), rep["vision"].get("score"))
    # 9 send for approval + remember
    done = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), [])
    if not any(d["job"] == job_id for d in done):
        done.append({"job": job_id, "topic": topic, "title": p.get("title"), "qc_ok": rep["ok"], "status": "made"})
        save(os.path.join(ROOT, "channels", ch["id"], "done.json"), done)
    import thumb; thumb.make(ch["id"], job_id)
    import review
    rv = review.review(ch["id"], job_id)
    if not meta.get("brain_judged"):
        try:
            import brain
            brain.judge(p.get("brain_ids") or [], bool(rv.get("ok")))
            meta["brain_judged"] = True; save(os.path.join(job, "meta.json"), meta)
        except Exception as e:
            log("brain judge failed", str(e)[:120])
    voice_fault = any(("instructions" in x or "does not start" in x or "starts late" in x or "of the script" in x)
                      for x in rv["problems"])
    if not rv["ok"] and voice_fault and meta.get("voice_retry", 0) < 1:
        meta["voice_retry"] = meta.get("voice_retry", 0) + 1
        save(os.path.join(job, "meta.json"), meta)
        log("review: voice problem, making a new voice once and rebuilding")
        args = [sys.executable, os.path.abspath(__file__), ch["id"], "--job", job_id, "--from", "voice"]
        if a.lang:
            args += ["--lang", a.lang]
        if a.no_send:
            args.append("--no-send")
        subprocess.run(args)
        return
    done = load(os.path.join(ROOT, "channels", ch["id"], "done.json"), [])
    for d in done:
        if d["job"] == job_id:
            d["status"] = "made" if rv["ok"] else "held"
            d["review"] = rv["problems"]
    save(os.path.join(ROOT, "channels", ch["id"], "done.json"), done)
    if not a.no_send and rv["ok"]:
        import send
        send.send(ch["id"], job_id)
    meta.update({"stage": "done"}); save(os.path.join(job, "meta.json"), meta)
    print(json.dumps({"final": final, "ok": rep["ok"]}))


if __name__ == "__main__":
    main()
