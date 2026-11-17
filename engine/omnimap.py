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

# (model, tier) tier 3 = strongest. Only free tiers / free keys the owner added.
TEXT = [
    ("gemini/gemini-3.8-flash", 3), ("gemini/gemini-3.1-pro-preview", 3), ("gemini/gemini-2.5-pro", 3),
    ("gemini/gemini-3.7-flash", 3), ("gemini/gemini-2.5-flash", 2), ("gemini/gemini-3-flash-preview", 2),
    ("gemini/gemini-3.1-flash-lite", 1), ("gemini/gemini-2.5-flash-lite", 1),
    ("zai/glm-5.3", 3), ("zai/glm-5.1", 3), ("zai/glm-5-turbo", 2), ("zai/glm-5.3-flash", 2), ("zai/glm-4.7-flash", 1),
    ("groq/openai/gpt-oss-120b", 3), ("groq/qwen/qwen3.8-27b", 2), ("groq/openai/gpt-oss-20b", 1), ("groq/qwen/qwen3.6-27b", 2),
    ("cloudflare-ai/@cf/moonshotai/kimi-k2.6", 3), ("cloudflare-ai/@cf/zai-org/glm-4.7-flash", 1),
    ("cloudflare-ai/@cf/google/gemma-4-26b-a4b-it", 1), ("cloudflare-ai/@cf/meta/llama-3.3-70b-instruct-fp8-fast", 1),
    ("siliconflow/deepseek-ai/DeepSeek-V3.2", 3), ("siliconflow/moonshotai/Kimi-K2.6", 3), ("siliconflow/zai-org/GLM-5.1", 3),
    ("siliconflow/Qwen/Qwen3.5-397B-A17B", 3), ("siliconflow/openai/gpt-oss-120b", 3), ("siliconflow/Qwen/Qwen3-8B", 1),
    ("siliconflow/THUDM/GLM-4-9B-0414", 1), ("siliconflow/Qwen/Qwen3.5-9B", 1),
    ("nvidia/nvidia/nemotron-3-ultra-550b-a55b", 3), ("nvidia/google/gemma-4-31b-it", 2),
    ("nvidia/nvidia/nemotron-3.5-lightning-30b-a3b", 1),
    ("nara/mistral-large", 3), ("nara/minimax-m3-free", 2), ("nara/qwen3.8-27b", 2), ("nara/stepfun-3.7-flash", 1),
    ("llm7/gpt-4.1-nano-2025-04-14", 1), ("llm7/deepseek-r1-0528", 2),
    ("huggingface/deepseek-ai/DeepSeek-V3", 3), ("huggingface/Qwen/Qwen2.5-7B-Instruct", 1),
    ("pollinations/openai-large", 3), ("pollinations/openai", 2), ("pollinations/deepseek", 3), ("pollinations/kimi", 3),
    ("pollinations/glm", 2), ("pollinations/mistral-large", 2), ("pollinations/gemini", 2),
    ("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", 3), ("openrouter/google/gemma-4-31b-it:free", 2),
    ("openrouter/baidu/ernie-5.5-flash-preview:free", 1), ("openrouter/inclusionai/ling-3.2-flash:free", 1),
]
VISION = [
    ("gemini/gemini-3.8-flash", 3), ("gemini/gemini-2.5-pro", 3), ("gemini/gemini-3.7-flash", 3), ("gemini/gemini-2.5-flash", 2),
    ("gemini/gemini-3-flash-preview", 2), ("gemini/gemini-3.1-flash-lite", 1),
    ("nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b", 3), ("openrouter/nvidia/nemotron-3.5-super-vl:free", 3),
    ("nvidia/google/gemma-4-31b-it", 2), ("openrouter/google/gemma-4-31b-it:free", 2),
    ("cloudflare-ai/@cf/google/gemma-4-26b-a4b-it", 1), ("siliconflow/zai-org/GLM-4.6V", 2),
    ("siliconflow/Qwen/Qwen2.5-VL-7B-Instruct", 1), ("pollinations/qwen-vision", 2), ("pollinations/openai", 2),
    ("pollinations/gemini", 2), ("huggingface/meta-llama/llama-3.2-11b-instruct", 1),
]
CODE = {"gemini/gemini-3.1-pro-preview", "gemini/gemini-2.5-pro", "gemini/gemini-3.8-flash", "zai/glm-5.3", "zai/glm-5.1",
        "cloudflare-ai/@cf/moonshotai/kimi-k2.6", "siliconflow/moonshotai/Kimi-K2.6", "siliconflow/deepseek-ai/DeepSeek-V3.2",
        "siliconflow/zai-org/GLM-5.1", "siliconflow/Qwen/Qwen3.5-397B-A17B", "groq/openai/gpt-oss-120b",
        "nvidia/nvidia/nemotron-3-ultra-550b-a55b", "huggingface/deepseek-ai/DeepSeek-V3", "pollinations/kimi",
        "pollinations/deepseek", "pollinations/openai-large", "nara/mistral-large", "gemini/gemini-3.7-flash"}


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
    return (d["choices"][0]["message"].get("content") or "").strip()


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
            out = _post(model, content)
            j = llm.parse_json(out)
            ok = "red" in str(j.get("left", "")).lower() and "blue" in str(j.get("right", "")).lower()
            why = "" if ok else "wrong answer: " + out[:80]
        else:
            out = _post(model, 'Return ONLY JSON {"line": "<one short Hinglish sentence in Roman letters: aasmaan neela kyun hai>"}',
                        max_tokens=400)
            j = llm.parse_json(out)
            line = str(j.get("line", ""))
            ok = len(line) > 10 and not any("\u0900" <= ch <= "\u097f" for ch in line)
            why = "" if ok else "bad answer: " + out[:80]
        return {"ok": ok, "secs": round(time.time() - t0, 1), "why": why}
    except urllib.error.HTTPError as e:
        return {"ok": False, "secs": round(time.time() - t0, 1), "why": f"HTTP {e.code} {e.read()[:120].decode('utf-8', 'ignore')}"}
    except Exception as e:
        return {"ok": False, "secs": round(time.time() - t0, 1), "why": str(e)[:120]}


