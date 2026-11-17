"""Sunday weekly report: ONE Telegram message (owner 17 Nov): what was posted, what worked, what the engine changed by itself,
and what needs the owner. Numbers come from done.json (stats.py fills views / avg watch), engine.log, selfcheck.json,
brain.jsonl and the dashboard's own needs-you list. No LLM: plain facts, so it never makes things up.
  python engine/weekly.py [--print]      (timer studio-weekly, Sunday 20:00)"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, telegram

WEEK = 7 * 86400


def _lines(since):
    try:
        for ln in open(os.path.join(OUT, "engine.log"), encoding="utf-8", errors="ignore"):
            if ln[:10] >= since:
                yield ln.rstrip("\n")
    except Exception:
        return


def build():
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - WEEK))
    lines = list(_lines(since))
    out = [f"📊 Studio weekly report ({since} to {time.strftime('%Y-%m-%d')})", ""]
    # ---- posted + what worked
    tot_posted = 0
    for cid in sorted(c for c in os.listdir(os.path.join(ROOT, "channels")) if os.path.isdir(os.path.join(ROOT, "channels", c))):
        done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
        name = (load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}).get("name", cid)
        posted = [d for d in done if (d.get("posted") or {}).get("at", "")[:10] >= since and d.get("status") == "posted"]
        tot_posted += len(posted)
        statuses = {}
        for d in done:
            statuses[d.get("status", "?")] = statuses.get(d.get("status", "?"), 0) + 1
        out.append(f"{name}: posted {len(posted)} | made total {len(done)} ({', '.join(f'{v} {k}' for k, v in sorted(statuses.items()))})")
        rows = []
        for d in posted:
            st = d.get("stats") or {}
            rows.append((st.get("views") or 0, d.get("title") or d.get("topic"), st.get("avg_watch_s"), d["job"]))
        for v, t, aw, j in sorted(rows, reverse=True)[:3]:
            out.append(f"   {v:,} views, avg watch {aw if aw is not None else '-'} s: {str(t)[:60]}")
    if not tot_posted:
        out.append("(Nothing was posted this week: posting starts 20 Nov, 1/day until 27 Nov, then the normal slots.)")
    # ---- first-pass rate this week
    rv = [ln for ln in lines if re.search(r" review \w+ [\w-]+ (HOLD|PASS|OK)", ln)]
    ok = sum(1 for ln in rv if re.search(r" review \w+ [\w-]+ (PASS|OK)\b", ln))
    out += ["", f"Quality gate: {ok} of {len(rv)} reviews passed first time" + (f" ({100 * ok // len(rv)}%)" if rv else "")]
    holds = {}
    for ln in rv:
        m = re.search(r"HOLD: (.{0,70})", ln)
        if m:
            k = re.sub(r"\d+", "N", m.group(1)); holds[k] = holds.get(k, 0) + 1
    for k, v in sorted(holds.items(), key=lambda x: -x[1])[:3]:
        out.append(f"   top hold reason ({v}x): {k}")
    # ---- what the engine changed by itself
    out += ["", "What the engine changed by itself:"]
    sc = (load(os.path.join(OUT, "selfcheck.json"), {}) or {}).get("fixes", [])
    wk = [f for f in sc if f.get("day", "") >= since]
    out.append(f"   code self-fixes: {len(wk)}" + ("".join(f"\n      - {f['file']}: {f['why'][:80]}" + ("" if f.get("verified") in (True, None) else " (unverified)") for f in wk[:4])))
    docs = [ln for ln in lines if " doctor: " in ln]
    out.append(f"   doctor repairs: {len(docs)} (disk cleanups {sum('disk' in d for d in docs)}, rebuilt held videos {sum('rebuilding' in d for d in docs)}, restarts {sum('started it again' in d or 'restarted' in d for d in docs)})")
    br = [json.loads(ln) for ln in open(os.path.join(ROOT, "knowledge", "brain.jsonl"), encoding="utf-8") if ln.strip()] if os.path.exists(os.path.join(ROOT, "knowledge", "brain.jsonl")) else []
    out.append(f"   brain: {len(br)} items, {sum(1 for b in br if b.get('added', '')[:10] >= since)} new this week, {sum(1 for b in br if b.get('on') is False)} retired")
    out.append(f"   topics picked by trend/score: {sum(' ideas ' in ln and 'picked' in ln for ln in lines)}; hook rules refreshed: {sum('hookstudy' in ln and 'rules:' in ln for ln in lines)}; new music tracks: {sum('musiclib ' in ln and ' fail' not in ln for ln in lines)}")
    rep = sum(1 for ln in lines if "comments reply" in ln)
    out.append(f"   comment replies sent: {rep}; first-comment questions: {sum('comments first comment' in ln for ln in lines)}")
    kj = load(os.path.join(OUT, "gemini-keys.json"), {}) or {}
    calls = sum(v.get("ok", 0) for v in (kj.get("keys") or {}).values())
    out.append(f"   Gemini keys: today {calls} calls, out of quota today: {sum(1 for v in (kj.get('keys') or {}).values() if v.get('out'))} of {len(kj.get('keys') or {})}")
    # ---- needs the owner
    needs = []
    for cid in ("tech", "katha", "raaz"):
        acc = load(os.path.expanduser(f"~/.studio-accounts/{cid}.json"), {}) or {}
        if not acc.get("yt"):
            needs.append(f"YouTube login for {cid}: on the laptop run  python tools/yt_login.py {cid}  (20 s)")
    unk = load(os.path.join(OUT, "doctor-unknown.json"), {}) or {}
    for k, v in list(unk.items())[:3]:
        needs.append("doctor could not fix: " + str(v.get("what", k))[:90] if isinstance(v, dict) else "doctor could not fix: " + str(k)[:90])
    held = [(cid, d["job"]) for cid in ("tech", "katha", "raaz") for d in (load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []) if d.get("status") == "held"]
    if held:
        needs.append(f"{len(held)} held video(s) the doctor could not rebuild: " + ", ".join(f"{c}/{j}" for c, j in held[:4]))
    out += ["", "Needs you:" if needs else "Needs you: nothing."] + [f"   - {n}" for n in needs]
    return "\n".join(out)[:3900]


if __name__ == "__main__":
    msg = build()
    print(msg)
    if "--print" not in sys.argv:
        telegram(msg); log("weekly report sent")
