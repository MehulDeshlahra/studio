"""Free-stack model calls for Studio (OmniRoute on the Oracle server, 127.0.0.1:20128).

text(prompt, json_mode)  -> str or parsed JSON, through the combo 'claude-free' then single fallbacks
watch(url, prompt)       -> Gemini watches a public YouTube URL (no download; YouTube blocks datacenter downloads)
"""
import json, os, re, time, urllib.error, urllib.request

URL = os.environ.get("OMNIROUTE_URL", "http://127.0.0.1:20128") + "/v1/chat/completions"
TEXT_MODELS = ["claude-free", "nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b", "gemini/gemini-3.1-flash-lite"]
WATCH_MODELS = ["gemini/gemini-3.1-flash-lite", "gemini/gemini-3.8-flash"]


def _key():
    k = os.environ.get("OMNIROUTE_KEY")
    if k:
        return k
    p = os.path.expanduser(os.environ.get("OMNIROUTE_KEY_FILE", "~/.omniroute-vajra.key"))
    return open(p).read().strip()


def _call(model, content, max_tokens=4000, timeout=240):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": content}],
                       "max_tokens": max_tokens, "temperature": 0.4}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Authorization": "Bearer " + _key(),
                                                          "Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=timeout))
    out = (d["choices"][0]["message"].get("content") or "").strip()
    if not out:
        raise RuntimeError("empty answer from " + model)
    return out


def parse_json(s):
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    s = m.group(1) if m else s
    m = re.search(r"[\[{].*[\]}]", s, re.S)
    return json.loads(m.group(0) if m else s)


def _chain(models, content, json_mode, max_tokens):
    errs = []
    for m in models:
        for attempt in range(2):
            try:
                out = _call(m, content, max_tokens)
                return parse_json(out) if json_mode else out
            except urllib.error.HTTPError as e:
                errs.append(f"{m}: HTTP {e.code}")
                if e.code in (429, 401, 403, 404):
                    break          # this model is out; next one
                time.sleep(5)
            except Exception as e:
                errs.append(f"{m}: {str(e)[:80]}")
                time.sleep(3)
    raise RuntimeError("all models failed: " + " | ".join(errs))


def text(prompt, json_mode=False, max_tokens=4000):
    if json_mode:
        prompt += "\n\nReturn ONLY valid JSON, no other text."
    return _chain(TEXT_MODELS, prompt, json_mode, max_tokens)


def watch(video_url, prompt, json_mode=True, max_tokens=3000):
    content = [{"type": "text", "text": prompt + ("\n\nReturn ONLY valid JSON, no other text." if json_mode else "")},
               {"type": "video_url", "video_url": {"url": video_url}}]
    return _chain(WATCH_MODELS, content, json_mode, max_tokens)
