"""The healer's coding agent (engine/healer.py calls fix()). Owner 18 Nov: the server fixes its own code.
  1. a separate git worktree (~/studio-heal/<id>, branch heal/<id>) off the current code; the live code is never touched
  2. aider (free models through OmniRoute combo studio-code, ~/aider-venv) gets the problem, the evidence (log lines,
     layout findings, the failing HTML) and the files that own it, and commits its edit in the worktree
  3. guards: only engine/ lib/ dashboard/ files, never the posting / doctor / healer / selfcheck code, <= 150 changed lines
  4. checks: compile + import; for a held video: compose + preflight of THAT video with the new code (no render) must pass,
     and one recent good video of the same page must still pass (a failure that the current code also has does not count)
  5. pass -> rebase onto the live code, fast-forward, push, one Telegram line; fail -> worktree and branch are deleted
Fixes that cannot be checked on the spot (an error inside a build) are merged as "unverified": the healer reverts them
automatically when the same error comes back (revert()).
  python engine/healcode.py --check <cid> <job>     (compose + preflight with the live code, no render)"""
import glob, json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, HOME, log, load, save, telegram

PY = "/home/ubuntu/studio-venv/bin/python"
AIDER = os.path.join(HOME, "aider-venv", "bin", "aider")
WT = os.path.join(HOME, "studio-heal")
ALLOWED = re.compile(r"^(engine|lib|dashboard)/[\w.-]+\.(py|js|css|html)$")
FORBIDDEN = {"engine/publish.py", "engine/send.py", "engine/doctor.py", "engine/healer.py", "engine/healcode.py",
             "engine/selfcheck.py", "engine/units.sh", "engine/core.py", "engine/omnimap.py"}
MAX_LINES = 150
RULES = """You are fixing the code of Studio, a fully automatic faceless short-video engine (Python 3.12, HyperFrames HTML
pages rendered to video). Rules: make the SMALLEST change that fixes exactly this problem; keep every other behaviour;
no new dependencies, services or API keys; never touch keys, accounts or posting; keep the existing code style and add a
short comment with the date (18 Nov style) explaining why. Fix the cause in code, not one video's data.
NEVER make a problem disappear by hiding it: do not remove or silence log lines, do not delete or weaken a check, a
quality gate or a retry limit, do not catch-and-ignore errors. If you cannot find the real cause, change nothing."""


