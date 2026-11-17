"""Studio's long-term brain (owner, 17 Nov: "why limited capacity? it should store everything").
Storage is unlimited: every learning is one line in knowledge/brain.jsonl (kept in git). What IS limited is how much
text one Gemini prompt can read, so each video gets only the items most relevant to it (semantic search with free
Gemini embeddings, keyword fallback). Items prove themselves: every video records which items it used; passes and
holds move each item's score; items that keep losing are retired automatically (never deleted, just switched off).
  add(items, source)            -> new ids (near-duplicates are merged, not added twice)
  relevant(query, k, areas)     -> [item]   (for the planner / editor)
  judge(ids, passed)            -> update scores after a review
  python engine/brain.py stats | search "<text>" | reembed"""
import hashlib, json, math, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log, load, save

STORE = os.path.join(ROOT, "knowledge", "brain.jsonl")
EMB = os.path.join(OUT, "brain-emb.json")             # vectors are cache (rebuildable), not in git
MODEL, DIM = "gemini-embedding-001", 256


def _key():
    import tts
    return tts._key()


def items():
    out = []
    if os.path.exists(STORE):
        for line in open(STORE, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def _write(all_):
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for it in all_:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    os.replace(tmp, STORE)


def embed(texts, task="RETRIEVAL_DOCUMENT"):
    """Free Gemini embeddings, 256 dims, batches of 50. Returns list of vectors (None on failure)."""
    out = []
    for i in range(0, len(texts), 50):
        chunk = texts[i:i + 50]
        body = {"requests": [{"model": f"models/{MODEL}", "content": {"parts": [{"text": t[:2000]}]}, "taskType": task,
                              "outputDimensionality": DIM} for t in chunk]}
        try:
            r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:batchEmbedContents",
                                       data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": _key()})
            d = json.load(urllib.request.urlopen(r, timeout=60))
            for e in d["embeddings"]:
                v = e["values"]; n = math.sqrt(sum(x * x for x in v)) or 1
                out.append([round(x / n, 5) for x in v])
        except Exception as e:
            log("brain: embedding failed", str(e)[:120]); out += [None] * len(chunk)
    return out


def _vecs():
    return load(EMB, {}) or {}


def _text(it):
    return f"{it.get('title', '')}. {it.get('text', '')} {it.get('how', '')}"


def _words(s):
    return set(re.findall(r"[a-z0-9]{3,}", s.lower()))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def add(new, source):
    """new: [{title, text, how?, area, kind}] -> ids added. Near-duplicates (cosine > 0.9 or same words) merge."""
    all_ = items(); vec = _vecs()
    nv = embed([_text(n) for n in new])
    ids = []
    for n, v in zip(new, nv):
        if not n.get("title") or not n.get("text"):
            continue
        dup = None
        for it in all_:
            iv = vec.get(it["id"])
            if (v and iv and _dot(v, iv) > 0.9) or _words(it["title"]) == _words(n["title"]):
                dup = it; break
        if dup:
            dup["seen"] = dup.get("seen", 1) + 1
            dup.setdefault("sources", []).append(source)
            dup["sources"] = dup["sources"][-8:]
            continue
        iid = hashlib.sha1((n["title"] + source).encode()).hexdigest()[:10]
        it = {"id": iid, "title": n["title"][:140], "text": n["text"][:900], "how": (n.get("how") or "")[:600],
              "area": n.get("area", "general"), "kind": n.get("kind", "knowledge"), "source": source, "sources": [source],
              "added": time.strftime("%Y-%m-%d"), "uses": 0, "wins": 0, "losses": 0, "on": True}
        all_.append(it); ids.append(iid)
        if v:
            vec[iid] = v
    _write(all_); save(EMB, vec)
    return ids


def relevant(query, k=14, areas=None):
    all_ = [it for it in items() if it.get("on", True) and it.get("kind") != "build" and (not areas or it.get("area") in areas or it.get("area") == "general")]
    if not all_:
        return []
    vec = _vecs()
    qv = (embed([query], "RETRIEVAL_QUERY") or [None])[0]
    qw = _words(query)
    def score(it):
        s = _dot(qv, vec[it["id"]]) if qv and it["id"] in vec else len(qw & _words(_text(it))) / (len(qw) + 5)
        trust = (it.get("wins", 0) + 1) / (it.get("wins", 0) + it.get("losses", 0) + 2)     # proven items rank higher
        return s * (0.7 + 0.6 * trust)
    return sorted(all_, key=score, reverse=True)[:k]


def prompt_block(query, k=14, areas=None):
    got = relevant(query, k, areas)
    if not got:
        return "", []
    lines = [f"- [{it['area']}] {it['title']}: {it['text']}" + (f" HOW: {it['how']}" if it.get("how") else "") for it in got]
    return ("KNOWLEDGE FROM OUR BRAIN (learned from repos, files, competitors and our own results; use what fits this video):\n"
            + "\n".join(lines)), [it["id"] for it in got]


def judge(ids, passed):
    if not ids:
        return
    all_ = items(); ch = 0
    for it in all_:
        if it["id"] in ids:
            it["uses"] = it.get("uses", 0) + 1
            it["wins" if passed else "losses"] = it.get("wins" if passed else "losses", 0) + 1
            if it["uses"] >= 8 and it["wins"] / it["uses"] < 0.25 and it.get("on", True):
                it["on"] = False; it["retired"] = time.strftime("%Y-%m-%d")
                log("brain: retired an item that kept losing:", it["title"][:80])
            ch += 1
    if ch:
        _write(all_)


def stats():
    all_ = items()
    on = [i for i in all_ if i.get("on", True)]
    by = {}
    for i in on:
        by[i.get("area")] = by.get(i.get("area"), 0) + 1
    return {"items": len(all_), "active": len(on), "build": sum(1 for i in all_ if i.get("kind") == "build"),
            "retired": sum(1 for i in all_ if not i.get("on", True)), "areas": by}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        print(json.dumps(stats(), indent=1))
    elif cmd == "search":
        for it in relevant(" ".join(sys.argv[2:]), 10):
            print(f"[{it['area']}] {it['title']}")
    elif cmd == "reembed":
        all_ = items(); vs = embed([_text(i) for i in all_])
        save(EMB, {i["id"]: v for i, v in zip(all_, vs) if v}); print("embedded", sum(1 for v in vs if v))
