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
from core import pages as _pages

DRY = "--dry" in sys.argv
_save = save


def save(path, data):
    """18 Nov: --dry still wrote healer.json from inside heal_held (a dry run marked steps as tried). Dry writes nothing."""
    if not DRY:
        _save(path, data)


STATE = os.path.join(OUT, "healer.json")
UNKNOWN = os.path.join(OUT, "doctor-unknown.json")
FIXES = os.path.join(ROOT, "knowledge", "fixes.json")
PY = "/home/ubuntu/studio-venv/bin/python"
# 19 Nov: clip pages (CutCapsule, channel.json kind "clips") are made by engine/clipper.py, not make.py: the healer's
# make.py rebuilds would break them, and a held test clip is held on purpose (no permission to post).
PAGES = [p for p in _pages() if (load(os.path.join(ROOT, "channels", p, "channel.json"), {}) or {}).get("kind") != "clips"]
S = load(STATE, {}) or {}
S.setdefault("items", {}); S.setdefault("seen_unknown", []); S.setdefault("log", [])
did = []

# problems that are not faults: every caller has a fallback model, or the cause was a restart
WAIT = re.compile(r"429|503|Too Many Requests|Service Unavailable|timed out|quota|overloaded|Connection refused|"
                  r"Temporary failure in name resolution|Connection reset|Remote end closed|EOF occurred|"
                  # 18 Nov: free providers hiccup; every caller falls back to the next model (not a code fault)
                  r"Bad Gateway|Gateway Time|HTTP Error 50[234]|tiny image|Expecting value|No results found|"
                  r"clip failed -> still image|no page key", re.I)
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
    """The CODE version: last commit that touched engine/ or lib/. (18 Nov: HEAD changes after every render because sync
    commits jobs + lessons, which would have re-run every healer step after every render.)"""
    return sh(f"git -C {ROOT} log -1 --format=%h -- engine lib")[1].strip()


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
PIC_PROB = re.compile(r"picture check|frame check|iconograph|wrong (traditional )?form", re.I)
PIC_WORDS = re.compile(r"dome|minaret|mosque|robe|saffron|orange|crown|tilak|jewel|beard|moustache|split|collage|blue skin|"
                       r"clothing|dhoti|deity|idol|god|goddess|monk|four-armed|third eye|tirthankara|bahubali", re.I)


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


WANT = os.path.join(OUT, "healer-wants-turn")


def want_turn(on):
    """18 Nov: the prep lane builds new videos almost non-stop, so 'one build at a time' starved the healer. When it
    has work but the server is busy it raises this flag; the prep lane skips one round (engine/daily.py)."""
    if DRY:
        return
    if on:                                      # 18 Nov: refreshed every round; written once it went stale after 1 h
        open(WANT, "w").write(time.strftime("%Y-%m-%d %H:%M"))      # (the lanes ignore a flag older than 1 h)
    elif os.path.exists(WANT):
        os.remove(WANT)


