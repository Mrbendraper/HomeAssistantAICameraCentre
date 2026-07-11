"""Generate AI Camera Centre brand assets.

Outputs (relative to the repo root, run from anywhere):
- brand/ai_camera_centre/ - icon.png 256, icon@2x.png 512, logo.png
  (<=512 wide, 128 high), logo@2x.png (exactly double) - sized to pass
  the home-assistant/brands CI checks, ready to copy into a brands PR
  (see docs/BRANDING.md).
- assets/logo-wide.png - larger wordmark used in the README header.

Requires Pillow and the Segoe UI Bold font (any Windows machine).
"""
from PIL import Image, ImageDraw, ImageFont
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "brand", "ai_camera_centre")
ASSETS = os.path.join(ROOT, "assets")
FONT_PATH = r"C:\Windows\Fonts\segoeuib.ttf"

SS = 4  # supersample factor
NAVY_TOP = (22, 67, 107)
NAVY_BOT = (12, 36, 56)
NAVY_MID = (18, 49, 79)
WHITE = (255, 255, 255)
AMBER = (251, 191, 36)


def star(draw, cx, cy, R, ir, fill):
    pts = [
        (cx, cy - R), (cx + ir, cy - ir), (cx + R, cy), (cx + ir, cy + ir),
        (cx, cy + R), (cx - ir, cy + ir), (cx - R, cy), (cx - ir, cy - ir),
    ]
    draw.polygon(pts, fill=fill)


def draw_glyph(draw, s, ox=0, oy=0):
    """Camera + sparkles, designed in 512-space, scaled by s, offset ox/oy."""
    def R(x0, y0, x1, y1, r, fill):
        draw.rounded_rectangle(
            [ox + x0 * s, oy + y0 * s, ox + x1 * s, oy + y1 * s],
            radius=r * s, fill=fill)

    def C(cx, cy, r, fill):
        draw.ellipse(
            [ox + (cx - r) * s, oy + (cy - r) * s,
             ox + (cx + r) * s, oy + (cy + r) * s], fill=fill)

    # stand + base
    R(195, 290, 227, 352, 10, WHITE)
    R(148, 344, 274, 372, 14, WHITE)
    # body
    R(104, 188, 322, 302, 34, WHITE)
    # lens
    C(330, 245, 62, WHITE)
    C(330, 245, 40, NAVY_BOT)
    C(340, 233, 13, WHITE)
    # status LED
    C(142, 216, 11, AMBER)
    # sparkles
    star(draw, ox + 398 * s, oy + 118 * s, 52 * s, 15 * s, AMBER)
    star(draw, ox + 452 * s, oy + 192 * s, 25 * s, 8 * s, AMBER)


def _tile(size):
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / size
        col = tuple(
            int(NAVY_TOP[i] + (NAVY_BOT[i] - NAVY_TOP[i]) * t) for i in range(3)
        )
        gd.line([(0, y), (size, y)], fill=col + (255,))
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * 100 / 512), fill=255
    )
    return grad, mask


def make_icon():
    size = 512 * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad, mask = _tile(size)
    img.paste(grad, (0, 0), mask)
    draw_glyph(ImageDraw.Draw(img), SS)
    img.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "icon@2x.png"))
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "icon.png"))


def make_logo(height, tile_px, font_px, out_main, out_2x=None, max_w=None):
    H = height * SS
    tile = tile_px * SS
    gap = 16 * SS
    font = ImageFont.truetype(FONT_PATH, font_px * SS)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    text = "AI Camera Centre"
    while True:
        bbox = tmp.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        W = tile + gap + tw + 8 * SS
        if max_w is None or W <= max_w * SS:
            break
        font = ImageFont.truetype(FONT_PATH, font.size - SS)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    grad, mask = _tile(tile)
    ty0 = (H - tile) // 2
    img.paste(grad, (0, ty0), mask)
    draw_glyph(d, tile / 512, ox=0, oy=ty0)
    d.text(
        (tile + gap, (H - th) // 2 - bbox[1]),
        text, font=font, fill=NAVY_MID + (255,),
    )
    w1, h1 = W // SS, H // SS
    if out_2x:
        img.resize((w1 * 2, h1 * 2), Image.LANCZOS).save(out_2x)
    img.resize((w1, h1), Image.LANCZOS).save(out_main)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(ASSETS, exist_ok=True)
    make_icon()
    # brands-compliant: shortest side >=128, longest <=512 (2x exactly double)
    make_logo(128, 100, 50,
              os.path.join(OUT, "logo.png"), os.path.join(OUT, "logo@2x.png"),
              max_w=512)
    # wide header for the README
    make_logo(140, 118, 62, os.path.join(ASSETS, "logo-wide.png"))
    for folder in (OUT, ASSETS):
        for f in sorted(os.listdir(folder)):
            if f.endswith(".png"):
                with Image.open(os.path.join(folder, f)) as im:
                    print(f, im.size)
