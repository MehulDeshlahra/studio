"""The "acts like Mehul" agent (owner 17 Nov: "I won't be there always to make the system better, so add an agent which
acts like me and does the changes I would like").
Every day (timer studio-mehul, 22:30 IST) it does what Mehul does when he looks at the system:
  1. WATCHES the day's finished videos the way he does: a contact sheet of every video (12 frames), judged against
     knowledge/mehul.md (his taste, his dislikes, page rules) + the page's own rules.
  2. READS the numbers: review holds and their reasons, stats (views / watch time) once posts exist, doctor notes.
  3. DECIDES like him and ACTS inside safe limits:
       - adds a rule to channels/<page>/lessons.md (the planner obeys it on the next video)        [auto]
       - changes a page knob in channel.json from a fixed allow-list (backlog, posts_per_day,
         serial.parts, length_s, music mood bias, series/genre lists)                               [auto, logged]
       - sends a held video back for a rebuild with a note                                          [auto]
       - writes a code task to knowledge/build-queue.md (tag [mehul]); engine/healer.py works on it  [auto]
     It never: spends money, signs up, deletes posted content, changes keys/accounts, posts on its own,
     edits engine code (that stays with selfcheck + Kiro), or turns posting on/off.
  4. LEARNS: every action is saved in knowledge/mehul-log.json; when Mehul gives new feedback in Telegram
     ("mehul: ..." / "rule: ..."), the inbox adds it to knowledge/mehul.md, and the agent re-reads that file every run.
  5. REPORTS in one short Telegram message only when it changed something (what + why).
  python engine/mehul.py [--dry]"""
import base64, json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log, read, sh, telegram

LOG = os.path.join(ROOT, "knowledge", "mehul-log.json")
DRY = "--dry" in sys.argv
KNOBS = {"schedule.backlog": (3, 15), "schedule.posts_per_day": (1, 3), "serial.parts": (5, 12),
         "edit.length_s.0": (20, 45), "edit.length_s.1": (35, 70)}
MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]

ASK = """You are Mehul, the owner of three faceless Shorts pages. You are reviewing today's work of your automatic studio.
HOW YOU THINK (your own words and rules):
{profile}
PAGE "{page}" RULES (already in force):
{rules}
TODAY'S DATA:
{data}
The image shows today's finished videos for this page, one row each (12 frames per video, time left to right), labelled.
Look at them as you would on your phone. Then decide what YOU would change so tomorrow's videos are better.
Only things that matter to a viewer or to growth; do not repeat a rule that already exists; at most 4 actions.
Allowed actions:
  {{"do": "rule", "text": "one clear rule for the planner/editor of this page (imperative, testable)"}}
  {{"do": "knob", "key": "<one of {knobs}>", "value": <number>, "why": "..."}}
  {{"do": "rebuild", "job": "<job id of a held video>", "note": "what to fix"}}
  {{"do": "task", "text": "a code change only a developer can do (be specific: file/feature + expected result)"}}
Return JSON {{"verdict": "one honest sentence on today's quality", "score": 1-10, "actions": [...]}}"""


def _gem(parts):
    import tts, llm, urllib.request
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3, "maxOutputTokens": 2500}}
    for m in tts.usable(MODELS):
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", data=json.dumps(body).encode(),
                                       headers={"Content-Type": "application/json", "x-goog-api-key": tts._key(m)})
            d = json.load(urllib.request.urlopen(r, timeout=240))
            return llm.parse_json("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
        except Exception as e:
            log("mehul agent gemini fail", m, str(e)[:100])
    try:                                                   # 18 Nov: our Gemini keys out -> same question through OmniRoute
        return llm.from_parts(parts, max_tokens=2500)
    except Exception as e:
        log("mehul agent omniroute fail", str(e)[:120])
    return None


def _sheet(cid, jobs, out):
    rows = []
    for k, j in enumerate(jobs):
        mp4 = os.path.join(OUT, cid, j, f"{cid}-{j}.mp4")
        if not os.path.exists(mp4):
            continue
        try:
            d = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).strip())
            r = out + f".{k}.jpg"
            sh(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vf", f"fps=12/{d:.2f},scale=120:214,tile=12x1,"   # 18 Nov: NOT keyframes only (they sit on scene cuts: half-black frames)   # 18 Nov: 213 (odd) crashed vstack (malloc corrupted, ffmpeg 6.1.1 arm64)
                "drawtext=text='" + j.replace("'", "") + "':x=6:y=6:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.7", "-frames:v", "1", "-threads", "1", r], timeout=420)
            rows.append(r)
        except Exception as e:                            # 18 Nov: the log kept only the command (first 80 chars), never the reason
            log("mehul agent sheet fail", j, str(e)[-200:].replace("\n", " "))
    if not rows:
        return None
    ins = sum([["-i", r] for r in rows], [])
    sh(["ffmpeg", "-v", "error", "-y"] + ins + ["-filter_complex", "".join(f"[{i}:v]" for i in range(len(rows))) + (f"vstack={len(rows)}" if len(rows) > 1 else "null"), out], timeout=120)
    for r in rows:
        os.remove(r)
    return out


