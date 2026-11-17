"""Studio healer (owner 18 Nov: "the server must fix things itself; why do you have to fix and do things?").
Runs every 15 min (timer studio-healer, low priority). The doctor keeps services alive with fixed recipes; the healer
works through EVERYTHING the doctor, selfcheck, review and the Mehul agent could not fix, so nothing waits for a Kiro session.

  inbox    held videos (channels/*/done.json), ~/studio-out/doctor-unknown.json (unknown errors, failed units, failed
           repairs, selfcheck could-not-fix), open [mehul] code tasks in knowledge/build-queue.md
  classify each item:  wait (free-tier quota / overload / a reboot) | gone (did not happen again) | retry (code changed
           since the last try) | input (change the scene: simpler type, new picture) | code (a code fix) | park
  held-video ladder (one step per run, each step only once per code version):
           1 known fix (knowledge/fixes.json) -> apply it straight away
           2 rebuild from the right stage when the code changed since the last try
           3 change the input: re-plan only the failing scenes (simpler type, shorter text, new picture)
           4 code fix (engine/healcode.py: coding agent in a separate git worktree, verified, merged only if it passes)
           5 park (retried automatically after the next code change)
  learning every verified fix is saved in knowledge/fixes.json (problem signature -> what fixed it), so the next match
           is fixed at step 1 without asking any model.
  limits   one build at a time, nothing when MemAvailable < 2.5 GB, never posts, never deletes posted content.
Everything is logged (engine.log "healer:" lines, ~/studio-out/healer.json, knowledge/STATE.md).
  python engine/healer.py [--dry] [--once <cid> <job>]"""
import glob, hashlib, json, os, re, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, HOME, log, load, save, read

DRY = "--dry" in sys.argv
STATE = os.path.join(OUT, "healer.json")
UNKNOWN = os.path.join(OUT, "doctor-unknown.json")
FIXES = os.path.join(ROOT, "knowledge", "fixes.json")
PY = "/home/ubuntu/studio-venv/bin/python"
PAGES = ("tech", "katha", "raaz")
S = load(STATE, {}) or {}
S.setdefault("items", {}); S.setdefault("seen_unknown", []); S.setdefault("log", [])
did = []

# problems that are not faults: every caller has a fallback model, or the cause was a restart
WAIT = re.compile(r"429|503|Too Many Requests|Service Unavailable|timed out|quota|overloaded|Connection refused|"
                  r"Temporary failure in name resolution|Connection reset|Remote end closed|EOF occurred", re.I)
CODE_HINT = re.compile(r"Traceback|Error\b|Exception|KeyError|TypeError|AttributeError|NameError|IndexError|ValueError|"
                       r"SyntaxError|No module named|not defined|unexpected keyword|object is not|failed:", re.I)
# code that a stage owns: a held video's problem points at these files
STAGE_FILES = {"compose": ["engine/compose.py", "engine/compose_lab.py"], "voice": ["engine/tts.py", "engine/align.py", "engine/pace.py"],
               "mix": ["lib/mix.py"], "preflight": ["engine/preflight.py"], "review": ["engine/review.py", "engine/qc.py"]}


def sh(cmd, timeout=120, cwd=None):
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def note(what):
    did.append(what); log("healer:", what)
    S["log"] = (S["log"] + [{"t": time.strftime("%Y-%m-%d %H:%M"), "what": what}])[-200:]


def mem_mb():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable"):
            return int(l.split()[1]) // 1024
    return 0


def busy():
    return sh("systemctl list-units --state=active,activating --no-legend 'studio-job-*.service' 'studio-make.service' 'studio-prep.service'")[1].strip()


def head():
    return sh(f"git -C {ROOT} rev-parse --short HEAD")[1].strip()


def changed_since(commit, files):
    """True when any of these files changed after `commit` (or commit unknown)."""
    if not commit:
        return True
    rc, out = sh(["git", "-C", ROOT, "diff", "--name-only", f"{commit}..HEAD", "--"] + files)
    return rc == 0 and bool(out.strip())


