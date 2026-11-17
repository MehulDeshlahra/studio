"""Studio self-check and self-fix (owner, 17 Nov: "I won't have this Kiro chat every time: fix yourself").
Runs every 30 min (systemd timer studio-selfcheck, low priority). The doctor (doctor.py) repairs servers and services;
this agent finds and repairs CODE problems and wrong numbers:
  probes   every dashboard API, every dashboard tab loaded in headless Chrome (blank page? JS error? "Offline"?),
           the dashboard audit (figures vs raw files), crashes (Python tracebacks) in the last 3 h of engine logs
  fixing   one finding at a time: find the file and line from the traceback, show the code to Gemini, apply the ONE
           small patch it returns, then check: compile, restart if needed, re-run the probe that failed.
           Pass -> git commit + push + one Telegram line. Fail -> automatic rollback.
           Engine code cannot be re-run on the spot (a crash inside a video build), so those fixes are committed as
           "unverified": if the same crash shows up again after the fix, the fix is reverted automatically.
  limits   4 fixes a day, 1 attempt per problem a day, patch <= 40 lines, only engine/ and dashboard/ files, never the
           posting code, the doctor, this file, secrets or configs. Everything is logged (engine.log "selfcheck:" lines,
           ~/studio-out/selfcheck.json, shown in the dashboard under Connected apps).
  Visual taste and new features are not decided here: those stay for a human session (build-queue.md).
  python engine/selfcheck.py [--dry]"""
import glob, hashlib, json, os, re, subprocess, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, HOME, log, load, save, telegram

DRY = "--dry" in sys.argv
BASE = "http://127.0.0.1:4788"
STATE = os.path.join(OUT, "selfcheck.json")
S = load(STATE, {}) or {}
S.setdefault("fixes", []); S.setdefault("attempts", {}); S.setdefault("findings", [])
TODAY = time.strftime("%Y-%m-%d")
TABS = ["today", "runs", "approvals", "channels", "server", "sources", "activity", "brain", "settings"]
ALLOW = re.compile(r"^(engine/(?!publish|doctor|selfcheck|core)[\w]+\.py|dashboard/[\w.-]+\.(py|js|css|html))$")
FUNC_HINT = {"progress": ["job_state"], "status": ["jobs"], "runs": ["jobs", "job_state"], "budget": ["budgets"], "disk": ["server"],
             "memory": ["server"], "load": ["server"], "uptime": ["server"], "timer": ["schedule"], "followers": ["channels", "meta_pages"],
             "IG posts": ["channels", "meta_pages"], "FB followers": ["channels", "meta_pages"], "VAJRA": ["channels"], "first-pass": ["quality"],
             "needs-you": ["needs_you"], "media": ["job_state"]}


def sh(cmd, timeout=120, cwd=None):
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def get(path, t=90):
    try:
        r = urllib.request.urlopen(BASE + path, timeout=t)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def sig(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


# ------------------------------------------------------------------ probes
def probe_api():
    out, state = [], None
    paths = ["/api/state", "/api/brain", "/api/learned", "/api/sources", "/api/brief", "/api/ideas?cid=tech", "/api/ideas?cid=katha", "/api/posts?cid=vajra"]
    for p in paths:
        code, body = get(p)
        try:
            j = json.loads(body)
        except Exception:
            j = None
        bad = code != 200 or j is None or (isinstance(j, dict) and j.get("error"))
        if bad:
            out.append({"kind": "api", "path": p, "msg": (j.get("error") if isinstance(j, dict) else None) or body[:160].decode("utf-8", "ignore") or f"HTTP {code}"})
        if p == "/api/state" and isinstance(j, dict):
            state = j
    if state and state.get("jobs"):
        j0 = state["jobs"][0]
        for p in (f"/api/job?cid={j0['cid']}&job={j0['job']}",):
            code, body = get(p)
            try:
                j = json.loads(body)
            except Exception:
                j = None
            if code != 200 or (isinstance(j, dict) and j.get("error")):
                out.append({"kind": "api", "path": p.split("?")[0], "msg": (j or {}).get("error", f"HTTP {code}") if isinstance(j, dict) else f"HTTP {code}"})
        cov = next((j for j in state["jobs"] if j["files"].get("cover.jpg")), None)
        if cov:
            code, _ = get(f"/media/{cov['cid']}/{cov['job']}/cover-s.jpg")
            if code != 200:
                out.append({"kind": "api", "path": "/media/.../cover-s.jpg", "msg": f"HTTP {code}"})
    if state and time.time() - state.get("now", 0) > 120:
        out.append({"kind": "api", "path": "/api/state", "msg": "state is stale"})
    return out


def chrome():
    c = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux-arm64/chrome-headless-shell")))
    return c[-1] if c else None


def probe_ui(tabs=TABS):
    out, ch = [], chrome()
    if not ch:
        return out
    for tab in tabs:
        rc2, html = sh([ch, "--no-sandbox", "--disable-gpu", "--virtual-time-budget=14000", "--dump-dom", f"{BASE}/?smoke={int(time.time())}#{tab}"], 90)
        m = re.search(r'<div id="view"[^>]*>(.*?)</div>\s*</div>\s*</div>\s*<nav', html, re.S)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1) if m else "")).strip()
        errs = re.search(r'data-errs="([^"]*)"', html)
        if errs and errs.group(1):
            out.append({"kind": "ui-js", "tab": tab, "msg": re.sub(r"&quot;|&#39;", "'", errs.group(1))[:300]})
        elif not m or len(text) < 60 or text.startswith("Loading"):
            out.append({"kind": "ui-blank", "tab": tab, "msg": f"tab shows {len(text)} characters: {text[:80]!r}"})
        elif "Offline" in html and "Offline · retrying" in html:
            out.append({"kind": "ui-blank", "tab": tab, "msg": "the page says Offline"})
    return out


