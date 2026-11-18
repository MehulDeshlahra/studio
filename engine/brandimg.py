"""Brand images (Pillow only, so it runs with the system python3: the studio venv has no Pillow).
Input: brand/<id>/src.jpg (the page's real Instagram DP) + the page's theme.
Output in brand/<id>/: dp_safe.png (logo shrunk so the circular crop never cuts it), yt_banner.png (2560x1440),
fb_cover.png (1640x624), hl_series.png / hl_sources.png / hl_about.png (Instagram highlight covers 1080x1920).
Usage: python3 brandimg.py <id> <bg> <accent> <accent2> <tagline> <name>   |   python3 brandimg.py scrollhouse"""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_CANDS = ["/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", r"C:\Windows\Fonts\ariblk.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(size):
    for p in FONT_CANDS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def content(img):
    """Crop the logo out of its flat background. Returns (cropped RGBA, bg colour, is_round)."""
    img = img.convert("RGB")
    w, h = img.size
    px = [img.getpixel(p) for p in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3))]
    bg = tuple(sorted(c[i] for c in px)[1] for i in range(3))
    diff = ImageChops.difference(img, Image.new("RGB", img.size, bg)).convert("L").point(lambda v: 255 if v > 38 else 0)
    box = diff.getbbox() or (0, 0, w, h)
    cw, ch = box[2] - box[0], box[3] - box[1]
    # a round DP (katha, jain) has its content filling the whole square: keep it as it is
    is_round = cw > w * .9 and ch > h * .9
    return img.crop(box), bg, is_round


def backdrop(w, h, bg, a1, a2):
    img = Image.new("RGB", (w, h), bg)
    g = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(g)
    d.ellipse([w * .55, -h * .3, w * 1.2, h * .8], fill=mix(bg, a2, .30))
    d.ellipse([-w * .2, h * .35, w * .45, h * 1.3], fill=mix(bg, a1, .26))
    g = g.filter(ImageFilter.GaussianBlur(max(w, h) * .09))
    return Image.blend(img, g, .9)


def fit(img, bw, bh):
    r = min(bw / img.width, bh / img.height)
    return img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))), Image.LANCZOS)


def ctext(d, cx, cy, text, f, fill, track=0):
    ws = [d.textlength(c, font=f) for c in text]
    x = cx - (sum(ws) + track * (len(text) - 1)) / 2
    bb = d.textbbox((0, 0), "Hg", font=f)
    y = cy - (bb[1] + bb[3]) / 2
    for c, wd in zip(text, ws):
        d.text((x, y), c, font=f, fill=fill)
        x += wd + track


def dp_safe(logo, bg, is_round, size=1080):
    if is_round:
        return logo.resize((size, size), Image.LANCZOS)
    img = Image.new("RGB", (size, size), bg)
    lg = fit(logo, int(size * .70), int(size * .46))
    img.paste(lg, ((size - lg.width) // 2, (size - lg.height) // 2))
    return img


def banner(logo, bg, a1, a2, tagline, w, h, logo_h, tag_px, lbg=None, is_round=False):
    img = backdrop(w, h, bg, a1, a2)
    d = ImageDraw.Draw(img)
    lg = fit(logo, int(w * .42), logo_h)
    gap = int(tag_px * 1.4) if tagline else 0
    total = lg.height + gap + (tag_px if tagline else 0)
    y0 = (h - total) // 2
    if is_round:
        m = Image.new("L", lg.size, 0)
        ImageDraw.Draw(m).ellipse([0, 0, lg.width - 1, lg.height - 1], fill=255)
    else:                                         # flat-background wordmark: its background becomes see-through
        m = ImageChops.difference(lg.convert("RGB"), Image.new("RGB", lg.size, lbg)).convert("L").point(lambda v: min(255, v * 5))
    img.paste(lg, ((w - lg.width) // 2, y0), m)
    if tagline:
        ctext(d, w / 2, y0 + lg.height + gap + tag_px / 2, tagline.upper(), font(tag_px), (240, 240, 240), track=tag_px // 8)
    return img


def highlight(label, bg, a1, a2, logo=None, w=1080, h=1920):
    img = backdrop(w, h, bg, a1, a2)
    d = ImageDraw.Draw(img)
    cx, cy, r = w / 2, h / 2, 330
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=a1, width=16)
    d.ellipse([cx - r + 40, cy - r + 40, cx + r - 40, cy + r - 40], outline=mix(bg, a2, .7), width=5)
    ctext(d, cx, cy, label, font(110 if len(label) < 7 else 88), a1)
    return img


def main():
    cid = sys.argv[1]
    out = os.path.join(ROOT, "brand", cid)
    os.makedirs(out, exist_ok=True)
    if cid == "scrollhouse":
        bg, a1, a2, tag, name = "#0b0b10", "#ffffff", "#f5c542", "A network of pages", "SCROLL HOUSE"
        img = Image.new("RGB", (1080, 1080), rgb(bg))
        d = ImageDraw.Draw(img)
        ctext(d, 540, 500, "SH", font(380), rgb(a1), track=-10)
        d.rounded_rectangle([430, 740, 650, 756], 8, fill=rgb(a2))
        img.save(os.path.join(out, "dp_safe.png"))
        lg = img.crop((0, 300, 1080, 800))
        logo, bgc, rnd = lg, rgb(bg), False
    else:
        bg, a1, a2, tag, name = sys.argv[2:7]
        logo, bgc, rnd = content(Image.open(os.path.join(out, "src.jpg")))
        dp_safe(logo, bgc, rnd).save(os.path.join(out, "dp_safe.png"))
    bgc2, A1, A2 = rgb(bg), rgb(a1), rgb(a2)
    banner(logo, bgc2, A1, A2, tag, 2560, 1440, 330, 58, bgc, rnd).save(os.path.join(out, "yt_banner.png"))
    banner(logo, bgc2, A1, A2, tag, 1640, 624, 210, 30, bgc, rnd).save(os.path.join(out, "fb_cover.png"))
    for lab in ("SERIES", "SOURCES", "ABOUT"):
        highlight(lab, bgc2, A1, A2).save(os.path.join(out, "hl_" + lab.lower() + ".png"))
    print("round" if rnd else "wide", cid)


if __name__ == "__main__":
    main()