def sig(text):
    t = re.sub(r"#?s\d+[a-z]*", "#s", str(text).lower())
    t = re.sub(r"\d+", "#", t)
    t = re.sub(r"'[^']*'|\"[^\"]*\"", "'…'", t)
    return t[:110]


def fixes():
    return load(FIXES, []) or []


def learn(problem, fix, detail=""):
    """Save a verified fix: next time the same problem signature is fixed at step 1."""
    if DRY:
        return
    fx, s = fixes(), sig(problem)
    row = next((f for f in fx if f["sig"] == s and f["fix"] == fix), None)
    if row:
        row["n"] += 1; row["last"] = time.strftime("%Y-%m-%d %H:%M")
    else:
        fx.append({"sig": s, "fix": fix, "detail": detail[:200], "n": 1, "first": time.strftime("%Y-%m-%d %H:%M"),
                   "last": time.strftime("%Y-%m-%d %H:%M"), "example": str(problem)[:200]})
    save(FIXES, fx)


def known_fix(problems):
    fx = fixes()
    for p in problems:
        s = sig(p)
        for f in sorted(fx, key=lambda f: -f["n"]):
            if f["sig"] == s:
                return f
    return None


# ---------------------------------------------------------------- held videos
def stage_for(probs):
    """Which stage a held video's problems point at."""
    t = " ".join(probs).lower()
    if "spoken instructions" in t or "does not start with the first line" in t or "starts late" in t or "of the script was found" in t \
            or "voice is" in t and "for" in t:
        return "voice"
    if "loudness" in t or "true peak" in t:
        return "mix"
    return "compose"                                        # layout, captions, pictures: all land in compose


def scenes_in(probs):
    out = set()
    for p in probs:
        for m in re.finditer(r"scenes?\s+(\d+)(?:\s*(?:,|and|&)\s*(\d+))*", str(p), re.I):
            out.update(int(x) - 1 for x in re.findall(r"\d+", m.group(0)))
    return sorted(out)


def rebuild(cid, job, frm, why, extra_env=""):
    lang = " --lang en" if job.endswith("-en") else ""
    unit = f"studio-job-heal-{int(time.time())}"
    cmd = (f"sudo systemd-run --unit={unit} --uid=ubuntu -p CPUWeight=20 -p Nice=15 -p MemoryHigh=2600M -p MemoryMax=3400M "
           f"--working-directory={ROOT} -E HOME={HOME} {extra_env} {PY} {ROOT}/engine/make.py {cid} --job {job} --from {frm}{lang}")
    if DRY:
        note(f"[dry] would rebuild {cid} {job} from {frm} ({why})"); return True
    rc, out = sh(cmd)
    note(f"rebuilding held {cid} {job} from {frm} ({why})" + ("" if rc == 0 else f" FAILED to start: {out[-120:]}"))
    return rc == 0


def simplify(cid, job, probs):
    """Step 3: change the input. Re-plan only the failing scenes: simpler type, shorter text, new picture."""
    import preflight
    jd = os.path.join(OUT, cid, job)
    p = load(os.path.join(jd, "plan.json"))
    ch = load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}
    if not p or not p.get("scenes"):
        return False
    idx = scenes_in(probs) or [len(p["scenes"]) - 1]
    bad = {}
    for k in idx:
        if 0 <= k < len(p["scenes"]):
            bad[str(k)] = [str(x) for x in probs if re.search(rf"scenes?\D{{0,12}}\b{k + 1}\b", str(x), re.I)] or [str(x) for x in probs]
            bad[str(k)].append("HEALER: earlier repairs did not pass. Make this scene SIMPLER: fewer words on screen (or none), "
                               "one clear subject, and keep any character exactly as the plan's cast describes.")
    if not bad:
        return False
    lang = p.get("lang") or ch.get("lang", "hi")
    if (ch.get("theme") or {}).get("style") == "lab":
        n = preflight.repair(p, bad, lang)
        redo = []
    else:
        redo = preflight.repair_classic(p, bad, lang, ch.get("name", cid))
        n = len(bad)
        for k in bad:                                       # classic: the failing scenes get a NEW picture
            k = int(k)
            if k not in redo:
                redo.append(k)
            if p["scenes"][k].get("type") == "card" and any("overlap" in x.lower() or "cut" in x.lower() for x in bad[str(k)]):
                p["scenes"][k]["type"] = "image"; p["scenes"][k]["big"] = None; p["scenes"][k]["small"] = None
    if not n and not redo:
        return False
    if DRY:
        note(f"[dry] would re-plan {cid} {job} scenes {[int(k) + 1 for k in bad]}"); return True
    save(os.path.join(jd, "plan.json"), p)
    got = load(os.path.join(jd, "assets.json"), {}) or {}
    for k in redo:
        got.pop(str(k), None)
    save(os.path.join(jd, "assets.json"), got)
    note(f"{cid} {job}: re-planned scenes {[int(k) + 1 for k in bad]} (simpler, new picture for {[k + 1 for k in redo]})")
    return True