def probe_audit():
    rc, o = sh([sys.executable, os.path.join(ROOT, "dashboard", "audit.py")], 240)
    bad = [l.strip(" ✗") for l in o.splitlines() if "✗" in l]
    if bad and not DRY:
        time.sleep(25)                                            # a build can change a file between two reads
        rc, o = sh([sys.executable, os.path.join(ROOT, "dashboard", "audit.py")], 240)
        bad = [l.strip(" ✗") for l in o.splitlines() if "✗" in l]
    return [{"kind": "data", "msg": b} for b in bad]


def probe_tracebacks(hours=3):
    rc, o = sh(f"journalctl -u 'studio-*' --since '-{hours}h' --no-pager -o cat 2>/dev/null", 60)
    out, cur = [], None
    for line in o.splitlines():
        if line.startswith("Traceback (most recent call last)"):
            cur = [line]
        elif cur is not None:
            cur.append(line)
            if line and not line.startswith((" ", "\t")) and not line.startswith("Traceback"):
                out.append("\n".join(cur)); cur = None
    seen, res = set(), []
    for tb in out:
        fr = frames(tb)
        if not fr:
            continue
        last = tb.strip().splitlines()[-1]
        if any(k in last for k in ("Network is unreachable", "timed out", "HTTP Error 5", "HTTP Error 429", "Connection reset", "No space left")):
            continue                                              # environment, not code
        k = sig(fr[-1][0], fr[-1][1], last[:60])
        if k not in seen:
            seen.add(k); res.append({"kind": "traceback", "tb": tb[-1800:], "msg": last[:200], "frames": fr})
    return res


def frames(tb):
    fr = [(os.path.relpath(f, ROOT), int(n)) for f, n in re.findall(r'File "(/home/ubuntu/studio/[^"]+)", line (\d+)', tb)]
    return [(f, n) for f, n in fr if not f.startswith(("..", "ref/"))]


# ------------------------------------------------------------------ fixing
def snippet(path, line, ctx=35):
    lines = open(os.path.join(ROOT, path), encoding="utf-8").read().splitlines()
    a, b = max(0, line - ctx), min(len(lines), line + ctx)
    return "\n".join(f"{i + 1}: {lines[i]}" for i in range(a, b)), "\n".join(lines[a:b])


def function_sources(path, names):
    import ast
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    tree, out = ast.parse(src), []
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name in names:
            out.append("\n".join(src.splitlines()[n.lineno - 1:n.end_lineno]))
    return "\n\n".join(out)[:9000]


