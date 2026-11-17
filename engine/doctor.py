"""Studio doctor (owner, 17 Nov: "an agent which detects broken things and fixes them; only tell me what needs me").
Runs every 10 min (systemd timer studio-doctor). Each check finds a known break and repairs it by itself; every action
goes to engine.log as "doctor: ..." (the dashboard shows it). Telegram is used ONLY for things the owner must do
himself (logins, money, app settings), at most once a day per item.
Unknown problems are written to ~/studio-out/doctor-unknown.json for the next Kiro session; never pinged.
  python engine/doctor.py [--dry]"""
import glob, json, os, re, shutil, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, HOME, log, load, save, telegram

DRY = "--dry" in sys.argv
STATE = os.path.join(OUT, "doctor-state.json")
UNKNOWN = os.path.join(OUT, "doctor-unknown.json")
st = load(STATE, {}) or {}
did, owner, unknown = [], [], []


def sh(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def fix(what, cmd=None, fn=None):
    """Do a repair (or just say it in --dry). Returns True when it worked."""
    if DRY:
        did.append("[dry] " + what); return True
    ok = True
    if cmd:
        rc, out = sh(cmd); ok = rc == 0
        if not ok:
            what += f" (FAILED: {out[-160:]})"
    if fn:
        try:
            fn()
        except Exception as e:
            ok = False; what += f" (FAILED: {str(e)[:160]})"
    did.append(what); log("doctor:", what)
    return ok


def once_a_day(key):
    day = time.strftime("%Y-%m-%d")
    if st.get("told", {}).get(key) == day:
        return False
    st.setdefault("told", {})[key] = day
    return True


def http_ok(url, t=8):
    try:
        urllib.request.urlopen(url, timeout=t); return True
    except Exception:
        return False


# ---------------------------------------------------------------- checks
def check_failed_units():
    rc, out = sh("systemctl list-units --failed --no-legend --plain 'studio*'")
    for line in out.splitlines():
        u = line.split()[0] if line.split() else ""
        if not u:
            continue
        _, last = sh(f"journalctl -u {u} -n 30 --no-pager -o cat")
        tb = [l for l in last.splitlines() if re.search(r"Error|Exception|Traceback", l)]
        cause = (tb[-1] if tb else last.splitlines()[-1] if last else "")[:200]
        fix(f"cleared failed unit {u} (cause: {cause})", f"sudo systemctl reset-failed {u}")
        if "No module named" in cause or "SyntaxError" in cause or "NameError" in cause:
            unknown.append({"what": f"code error in {u}", "detail": cause})


def check_timers():
    for t in ("studio-inbox", "studio-prep", "studio-make", "studio-scout", "studio-stats", "studio-post", "studio-doctor", "studio-learn", "studio-selfcheck"):
        rc, _ = sh(f"systemctl is-active --quiet {t}.timer")
        if rc != 0 and os.path.exists(f"/etc/systemd/system/{t}.timer"):
            fix(f"timer {t} was stopped, started it again", f"sudo systemctl enable --now {t}.timer")


def check_services():
    if not http_ok("http://127.0.0.1:4788/api/state", 60):
        fix("dashboard was not answering, restarted it", "sudo systemctl restart studio-dash")
    for port, unit in ((20241, "jb-musebridge2"), (20240, "jb-musebridge")):
        if not http_ok(f"http://127.0.0.1:{port}/health"):
            k = f"muse-{port}"
            st[k] = st.get(k, 0) + 1
            if st[k] >= 2:                                        # down on two checks in a row (20 min)
                fix(f"Muse {unit} not answering for 20 min, restarted it", f"sudo systemctl restart {unit}")
                st[k] = 0
        else:
            st[f"muse-{port}"] = 0


def check_stuck_jobs():
    """A make.py whose job folder has not changed for 60 min is hung (e.g. a render that never ends). Kill it; the
    render lane picks the job up again from the last finished stage."""
    rc, out = sh("ps -eo pid,etimes,args | grep '[e]ngine/make.py'")
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(.*)", line)
        if not m:
            continue
        pid, age, args = int(m.group(1)), int(m.group(2)), m.group(3).split()
        if age < 3600:
            continue
        try:
            cid = args[args.index(next(a for a in args if a.endswith("make.py"))) + 1]
            job = args[args.index("--job") + 1] if "--job" in args else None
        except Exception:
            continue
        dirs = [os.path.join(OUT, cid, job)] if job else sorted(glob.glob(os.path.join(OUT, cid, "*")), key=os.path.getmtime)[-1:]
        newest = max((os.path.getmtime(os.path.join(dp, f)) for d in dirs for dp, _, fs in os.walk(d) for f in fs), default=0)
        if newest and time.time() - newest > 3600:
            fix(f"job {cid} {job or os.path.basename(dirs[0])} made no progress for 60 min, stopped it (it restarts from its last step)",
                f"sudo kill -TERM {pid}; sleep 5; sudo pkill -TERM -P {pid} || true")


def check_disk():
    du = shutil.disk_usage("/")
    pct = 100 * du.used / du.total
    if pct < 90 or time.time() - st.get("disk_clean", 0) < 6 * 3600:   # 17 Nov: it cleaned every 10 min for nothing
        return
    st["disk_clean"] = time.time()
    fix(f"disk {pct:.0f}% full: cleaned rebuildable caches",
        "sudo journalctl --vacuum-size=300M; (~/.local/bin/uv cache clean || uv cache clean) >/dev/null 2>&1; "
        "rm -rf ~/.cache/pip; find ~/.npm/_npx -maxdepth 1 -mindepth 1 -mtime +3 -exec rm -rf {} + ; "
        "find ~/studio-out -path '*/render/*' -name '*.mp4' -mtime +3 -delete; find /tmp -maxdepth 1 -mtime +2 -name '*.wav' -delete")
    # renders of finished jobs keep raw.mp4 + mix.wav that can be rebuilt: drop them after 7 days
    for p in glob.glob(os.path.join(OUT, "*", "*", "raw.mp4")):
        if time.time() - os.path.getmtime(p) > 7 * 86400:
            fix(f"removed old intermediate {p.replace(OUT + '/', '')}", fn=lambda p=p: os.remove(p))
    du = shutil.disk_usage("/")
    if 100 * du.used / du.total >= 93 and once_a_day("disk"):
        owner.append(f"Disk is still {100 * du.used / du.total:.0f}% full after cleaning. Nothing urgent tonight; I will free more space next session.")


def check_housekeeping():
    """Once a day: finished videos older than a day keep only the video, cover, plan, timing and assets. The rendered page
    folder (render/) is rebuilt from those when needed (compose)."""
    day = time.strftime("%Y-%m-%d")
    if st.get("housekeeping") == day:
        return
    st["housekeeping"] = day
    freed = 0
    for jd in glob.glob(os.path.join(OUT, "*", "*")):
        cid, job = os.path.basename(os.path.dirname(jd)), os.path.basename(jd)
        fin = os.path.join(jd, f"{cid}-{job}.mp4")
        if not os.path.exists(fin) or time.time() - os.path.getmtime(fin) < 86400:
            continue
        for p in (os.path.join(jd, "render"), os.path.join(jd, "raw.mp4"), os.path.join(jd, "mix-tp.wav")):
            if os.path.exists(p):
                sz = sh(["du", "-sb", p])[1].split()[0] if not DRY else "0"
                freed += int(sz) if sz.isdigit() else 0
                if not DRY:
                    shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
    if freed:
        did.append(f"housekeeping: freed {freed // 1048576} MB of old render files"); log("doctor:", did[-1])


def check_git():
    rc, out = sh(f"git -C {ROOT} status --porcelain=v1 -b")
    if "UU " in out or "AA " in out or "rebase" in sh(f"ls {ROOT}/.git")[1]:
        fix("git was stuck in a merge/rebase, aborted it (local lessons kept in a stash)",
            f"cd {ROOT} && (git rebase --abort || git merge --abort || true) && git stash -q || true")
    rc, out = sh(f"cd {ROOT} && timeout 60 git pull -q --rebase --autostash")
    if rc != 0:
        k = "gitpull"; st[k] = st.get(k, 0) + 1
        if st[k] >= 3:
            unknown.append({"what": "git pull keeps failing on the server", "detail": out[-200:]}); st[k] = 0
    else:
        st["gitpull"] = 0


def check_held():
    """A held video whose problem the engine can repair is rebuilt once: caption timing (re-align with the current
    aligner) or loudness (re-master). Other holds (visual) are noted for the next fix session."""
    busy = sh("systemctl list-units --state=active --no-legend 'studio-job-*.service' 'studio-make.service' 'studio-prep.service'")[1].strip()
    for cid in ("tech", "katha", "raaz"):
        done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
        for d in done:
            if d.get("status") != "held":
                continue
            jd = os.path.join(OUT, cid, d["job"])
            meta = load(os.path.join(jd, "meta.json"), {}) or {}
            probs = " ".join(map(str, d.get("review") or (load(os.path.join(jd, "review.json"), {}) or {}).get("problems", [])))
            head = sh(f"git -C {ROOT} rev-parse --short HEAD")[1].strip()
            tries = meta.get("doctor_tries", 1 if meta.get("doctor_rebuilt") else 0)
            if meta.get("doctor_rebuilt") and (meta.get("doctor_code") == head or tries >= 3):   # retry only after a code fix
                if "visual" in probs:
                    unknown.append({"what": f"held video still failing after rebuild: {cid} {d['job']}", "detail": probs[:200]})
                continue
            if busy:
                return                                             # one build at a time; try next run
            frm = None
            if "spoken instructions" in probs or "does not start with the first line" in probs or "starts late" in probs:
                frm = "voice"                                      # new voice (the instruction cut is fixed in code)
            elif "of the script was found" in probs:
                frm = "compose"
                fix(f"held {cid} {d['job']}: caption timing redone with the new aligner", fn=lambda jd=jd: os.path.exists(os.path.join(jd, "timing.json")) and os.remove(os.path.join(jd, "timing.json")))
            elif "loudness" in probs or "true peak" in probs:
                frm = "mix"
            elif "visual" in probs:
                frm = "compose"                                    # layout fixes land in compose code
            if not frm:
                continue
            meta.update(doctor_rebuilt=time.strftime("%Y-%m-%d %H:%M"), doctor_code=head, doctor_tries=tries + 1)
            save(os.path.join(jd, "meta.json"), meta)
            args = f"/home/ubuntu/studio-venv/bin/python {ROOT}/engine/make.py {cid} --job {d['job']} --from {frm}" + (" --lang en" if d["job"].endswith("-en") else "")
            fix(f"rebuilding held {cid} {d['job']} from {frm}",
                f"sudo systemd-run --unit=studio-job-doc-{int(time.time())} --uid=ubuntu -p CPUWeight=20 -p Nice=15 --working-directory={ROOT} -E HOME={HOME} {args}")
            return                                                 # one rebuild per run


def check_budget_stall():
    """Prep lane says 'reel budget used' or 'voice budget used' every run after midnight -> budget file stuck."""
    b = load(os.path.join(OUT, "budget.json"), {}) or {}
    if len(b) > 7:
        fix("trimmed old days from budget.json", fn=lambda: save(os.path.join(OUT, "budget.json"), dict(sorted(b.items())[-7:])))


def check_owner_items():
    """Only things the owner must do himself."""
    try:
        ut = open(os.path.join(HOME, ".studio-meta-user.token")).read().strip()
        d = json.load(urllib.request.urlopen(f"https://graph.facebook.com/v23.0/debug_token?input_token={ut}&access_token={ut}", timeout=30))["data"]
        if not d.get("is_valid"):
            if once_a_day("meta-invalid"):
                owner.append("Meta login stopped working, so posting is paused. Log in to Meta Business Suite once on your phone.")
        else:
            left = (d.get("data_access_expires_at", 0) - time.time()) / 86400
            if left < 14 and once_a_day("meta-days"):
                owner.append(f"Meta data access ends in {left:.0f} days. Open Meta Business Suite once (any page) to renew it.")
    except Exception:
        pass
    for line in reversed(open(os.path.join(OUT, "engine.log"), encoding="utf-8", errors="ignore").readlines()[-400:]):
        if "Spend cap" in line or "billing" in line.lower() and "403" in line:
            if once_a_day("gemini-cap"):
                owner.append("Gemini says its spend cap or free credit is used up, so new videos are paused. Only you can decide on money.")
            break


def check_repeating_errors():
    """Same error 5+ times in 2 h that no check above knows about -> note it for Kiro (not the owner)."""
    lines = open(os.path.join(OUT, "engine.log"), encoding="utf-8", errors="ignore").readlines()[-1500:]
    cut = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 7200))
    seen = {}
    for l in lines:
        if l[:19] < cut or not re.search(r"\b(fail|failed|error|traceback|exception)\b", l, re.I):
            continue
        if re.search(r"muse (image|video) retry|doctor:|review .* HOLD|qc PROBLEMS", l):
            continue
        k = re.sub(r"\d+", "#", l[20:])[:90]
        seen[k] = seen.get(k, 0) + 1
    for k, n in seen.items():
        if n >= 5:
            unknown.append({"what": f"error repeated {n} times in 2 h", "detail": k})


def main():
    for c in (check_failed_units, check_timers, check_services, check_stuck_jobs, check_disk, check_housekeeping, check_git, check_held,
              check_budget_stall, check_owner_items, check_repeating_errors):
        try:
            c()
        except Exception as e:
            unknown.append({"what": f"doctor check {c.__name__} crashed", "detail": str(e)[:200]})
    if unknown:
        old = load(UNKNOWN, []) or []
        known = {(u["what"], u["detail"]) for u in old}
        new = [dict(u, t=time.strftime("%Y-%m-%d %H:%M")) for u in unknown if (u["what"], u["detail"]) not in known]
        if new and not DRY:
            save(UNKNOWN, (old + new)[-60:]); log("doctor: noted for the next fix session:", "; ".join(u["what"] for u in new)[:300])
    if owner and not DRY:
        telegram("🛠️ Needs you (only you can do this):\n- " + "\n- ".join(owner))
    st["last"] = int(time.time()); st["last_did"] = did[-10:]
    if not DRY:
        save(STATE, st)
    print(json.dumps({"did": did, "owner": owner, "unknown": unknown}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
