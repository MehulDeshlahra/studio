"""Model scout + test set (20 Nov, owner: "an agent which daily checks any free models available and automatically adds
them to OmniRoute if good"; "use the most efficient models first").

Runs inside omnimap (04:40 daily) before the combos are rebuilt:
  1. DISCOVER  OmniRoute's /v1/models lists every model of every connection. A model is a candidate only on a
               connection Studio owns and only when it is free: OpenRouter ':free', Z.ai '-flash', Gemini without the
               paid Pro / Argon / Carbon lines, all of Groq / NVIDIA / Cloudflare / nara. SiliconFlow and Hugging Face
               are never auto-added (one paid call answers 402 and locks the whole key, 18 Nov).
  2. TEST      every model (new and old, each one at most once a week) answers OUR test set, not a toy probe:
               text  : Hinglish in Roman letters, exact JSON, iconography facts, a small sum
               vision: labelled frames from our own past mistakes (bearded Mahavira, saffron sage, Kuber with Krishna's
                       peacock feather, a standing Tirthankara photo, a clean yagya frame)
  3. RANK      omnimap orders each combo by this score (quality first, then reliability, then speed). A model that
               scores under 0.5 is never used. knowledge/models.json keeps every result; Telegram gets the changes.
"""
import base64, json, os, re, sys, time, urllib.request
from core import ROOT, OUT, log, load, save

MODELS = os.path.join(ROOT, "knowledge", "models.json")
EVAL_DIR = os.path.join(OUT, "evalset")
OK_PROVIDERS = {"gemini", "groq", "nvidia", "cloudflare-ai", "cf", "openrouter", "nara", "zai", "llm7", "pollinations"}
SKIP = re.compile(r"embed|tts|whisper|guard|safeguard|rerank|flux|stable-diffusion|sdxl|image-gen|imagen|veo|seedance|"
                  r"lora|ocr|parse|-tts|audio|speech|vl-embed|reward|:batch|nano-banana|lyria|live|moderation|retriev", re.I)
PAID_GEMINI = re.compile(r"pro|argon|carbon|ultra|image|2\.5-pro|deep-?think|computer-use", re.I)

TEXT_TESTS = [
    ('Return ONLY JSON {"line": "<one short Hinglish sentence in Roman letters: aasmaan neela kyun hai>"}',
     lambda j: len(str(j.get("line", ""))) > 10 and not re.search(r"[\u0900-\u097f]", str(j.get("line", "")))),
    ('Return ONLY JSON {"months": [<exactly three Hindu calendar month names written in Roman letters>]}',
     lambda j: isinstance(j.get("months"), list) and len(j["months"]) == 3 and all(re.fullmatch(r"[A-Za-z \-]+", str(m)) for m in j["months"])),
    ('In Jain temple idols, which animal is the emblem (lanchhan) below Parshvanath, and which bird does the god Kartikeya '
     'ride? Return ONLY JSON {"parshvanath": "<one word>", "kartikeya": "<one word>"}',
     lambda j: re.search(r"snake|serpent|cobra|naga", str(j.get("parshvanath", "")), re.I) and re.search(r"peacock|peafowl", str(j.get("kartikeya", "")), re.I)),
    ('A reel has 14 scenes of 2.5 seconds each and a 1.4 second end card. Return ONLY JSON {"seconds": <total as a number>}',
     lambda j: abs(float(j.get("seconds", 0)) - 36.4) < 0.01),
]
# (file in EVAL_DIR, [(question, expected yes/no)])
VISION_TESTS = [
    ("mahavira-beard.jpg", [("Does the main seated figure have a beard or moustache?", True),
                            ("Is the main figure a white marble statue?", False)]),
    ("saffron-sage.jpg", [("Is the old man on the left wearing orange or saffron clothes?", True),
                          ("Does the old man have a white beard?", True)]),
    ("kuber-peacock.jpg", [("Is there a peacock feather on the crown of the main figure?", True),
                           ("Is the main figure thin?", False)]),
    ("tirthankara-standing.jpg", [("Is the statue standing upright?", True),
                                  ("Is the statue wearing necklaces or other jewellery?", False)]),
    ("yagya-clean.jpg", [("Is there a fire in the picture?", True),
                         ("Does any figure in the picture have blue skin?", False)]),
]


def _post(model, content, max_tokens=1500, timeout=120):
    import omnimap
    return omnimap._post(model, content, timeout=timeout, max_tokens=max_tokens)