def heal_held():
    rows = []
    for cid in PAGES:
        for d in load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []:
            if d.get("status") == "held" and not d["job"].endswith("-en"):
                it = S["items"].get(f"held:{cid}:{d['job']}") or {}
                parked = it.get("state") == "parked" and not d.get("replan_requested")
                last_t = ((it.get("steps") or [{}])[-1]).get("t", "")
                rows.append((("1" if parked else "0") + last_t, cid, d))
    if not any(r[0].startswith("0") for r in rows):         # only parked ones: no need to take the prep lane's turn
        want_turn(False)
        if not rows:
            return
    if busy():
        if any(r[0].startswith("0") for r in rows):
            want_turn(True)
        return
    try:                                         # 18 Nov: a live page about to run out of videos gets the server first
        import daily
        urg = daily.urgent_pages()
    except Exception as e:
        urg = []; log("healer: urgent check failed", str(e)[:100])
    if urg:
        want_turn(False)
        log("healer: rebuilds wait, new videos first for", ", ".join(urg), f"(fewer than {daily.URGENT_MIN} ready)")
        return
    if mem_mb() < 2500:
        note(f"waiting: only {mem_mb()} MB free (needs 2500)"); return
    want_turn(False)
    h = head()
    # oldest last attempt first: every held video gets its turn (18 Nov: one tech video took every run)
    for _, cid, d in sorted(rows, key=lambda r: r[0]) + [(None, cid_, d_) for cid_ in PAGES
                                                          for d_ in (load(os.path.join(ROOT, "channels", cid_, "done.json"), []) or [])
                                                          if d_.get("status") == "held" and d_["job"].endswith("-en")]:
        if True:
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
            # 18 Nov: a code step that crashed mid-way (no result) is not a try; drop it so it runs again
            it["steps"] = [s for s in it["steps"] if not (s["step"] == "code" and "result" not in s)]
            tried = {(s["step"], s.get("code")) for s in it["steps"]}
            today_steps = sum(1 for s in it["steps"] if s.get("t", "")[:10] == time.strftime("%Y-%m-%d"))
            if today_steps >= 6:                            # a hard daily cap per video: never loop on one job
                continue
            stg = stage_for(probs)
            files = STAGE_FILES.get(stg, []) + STAGE_FILES["preflight"] + ["engine/make.py", "engine/plan.py"]
            # 0 the owner agent (engine/mehul.py) asked for a new plan: honour it first, once per request
            req = d.get("replan_requested")
            if req and not any(s["step"] == "replan" and s.get("req") == req for s in it["steps"]):
                it["state"] = "working"
                it["steps"].append({"step": "replan", "req": req, "code": h, "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                rebuild(cid, job, "plan", "the owner agent asked for a new plan"); save(STATE, S); return
            # 1 known fix
            kf = known_fix(probs)
            if kf and ("known", h) not in tried:
                it["state"] = "working"; it["steps"].append({"step": "known", "code": h, "fix": kf["fix"], "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                if kf["fix"] == "simplify" and simplify(cid, job, probs):
                    rebuild(cid, job, "assets" if stg == "compose" else stg, f"known fix: {kf['fix']}")
                else:
                    rebuild(cid, job, stg, f"known fix: {kf['fix']}")
                save(STATE, S); return
            # 1b 20 Nov: a wrong PICTURE is not fixed by a rebuild (it reuses the picture). Redraw only the flagged scenes
            # through engine/picsmith.py (prompt engineer, reference / real idol photo, Decisions check), once per code
            pic = [x for x in probs if PIC_PROB.search(x) or (re.search(r"\bFIT:|visual:", x) and PIC_WORDS.search(x))]
            ks = sorted(k for k in scenes_in(pic) if k >= 0) if pic else []
            done_sets = [s_.get("scenes") for s_ in it["steps"] if s_["step"] == "redraw" and s_.get("code") == h]
            if ks and [k + 1 for k in ks] not in done_sets and len(done_sets) < 3:     # new scenes flagged -> redraw them
                it["state"] = "working"
                it["steps"].append({"step": "redraw", "code": h, "scenes": [k + 1 for k in ks], "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                if not DRY:
                    jd_ = os.path.join(OUT, cid, job)
                    got = load(os.path.join(jd_, "assets.json"), {}) or {}
                    for k in ks:
                        got.pop(str(k), None)
                    save(os.path.join(jd_, "assets.json"), got)
                    p_ = load(os.path.join(jd_, "plan.json"), {}) or {}
                    p_.pop("pic_redraws", None)
                    for k in ks:
                        if k < len(p_.get("scenes") or []):
                            p_["scenes"][k].pop("pic", None)
                    save(os.path.join(jd_, "plan.json"), p_)
                note(f"{cid} {job}: new pictures for scenes {[k + 1 for k in ks]} (picsmith)")
                rebuild(cid, job, "assets", "wrong pictures redrawn"); save(STATE, S); return
            # 1c 20 Nov: informal address ("tum", "batao") -> rewrite the lines (engine/respect.py) and make a new voice
            if any("informal '" in x for x in probs) and ("respect", h) not in tried:
                it["state"] = "working"; it["steps"].append({"step": "respect", "code": h, "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                if not DRY:
                    import respect
                    jd_ = os.path.join(OUT, cid, job)
                    p_ = load(os.path.join(jd_, "plan.json"), {}) or {}
                    respect.fix_plan(p_); save(os.path.join(jd_, "plan.json"), p_)
                    if "owner-approved" in " ".join(probs):      # tools/revoice.py marks videos the owner had approved
                        m_ = load(os.path.join(jd_, "meta.json"), {}) or {}
                        m_["keep_approval"] = True; save(os.path.join(jd_, "meta.json"), m_)
                    for f_ in ("vo-raw.wav", "vo-paced.wav", "timing.json"):
                        if os.path.exists(os.path.join(jd_, f_)):
                            os.remove(os.path.join(jd_, f_))
                note(f"{cid} {job}: lines rewritten to 'aap' + request, new voice")
                rebuild(cid, job, "voice", "informal address fixed"); save(STATE, S); return
            # 2 rebuild after a code change
            since = next((s["code"] for s in reversed(it["steps"]) if s.get("code")), None) or \
                (load(os.path.join(OUT, cid, job, "meta.json"), {}) or {}).get("doctor_code")
            if ("rebuild", h) not in tried and changed_since(since, files):
                it["state"] = "working"; it["steps"].append({"step": "rebuild", "code": h, "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                rebuild(cid, job, stg, "code changed since the last try"); save(STATE, S); return
            # 3 change the input (once per code version)
            if ("simplify", h) not in tried and stg == "compose":
                it["state"] = "working"; it["steps"].append({"step": "simplify", "code": h, "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                if simplify(cid, job, probs):
                    rebuild(cid, job, "assets", "failing scenes re-planned"); save(STATE, S); return
                it["steps"][-1].update(pending=False, result="nothing to re-plan")
            if ("simplify", h) not in tried and stg == "voice":
                it["state"] = "working"; it["steps"].append({"step": "simplify", "code": h, "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
                for f_ in ("vo-raw.wav", "vo-paced.wav", "timing.json"):
                    p_ = os.path.join(OUT, cid, job, f_)
                    if os.path.exists(p_) and not DRY:
                        os.remove(p_)
                rebuild(cid, job, "voice", "new voice"); save(STATE, S); return
            # 4 code fix
            if ("code", h) not in tried and S.get("code_day", {}).get(time.strftime("%Y-%m-%d"), 0) < 6:
                it["state"] = "working"; it["steps"].append({"step": "code", "code": h, "t": time.strftime("%Y-%m-%d %H:%M")})
                save(STATE, S)
                r = code_fix(f"held video {cid} {job}", probs, STAGE_FILES.get(stg, []) + ["engine/preflight.py"], verify=(cid, job))
                if r.get("skipped"):                     # 18 Nov: low memory / busy is not a try; the next round asks again
                    it["steps"].pop(); save(STATE, S); return
                if r.get("merged"):
                    it["steps"][-1]["result"] = "code fixed"; learn(probs[0], "code", "see git log: healer")
                    it["state"] = "working"; it["steps"].append({"step": "rebuild", "code": head(), "t": time.strftime("%Y-%m-%d %H:%M"), "pending": True})
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
            if meta is None or job in known or job.endswith("-en") or meta.get("stage") in ("done", "prepped", "held", "cancelled"):
                continue                                    # 19 Nov: "cancelled" = the owner stopped it from the Run tab
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
            last = next((s for s in reversed(it["steps"]) if s.get("step") in ("known", "rebuild", "simplify", "replan")), None)
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
        what, detail = u.get("what", ""), u.get("detail", "")
        # 18 Nov: keyed by the error itself; "repeated 5 times" and "repeated 7 times" were 2 items for one error
        k = hashlib.sha1((re.sub(r"\d+", "#", what) + detail).encode()).hexdigest()[:12]
        sk = k + ":" + str(u.get("t", ""))
        if sk in seen:
            continue
        seen.add(sk)
        key = f"unk:{k}"
        it = S["items"].setdefault(key, {"first": u.get("t"), "what": what, "detail": detail[:300], "steps": []})
        it["what"] = what
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
    # 18 Nov: a failed unit is judged by the unit itself (scout was fixed in its unit file, not in engine code)
    for key, it in S["items"].items():
        if not key.startswith("unk:") or it.get("state") not in ("open", "parked"):
            continue
        m = re.search(r"(studio-[\w.-]+?)(?:\.service|$)", it.get("what", ""))
        if m and re.match(r"(unit failed|code error in)", it.get("what", "")) and "#" not in m.group(1):
            res = sh(f"systemctl show {m.group(1)}.service -p Result --value")[1].strip()
            if res == "success":
                it.update(state="gone", why="the unit runs fine again"); note(f"closed: {it['what'][:80]} (the unit runs fine again)")
    # 18 Nov: close every finished / provider-only item first; the fix loop below returns early when the server is busy,
    # so items behind the first one stayed "open" for hours (dashboard showed a 13:54 error at 17:20)
    for key, it in S["items"].items():
        if not key.startswith("unk:") or it.get("state") not in ("open", "parked"):
            continue
        if WAIT.search(it.get("detail", "")) and not re.search(r"Traceback|KeyError|TypeError|AttributeError|NameError", it.get("detail", "")):
            it.update(state="wait", why="free provider hiccup: every caller falls back to the next model")
        elif not still_happening(it["detail"], 180):
            it.update(state="gone", why="stopped by itself"); note(f"closed: {it['what'][:80]} (stopped by itself)")
    # open items: try a code fix (one per run)
    for key, it in S["items"].items():
        if not key.startswith("unk:") or it.get("state") != "open":
            continue
        if it.get("tried_code") == head() or S.get("code_day", {}).get(time.strftime("%Y-%m-%d"), 0) >= 6:
            continue
        if busy() or mem_mb() < 3000:              # wait for a quiet moment; do not burn this code version's try
            return
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
    if S.get("task_day") == day or busy() or mem_mb() < 3000:      # wait for a quiet moment; do not burn today's try
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
        note(f"code fix for {what} waits: only {mem_mb()} MB free"); return {"skipped": True}
    if busy():                                   # 18 Nov: one heavy thing at a time (the checks build a video too)
        return {"skipped": True}
    day = time.strftime("%Y-%m-%d")
    cd = S.setdefault("code_day", {})          # 18 Nov 07:07: S["code_day"] was read before it existed -> KeyError
    cd[day] = cd.get(day, 0) + 1
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
