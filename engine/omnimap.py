"""OmniRoute map for Studio (owner 18 Nov: "use each and every key fully").
Every day (timer studio-omnimap 04:40) and on demand:
  1. PROBES every candidate model in OmniRoute with one real call: text (JSON in Hinglish, Roman letters) and, for vision
     candidates, a two-colour picture. Records ok / latency / reason in ~/studio-out/omni-probe.json.
  2. REBUILDS Studio's own combos from the results (working models only, best tier first, then fastest):
       studio-text    planning, scripts, repairs (strong models)
       studio-fast    small JSON jobs (classify, tags, short lines)
       studio-vision  frame / sheet checks (models that really read the picture)
       studio-code    the healer's code fixes (strong coding models)
     The job bot's combos (claude-free, agent-free, forms-free) are never touched.
  3. Logs one line per combo; a provider that stopped answering simply drops out until it answers again.
  python engine/omnimap.py [--probe-only] [--dry]"""
import base64, json, os, subprocess, sys, tempfile, threading, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, HOME, log, load, save

URL = "http://127.0.0.1:20128/v1/chat/completions"
PROBE = os.path.join(OUT, "omni-probe.json")
ADMIN = os.path.join(ROOT, "tools", "omni.mjs")
DRY = "--dry" in sys.argv

# (model, tier) tier 4 = best for our Hinglish scripts, 1 = small. ONLY free models: on zai / siliconflow / huggingface a
# paid model answers 402 and OmniRoute then marks the WHOLE connection "credits_exhausted" (free models too, also for the
# job bot). Learned 18 Nov 04:00: a first probe locked all three; heal_connections() below re-tests and re-opens them.
TEXT = [
    ("gemini/gemini-3.8-flash", 4), ("gemini/gemini-3.7-flash", 4), ("gemini/gemini-3.1-pro-preview", 4),
    ("gemini/gemini-3-flash-preview", 3), ("gemini/gemini-3.1-flash-lite", 2),
    ("groq/openai/gpt-oss-120b", 3), ("groq/qwen/qwen3.8-27b", 2), ("groq/openai/gpt-oss-20b", 1), ("groq/compound", 2),
    ("nvidia/nvidia/nemotron-3-ultra-550b-a55b", 3), ("nvidia/google/gemma-4-31b-it", 2),
    ("nvidia/nvidia/nemotron-3.5-lightning-30b-a3b", 1), ("nvidia/poolside/laguna-xs-2.1", 1),
    ("cloudflare-ai/@cf/zai-org/glm-4.7-flash", 2), ("cloudflare-ai/@cf/google/gemma-4-26b-a4b-it", 2),
    ("cloudflare-ai/@cf/meta/llama-3.3-70b-instruct-fp8-fast", 1), ("cloudflare-ai/@cf/qwen/qwen2.5-coder-32b-instruct", 1),
    ("zai/glm-4.7-flash", 2), ("zai/glm-4.5-flash", 2),
    ("siliconflow/Qwen/Qwen3-8B", 1),                   # 18 Nov: Qwen2.5-7B / GLM-4-9B answered 402 there (locks the key)
    ("nara/qwen3.8-27b", 2),
    ("llm7/codestral-latest", 1), ("llm7/default", 1),
    ("huggingface/deepseek-ai/DeepSeek-V3", 2),         # small monthly free credit: low in the chain
    ("pollinations/openai-large", 3), ("pollinations/deepseek", 3), ("pollinations/openai", 2), ("pollinations/mistral-large", 2),
    ("pollinations/kimi", 3), ("pollinations/glm", 2), ("pollinations/gemini", 2), ("pollinations/qwen-coder-large", 2),
    ("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", 3), ("openrouter/google/gemma-4-31b-it:free", 2),
    ("openrouter/baidu/ernie-5.5-flash-preview:free", 1), ("openrouter/inclusionai/ling-3.2-flash:free", 1),
]
VISION = [
    ("gemini/gemini-3.8-flash", 4), ("gemini/gemini-3.7-flash", 4), ("gemini/gemini-3-flash-preview", 3),
    ("gemini/gemini-3.1-flash-lite", 2),
    ("nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b", 3), ("openrouter/nvidia/nemotron-3.5-super-vl:free", 3),
    ("nvidia/google/gemma-4-31b-it", 2), ("openrouter/google/gemma-4-31b-it:free", 2),
    ("cloudflare-ai/@cf/google/gemma-4-26b-a4b-it", 2), ("pollinations/openai", 2), ("pollinations/qwen-vision", 2),
    ("pollinations/gemini", 2),
]
CODE = {"gemini/gemini-3.1-pro-preview", "gemini/gemini-3.8-flash", "gemini/gemini-3.7-flash", "groq/openai/gpt-oss-120b",
        "nvidia/nvidia/nemotron-3-ultra-550b-a55b", "huggingface/deepseek-ai/DeepSeek-V3", "pollinations/kimi",
        "pollinations/deepseek", "pollinations/openai-large", "pollinations/qwen-coder-large", "gemini/gemini-3-flash-preview",
        "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"}