def context_for(f):
    """-> (file, text shown to the model, problem description) or None"""
    if f["kind"] == "traceback":
        fr = [x for x in f["frames"] if ALLOW.match(x[0].replace("\\", "/"))]
        if not fr:
            return None
        path, line = fr[-1]
        numbered, _ = snippet(path, line)
        return path.replace("\\", "/"), numbered, f"A crash in production:\n{f['tb']}"
    if f["kind"] == "api":
        err = os.path.join(OUT, "dash-errors.log")
        tb = open(err, encoding="utf-8", errors="ignore").read()[-6000:] if os.path.exists(err) else ""
        blocks = tb.split("\n=== ")
        mine = next((b for b in reversed(blocks) if f["path"].split("?")[0] in b.split("\n")[0]), "")
        fr = frames(mine)
        fr = [x for x in fr if ALLOW.match(x[0].replace("\\", "/"))]
        if not fr:
            return None
        path, line = fr[-1]
        numbered, _ = snippet(path.replace("\\", "/"), line)
        return path.replace("\\", "/"), numbered, f"The dashboard endpoint {f['path']} fails with: {f['msg']}\n{mine[-1500:]}"
    if f["kind"] in ("ui-js", "ui-blank"):
        m = re.search(r"(app\.js)[^:]*:(\d+)", f["msg"])
        if m:
            numbered, _ = snippet("dashboard/app.js", int(m.group(2)))
            return "dashboard/app.js", numbered, f"The browser reports on tab '{f['tab']}': {f['msg']}"
        return "dashboard/app.js", function_sources("dashboard/app.js", []) or snippet("dashboard/app.js", 1, 60)[0], \
            f"On tab '{f['tab']}' the page is blank or broken: {f['msg']}. The tab's renderer is V.{f['tab']} in app.js."
    if f["kind"] == "data":
        names = []
        for k, v in FUNC_HINT.items():
            if k.lower() in f["msg"].lower():
                names += v
        if not names:
            return None
        return "dashboard/api.py", function_sources("dashboard/api.py", set(names)), f"The dashboard shows a different number than the raw files: {f['msg']}"
    return None


PROMPT = """You are fixing a bug in an automated video studio's own code (Python / JavaScript). Make the SMALLEST change that
fixes the problem; do not refactor, rename or add features.
PROBLEM:
{problem}

FILE: {path}
CODE (line numbers are for reference only; they are NOT part of the code):
{code}

Return JSON: {{"file": "{path}", "old": "<exact text from the code above, WITHOUT line-number prefixes, appears exactly once in the file>",
"new": "<the replacement>", "why": "one plain sentence for the owner"}}
If the cause is not in this code, or you are not sure, return {{"give_up": "reason"}}."""


def apply_patch(path, old, new):
    full = os.path.join(ROOT, path)
    src = open(full, encoding="utf-8").read()
    if src.count(old) != 1:
        return None, f"old text found {src.count(old)} times"
    nl = abs(len(new.splitlines()) - len(old.splitlines())) + max(len(new.splitlines()), len(old.splitlines()))
    if nl > 80:
        return None, "patch too large"
    open(full, "w", encoding="utf-8", newline="\n").write(src.replace(old, new))
    return src, None


def compiles(path):
    full = os.path.join(ROOT, path)
    if path.endswith(".py"):
        return sh([sys.executable, "-m", "py_compile", full])[0] == 0
    if path.endswith(".js"):
        return sh(["node", "--check", full])[0] == 0
    return True


def restart_dash():
    sh("sudo systemctl restart studio-dash && sleep 4", 40)


def recheck(f):
    if f["kind"] == "api":
        return not any(x["path"] == f["path"] for x in probe_api())
    if f["kind"] in ("ui-js", "ui-blank"):
        return not probe_ui([f["tab"]])
    if f["kind"] == "data":
        return f["msg"] not in [x["msg"] for x in probe_audit()]
    return None                                                   # tracebacks cannot be replayed


