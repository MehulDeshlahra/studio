"""Free-stack model calls for Studio (OmniRoute on the Oracle server, 127.0.0.1:20128).

Studio has its own OmniRoute key (~/.omniroute-studio.key, 18 Nov) and its own combos, rebuilt every day from real test
calls by engine/omnimap.py (working models only, best first):
  studio-text    planning, scripts, repairs        text(prompt)
  studio-fast    small JSON jobs                   text(prompt, fast=True)
  studio-vision  frame / contact-sheet checks      vision(prompt, jpeg_bytes)
  studio-code    the healer's code fixes           code(prompt)
watch(url, prompt) -> Gemini watches a public YouTube URL (no download; YouTube blocks datacenter downloads)
Each combo walks its own models inside OmniRoute (cool-downs, 429s), so one call here = one answer or one clear error.
"""
import base64, json, os, re, time, urllib.error, urllib.request

URL = os.environ.get("OMNIROUTE_URL", "http://127.0.0.1:20128") + "/v1/chat/completions"
TEXT_MODELS = ["studio-text", "claude-free", "gemini/gemini-3.1-flash-lite"]
FAST_MODELS = ["studio-fast", "studio-text"]
VISION_MODELS = ["studio-vision", "gemini/gemini-3.1-flash-lite"]
CODE_MODELS = ["studio-code", "studio-text"]
WATCH_MODELS = ["gemini/gemini-3.1-flash-lite", "gemini/gemini-3.8-flash"]
last_model = ""                                     # which upstream model answered the last call (for logs)
QUOTA_TEXT = re.compile(r"account behind this API key doesn.t have enough credits|enter\.pollinations\.ai/(top-up|quests)", re.I)


def _key():
    k = os.environ.get("OMNIROUTE_KEY")
    if k:
        return k
    for p in (os.environ.get("OMNIROUTE_KEY_FILE", ""), "~/.omniroute-studio.key", "~/.omniroute-vajra.key"):
        p = os.path.expanduser(p) if p else ""
        if p and os.path.exists(p):
            return open(p).read().strip()
    raise RuntimeError("no OmniRoute key file")


def _call(model, content, max_tokens=4000, timeout=300):
    global last_model
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": content}],
                       "max_tokens": max_tokens, "temperature": 0.4}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Authorization": "Bearer " + _key(),
                                                          "Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=timeout))
    out = (d["choices"][0]["message"].get("content") or "").strip()
    if not out:
        raise RuntimeError("empty answer from " + model)
    if QUOTA_TEXT.search(out[:600]):        # 18 Nov: Pollinations answers "not enough credits, top up" as a normal 200 reply
        raise RuntimeError(f"quota message instead of an answer from {d.get('model') or model}")
    last_model = d.get("model") or model
    return out


def parse_json(s):
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    s = m.group(1) if m else s
    m = re.search(r"[\[{].*[\]}]", s, re.S)
    return json.loads(m.group(0) if m else s)


def _today():
    t = time.localtime()
    return (f"TODAY IS {time.strftime('%A, %d %B %Y', t)} (India). Your training memory ends well before today: anything you "
            f"remember as upcoming, rumoured, unreleased or 'coming in {t.tm_year - 1}' may already have happened. For anything "
            f"about the present (launches, releases, prices, rates, rules, events, who holds a post), trust only the dated sources "
            f"given in this prompt, newest first. Never present an older year as the current one: the current year is {t.tm_year}.\n\n")


def _dated(content):
    """19 Nov (owner: GTA 6 became 'kab aayega' though it is out; gold came out as 2025): every call carries today's date
    (same text as core.today_line; lib/ does not import the engine)."""
    if isinstance(content, str):
        return content if content.startswith("TODAY IS ") else _today() + content
    if isinstance(content, list) and content and isinstance(content[0], dict) and content[0].get("type") == "text" \
            and not content[0]["text"].startswith("TODAY IS "):
        content = [dict(content[0], text=_today() + content[0]["text"])] + content[1:]
    return content