def _key():
    for p in ("~/.omniroute-studio.key", "~/.omniroute-vajra.key"):
        p = os.path.expanduser(p)
        if os.path.exists(p):
            return open(p).read().strip()
    raise RuntimeError("no OmniRoute key")


def _post(model, content, timeout=90, max_tokens=300):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens,
                       "temperature": 0.2}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=timeout))
    out = (d["choices"][0]["message"].get("content") or "").strip()
    import llm
    if llm.QUOTA_TEXT.search(out[:600]):                 # a "top up" text in a 200 reply is a failure, not an answer
        raise RuntimeError("quota message instead of an answer")
    return out


def _image():
    f = os.path.join(tempfile.gettempdir(), "omni-probe.jpg")
    if not os.path.exists(f):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-filter_complex", "color=red:s=160x240[a];color=blue:s=160x240[b];[a][b]hstack",
                        "-frames:v", "1", f], check=True)
    return base64.b64encode(open(f, "rb").read()).decode()


def probe_one(model, kind):
    import llm
    t0 = time.time()
    try:
        if kind == "vision":
            content = [{"type": "text", "text": 'This picture has two halves. Return ONLY JSON {"left": "<colour>", "right": "<colour>"}.'},
                       {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + _image()}}]
            out = _post(model, content, max_tokens=1500)
            j = llm.parse_json(out)
            ok = "red" in str(j.get("left", "")).lower() and "blue" in str(j.get("right", "")).lower()
            why = "" if ok else "wrong answer: " + out[:80]
        else:
            out = _post(model, 'Return ONLY JSON {"line": "<one short Hinglish sentence in Roman letters: aasmaan neela kyun hai>"}',
                        max_tokens=1500)                # thinking models spend tokens before they answer
            j = llm.parse_json(out)
            line = str(j.get("line", ""))
            ok = len(line) > 10 and not any("\u0900" <= ch <= "\u097f" for ch in line)
            why = "" if ok else "bad answer: " + out[:80]
        return {"ok": ok, "secs": round(time.time() - t0, 1), "why": why}
    except urllib.error.HTTPError as e:
        return {"ok": False, "secs": round(time.time() - t0, 1), "why": f"HTTP {e.code} {e.read()[:120].decode('utf-8', 'ignore')}"}
    except Exception as e:
        return {"ok": False, "secs": round(time.time() - t0, 1), "why": str(e)[:120]}


