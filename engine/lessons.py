"""Lessons agent (19 Nov, owner: "you are learning from mistakes right? it should decrease over time; auto think, I
will not be there every time"). Daily 03:45 (after the janitor).

Every check already writes what it found (review/qc -> channels/<id>/lessons-auto.md; pre-render check, numbers check,
reviewer holds and owner feedback -> channels/<id>/done.json). But the planner reads only the newest 2,000 characters of
each log, so a mistake made 20 times last week was forgotten. This agent counts EVERY problem on EVERY page, merges them
into at most 40 short permanent rules (ALWAYS / NEVER ...), most frequent first, and writes knowledge/lessons-learnt.md.
engine/plan.py puts those rules in every script prompt, so a brand-new page starts with all the old pages' lessons.
Existing rules are kept and merged (the list grows wiser, it is not rewritten each night). knowledge/kiro-lessons.md
(what the Kiro sessions learnt the hard way) is an input too.
  python engine/lessons.py [--dry]"""
import collections, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, log, read
from core import pages as _pages

DRY = "--dry" in sys.argv
OUTF = os.path.join(ROOT, "knowledge", "lessons-learnt.md")


def norm(t):
    t = re.sub(r"\b(scene|s)\s*\d+\b", "", str(t), flags=re.I)
    t = re.sub(r"[\d₹,.%]+", "#", t)
    return re.sub(r"\s+", " ", t).strip(" :-|").lower()[:140]


def collect():
    cnt, pages_of, example = collections.Counter(), collections.defaultdict(set), {}
    for cid in _pages():
        lines = []
        auto = read(os.path.join(ROOT, "channels", cid, "lessons-auto.md"))
        lines += [x[2:] for x in auto.splitlines() if x.startswith("- ")]
        for d in load(os.path.join(ROOT, "channels", cid, "done.json"), []) or []:
            if d.get("status") in ("held", "rejected", "removed", "fix") or d.get("feedback"):
                lines += [str(x) for x in (d.get("review") or [])]
                lines += ["OWNER: " + str(x) for x in (d.get("feedback") or [])]
        for x in lines:
            x = x.strip()
            if len(x) < 12:
                continue
            k = norm(x)
            cnt[k] += 1; pages_of[k].add(cid); example.setdefault(k, x[:260])
    return cnt, pages_of, example


ASK = """You keep the RULE BOOK of a faceless Reels studio with several pages ({pages}). Below are the CURRENT rules and
every problem our checks and the owner found, with how often and on which pages.
Merge them into AT MOST 40 short, general, actionable rules that stop these mistakes from happening again on ANY page,
including new pages in new niches. Most frequent / most costly first. Each rule: one line, starts with ALWAYS or NEVER,
concrete (what to do instead), no page names unless the rule only fits one format, end with "(seen N times: pages)".
Keep every current rule that is still right (merge duplicates, update counts); drop nothing that was learnt the hard way.
OWNER problems weigh 5x.
CURRENT RULES:
{current}
PROBLEMS (count | pages | example):
{problems}
Return JSON {{"rules": ["ALWAYS ... (seen N times: tech, katha)", ...]}}"""


def run():
    cnt, pages_of, example = collect()
    if not cnt:
        log("lessons: nothing recorded yet"); return
    rows = []
    for k, n in sorted(cnt.items(), key=lambda kv: -(kv[1] * (5 if example[kv[0]].startswith("OWNER") else 1)))[:180]:
        rows.append(f"{n} | {', '.join(sorted(pages_of[k]))} | {example[k]}")
    current = "\n".join(x for x in read(OUTF).splitlines() if x.startswith("- "))
    kiro = read(os.path.join(ROOT, "knowledge", "kiro-lessons.md"), 4000)
    import plan
    r = plan.ask(ASK.format(pages=", ".join(_pages()), current=(current or "(none yet)") + ("\nFROM KIRO SESSIONS:\n" + kiro if kiro else ""),
                            problems="\n".join(rows)), max_tokens=5000) or {}
    rules = [str(x).strip() for x in (r.get("rules") or []) if str(x).strip().upper().startswith(("ALWAYS", "NEVER"))][:40]
    if len(rules) < 5:
        log("lessons: the model gave too few rules, keeping the old book", len(rules)); return
    txt = ("# Rules learnt from mistakes (engine/lessons.py, daily; every script prompt reads this)\n"
           f"Updated {time.strftime('%Y-%m-%d %H:%M')} from {sum(cnt.values())} recorded problems on {len(_pages())} pages.\n\n"
           + "\n".join("- " + x for x in rules) + "\n")
    log("lessons:", len(rules), "rules from", sum(cnt.values()), "problems")
    if DRY:
        print(txt); return
    open(OUTF + ".new", "w", encoding="utf-8", newline="\n").write(txt); os.replace(OUTF + ".new", OUTF)
    if os.system(f"cd {ROOT} && git add knowledge/lessons-learnt.md >/dev/null 2>&1 && git commit -qm 'lessons: rule book updated' >/dev/null 2>&1") == 0:
        os.system(f"cd {ROOT} && git pull -q --rebase --autostash && git push -q")
    print(txt)


if __name__ == "__main__":
    run()
