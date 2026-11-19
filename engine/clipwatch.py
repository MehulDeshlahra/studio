"""Auto-clipper (19 Nov, owner: "maximum money"). For every active source in channels/<cid>/sources.json (a campaign the
owner joined, or a creator who allows clipping): new uploads on its YouTube channels and any listed source videos are
clipped by engine/clipper.py, with that campaign's rules. Runs hourly (timer studio-clipwatch).

Source entry (dashboard "Cut Capsule sources" writes it):
  {"campaign_url": "...", "campaign_id": "...", "channels": ["@handle" | "UC..."], "videos": ["https://youtu.be/..."],
   "rules": ["..."], "caption_add": "...", "no_watermark": false, "clips_per_video": 4, "active": true, "added": "..."}
Limits: one source video per run (the laptop is the renderer), only while the laptop is on; skips when the page already has
`clip.backlog` clips waiting (default 12); a channel's uploads older than 3 days or than the source itself are skipped."""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save, telegram, pages

STATE = os.path.join(OUT, "clipwatch.json")


def _yt(path):
    import rivals
    return rivals._yt_api(path)


def channel_id(h):
    h = str(h).strip()
    m = re.search(r"(UC[\w-]{22})", h)
    if m:
        return m.group(1)
    handle = re.sub(r"^.*/(@[\w.-]+).*$", r"\1", h)
    handle = handle if handle.startswith("@") else "@" + handle.lstrip("@")
    d = _yt(f"channels?part=id&forHandle={handle}")
    return ((d.get("items") or [{}])[0]).get("id")


def uploads(ch_id, n=8):
    d = _yt(f"channels?part=contentDetails&id={ch_id}")
    pl = (((d.get("items") or [{}])[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    if not pl:
        return []
    d = _yt(f"playlistItems?part=contentDetails,snippet&maxResults={n}&playlistId={pl}")
    out = []
    for it in d.get("items") or []:
        vid = (it.get("contentDetails") or {}).get("videoId")
        if vid:
            out.append({"id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "title": (it.get("snippet") or {}).get("title", ""),
                        "at": (it.get("contentDetails") or {}).get("videoPublishedAt") or ""})
    if out:                                            # Shorts and lives are not clipping material: keep videos >= 6 min
        d = _yt("videos?part=contentDetails,snippet&id=" + ",".join(v["id"] for v in out))
        dur = {}
        for it in d.get("items") or []:
            m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", (it.get("contentDetails") or {}).get("duration", ""))
            dur[it["id"]] = sum(int(x or 0) * k for x, k in zip(m.groups(), (3600, 60, 1))) if m else 0
            if (it.get("snippet") or {}).get("liveBroadcastContent") in ("live", "upcoming"):
                dur[it["id"]] = 0
        out = [dict(v, dur=dur.get(v["id"], 0)) for v in out if dur.get(v["id"], 0) >= 360]
    return out


def waiting(cid):
    return sum(1 for d in load(os.path.join(ROOT, "channels", cid, "done.json"), []) or [] if d.get("status") in ("made", "approved"))


def run(only=None):
    import laptop, clipper
    st = load(STATE, {}) or {}
    st.setdefault("done", {})
    for cid in pages():
        ch = load(os.path.join(ROOT, "channels", cid, "channel.json"), {}) or {}
        if ch.get("kind") != "clips" or (only and cid != only):
            continue
        srcs = {k: v for k, v in ((load(os.path.join(ROOT, "channels", cid, "sources.json"), {}) or {}).get("sources") or {}).items()
                if v.get("active", True)}
        if not srcs:
            log("clipwatch:", cid, "no active sources (join a campaign + add it in the dashboard)"); continue
        cap = int((ch.get("clip") or {}).get("backlog", 12))
        if waiting(cid) >= cap:
            log("clipwatch:", cid, f"{waiting(cid)} clips already waiting (cap {cap}), skip"); continue
        if not laptop.available():
            log("clipwatch: the laptop is off, nothing to clip with"); return
        todo = []
        for key, s in srcs.items():
            added = s.get("added_t") or 0
            for v in s.get("videos") or []:
                if f"{cid}:{v}" not in st["done"]:
                    todo.append((0, key, v, s))
                elif "/folders/" in v and time.time() - st["done"][f"{cid}:{v}"] > 12 * 3600:
                    todo.append((1, key, v, s))   # 19 Nov: a Drive folder has many files; each run takes the next unused ones
            for h in s.get("channels") or []:
                try:
                    cidy = s.setdefault("_ids", {}).get(h) or channel_id(h)
                    for v in uploads(cidy):
                        t = time.mktime(time.strptime(v["at"][:19], "%Y-%m-%dT%H:%M:%S")) if v["at"] else 0
                        if f"{cid}:{v['url']}" in st["done"] or time.time() - t > 3 * 86400 or (added and t < added - 86400):
                            continue
                        todo.append((-t, key, v["url"], s))
                except Exception as e:
                    log("clipwatch: channel", h, "failed:", str(e)[:120])
        if not todo:
            log("clipwatch:", cid, "no new source videos"); continue
        todo.sort(key=lambda x: x[0])
        # 19 Nov: one source per run left 4 campaigns waiting 4 hours. Now: one video per campaign, up to 3 per run,
        # within ~70 min, while the backlog has room.
        t0, picked = time.time(), set()
        for _, key, url, s in todo:
            if key in picked or len(picked) >= 3 or time.time() - t0 > 70 * 60 or waiting(cid) >= cap:
                continue
            picked.add(key)
            st["done"][f"{cid}:{url}"] = time.time(); save(STATE, st)
            log("clipwatch:", cid, "clipping", url, "for", key)
            try:
                made = clipper.make(cid, url, int(s.get("clips_per_video") or 4), test=False, campaign=key)
                ok = [j for j, q, p, lay, sc in made if not p]
                log("clipwatch: made", len(made), "clips,", len(ok), "passed checks")
            except Exception as e:
                log("clipwatch: clip run failed", str(e)[:200])
                st["done"].pop(f"{cid}:{url}", None); save(STATE, st)     # try again next hour
                n = st.setdefault("fails", {}).get(url, 0) + 1
                st["fails"][url] = n
                # 19 Nov (owner: "i keep getting error messages in telegram"): ~30 alerts a day, most fixed by the next
                # hourly retry or by a code fix. Tell him once per link, only after 3 failed tries in a row, and only
                # when he can do something; the healer handles code errors
                if n == 3:
                    telegram(f"⚠ Cut Capsule: footage for '{key}' failed 3 times ({str(e)[:160]}). Studio keeps trying "
                             "daily; nothing to do unless the campaign link itself is wrong.")
    save(STATE, st)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