def probe_long(model):
    """18 Nov: the coding agent sends ~30k tokens; some models that pass the tiny probe answer 400 or hang on that.
    One real engine file (~6k tokens) + a question whose answer is in it."""
    import llm
    t0 = time.time()
    try:
        src = open(os.path.join(ROOT, "engine", "compose.py"), encoding="utf-8").read()
        out = _post(model, src + '\n\nIn the code above, what is the value of `endcard` when a handle is set? '
                    'Return ONLY JSON {"endcard": <number>}', timeout=180, max_tokens=1500)
        ok = abs(float(llm.parse_json(out).get("endcard", 0)) - 1.4) < 0.01
        return {"ok": ok, "secs": round(time.time() - t0, 1), "why": "" if ok else "wrong answer: " + out[:60]}
    except urllib.error.HTTPError as e:
        return {"ok": False, "secs": round(time.time() - t0, 1), "why": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "secs": round(time.time() - t0, 1), "why": str(e)[:100]}


def providers_status():
    """[(connection id, provider, name, status)] from OmniRoute's own provider list."""
    r = admin("GET", "/api/providers").get("body") or {}
    conns = r.get("connections", r) if isinstance(r, dict) else r
    return [(c.get("id"), c.get("provider"), c.get("name"), c.get("testStatus") or c.get("test_status")) for c in conns or []]


def heal_connections():
    """A connection stuck in credits_exhausted / error after one bad answer blocks every model on it (also for the job
    bot). Re-test it: OmniRoute re-opens it when the test passes. Returns what was done."""
    did = []
    env = dict(os.environ, PATH=os.path.join(HOME, ".npm-global", "bin") + ":" + os.environ.get("PATH", ""))
    hp = os.path.join(OUT, "omni-heal.json")
    hs = load(hp, {}) or {}
    for cid, prov, name, status in providers_status():
        if status != "credits_exhausted" or prov == "ollama-cloud":
            continue                                    # "unavailable" = OmniRoute's own rate-limit cool-down: leave it alone
        h = hs.get(cid, {})
        if time.time() < h.get("rest_until", 0):
            continue
        if time.time() - h.get("reopened", 0) < 6 * 3600:   # locked again soon after a re-open: the free credit is really
            hs[cid] = dict(h, rest_until=time.time() + 86400)    # out (e.g. Hugging Face monthly credit) -> rest a day
            did.append(f"{name} locked again within 6 h: really out of free credit, left closed for 24 h"); log("omnimap:", did[-1])
            continue
        p = subprocess.run(["omniroute", "-q", "--no-color", "providers", "test", cid], capture_output=True, text=True, env=env, timeout=120)
        ok = "passed" in (p.stdout + p.stderr)
        if ok:
            hs[cid] = {"reopened": time.time()}
        save(hp, hs)
        did.append(f"{name} was {status}: re-test {'passed, open again' if ok else 'failed, stays closed'}")
        log("omnimap:", did[-1])
    save(hp, hs)
    return did


def probe():
    if not DRY:
        heal_connections()                              # a locked connection would make its free models look broken
    old = load(PROBE, {}) or {}
    skip = {k for k, v in (old.get("paid") or {}).items() if time.time() - v < 30 * 86400}     # paid models: never call again
    gone = {k for k, v in (old.get("gone") or {}).items() if time.time() - v < 7 * 86400}      # 404: look again in a week
    jobs = [(m, "text") for m, _ in TEXT] + [(m, "vision") for m, _ in VISION] + [(m, "long") for m in sorted(CODE)]
    jobs = [(m, k) for m, k in jobs if f"{k}:{m}" not in skip | gone]
    res, lock = {}, threading.Lock()
    by_provider = {}
    for m, k in jobs:                                   # one call at a time per provider: never burst a free key
        by_provider.setdefault(m.split("/")[0], []).append((m, k))

    def worker(items):
        for m, k in items:
            r = probe_long(m) if k == "long" else probe_one(m, k)
            with lock:
                res[f"{k}:{m}"] = r
    ths = [threading.Thread(target=worker, args=(v,)) for v in by_provider.values()]
    [t.start() for t in ths]; [t.join() for t in ths]
    hist, paid, gonem = old.get("history", {}), old.get("paid", {}), old.get("gone", {})
    for k, r in res.items():                            # keep the last 7 results per model: one bad day is not a verdict
        if not r["why"].startswith("HTTP 429"):            # busy is not broken: a 429 does not count against a model
            hist[k] = (hist.get(k, []) + [1 if r["ok"] else 0])[-7:]
        if r["why"].startswith("HTTP 402") and "connection(s) credits exhausted" not in r["why"]:
            paid[k] = time.time()
        if r["why"].startswith("HTTP 404") or "no longer avail" in r["why"] or "currently unavailable" in r["why"]:
            gonem[k] = time.time()
    data = {"t": time.strftime("%Y-%m-%d %H:%M"), "results": res, "history": hist, "paid": paid, "gone": gonem,
            "healed": heal_connections() if not DRY else []}
    if not DRY:
        save(PROBE, data)
    ok = [k for k, r in res.items() if r["ok"]]
    log("omnimap: probed", len(res), "models,", len(ok), "answered correctly")
    return data


