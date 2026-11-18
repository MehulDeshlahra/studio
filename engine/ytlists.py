"""YouTube playlists per serial / series (MONEY.md: "series formats that bring followers back daily").
Each part of an Aage Suno serial or a Puraan Ki Katha series goes into a playlist named after the story, so a viewer who
finishes part 3 gets part 4 next and watch time per viewer goes up. Called by publish.py after a YouTube upload; any failure
is only logged. Playlist ids are cached in channels/<id>/playlists.json (title -> id)."""
import json, os, re, urllib.parse, urllib.request
from core import ROOT, load, save, log

SERIES_RX = re.compile(r"(.+?) - Part (\d+):")


def _tok(y):
    d = urllib.parse.urlencode({"client_id": y["client_id"], "client_secret": y["client_secret"],
                                "refresh_token": y["refresh_token"], "grant_type": "refresh_token"}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=d), timeout=60))["access_token"]


def _api(tok, path, body=None, method=None):
    r = urllib.request.Request("https://www.googleapis.com/youtube/v3/" + path, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"}, method=method)
    return json.load(urllib.request.urlopen(r, timeout=60))


def story_title(ch, nxt):
    """The serial title or the series title this post belongs to, else None."""
    topic = str(nxt.get("topic") or "")
    try:
        if ch.get("serial"):
            import serials
            s, _n = serials._find(ch, nxt.get("topic"))
            if s:
                return str(s["title"])
    except Exception:
        pass
    m = SERIES_RX.match(topic)
    return m.group(1).strip() if m else None


def add(acc, ch, nxt, vid):
    title = story_title(ch, nxt)
    if not title or not acc.get("yt") or not vid:
        return None
    cid = ch["id"]
    f = os.path.join(ROOT, "channels", cid, "playlists.json")
    ids = load(f, {}) or {}
    tok = _tok(acc["yt"])
    pid = ids.get(title)
    if not pid:
        link = f"https://scrollhouse.in/go/{cid}.html"
        pid = _api(tok, "playlists?part=snippet,status", {"snippet": {"title": title[:150], "description": f"{title}: every part, in order.\n{link}"},
                                                         "status": {"privacyStatus": "public"}})["id"]
        ids[title] = pid
        save(f, ids)
        log("ytlists: new playlist", cid, title, pid)
    _api(tok, "playlistItems?part=snippet", {"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}})
    log("ytlists: added", cid, vid, "to", title)
    return pid
