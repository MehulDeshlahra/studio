"""Daily stats + report (systemd timer studio-stats, 09:00 IST).
1. For every posted video: Instagram Reel insights (views, reach, likes, comments, shares, saves, avg watch time)
   -> done.json "stats", channels/<id>/results.md (table) and knowledge/results.md (all pages).
2. Telegram morning report: per page made / approved / posted, best and worst posts, today's budgets.
The planner reads results.md, so what wins gets made more.
  python engine/stats.py [--no-report]"""
import json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, load, save, log, telegram
import publish

G = "https://graph.facebook.com/v23.0"
METRICS = "views,reach,likes,comments,shares,saved,ig_reels_avg_watch_time"


def insights(media_id, token):
    try:
        d = json.load(urllib.request.urlopen(f"{G}/{media_id}/insights?metric={METRICS}&access_token={token}", timeout=30))
        out = {}
        for m in d.get("data", []):
            v = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
            out[m["name"]] = v
        if "ig_reels_avg_watch_time" in out and out["ig_reels_avg_watch_time"]:
            out["avg_watch_s"] = round(out.pop("ig_reels_avg_watch_time") / 1000, 1)
        return out
    except Exception as e:
        log("stats fail", media_id, str(e)[:150])
        return None


def main():
    report = "--no-report" not in sys.argv
    lines, all_rows = [], []
    for cid in sorted(os.listdir(os.path.join(ROOT, "channels"))):
        ch = load(os.path.join(ROOT, "channels", cid, "channel.json"))
        if not ch:
            continue
        p = os.path.join(ROOT, "channels", cid, "done.json")
        done = load(p, [])
        acc = publish.resolve(load(os.path.expanduser(f"~/.studio-accounts/{cid}.json")))
        rows = []
        for d in done:
            ig = (d.get("posted") or {}).get("ig")
            if ig and acc and acc.get("page_token"):
                s = insights(ig, acc["page_token"])
                if s:
                    d["stats"] = dict(s, at=time.strftime("%Y-%m-%d %H:%M"))
            if d.get("stats"):
                rows.append(d)
        save(p, done)
        rows.sort(key=lambda d: -(d["stats"].get("views") or 0))
        if rows:
            tab = ["| job | title | views | reach | avg watch s | shares | saves | comments | posted |", "|---|---|---|---|---|---|---|---|---|"]
            for d in rows:
                s = d["stats"]
                tab.append(f"| {d['job']} | {d.get('title', '')[:60]} | {s.get('views')} | {s.get('reach')} | {s.get('avg_watch_s')} | "
                           f"{s.get('shares')} | {s.get('saved')} | {s.get('comments')} | {(d.get('posted') or {}).get('at', '')} |")
            open(os.path.join(ROOT, "channels", cid, "results.md"), "w", encoding="utf-8").write(
                f"# {cid} results (updated {time.strftime('%d %b %H:%M')}, best first)\n" + "\n".join(tab) + "\n")
            all_rows += [(cid, d) for d in rows]
        c = {}
        for d in done:
            c[d.get("status")] = c.get(d.get("status"), 0) + 1
        best = f" · best: {rows[0].get('title', '')[:40]} ({rows[0]['stats'].get('views')} views)" if rows else ""
        lines.append(f"{cid} ({ch.get('handle') or 'no handle'}): " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())) + best)
    if all_rows:
        all_rows.sort(key=lambda x: -(x[1]["stats"].get("views") or 0))
        open(os.path.join(ROOT, "knowledge", "results.md"), "w", encoding="utf-8").write(
            "# Results, all pages (best first; the planner reads this)\n| page | title | views | avg watch s | shares | saves |\n|---|---|---|---|---|---|\n"
            + "\n".join(f"| {c} | {d.get('title', '')[:60]} | {d['stats'].get('views')} | {d['stats'].get('avg_watch_s')} | "
                        f"{d['stats'].get('shares')} | {d['stats'].get('saved')} |" for c, d in all_rows) + "\n")
    b = load(os.path.join(OUT, "budget.json"), {}).get(time.strftime("%Y-%m-%d"), {})
    u2 = load(os.path.expanduser("~/musebridge2/usage.json"), {})
    msg = ("☀️ Studio morning report\n" + "\n".join(lines) +
           f"\n\nToday so far: voice {b.get('tts', 0)}, new videos {b.get('reels', 0)}, Muse-2 images {u2.get('image', 0)}/40 clips {u2.get('video', 0)}/15"
           "\nReply to any video: ok / no / feedback. /status any time.")
    log("stats done", len(all_rows), "posted videos")
    if report:
        telegram(msg)
    import subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, "engine", "sync.py")], timeout=300)


if __name__ == "__main__":
    main()
