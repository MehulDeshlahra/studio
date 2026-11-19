"""Whop robot for Cut Capsule (19 Nov, owner: "you are asking me too much, let's automate"). Runs on the LAPTOP with a
saved browser profile (C:\\Users\\mehul\\studio-render\\whop-profile), logged in once by the owner. Whop has no public API
for clippers, so this drives the real site like a person would.
  python tools/whop.py login                 one time: a window opens, log in to Whop, close it
  python tools/whop.py check                 is the saved login still valid?
  python tools/whop.py look <url>            save the page text, links and buttons (to learn the page layout)
  python tools/whop.py brief <campaign url>  join if needed + read the brief: rules, footage links, required tags
  python tools/whop.py submit <campaign url> <post url>   submit a posted clip
Every result is JSON on stdout (the laptop worker sends it to the server)."""
import json, os, re, sys, time

PROFILE = r"C:\Users\mehul\studio-render\whop-profile"
SHOTS = r"C:\Users\mehul\studio-render\whop-shots"


def browser(p, headless=True):
    os.makedirs(PROFILE, exist_ok=True)
    return p.chromium.launch_persistent_context(PROFILE, headless=headless, viewport={"width": 1280, "height": 900},
                                                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                                           "(KHTML, like Gecko) Chrome/131 Safari/537.36")


def shot(page, name):
    os.makedirs(SHOTS, exist_ok=True)
    f = os.path.join(SHOTS, f"{time.strftime('%m%d-%H%M%S')}-{name}.png")
    try:
        page.screenshot(path=f, full_page=True)
    except Exception:
        pass
    return f


def logged_in(page):
    page.goto("https://whop.com/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    html = page.content().lower()
    return not re.search(r'>\s*(log in|sign in|sign up)\s*<', html) or "/logout" in html or "my whops" in html


def look(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    text = page.inner_text("body")[:20000]
    links = page.eval_on_selector_all("a[href]", "els => els.map(e => [e.innerText.trim().slice(0,80), e.href]).slice(0,300)")
    buttons = page.eval_on_selector_all("button, [role=button]", "els => els.map(e => e.innerText.trim().slice(0,80)).filter(Boolean).slice(0,120)")
    inputs = page.eval_on_selector_all("input, textarea", "els => els.map(e => [e.name||'', e.placeholder||'', e.type||'']).slice(0,40)")
    return {"url": page.url, "title": page.title(), "text": text, "links": links, "buttons": buttons, "inputs": inputs,
            "shot": shot(page, "look")}


FOOTAGE = re.compile(r"https?://(www\.)?(youtube\.com|youtu\.be|drive\.google\.com|dropbox\.com|twitch\.tv|kick\.com|"
                     r"mega\.nz|we\.tl|wetransfer\.com|frame\.io|streamable\.com|vimeo\.com)[^\s\"'<>)]*", re.I)


def click_text(page, words, timeout=4000):
    for w in words:
        loc = page.get_by_role("button", name=re.compile(w, re.I))
        if loc.count():
            try:
                loc.first.click(timeout=timeout); page.wait_for_timeout(2500); return w
            except Exception:
                continue
    return None


def brief(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    joined = click_text(page, [r"^join( campaign)?$", r"^start (earning|clipping)$", r"^get started$", r"^apply$", r"join now"])
    page.wait_for_timeout(3000)
    for tab in ("Brief", "Requirements", "Rules", "Content", "Assets", "Resources"):
        try:
            t = page.get_by_role("tab", name=re.compile(tab, re.I))
            if t.count():
                t.first.click(timeout=3000); page.wait_for_timeout(1500)
        except Exception:
            pass
    text = page.inner_text("body")
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    foot = sorted({m.group(0).rstrip(".,") for m in FOOTAGE.finditer(text + "\n" + "\n".join(hrefs))})
    tags = sorted(set(re.findall(r"(?<![\w/])[#@][A-Za-z0-9_.]{2,30}", text)))[:30]
    return {"url": page.url, "joined_click": joined, "footage": foot, "tags": tags, "text": text[:15000], "shot": shot(page, "brief")}


def submit(page, url, post):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    click_text(page, [r"submit( a)?( post| clip| content)?", r"^\+?\s*new submission", r"add submission"])
    box = None
    for sel in ("input[type=url]", "input[placeholder*='http' i]", "input[placeholder*='link' i]", "input[placeholder*='url' i]",
                "textarea[placeholder*='link' i]", "input[name*='url' i]"):
        if page.locator(sel).count():
            box = page.locator(sel).first; break
    if not box:
        return {"ok": False, "why": "no link box found", "shot": shot(page, "submit-nobox"), "buttons":
                page.eval_on_selector_all("button", "els => els.map(e => e.innerText.trim()).filter(Boolean).slice(0,60)")}
    box.fill(post); page.wait_for_timeout(1000)
    done = click_text(page, [r"^submit$", r"^submit (post|clip|link)$", r"^send$", r"^confirm$"])
    page.wait_for_timeout(4000)
    text = page.inner_text("body")
    ok = bool(done) and not re.search(r"(invalid|error|already submitted|not eligible)", text, re.I)
    return {"ok": ok, "clicked": done, "shot": shot(page, "submit"), "note": re.findall(r"[^.\n]*(submitted|pending|review)[^.\n]*", text, re.I)[:3]}


def main():
    from playwright.sync_api import sync_playwright
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    with sync_playwright() as p:
        if cmd == "login":
            ctx = browser(p, headless=False)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://whop.com/login/", wait_until="domcontentloaded")
            print("Log in to Whop in this window. It closes by itself once you are logged in (15 min max).", flush=True)
            ok = False
            for _ in range(180):                         # 19 Nov: /login redirected at once, so the URL alone proved nothing
                try:
                    page.wait_for_timeout(5000)
                    names = {c["name"].lower() for c in ctx.cookies("https://whop.com")}
                    if any(("token" in n or "session" in n) and "csrf" not in n for n in names) and "/login" not in page.url:
                        txt = page.inner_text("body")[:4000]
                        if not re.search(r"\bSign in\b|\bLog in\b", txt):
                            ok = True; page.wait_for_timeout(3000); break
                except Exception:
                    break                                # the owner closed the window
            try:
                ctx.close()
            except Exception:
                pass
            print(json.dumps({"ok": ok})); return
        ctx = browser(p)
        page = ctx.new_page()
        try:
            if cmd == "check":
                out = {"logged_in": logged_in(page)}
            elif cmd == "look":
                out = look(page, sys.argv[2])
            elif cmd == "brief":
                out = brief(page, sys.argv[2])
            elif cmd == "submit":
                out = submit(page, sys.argv[2], sys.argv[3])
            else:
                out = {"error": "unknown command"}
        except Exception as e:
            out = {"error": str(e)[:500], "shot": shot(page, "error")}
        ctx.close()
    if os.environ.get("WHOP_OUT"):                       # a file path: written as utf-8 (PowerShell '>' writes UTF-16)
        json.dump(out, open(os.environ["WHOP_OUT"], "w", encoding="utf-8"), ensure_ascii=False)
    print(json.dumps(out, ensure_ascii=True))


if __name__ == "__main__":
    main()