def sh(cmd, timeout=300, cwd=None, env=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except Exception as e:
        return 1, str(e)


def git(*a, cwd=ROOT, timeout=120):
    return sh(["git"] + list(a), timeout=timeout, cwd=cwd)


# ---------------------------------------------------------------- check one video with some code (no render)
def sig(text):
    t = re.sub(r"#?s\d+[a-z]*", "#s", str(text).lower())
    return re.sub(r"\d+", "#", t)[:110]


CATS = (("EMPTY", r"empty|dark frame|no main visual"), ("OVERLAP", r"overlap|collid|covering"), ("CUT", r"cut off|clipped|cut\b"),
        ("READ", r"faint|unreadable|too small|hard to read|\bread\b"), ("LANG", r"language"), ("DUP", r"twice|duplicate"),
        ("FIT", r"fit|match|inconsisten|wrong|broken|garbled|watermark"))


def keys_of(problems):
    """(scene, category) pairs for a list of problem lines. The vision reviewer words things differently on every run, so
    a problem is compared by WHERE (scene) and WHAT KIND (category), not by its exact text."""
    out = set()
    for p in problems:
        t = str(p)
        m = re.search(r"\b(EMPTY|OVERLAP|CUT|READ|LANG|FIT|DUP)\b", t)
        cat = m.group(1) if m else next((c for c, rx in CATS if re.search(rx, t, re.I)), "OTHER")
        scenes = [int(x) for g in re.findall(r"scenes?\s+((?:\d+\s*(?:,|and|&)?\s*)+)", t, re.I) for x in re.findall(r"\d+", g)] or [0]
        out |= {(s, cat) for s in scenes}
    return out


def layout_set(pr):
    return {(f.get("code"), re.sub(r"\d+$", "", f.get("selector") or "")) for f in (pr or {}).get("layout") or []}


def check(code_dir, cid, job):
    """Compose + ONE preflight (no repairs) of an existing job with the code in code_dir, on a COPY of the job (live files
    untouched). Returns (ok, short reason, preflight result or None when the build crashed)."""
    src = os.path.join(OUT, cid, job)
    if not os.path.exists(os.path.join(src, "plan.json")) or not os.path.exists(os.path.join(src, "timing.json")):
        return None, "job has no plan/timing", None
    tmp = os.path.join(OUT, ".healcheck", f"{int(time.time())}-{job}")
    dst = os.path.join(tmp, cid, job)
    os.makedirs(dst)
    for f in os.listdir(src):
        p = os.path.join(src, f)
        if f in ("render", "preflight.json") or f.endswith((".mp4", ".mov")) or f.startswith(("sheet", "preflight-sheet", "cover-variants")):
            # 18 Nov: the old preflight.json was copied too, so a crashed build looked like "still failing"
            continue
        (shutil.copytree if os.path.isdir(p) else shutil.copy2)(p, os.path.join(dst, f))
    for f in ("gemini-keys.json", "realmedia-usage.json", "music-usage.json"):    # key quota state is shared, not reset
        if os.path.exists(os.path.join(OUT, f)):
            shutil.copy2(os.path.join(OUT, f), os.path.join(tmp, f))
    env = dict(os.environ, STUDIO_OUT=tmp, STUDIO_STOP_AFTER_PREFLIGHT="1", STUDIO_PREFLIGHT_TRIES="1", HOME=HOME)
    args = [PY, os.path.join(code_dir, "engine", "make.py"), cid, "--job", job, "--from", "compose", "--no-send"]
    if job.endswith("-en"):
        args += ["--lang", "en"]
    rc, out = sh(args, timeout=1500, cwd=code_dir, env=env)
    pr = load(os.path.join(dst, "preflight.json"), None)
    shutil.rmtree(tmp, ignore_errors=True)
    if '"preflight_ok": true' in out:
        return True, "preflight passed", pr or {"ok": True, "bad": {}, "layout": []}
    if pr:
        return False, "; ".join(f"s{int(k) + 1}: {v[0]}" for k, v in (pr.get("bad") or {}).items())[:300] or "preflight failed", pr
    return False, "build crashed: " + out.strip()[-300:], None


def problems_of(pr):
    return [f"before render, scene {int(k) + 1}: {v}" for k, vs in ((pr or {}).get("bad") or {}).items() for v in vs]


def verify_fix(wt, cid, job, problems):
    """True/False + reason. The fix passes when (1) the ORIGINAL problems are gone (layout audit exactly; vision problems
    by scene + kind) and (2) it adds no layout problem that the live code does not have, on this video and a good one."""
    ok, why, pr = check(wt, cid, job)
    if pr is None:
        return False, f"the build crashed with the fix: {why}"
    base = load(os.path.join(OUT, cid, job, "preflight.json"), {}) or {}
    still = keys_of(problems) & keys_of(problems_of(pr))
    lay_still = layout_set(base) & layout_set(pr) if any("layout audit" in str(p) for p in problems) else set()
    if still or lay_still:
        return False, f"the original problem is still there ({sorted(still) or sorted(lay_still)})"
    added = layout_set(pr) - layout_set(base)
    if added:
        return False, f"it adds new layout problems {sorted(added)}"
    g = good_job(cid, job)
    if g:
        okg, whyg, prg = check(wt, cid, g)
        if prg is None:
            return False, f"it breaks the good video {cid} {g}: {whyg}"
        if layout_set(prg):
            ok0, _, pr0 = check(ROOT, cid, g)
            extra = layout_set(prg) - layout_set(pr0)
            if extra:
                return False, f"it adds layout problems on the good video {cid} {g}: {sorted(extra)}"
    return True, "original problem gone, nothing new" + (f" (other notes on this video: {why[:120]})" if not ok else "")


def good_job(cid, not_job):
    done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
    for d in reversed(done):
        j = d["job"]
        tj = load(os.path.join(OUT, cid, j, "timing.json"), {}) or {}
        if d.get("status") in ("approved", "made", "posted") and j != not_job and not j.endswith("-en") \
                and tj.get("method") == "whisper" and (tj.get("cover") or 0) >= 0.75 \
                and os.path.exists(os.path.join(OUT, cid, j, "assets.json")):      # 18 Nov: an old job without a voice score
            return j                                                                    # made the check re-voice it
    return None


# ---------------------------------------------------------------- evidence for a held video
def evidence_for(cid, job):
    jd = os.path.join(OUT, cid, job)
    ev = []
    pr = load(os.path.join(jd, "preflight.json"), {}) or {}
    for f in (pr.get("layout") or [])[:6]:
        ev.append(f"layout audit: scene {f.get('scene', 0) + 1} {f.get('code')} on {f.get('selector')}: {f.get('msg')}")
    p = load(os.path.join(jd, "plan.json"), {}) or {}
    idx = sorted({int(k) for k in (pr.get("bad") or {})})
    for k in idx[:3]:
        if k < len(p.get("scenes", [])):
            s = {kk: vv for kk, vv in p["scenes"][k].items() if kk not in ("prompt",)}
            ev.append(f"plan scene {k + 1} (index {k}): {json.dumps(s, ensure_ascii=False)[:500]}")
    html = os.path.join(jd, "render", "index.html")
    if os.path.exists(html):
        h = open(html, encoding="utf-8").read()
        ids = {m for f in (pr.get("layout") or []) for m in re.findall(r"#([\w-]+)", f.get("selector") or "")}
        for i in list(ids)[:3]:
            m = re.search(rf'<div id="{re.escape(re.sub(r"[a-z]+$", "", i) or i)}"[^>]*>.*?</div></div>', h, re.S)
            if m:
                ev.append(f"rendered HTML of that scene: {m.group(0)[:700]}")
        m = re.search(r'<div id="endc".*?</div></div>', h, re.S)
        if m and ids:
            ev.append(f"end card HTML: {m.group(0)[:400]}")
    return ev


# ---------------------------------------------------------------- the fix
def fix(what, problems, files, verify=None, task=False):
    if not os.path.exists(AIDER):
        return {"result": "no coding agent installed (~/aider-venv)"}
    hid = time.strftime("%m%d-%H%M%S")
    wt, br = os.path.join(WT, hid), f"heal/{hid}"
    os.makedirs(WT, exist_ok=True)
    git("worktree", "prune")
    rc, out = git("worktree", "add", "-q", "-b", br, wt, "HEAD")
    if rc != 0:
        return {"result": "worktree failed: " + out[-200:]}
    base = git("rev-parse", "HEAD", cwd=wt)[1].strip()
    logf = os.path.join(OUT, "heal", f"{hid}.log")
    os.makedirs(os.path.dirname(logf), exist_ok=True)
    try:
        ev = list(problems)
        if verify:
            ev += evidence_for(*verify)
        msg = (RULES + "\n\nPROBLEM: " + what + "\nEVIDENCE:\n- " + "\n- ".join(str(e)[:700] for e in ev[:14]) +
               ("\n\nThis is a task from the owner's agent: do it only if it is a small, clear code change; otherwise change nothing."
                if task else "\n\nFind the cause in the given files and fix it."))
        fl = [f for f in (files or []) if os.path.exists(os.path.join(wt, f))]
        env = dict(os.environ, OPENAI_API_BASE="http://127.0.0.1:20128/v1",
                   OPENAI_API_KEY=open(os.path.join(HOME, ".omniroute-studio.key")).read().strip(), HOME=HOME)
        cmd = [AIDER, "--model", "openai/studio-code", "--edit-format", "diff", "--yes-always", "--no-stream", "--no-pretty",
               "--no-check-update", "--analytics-disable", "--no-show-model-warnings", "--no-gitignore", "--no-show-release-notes",
               "--map-tokens", "0" if fl else "2048", "--timeout", "600", "--message", msg] + fl
        rc, out = sh(cmd, timeout=1200, cwd=wt, env=env)
        open(logf, "w", encoding="utf-8").write(msg + "\n\n===== aider =====\n" + out)
        changed = [l for l in git("diff", "--name-only", f"{base}..HEAD", cwd=wt)[1].split() if l]
        if not changed:
            return {"result": "the coding agent made no change"}
        bad = [f for f in changed if not ALLOWED.match(f) or f in FORBIDDEN]
        if bad:
            return {"result": f"refused: it changed files it may not touch {bad}"}
        stat = git("diff", "--numstat", f"{base}..HEAD", cwd=wt)[1]
        nlines = sum(int(a) + int(b) for a, b, *_ in (l.split("\t") for l in stat.splitlines() if l and l[0].isdigit()))
        if nlines > MAX_LINES:
            return {"result": f"refused: {nlines} changed lines (max {MAX_LINES})"}
        # compile + import
        for f in changed:
            if f.endswith(".py"):
                rc, out = sh([PY, "-m", "py_compile", os.path.join(wt, f)])
                if rc != 0:
                    return {"result": f"does not compile: {f}: {out[-200:]}"}
                if f.startswith("engine/") and f not in ("engine/make.py",):
                    mod = os.path.basename(f)[:-3]
                    rc, out = sh([PY, "-c", f"import sys; sys.path[:0]=['{wt}/engine','{wt}/lib']; import {mod}"], timeout=60, cwd=wt)
                    if rc != 0:
                        return {"result": f"import failed: {mod}: {out.strip()[-200:]}"}
            elif f.endswith(".js"):
                rc, out = sh(["node", "--check", os.path.join(wt, f)])
                if rc != 0:
                    return {"result": f"JS does not parse: {f}: {out[-200:]}"}
        verified = False
        if verify:
            cid, job = verify
            ok, why = verify_fix(wt, cid, job, problems)
            if not ok:
                return {"result": f"not merged: {why}"}
            verified = True
            log("healer: fix checked on", cid, job, "-", why[:160])
        elif any(f in ("engine/compose.py", "engine/compose_lab.py", "engine/preflight.py", "engine/make.py") for f in changed):
            for cid in ("katha", "tech"):
                g = good_job(cid, "")
                if g:
                    okg, whyg, prg = check(wt, cid, g)
                    if prg is None:
                        return {"result": f"refused: it breaks the good video {cid} {g}: {whyg}"}
                    if layout_set(prg) - layout_set(check(ROOT, cid, g)[2]):
                        return {"result": f"refused: it adds layout problems on the good video {cid} {g}"}
        return merge(wt, br, what, changed, verified)
    finally:
        git("worktree", "remove", "--force", wt)
        git("branch", "-D", br)
        shutil.rmtree(os.path.join(OUT, ".healcheck"), ignore_errors=True)


def merge(wt, br, what, changed, verified):
    git("pull", "-q", "--rebase", "--autostash", timeout=120)
    rc, out = git("rebase", "-q", "main", cwd=wt)
    if rc != 0:
        git("rebase", "--abort", cwd=wt)
        return {"result": "could not rebase onto the live code: " + out[-160:]}
    git("commit", "--amend", "-q", "-m", f"healer: {what[:70]}" + ("" if verified else " (unverified)") +
        f"\n\nChanged: {', '.join(changed)}. Found and fixed by the server's own healer (engine/healer.py).", cwd=wt)
    rc, out = git("merge", "-q", "--ff-only", br)
    if rc != 0:
        return {"result": "fast-forward failed: " + out[-160:]}
    commit = git("rev-parse", "--short", "HEAD")[1].strip()
    for _ in range(3):
        rc, out = git("push", "-q", timeout=120)
        if rc == 0:
            break
        git("pull", "-q", "--rebase", "--autostash", timeout=120)
    if any(f.startswith("dashboard/") for f in changed):
        sh(["sudo", "systemctl", "restart", "studio-dash"], timeout=120)
    log("healer: merged code fix", commit, what[:100], "verified" if verified else "unverified")
    if os.environ.get("STUDIO_NO_TELEGRAM") != "1":
        telegram(f"🩹 Studio fixed its own code: {what[:120]} ({', '.join(changed)}; {'checked on the failing video' if verified else 'watching for a repeat'}).")
    return {"result": "merged" + ("" if verified else " (unverified)"), "merged": True, "commit": commit, "verified": verified}


def revert(commit, why):
    git("pull", "-q", "--rebase", "--autostash")
    rc, out = git("revert", "--no-edit", commit)
    if rc != 0:
        git("revert", "--abort")
        return False
    git("push", "-q")
    log("healer: reverted", commit, why[:120])
    return True


if __name__ == "__main__":
    if "--check" in sys.argv:
        i = sys.argv.index("--check")
        print(check(ROOT, sys.argv[i + 1], sys.argv[i + 2])[:2])