def rank(data, cands, kind, need_tier=0, only=None):
    out = []
    for m, tier in cands:
        r = data["results"].get(f"{kind}:{m}")
        h = data["history"].get(f"{kind}:{m}", [1])
        rel = sum(h) / len(h)
        cooling = bool(r) and r["why"].startswith("HTTP 429") and rel >= 0.5   # busy today but usually works: keep it, last
        if not r or not (r["ok"] or cooling) or tier < need_tier or (only and m not in only):
            continue
        # 18 Nov: a 429 at probe time only means "busy this minute"; OmniRoute skips a busy model per request anyway,
        # so a usually-working model keeps its place (04:40 run had put every Gemini model last for the whole day)
        out.append((-(tier * 10 + rel * 5) + min(r["secs"], 60) / 6, m))
    return [m for _, m in sorted(out)]


def admin(method, path, body=None):
    args = ["node", ADMIN, method, path] + ([json.dumps(body)] if body is not None else [])
    p = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return json.loads(p.stdout or "{}")


def set_combo(name, models):
    if not models:
        log("omnimap:", name, "has no working model today, kept as it was"); return False
    body = {"name": name, "models": models, "strategy": "priority"}
    if DRY:
        log("omnimap dry:", name, "->", ", ".join(models[:6])); return True
    cur = admin("GET", "/api/combos").get("body") or {}
    combos = cur.get("combos", cur) if isinstance(cur, dict) else cur
    old = next((c for c in combos if c.get("name") == name), None)
    r = admin("PUT", f"/api/combos/{old['id']}", body) if old else admin("POST", "/api/combos", body)
    ok = r.get("status") in (200, 201)
    log("omnimap:", name, "updated" if ok else f"FAILED {r.get('status')} {str(r.get('body'))[:160]}", "->", " > ".join(models[:5]),
        f"(+{max(0, len(models) - 5)} more)")
    return ok


def main():
    data = probe() if "--no-probe" not in sys.argv else load(PROBE)
    if "--probe-only" in sys.argv:
        return data
    text = rank(data, TEXT, "text", need_tier=2)
    fast = sorted([m for m in rank(data, TEXT, "text")], key=lambda m: data["results"][f"text:{m}"]["secs"])[:10]
    set_combo("studio-text", text)
    set_combo("studio-fast", fast)
    set_combo("studio-vision", rank(data, VISION, "vision"))
    # code: only models that read a whole engine file correctly (long probe), strongest first
    set_combo("studio-code", rank(data, [(m, t) for m, t in TEXT if m in CODE], "long") or rank(data, TEXT, "text", only=CODE))
    return data


if __name__ == "__main__":
    d = main()
    for k, r in sorted((d or {}).get("results", {}).items()):
        print(("OK  " if r["ok"] else "--  ") + f"{r['secs']:>5}s {k}  {r['why'][:90]}")