def _chain(models, content, json_mode, max_tokens, timeout=300):
    errs = []
    if models is not CODE_MODELS:
        content = _dated(content)
    for m in models:
        for attempt in range(2):
            try:
                out = _call(m, content, max_tokens, timeout)
                return parse_json(out) if json_mode else out
            except urllib.error.HTTPError as e:
                errs.append(f"{m}: HTTP {e.code}")
                if e.code in (429, 401, 402, 403, 404):
                    break          # this model / combo is out; next one
                time.sleep(5)
            except (ValueError, json.JSONDecodeError) as e:
                errs.append(f"{m}: bad JSON")      # malformed JSON is usually a one-off: ask again once
            except Exception as e:
                errs.append(f"{m}: {str(e)[:80]}")
                time.sleep(3)
    raise RuntimeError("all models failed: " + " | ".join(errs))


def text(prompt, json_mode=False, max_tokens=4000, fast=False):
    if json_mode:
        prompt += "\n\nReturn ONLY valid JSON, no other text."
    return _chain(FAST_MODELS if fast else TEXT_MODELS, prompt, json_mode, max_tokens)


def code(prompt, max_tokens=8000):
    return _chain(CODE_MODELS, prompt, False, max_tokens, timeout=600)


def vision(prompt, image, json_mode=True, max_tokens=3000, mime="image/jpeg"):
    """image: bytes or a file path. Used when Studio's own Gemini keys are out for the day."""
    if isinstance(image, str):
        image = open(image, "rb").read()
    content = [{"type": "text", "text": prompt + ("\n\nReturn ONLY valid JSON, no other text." if json_mode else "")},
               {"type": "image_url", "image_url": {"url": f"data:{mime};base64," + base64.b64encode(image).decode()}}]
    return _chain(VISION_MODELS, content, json_mode, max_tokens)


def from_parts(parts, json_mode=True, max_tokens=4000):
    """The same request as a Gemini "parts" list ({"text"} / {"inline_data"}), answered through Studio's OmniRoute combos.
    Every engine caller that talks to Gemini directly uses this once its own Gemini keys are out for the day (18 Nov:
    before this, preflight / review / covers / Mehul agent simply got no answer in the afternoon)."""
    content, img = [], False
    for p in parts:
        if "text" in p:
            content.append({"type": "text", "text": p["text"]})
        elif "inline_data" in p and str(p["inline_data"].get("mime_type", "")).startswith("image/"):
            d = p["inline_data"]; img = True
            content.append({"type": "image_url", "image_url": {"url": f"data:{d['mime_type']};base64,{d['data']}"}})
    if not content:
        raise RuntimeError("nothing to send")
    if json_mode:
        content[0]["text"] += "\n\nReturn ONLY valid JSON, no other text."
    if not img:
        return _chain(TEXT_MODELS, "\n\n".join(c["text"] for c in content), json_mode, max_tokens)
    return _chain(VISION_MODELS, content, json_mode, max_tokens)


BLIND = re.compile(r"(can'?t|cannot|unable to|don'?t have the ability to) (see|view|watch|access|open|play)\b.{0,40}"
                   r"(video|link|url|content)|share (it|the video)|describe (it|the video)", re.I)


def watch(video_url, prompt, json_mode=True, max_tokens=3000):
    """19 Nov: gemini-3.8-flash answers "I can't see the video" (no video input) and the chain took that as a success:
    a model must prove it watched (no "can't see" text, and JSON when JSON was asked) or the next one is tried."""
    content = [{"type": "text", "text": prompt + ("\n\nReturn ONLY valid JSON, no other text." if json_mode else "")},
               {"type": "video_url", "video_url": {"url": video_url}}]
    errs = []
    for m in WATCH_MODELS:
        try:
            out = _chain([m], content, json_mode, max_tokens, timeout=180)
        except Exception as e:
            errs.append(f"{m}: {str(e)[:100]}"); continue
        txt = json.dumps(out) if not isinstance(out, str) else out
        if BLIND.search(txt[:600]) or (json_mode and not isinstance(out, (dict, list))):
            errs.append(f"{m}: did not watch the video"); continue
        return out
    raise RuntimeError("no model watched the video: " + " | ".join(errs))
