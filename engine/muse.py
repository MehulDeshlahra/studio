"""Muse bridges on the server (127.0.0.1:20241 = second account, Studio's own; 20240 = VAJRA's, shared).
Studio uses bridge 2 first; on bridge 1 it takes at most STUDIO_B1_VIDEO videos/day so VAJRA keeps its budget."""
import base64, json, os, shutil, time, urllib.request
from core import log, load

BRIDGES = [{"url": "http://127.0.0.1:20241", "key": "~/musebridge2/key.txt", "usage": "~/musebridge2/usage.json",
            "video_cap": 15, "image_cap": 40},
           {"url": "http://127.0.0.1:20240", "key": "~/musebridge/key.txt", "usage": "~/musebridge/usage.json",
            "video_cap": int(os.environ.get("STUDIO_B1_VIDEO", "2")), "image_cap": int(os.environ.get("STUDIO_B1_IMAGE", "20"))}]
LEDGER = os.path.expanduser("~/studio-out/muse-ledger.json")   # what STUDIO took from each bridge today


def _health(b):
    try:
        return json.load(urllib.request.urlopen(b["url"] + "/health", timeout=10))
    except Exception:
        return None


def _taken(i, kind):
    d = load(LEDGER, {})
    return d.get(time.strftime("%Y-%m-%d"), {}).get(f"{i}:{kind}", 0)


def _note(i, kind):
    d = load(LEDGER, {}); day = time.strftime("%Y-%m-%d")
    d = {day: d.get(day, {})}
    d[day][f"{i}:{kind}"] = d[day].get(f"{i}:{kind}", 0) + 1
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump(d, open(LEDGER, "w"))


def _post(b, path, body, timeout):
    key = open(os.path.expanduser(b["key"])).read().strip()
    req = urllib.request.Request(b["url"] + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def _bridges(kind):
    out = []
    for i, b in enumerate(BRIDGES):
        h = _health(b)
        if not h or not h.get("ok"):
            continue
        u, caps = h.get("usage", {}), h.get("caps", {})
        if u.get(kind, 0) >= caps.get(kind, 0):
            continue
        if _taken(i, kind) >= b[f"{kind}_cap"]:
            continue
        out.append((i, b))
    return out


def image(prompt, dest, tries=3):
    for i, b in _bridges("image"):
        for t in range(tries):
            try:
                f = _post(b, "/v1/images/generations", {"prompt": prompt, "size": "9:16"}, 480)["data"][0]["file"]
                shutil.copy(f, dest); _note(i, "image"); log("muse image", i, os.path.basename(dest))
                return dest
            except Exception as e:
                # 17 Nov: 502s came from a cold browser (bridge stops it after 20 idle min; first clicks time out
                # on a busy server). Wait longer and retry before calling it a failure.
                last = t == tries - 1
                log("muse image " + ("fail" if last else "retry"), i, str(e)[:120]); time.sleep(0 if last else 30 if "502" in str(e) else 10)
    return None


BREAKER = os.path.expanduser("~/studio-out/muse-breaker.json")


def _broken(i, kind):
    """18 Nov: bridge 0 answered 502 for every video while each try waited minutes, so one clip scene held the prep lane
    for 30+ min. Two failures in 30 min -> skip that bridge for this kind for an hour (the scene becomes a still)."""
    d = load(BREAKER, {}) or {}
    fails = [t for t in d.get(f"{i}:{kind}", []) if time.time() - t < 1800]
    return len(fails) >= 2 and time.time() - fails[-1] < 3600


def _fail(i, kind):
    d = load(BREAKER, {}) or {}
    k = f"{i}:{kind}"
    d[k] = [t for t in d.get(k, []) if time.time() - t < 3600] + [time.time()]
    json.dump(d, open(BREAKER, "w"))


def video(prompt, start_image, dest, tries=3):
    body = {"prompt": prompt, "size": "9:16"}
    if start_image:
        body["image_b64"] = base64.b64encode(open(start_image, "rb").read()).decode()
    for i, b in _bridges("video"):
        if _broken(i, "video"):
            log("muse video: bridge", i, "failed twice in 30 min, skipped for an hour"); continue
        for t in range(tries):
            try:
                f = _post(b, "/v1/videos", body, 700)["file"]
                shutil.copy(f, dest); _note(i, "video"); log("muse video", i, os.path.basename(dest))
                return dest
            except Exception as e:
                last = t == tries - 1
                _fail(i, "video")
                log("muse video " + ("fail" if last else "retry"), i, str(e)[:120])
                if _broken(i, "video"):
                    break
                time.sleep(0 if last else 30 if "502" in str(e) else 15)
    return None


CF_ACCOUNT = "3d44fbd85f54ea694dd4f73153843dd3"


def cloudflare(prompt, dest):
    """Cloudflare Workers AI FLUX.1 schnell (free daily quota ~170 images; token ~/videngine/cf.token). Text to image."""
    try:
        tok = open(os.path.expanduser("~/videngine/cf.token")).read().strip()
        body = json.dumps({"prompt": prompt + ", vertical 9:16 portrait composition", "steps": 6}).encode()
        req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/@cf/black-forest-labs/flux-1-schnell",
                                     data=body, headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=150))
        open(dest, "wb").write(base64.b64decode(r["result"]["image"]))
        log("cloudflare image", os.path.basename(dest))
        return dest
    except Exception as e:
        log("cloudflare fail", str(e)[:120])
        return None