def _data(cid, done, since):
    lines = []
    for d in done:
        if d["job"].endswith("-en"):                    # 18 Nov: old English editions are history (English is off and
            continue                                    # never posted: no handle_en); it kept "finding" them as a violation
        st = d.get("stats") or {}
        lines.append(f"- {d['job']} [{d.get('status')}] {str(d.get('title') or d.get('topic'))[:70]}"
                     + (f" | views {st.get('views')} avg watch {st.get('avg_watch_s')} s" if st else "")
                     + (f" | held for: {'; '.join(d.get('review') or [])[:220]}" if d.get("status") == "held" else ""))
    holds = []
    try:
        for ln in open(os.path.join(OUT, "engine.log"), encoding="utf-8", errors="ignore"):
            if ln[:10] >= since and f" review {cid} " in ln and "HOLD" in ln:
                holds.append(re.sub(r"\d+", "N", ln.split("HOLD:", 1)[1])[:120].strip())
    except Exception:
        pass
    c = {}
    for h in holds:
        c[h] = c.get(h, 0) + 1
    top = sorted(c.items(), key=lambda x: -x[1])[:5]
    lines.append("(English editions are switched off on every page and are never posted; old -en jobs are history.)")
    return "\n".join(lines[-14:]) + ("\nMost common hold reasons this week:\n" + "\n".join(f"  {n}x {h}" for h, n in top) if top else "")


def _set_knob(cid, key, value):
    p = os.path.join(ROOT, "channels", cid, "channel.json")
    ch = load(p, {})
    lo, hi = KNOBS[key]
    v = max(lo, min(hi, int(round(float(value)))))
    parts = key.split(".")
    cur = ch
    for k in parts[:-1]:
        cur = cur.setdefault(k, {}) if not k.isdigit() else cur[int(k)]
    last = parts[-1]
    if last.isdigit():
        old = cur[int(last)]; cur[int(last)] = v
    else:
        old = cur.get(last); cur[last] = v
    if old == v:
        return None
    if not DRY:
        save(p, ch)
    return f"{key}: {old} -> {v}"


def _mem_ok(need_mb=2500):
    """18 Nov: a hand-started agent run on a nearly full server froze it (reboot needed). Never start below need_mb free."""
    try:
        return int(next(l for l in open("/proc/meminfo") if l.startswith("MemAvailable")).split()[1]) // 1024 >= need_mb
    except Exception:
        return True