def probe():
    jobs = [(m, "text") for m, _ in TEXT] + [(m, "vision") for m, _ in VISION]
    res, lock = {}, threading.Lock()
    by_provider = {}
    for m, k in jobs:                                   # one call at a time per provider: never burst a free key
        by_provider.setdefault(m.split("/")[0], []).append((m, k))

    def worker(items):
        for m, k in items:
            r = probe_one(m, k)
            with lock:
                res[f"{k}:{m}"] = r
    ths = [threading.Thread(target=worker, args=(v,)) for v in by_provider.values()]
    [t.start() for t in ths]; [t.join() for t in ths]
    old = load(PROBE, {}) or {}
    hist = old.get("history", {})
    for k, r in res.items():                            # keep the last 7 results per model: one bad day is not a verdict
        hist[k] = (hist.get(k, []) + [1 if r["ok"] else 0])[-7:]
    data = {"t": time.strftime("%Y-%m-%d %H:%M"), "results": res, "history": hist}
    if not DRY:
        save(PROBE, data)
    ok = [k for k, r in res.items() if r["ok"]]
    log("omnimap: probed", len(res), "models,", len(ok), "answered correctly")
    return data


def rank(data, cands, kind, need_tier=0, only=None):
    out = []
    for m, tier in cands:
        r = data["results"].get(f"{kind}:{m}")
        if not r or not r["ok"] or tier < need_tier or (only and m not in only):
            continue
        h = data["history"].get(f"{kind}:{m}", [1])
        rel = sum(h) / len(h)
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
    set_combo("studio-code", rank(data, TEXT, "text", only=CODE))
    return data


if __name__ == "__main__":
    d = main()
    for k, r in sorted((d or {}).get("results", {}).items()):
        print(("OK  " if r["ok"] else "--  ") + f"{r['secs']:>5}s {k}  {r['why'][:90]}")