# 18 Nov: z-image dropped after one real katha frame drew Kartikeya as a woman in revealing clothes on a split panel
OMNI_IMAGE = ["nvidia/black-forest-labs/flux.1-dev", "nvidia/black-forest-labs/flux.2-klein-4b", "nvidia/black-forest-labs/flux.1-schnell"]


def omni_image(prompt, dest):
    """18 Nov: free FLUX.1-dev (NVIDIA key) and z-image (Pollinations) through OmniRoute, 768x1344, ~10 s; checked on real
    frames (clean, no artefacts). Second picture source after Muse, before Cloudflare schnell."""
    import llm
    for m in OMNI_IMAGE:
        try:
            body = json.dumps({"model": m, "prompt": prompt, "size": "768x1344", "n": 1}).encode()
            req = urllib.request.Request("http://127.0.0.1:20128/v1/images/generations", data=body,
                                         headers={"Authorization": "Bearer " + llm._key(), "Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=240))["data"][0]
            raw = base64.b64decode(d["b64_json"]) if d.get("b64_json") else urllib.request.urlopen(d["url"], timeout=90).read()
            if len(raw) < 20000:
                raise RuntimeError("tiny image")
            open(dest, "wb").write(raw); log("omniroute image", m, os.path.basename(dest))
            return dest
        except Exception as e:
            log("omniroute image fail", m, str(e)[:120])
    return None


def pollinations(prompt, dest):
    """Free backup still. 20 Nov: OmniRoute's Pollinations connection lost its key (401); the owner's 4 keys go direct
    (FLUX.2 klein 4B, engine/picsmith.poll_klein), OmniRoute only if that fails."""
    import llm
    try:
        import picsmith
        if picsmith.poll_klein(prompt, [], dest):
            return dest
    except Exception as e:
        log("pollinations direct fail", str(e)[:120])
    try:
        body = json.dumps({"model": "pollinations/flux", "prompt": prompt, "size": "1080x1920", "n": 1}).encode()
        req = urllib.request.Request("http://127.0.0.1:20128/v1/images/generations", data=body,
                                     headers={"Authorization": "Bearer " + llm._key(), "Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=240))["data"][0]
        raw = base64.b64decode(d["b64_json"]) if d.get("b64_json") else urllib.request.urlopen(d["url"], timeout=90).read()
        open(dest, "wb").write(raw); log("pollinations image", os.path.basename(dest))
        return dest
    except Exception as e:
        log("pollinations fail", str(e)[:120])
        return None