def heal_held():
    if busy():
        return
    if mem_mb() < 2500:
        note(f"waiting: only {mem_mb()} MB free (needs 2500)"); return
    h = head()
    for cid in PAGES:
        done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
        for d in done:
            if d.get("status") != "held":
                continue
            job, probs = d["job"], [str(x) for x in (d.get("review") or [])]
            key = f"held:{cid}:{job}"
            it = S["items"].setdefault(key, {"first": time.strftime("%Y-%m-%d %H:%M"), "steps": []})
            it["problems"] = probs
            if job.endswith("-en"):                         # owner 18 Nov: English editions are off on every page
                if it.get("state") != "parked":
                    it.update(state="parked", why="English editions are off (owner 18 Nov)"); note(f"parked {cid} {job}: English editions are off")
                continue
            # a rebuild we started finished: did it pass?
            last = it["steps"][-1] if it["steps"] else None
            if last and last.get("pending"):
                last["pending"] = False
                last["result"] = "still held: " + "; ".join(probs)[:160]
            tried = {(s["step"], s.get("code")) for s in it["steps"]}
            stg = stage_for(probs)
            files = STAGE_FILES.get(stg, []) + STAGE_FILES["preflight"] + ["engine/make.py", "engine/plan.py"]
            # 1 known fix
            kf = known_fix(probs)
            if kf and ("known", h) not in tried:
                it["steps"].append({"step": "known", "code": h, "fix": kf["fix"], "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                if kf["fix"] == "simplify" and simplify(cid, job, probs):
                    rebuild(cid, job, "assets" if stg == "compose" else stg, f"known fix: {kf['fix']}")
                else:
                    rebuild(cid, job, stg, f"known fix: {kf['fix']}")
                save(STATE, S); return
            # 2 rebuild after a code change
            since = next((s["code"] for s in reversed(it["steps"]) if s.get("code")), None) or \
                (load(os.path.join(OUT, cid, job, "meta.json"), {}) or {}).get("doctor_code")
            if ("rebuild", h) not in tried and changed_since(since, files):
                it["steps"].append({"step": "rebuild", "code": h, "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                rebuild(cid, job, stg, "code changed since the last try"); save(STATE, S); return
            # 3 change the input (once per code version)
            if ("simplify", h) not in tried and stg == "compose":
                it["steps"].append({"step": "simplify", "code": h, "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                if simplify(cid, job, probs):
                    rebuild(cid, job, "assets", "failing scenes re-planned"); save(STATE, S); return
                it["steps"][-1].update(pending=False, result="nothing to re-plan")
            if ("simplify", h) not in tried and stg == "voice":
                it["steps"].append({"step": "simplify", "code": h, "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                for f_ in ("vo-raw.wav", "vo-paced.wav", "timing.json"):
                    p_ = os.path.join(OUT, cid, job, f_)
                    if os.path.exists(p_) and not DRY:
                        os.remove(p_)
                rebuild(cid, job, "voice", "new voice"); save(STATE, S); return
            # 4 code fix
            if ("code", h) not in tried and S.get("code_day", {}).get(time.strftime("%Y-%m-%d"), 0) < 6:
                it["steps"].append({"step": "code", "code": h, "t": time.strftime("%Y-%m-%d %H:%M")})
                save(STATE, S)
                if code_fix(f"held video {cid} {job}", probs, STAGE_FILES.get(stg, []) + ["engine/preflight.py"], verify=(cid, job)).get("merged"):
                    it["steps"][-1]["result"] = "code fixed"; learn(probs[0], "code", "see git log: healer")
                    it["steps"].append({"step": "rebuild", "code": head(), "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                    rebuild(cid, job, stg, "code fixed by the healer")
                else:
                    it["steps"][-1]["result"] = "no verified code fix"
                save(STATE, S); return
            if it.get("state") != "parked":
                it.update(state="parked", why="every step tried for this code version; retried after the next code change")
                note(f"parked {cid} {job}: {'; '.join(probs)[:140]}")


def heal_orphans():
    """18 Nov: jobs cut off mid-build (the 01:50 freeze + reboot left katha 1118-0053 and 1118-0133 with a voice but no
    pictures) were never picked up again: no lane resumes a job without a stage. Resume the oldest one from its last
    finished step (make.py skips every step whose output exists), up to the prepped stage."""
    if busy() or mem_mb() < 2500:
        return
    for cid in PAGES:
        known = {d["job"] for d in load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []}
        for jd in sorted(glob.glob(os.path.join(OUT, cid, "*"))):
            job = os.path.basename(jd)
            meta = load(os.path.join(jd, "meta.json"), None)
            if meta is None or job in known or job.endswith("-en") or meta.get("stage") in ("done", "prepped", "held"):
                continue
            newest = max((os.path.getmtime(os.path.join(dp, f)) for dp, _, fs in os.walk(jd) for f in fs), default=0)
            if time.time() - newest < 3600:
                continue                                    # still being built (or just stopped): not an orphan yet
            key = f"orphan:{cid}:{job}"
            it = S["items"].setdefault(key, {"first": time.strftime("%Y-%m-%d %H:%M"), "steps": [], "what": meta.get("topic", "")})
            if len(it["steps"]) >= 2:
                if it.get("state") != "parked":
                    it.update(state="parked", why="resumed twice and still unfinished"); note(f"parked orphan {cid} {job}")
                continue
            it["steps"].append({"step": "resume", "t": time.strftime("%Y-%m-%d %H:%M")}); it["state"] = "working"
            unit = f"studio-job-resume-{int(time.time())}"
            cmd = (f"sudo systemd-run --unit={unit} --uid=ubuntu -p CPUWeight=20 -p Nice=15 -p MemoryHigh=2600M -p MemoryMax=3400M "
                   f"--working-directory={ROOT} -E HOME={HOME} {PY} {ROOT}/engine/make.py {cid} --job {job} --until assets")
            if DRY:
                note(f"[dry] would resume unfinished {cid} {job} ({meta.get('topic', '')[:60]})"); return
            rc, out = sh(cmd)
            note(f"resumed unfinished {cid} {job} ({meta.get('topic', '')[:60]})" + ("" if rc == 0 else f" FAILED: {out[-100:]}"))
            save(STATE, S)
            return


def check_cleared():
    """Held items whose video is no longer held: record what fixed it (learning)."""
    status = {}
    for cid in PAGES:
        for d in load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []:
            status[f"held:{cid}:{d['job']}"] = d.get("status")
    for key, it in S["items"].items():
        if key.startswith("orphan:") and it.get("state") == "working":
            m = load(os.path.join(OUT, key.split(":")[1], key.split(":")[2], "meta.json"), {}) or {}
            if m.get("stage") in ("prepped", "done"):
                it.update(state="fixed", fixed=time.strftime("%Y-%m-%d %H:%M")); note(f"unfinished {key[7:]} is {m['stage']} now")
            continue
        if not key.startswith("held:") or it.get("state") == "fixed":
            continue
        st = status.get(key)
        if st and st != "held":
            last = next((s for s in reversed(it["steps"]) if s.get("step") in ("known", "rebuild", "simplify")), None)
            it.update(state="fixed", fixed=time.strftime("%Y-%m-%d %H:%M"), status=st)
            if last:
                last.update(pending=False, result="passed")
                learn((it.get("problems") or ["?"])[0], "simplify" if last["step"] == "simplify" else last.get("fix", "rebuild"))
            note(f"fixed {key[5:]}: now {st} (step: {last['step'] if last else '?'})")


# ---------------------------------------------------------------- unknown errors
def recent_log(minutes):
    cut = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - minutes * 60))
    try:
        lines = open(os.path.join(OUT, "engine.log"), encoding="utf-8", errors="ignore").readlines()[-4000:]
    except OSError:
        return []
    return [l for l in lines if l[:19] >= cut]


def still_happening(detail, minutes=60):
    pat = re.escape(detail.strip()[:60]).replace("\\#", r"\d+")
    try:
        rx = re.compile(pat)
    except re.error:
        return False
    return any(rx.search(re.sub(r"\d+", lambda m: m.group(0), l[20:])) for l in recent_log(minutes))


def code_location(detail):
    """Find the engine file that writes this log message (works without a traceback: grep the message text)."""
    m = re.match(r"\s*((?:[A-Za-z][\w-]*\s+){1,7}[A-Za-z][\w-]*)", re.sub(r"[#\d]+", " ", detail))
    words = (m.group(1) if m else "").split()
    for n in range(len(words), 1, -1):                     # longest leading phrase that appears in a source file
        phrase = " ".join(words[:n])
        if len(phrase) < 8:
            break
        rc, out = sh(["grep", "-rlF", "--include=*.py", phrase, os.path.join(ROOT, "engine"), os.path.join(ROOT, "lib"),
                      os.path.join(ROOT, "dashboard")])
        found = [os.path.relpath(f, ROOT) for f in out.splitlines() if f.endswith(".py") and not f.endswith(("healer.py", "doctor.py"))]
        if found:
            return found[:3]
    return []


def heal_unknown():
    items = load(UNKNOWN, []) or []
    seen = set(S["seen_unknown"])
    for u in items:
        k = hashlib.sha1((u.get("what", "") + u.get("detail", "")).encode()).hexdigest()[:12]
        if k in seen:
            continue
        seen.add(k)
        what, detail = u.get("what", ""), u.get("detail", "")
        key = f"unk:{k}"
        it = S["items"].setdefault(key, {"first": u.get("t"), "what": what, "detail": detail[:300], "steps": []})
        if what.startswith("held video still failing"):
            it.update(state="merged", why="handled by the held-video ladder"); continue
        if WAIT.search(detail) and not CODE_HINT.search(detail.replace("HTTP Error", "")):
            it.update(state="wait", why="free-tier quota / restart: every caller has a fallback")
            continue
        if what.startswith("selfcheck found"):              # selfcheck re-probes every 30 min: trust its latest findings
            cur = json.dumps((load(os.path.join(OUT, "selfcheck.json"), {}) or {}).get("findings", []))
            tag = what.split("could not fix:", 1)[-1].strip()
            if tag and tag in cur:
                it.update(state="open")
            else:
                it.update(state="gone", why="selfcheck no longer finds it")
            continue
        if not still_happening(detail):
            it.update(state="gone", why="did not happen again in the last hour"); continue
        it.update(state="open")
    S["seen_unknown"] = list(seen)[-400:]
    # open items: try a code fix (one per run)
    for key, it in S["items"].items():
        if not key.startswith("unk:") or it.get("state") != "open":
            continue
        if not still_happening(it["detail"], 180):
            it.update(state="gone", why="stopped by itself"); note(f"closed: {it['what'][:80]} (stopped by itself)"); continue
        if it.get("tried_code") == head() or S.get("code_day", {}).get(time.strftime("%Y-%m-%d"), 0) >= 6:
            continue
        it["tried_code"] = head()
        files = code_location(it["detail"]) or code_location(it["what"])
        if not files:
            it.update(state="parked", why="no code location found"); note(f"parked: {it['what'][:80]} (no code location)"); continue
        ev = [it["what"], it["detail"]] + [l.strip()[:300] for l in recent_log(180) if it["detail"][:30].replace("#", "") in l][:8]
        r = code_fix(it["what"], ev, files)
        if r.get("merged"):
            it.update(state="fixed", fixed=time.strftime("%Y-%m-%d %H:%M"), fixed_ts=time.time(), commit=r.get("commit"),
                      verified=r.get("verified"))
            learn(it["detail"], "code", ",".join(files))
        save(STATE, S)
        return


def watch_unverified():
    """An unverified code fix whose error comes back within 2 days is reverted automatically."""
    import healcode
    for key, it in S["items"].items():
        if it.get("state") != "fixed" or it.get("verified") or not it.get("commit") or it.get("reverted"):
            continue
        age = time.time() - it.get("fixed_ts", time.time())
        if age < 1800 or age > 2 * 86400:
            continue
        if still_happening(it["detail"], int(age // 60) - 20):
            ok = DRY or healcode.revert(it["commit"], it["what"])
            it.update(reverted=bool(ok), state="open" if ok else "fixed")
            note(f"reverted {it['commit']} ({it['what'][:80]}): the same error came back")


# ---------------------------------------------------------------- [mehul] code tasks
def heal_tasks():
    """Open '- [ ] [mehul] ...' tasks the Mehul agent wrote for code: one attempt per task per code version, max 1 a day."""
    day = time.strftime("%Y-%m-%d")
    if S.get("task_day") == day:
        return
    q = read(os.path.join(ROOT, "knowledge", "build-queue.md"))
    for line in q.splitlines():
        if not line.startswith("- [ ] [mehul]"):
            continue
        k = "task:" + hashlib.sha1(line.encode()).hexdigest()[:12]
        it = S["items"].setdefault(k, {"what": line[:300], "steps": []})
        if it.get("tried_code") == head() or it.get("state") == "fixed":
            continue
        it["tried_code"] = head(); S["task_day"] = day
        if code_fix("owner-agent task", [line], None, task=True).get("merged"):
            it["state"] = "fixed"
            if not DRY:
                txt = read(os.path.join(ROOT, "knowledge", "build-queue.md")).replace(line, line.replace("- [ ]", "- [x]", 1) + " (healer)")
                open(os.path.join(ROOT, "knowledge", "build-queue.md"), "w", encoding="utf-8").write(txt)
        save(STATE, S)
        return


def code_fix(what, evidence, files, verify=None, task=False):
    """Hand the problem to the coding agent (engine/healcode.py). True only when a fix was verified and merged."""
    if DRY:
        note(f"[dry] would ask the coding agent: {what} ({files})"); return {}
    if mem_mb() < 3000:
        note(f"code fix for {what} waits: only {mem_mb()} MB free"); return {}
    day = time.strftime("%Y-%m-%d")
    S.setdefault("code_day", {})[day] = S["code_day"].get(day, 0) + 1
    S["code_day"] = dict(sorted(S["code_day"].items())[-7:])
    import healcode
    r = healcode.fix(what, evidence, files, verify=verify, task=task)
    note(f"code fix for {what}: {r.get('result')}" + (f" (commit {r['commit']})" if r.get("commit") else ""))
    return r


# ---------------------------------------------------------------- state file
def write_state():
    """knowledge/STATE.md: the server's own picture of itself (a new session reads this, not hand-written notes)."""
    try:
        import state
        state.write()
    except Exception as e:
        log("healer: state file failed", str(e)[:120])


def main():
    if "--once" in sys.argv:
        i = sys.argv.index("--once"); cid, job = sys.argv[i + 1], sys.argv[i + 2]
        S["items"].pop(f"held:{cid}:{job}", None)
    for step in (check_cleared, watch_unverified, heal_held, heal_orphans, heal_unknown, heal_tasks):
        try:
            step()
        except Exception as e:
            import traceback
            log("healer:", step.__name__, "crashed:", traceback.format_exc()[-400:].replace("\n", " | "))
    if not DRY:
        save(STATE, S)
        write_state()
    print(json.dumps({"did": did}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