def run_text(model):
    import llm
    ok = 0
    t0 = time.time()
    for q, good in TEXT_TESTS:
        try:
            j = llm.parse_json(_post(model, q)) or {}
            ok += bool(good(j))
        except Exception:
            pass
    return round(ok / len(TEXT_TESTS), 2), round((time.time() - t0) / len(TEXT_TESTS), 1)


def run_vision(model):
    import llm
    ok = n = 0
    t0 = time.time()
    for f, qs in VISION_TESTS:
        p = os.path.join(EVAL_DIR, f)
        if not os.path.exists(p):
            continue
        b = base64.b64encode(open(p, "rb").read()).decode()
        text = ("Answer each question about this picture with true or false.\n" + "\n".join(f"{i + 1}. {q}" for i, (q, _) in enumerate(qs))
                + '\nReturn ONLY JSON {"answers": [true/false, ...]} in the same order.')
        n += len(qs)
        try:
            j = llm.parse_json(_post(model, [{"type": "text", "text": text},
                                              {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}}])) or {}
            ans = j.get("answers") or []
            ok += sum(1 for (_, want), got in zip(qs, ans) if got is want)
        except Exception:
            pass
    return (round(ok / n, 2) if n else 0.0), round((time.time() - t0) / max(1, len(VISION_TESTS)), 1)


def discover():
    import llm
    req = urllib.request.Request("http://127.0.0.1:20128/v1/models", headers={"Authorization": "Bearer " + llm._key()})
    out = {}
    for m in json.load(urllib.request.urlopen(req, timeout=60)).get("data") or []:
        mid = m.get("id", "")
        prov = mid.split("/")[0]
        if prov not in OK_PROVIDERS or SKIP.search(mid) or "text" not in (m.get("output_modalities") or ["text"]):
            continue
        if prov == "openrouter" and not mid.endswith(":free"):
            continue
        if prov == "zai" and "flash" not in mid:
            continue
        if prov == "gemini" and PAID_GEMINI.search(mid.split("/", 1)[1]):
            continue
        out[mid] = {"vision": "image" in (m.get("input_modalities") or [])}
    return out


def scout(max_tests=40):
    """Test new candidates and re-test old ones once a week. Returns models.json."""
    import omnimap
    db = load(MODELS, {}) or {}
    try:
        cands = discover()
    except Exception as e:
        log("modelscout: discovery failed", str(e)[:120]); cands = {}
    for m, _ in omnimap.BASE_TEXT:
        cands.setdefault(m, {"vision": False})
    for m, _ in omnimap.BASE_VISION:
        cands.setdefault(m, {})["vision"] = True
    now, week = time.time(), 7 * 86400
    todo = [m for m in cands if now - (db.get(m) or {}).get("tested", 0) > week]
    todo.sort(key=lambda m: (m in db, (db.get(m) or {}).get("tested", 0)))     # never-tested first
    added, dropped = [], []
    for m in todo[:max_tests]:
        e = db.get(m) or {"first_seen": time.strftime("%Y-%m-%d")}
        before = e.get("text", 0) >= 0.5 or e.get("vision", 0) >= 0.5
        e["text"], e["text_secs"] = run_text(m)
        if cands[m].get("vision"):
            e["vision"], e["vision_secs"] = run_vision(m)
        e["tested"] = now; e["tested_day"] = time.strftime("%Y-%m-%d")
        db[m] = e
        good = e.get("text", 0) >= 0.5 or e.get("vision", 0) >= 0.5
        if good and not before:
            added.append(f"{m} (text {e.get('text')}" + (f", vision {e.get('vision')}" if "vision" in e else "") + ")")
        if before and not good:
            dropped.append(m)
        log("modelscout:", m, "text", e.get("text"), "vision", e.get("vision", "-"))
        save(MODELS, db)
    if added or dropped:
        try:
            from core import telegram
            telegram("🧪 Model scout: " + (("added " + "; ".join(added[:8])) if added else "") +
                     ((" | dropped " + ", ".join(dropped[:8])) if dropped else ""))
        except Exception:
            pass
    return db


def tiers(kind):
    """[(model, tier)] for omnimap from the test results: tier 4 >= 0.9, 3 >= 0.75, 2 >= 0.5; under 0.5 never used."""
    db = load(MODELS, {}) or {}
    out = []
    for m, e in db.items():
        s = e.get(kind)
        if s is None:
            continue
        t = 4 if s >= 0.9 else 3 if s >= 0.75 else 2 if s >= 0.5 else 0
        if t:
            out.append((m, t))
    return out


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    scout(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