def try_fix(f):
    fid = sig(f["kind"], f.get("path") or f.get("tab") or "", f["msg"][:80])
    if S["attempts"].get(fid) == TODAY or sum(1 for x in S["fixes"] if x["day"] == TODAY) >= 4:
        return False
    S["attempts"][fid] = TODAY
    ctx = context_for(f)
    if not ctx:
        note(f, "no code location found"); return False
    path, code, problem = ctx
    if not ALLOW.match(path):
        note(f, f"{path} is not allowed to be changed automatically"); return False
    import plan as planner
    r = planner.ask(PROMPT.format(problem=problem[:3500], path=path, code=code[:9000]), max_tokens=2500) or {}
    if r.get("give_up") or not r.get("old") or "new" not in r:
        note(f, "the model gave up: " + str(r.get("give_up", ""))[:120]); return False
    old = re.sub(r"(?m)^\d+: ", "", r["old"]) if re.match(r"\d+: ", r["old"]) else r["old"]
    new = re.sub(r"(?m)^\d+: ", "", r["new"]) if re.match(r"\d+: ", r["new"]) else r["new"]
    if DRY:
        log("selfcheck dry: would patch", path, "|", r.get("why", "")); return False
    before, err = apply_patch(path, old, new)
    if err:
        note(f, "patch not applicable: " + err); return False
    if not compiles(path):
        open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n").write(before)
        note(f, "patch did not compile, rolled back"); return False
    if path.startswith("dashboard/"):
        restart_dash()
    ok = recheck(f)
    if ok is False:
        open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n").write(before)
        if path.startswith("dashboard/"):
            restart_dash()
        note(f, "the fix did not solve it, rolled back"); return False
    msg = f"selffix: {r.get('why', '')[:110]} ({path})"
    sh(["git", "-C", ROOT, "add", path]); sh(["git", "-C", ROOT, "commit", "-q", "-m", msg])
    sh(f"cd {ROOT} && timeout 60 git pull -q --rebase --autostash && git push -q", 120)
    head = sh(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"])[1]
    S["fixes"].append({"t": time.strftime("%Y-%m-%d %H:%M"), "day": TODAY, "file": path, "why": r.get("why", ""), "commit": head,
                       "sig": fid, "verified": ok is True, "tb_sig": f.get("tbsig")})
    log("selfcheck: fixed", path, "-", r.get("why", ""), "(verified)" if ok else "(unverified, reverts itself if the crash returns)")
    telegram(f"🔧 Studio fixed a bug in itself: {r.get('why', '')}\nFile: {path} · change {head}" + ("" if ok else "\n(This one could not be tested on the spot; it undoes itself if the crash comes back.)"))
    return True


def note(f, why):
    log("selfcheck: could not fix", f["kind"], f.get("path") or f.get("tab") or "", "-", why, "|", f["msg"][:140])
    k = [x for x in (load(os.path.join(OUT, "doctor-unknown.json"), []) or [])]
    k.append({"what": f"selfcheck found a problem it could not fix: {f['kind']} {f.get('path') or f.get('tab') or ''}", "detail": f"{f['msg'][:200]} ({why})",
              "t": time.strftime("%Y-%m-%d %H:%M")})
    if not DRY:
        save(os.path.join(OUT, "doctor-unknown.json"), k[-60:])


def verify_old_fixes(tbs):
    """An engine fix that could not be tested is undone if the same crash comes back afterwards."""
    now = time.time()
    for fx in S["fixes"]:
        if fx.get("verified") or fx.get("reverted"):
            continue
        t0 = time.mktime(time.strptime(fx["t"], "%Y-%m-%d %H:%M"))
        if now - t0 < 1800:
            continue
        again = [t for t in tbs if fx.get("tb_sig") and sig(t["frames"][-1][0], t["frames"][-1][1], t["msg"][:60]) == fx["tb_sig"]]
        if again and not DRY:
            sh(["git", "-C", ROOT, "revert", "--no-edit", fx["commit"]]); sh(f"cd {ROOT} && timeout 60 git push -q", 90)
            fx["reverted"] = True
            log("selfcheck: undid fix", fx["commit"], "- the same crash came back")
            telegram(f"↩️ Studio undid its own earlier fix ({fx['file']}) because the same crash came back. It is noted for the next fix session.")
        elif now - t0 > 86400:
            fx["verified"] = True


# ------------------------------------------------------------------ main
def main():
    findings = []
    findings += probe_api()
    findings += probe_ui()
    findings += probe_audit()
    tbs = probe_tracebacks()
    findings += tbs
    verify_old_fixes(tbs)
    log("selfcheck:", len(findings), "finding(s)" if findings else "all clear", "| " + "; ".join(f"{f['kind']} {f.get('path') or f.get('tab') or f['msg'][:40]}" for f in findings[:5]) if findings else "")
    fixed = 0
    for f in findings:
        if f["kind"] == "traceback":
            f["tbsig"] = sig(f["frames"][-1][0], f["frames"][-1][1], f["msg"][:60])
        try:
            if try_fix(f):
                fixed += 1
        except Exception as e:
            log("selfcheck: fix attempt crashed", str(e)[:160])
    S["last"] = int(time.time()); S["count"] = len(findings); S["fixed_now"] = fixed
    S["findings"] = [{"kind": f["kind"], "where": f.get("path") or f.get("tab") or "", "msg": f["msg"][:160]} for f in findings][:12]
    if not DRY:
        save(STATE, S)
    print(json.dumps({"findings": len(findings), "fixed": fixed, "list": S["findings"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