def run():
    if not _mem_ok():
        log("mehul agent: not enough free memory, skipped today (will run tomorrow)"); return []
    profile = read(os.path.join(ROOT, "knowledge", "mehul.md"), 6000)
    hist = load(LOG, []) or []
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))
    report = []
    for cid in sorted(c for c in os.listdir(os.path.join(ROOT, "channels")) if os.path.isdir(os.path.join(ROOT, "channels", c))):
        ch = load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}
        if ch.get("status") not in ("pilot", "active", "live (warm-up)", "live"):
            continue
        try:                                       # where viewers leave (needs posted videos with stats)
            import extras
            extras.scene_dropoff(cid)
        except Exception as e:
            log("dropoff skipped", str(e)[:80])
        done = load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []
        recent = [d["job"] for d in done if not d["job"].endswith("-en") and os.path.exists(os.path.join(OUT, cid, d["job"], f"{cid}-{d['job']}.mp4"))][-5:]
        if not recent:
            continue
        try:
            sheet = _sheet(cid, recent[-4:], os.path.join(OUT, f"mehul-{cid}.jpg"))
        except Exception as e:                      # low memory on the shared server: judge from the numbers only
            log("mehul agent: no contact sheet for", cid, str(e)[:80]); sheet = None
        rules = (read(os.path.join(ROOT, "channels", cid, "lessons.md"), 3000) + "\n" + "\n".join("- " + r for r in ch.get("rules", [])))[-3500:]
        parts = [{"text": ASK.format(profile=profile, page=f"{ch.get('name', cid)} ({cid})", rules=rules, data=_data(cid, done, since),
                                     knobs=", ".join(KNOBS))}]
        if sheet:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(sheet, "rb").read()).decode()}})
        r = _gem(parts) or {}
        did = []
        for a in (r.get("actions") or [])[:4]:
            if not isinstance(a, dict):
                continue
            try:
                if a.get("do") == "rule" and a.get("text"):
                    t = a["text"].strip().replace("\n", " ")[:300]
                    lp = os.path.join(ROOT, "channels", cid, "lessons.md")
                    cur = read(lp)
                    if t[:40].lower() in cur.lower():
                        continue
                    if not DRY:
                        with open(lp, "a", encoding="utf-8", newline="\n") as f:
                            if "## Mehul agent" not in cur:
                                f.write("\n## Mehul agent (rules added automatically, acting for the owner)\n")
                            f.write(f"- {time.strftime('%d %b')}: {t}\n")
                    did.append("rule: " + t)
                elif a.get("do") == "knob" and a.get("key") in KNOBS:
                    ch_ = _set_knob(cid, a["key"], a.get("value"))
                    if ch_:
                        did.append(f"setting {ch_} ({str(a.get('why', ''))[:80]})")
                elif a.get("do") == "rebuild" and a.get("job"):
                    row = next((d for d in done if d["job"] == a["job"] and d.get("status") == "held"), None)
                    if row and not row.get("mehul_rebuilt"):
                        row["mehul_rebuilt"] = time.strftime("%Y-%m-%d"); row.setdefault("review", []).insert(0, "owner agent: " + str(a.get("note", ""))[:200])
                        # 18 Nov: it started its own build next to the healer's (3 Studio builds at once, 1.9 GB free).
                        # Now it only asks; engine/healer.py runs the new plan when nothing else is building.
                        row["replan_requested"] = time.strftime("%Y-%m-%d %H:%M")
                        if not DRY:
                            save(os.path.join(ROOT, "channels", cid, "done.json"), done)
                        did.append(f"asked the healer to re-plan {a['job']}: {str(a.get('note', ''))[:80]}")
                elif a.get("do") == "task" and a.get("text"):
                    bq = os.path.join(ROOT, "knowledge", "build-queue.md")
                    t = a["text"].strip().replace("\n", " ")[:300]
                    if t[:40].lower() not in read(bq).lower():
                        if not DRY:
                            with open(bq, "a", encoding="utf-8", newline="\n") as f:
                                f.write(f"- [ ] [mehul] {time.strftime('%d %b')} {cid}: {t}\n")
                        did.append("code task (the healer works on it): " + t)
            except Exception as e:
                log("mehul agent action failed", cid, str(e)[:120])
        hist.append({"t": time.strftime("%Y-%m-%d %H:%M"), "page": cid, "score": r.get("score"), "verdict": r.get("verdict"), "did": did, "dry": DRY})
        log("mehul agent", cid, "score", r.get("score"), "|", str(r.get("verdict"))[:120], "|", len(did), "actions")
        if did:
            report.append(f"{ch.get('name', cid)} ({r.get('score')}/10): {r.get('verdict', '')}\n" + "\n".join("  - " + x for x in did))
    save(LOG, hist[-300:])
    if report and not DRY:
        try:
            subprocess.run(["git", "-C", ROOT, "add", "channels", "knowledge"], timeout=60)
            subprocess.run(["git", "-C", ROOT, "commit", "-qm", "mehul agent: daily changes"], timeout=60)
            subprocess.run(["git", "-C", ROOT, "pull", "-q", "--rebase", "--autostash"], timeout=120)
            subprocess.run(["git", "-C", ROOT, "push", "-q"], timeout=120)
        except Exception as e:
            log("mehul agent git failed", str(e)[:100])
        telegram("🧑‍💼 Mehul-agent (acting for you) changed today:\n\n" + "\n\n".join(report)[:3500])
    return report


if __name__ == "__main__":
    for x in run() or ["(nothing to change)"]:
        print(x)
