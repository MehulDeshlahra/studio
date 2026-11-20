"""Build the reference-picture library (20 Nov, owner: "provide sample images / references so there is no scope of a
mistake"). For every sacred figure in engine/iconography.py: search Wikimedia Commons (real temple idols for Jain
figures, Raja Ravi Varma and other public-domain paintings for Hindu deities), score each candidate with the Gemini
Decisions API ("is this clearly <figure in its traditional form>, one main figure, no text / collage?"), keep the best 2.
Writes knowledge/refs.json (Commons titles + scores; the repo keeps only the index) and caches 512x512 PNGs in
~/studio-out/refs/. Re-run any time: python tools/refs_build.py [figure ...]"""
import base64, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "engine")); sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import iconography, picsmith
from core import ROOT, OUT, log, save, load

# 20 Nov, checked by eye: wrong person (Shakuntala as Sita), unusual form (Vishnu as the Cosmic Man), statue under
# scaffolding. Kali has no reference picture: her paintings show severed heads (page rule: never gory).
BAN = re.compile(r"Shakuntala|Cosmic Man|Gommateshwara Statue 1\.jpg|Damayanti|Menaka|Urvashi", re.I)
UA = {"User-Agent": "StudioRefs/1.0 (https://scrollhouse.in; reference pictures for devotional art)"}
INDEX = os.path.join(ROOT, "knowledge", "refs.json")
# what to search for each figure (first queries are the most specific)
Q = {
    "Mahavir Swami": ["Mahavira idol marble", "Mahavira statue Jain temple", "Tirthankara Mahavira murti"],
    "Rishabhdev": ["Rishabhanatha idol", "Adinath idol Jain", "Rishabhdev statue"],
    "Parshvanath": ["Parshvanatha idol serpent hood", "Parshvanath statue Jain"],
    "Neminath": ["Neminatha idol", "Neminath Jain statue"],
    "Bahubali": ["Gommateshwara Shravanabelagola close", "Bahubali statue Karkala", "Bahubali statue Jain", "Gommateshwara statue"],
    "Jain monk": ["Svetambara Jain monks white", "Jain sadhvi white robes", "Jain monk muhpatti"],
    "Shiva": ["Shiva Ravi Varma Press", "Shiva meditating painting", "Shiva Kailash painting", "Shiva Mahadeva painting"],
    "Parvati": ["Raja Ravi Varma Parvati", "Parvati painting"],
    "Ganesha": ["Raja Ravi Varma Ganesha", "Ganesha painting traditional"],
    "Kartikeya": ["Raja Ravi Varma Kartikeya", "Kartikeya peacock painting"],
    "Durga": ["Durga painting lion traditional", "Raja Ravi Varma Durga"],
    "Vishnu": ["Raja Ravi Varma Vishnu", "Vishnu painting four arms"],
    "Lakshmi": ["Lakshmi Ravi Varma Press", "Gajalakshmi painting", "Goddess Lakshmi painting", "Lakshmi seated lotus"],
    "Krishna": ["Raja Ravi Varma Krishna", "Krishna painting flute"],
    "Rama": ["Raja Ravi Varma Rama", "Rama painting bow"],
    "Sita": ["Sita Rama painting", "Sita Ravi Varma Press", "Sita Ashoka vatika painting"],
    "Hanuman": ["Hanuman painting traditional", "Raja Ravi Varma Hanuman"],
    "Brahma": ["Brahma painting four faces", "Raja Ravi Varma Brahma"],
    "Saraswati": ["Raja Ravi Varma Saraswati", "Saraswati painting veena"],
    "Yamraj": ["Yama god buffalo painting", "Yamaraja painting"],
    "Indra": ["Indra Airavata painting", "Raja Ravi Varma Indra"],
    "Surya": ["Surya chariot seven horses painting", "Surya deity painting"],
    "Ganga": ["Ganga goddess makara painting", "Raja Ravi Varma Ganga"],
    "Narad": ["Narada painting", "Narada muni", "Narada veena sage painting"],
    "Kuber": ["Kubera painting", "Kubera statue"],
}


def api(params):
    u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(dict(params, format="json"))
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))


def candidates(q, n=6):
    d = api({"action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {q}", "gsrnamespace": 6, "gsrlimit": n,
             "prop": "imageinfo", "iiprop": "url|size|mime", "iiurlwidth": 768})
    out = []
    for pg in (d.get("query") or {}).get("pages", {}).values():
        ii = (pg.get("imageinfo") or [{}])[0]
        if ii.get("mime") in ("image/jpeg", "image/png") and min(ii.get("width", 0), ii.get("height", 0)) >= 400:
            out.append({"title": pg["title"], "thumb": ii.get("thumburl") or ii.get("url")})
    return out


def fetch(c, dest):
    if not os.path.exists(dest):
        raw = urllib.request.urlopen(urllib.request.Request(c["thumb"], headers=UA), timeout=90).read()
        tmp = dest + ".src"
        open(tmp, "wb").write(raw)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-vf", "scale=512:512:force_original_aspect_ratio=decrease,"
                        "pad=512:512:(ow-iw)/2:(oh-ih)/2:white", dest], check=True)
        os.remove(tmp)
    return dest


def main(only):
    idx = load(INDEX, {}) or {}
    os.makedirs(os.path.join(OUT, "refs"), exist_ok=True)
    for fig, qs in Q.items():
        if only and fig not in only:
            continue
        form = iconography.FORMS.get(fig, ("", ""))[1]
        seen, scored = set(), []
        for q in qs:
            try:
                cs = candidates(q)
            except Exception as e:
                log("refs: search failed", fig, q, str(e)[:80]); continue
            for c in cs:
                if c["title"] in seen or BAN.search(c["title"]):
                    continue
                seen.add(c["title"])
                slug = re.sub(r"[^a-z0-9]+", "-", c["title"].lower())[5:60].strip("-")
                f = os.path.join(OUT, "refs", f"cand-{slug}.png")
                try:
                    fetch(c, f)
                    a = picsmith.decide(f, f"Reference picture for {fig}.", {
                        "is": f"Does this picture clearly show {fig} in the traditional form ({iconography._positive(form)}), "
                              f"as one main figure that fills much of the frame?",
                        "bad": "Does the picture have large text, a watermark, a collage of several pictures, or is the figure tiny, "
                               "blurry or hidden?"})
                    s = round(a.get("is", 0) - a.get("bad", 0), 3)
                    scored.append({"title": c["title"], "file": os.path.basename(f), "score": s, "is": a.get("is"), "bad": a.get("bad")})
                except Exception as e:
                    log("refs: candidate failed", c["title"][:60], str(e)[:80])
                time.sleep(0.4)
        best = [x for x in sorted(scored, key=lambda x: -x["score"]) if x["score"] >= 0.4][:2]
        idx[fig] = {"pattern": iconography.FORMS.get(fig, ("",))[0], "refs": best, "checked": time.strftime("%Y-%m-%d"),
                    "candidates": len(scored)}
        log("refs:", fig, "kept", [(b["title"][5:50], b["score"]) for b in best], "of", len(scored))
        save(INDEX, idx)
    return idx


if __name__ == "__main__":
    main(set(sys.argv[1:]))
