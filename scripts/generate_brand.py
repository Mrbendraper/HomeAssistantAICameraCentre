"""Generate AI Camera Centre brand assets.

Design: a ceiling dome camera on a white tile. The dome's rim carries the
four Simple Addins brand colours (green / orange / pink / blue) and the
housing + wordmark use the Simple Addins navy, so the add-in reads as part
of the same family as simpleaddins.com.

Outputs (relative to the repo root, run from anywhere):
- brand/ai_camera_centre/ - icon.png 256, icon@2x.png 512, logo.png
  (<=512 wide, 128 high), logo@2x.png (exactly double) - sized to pass
  the home-assistant/brands CI checks, ready to copy into a brands PR
  (see docs/BRANDING.md).
- assets/logo-wide.png - larger wordmark used in the README header.

Requires Pillow and the Segoe UI Bold font (any Windows machine).
"""
from PIL import Image, ImageChops, ImageDraw, ImageFont
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "brand", "ai_camera_centre")
ASSETS = os.path.join(ROOT, "assets")
FONT_PATH = r"C:\Windows\Fonts\segoeuib.ttf"

SS = 4  # supersample factor

# Simple Addins palette
NAVY = (29, 46, 110)
GREEN = (29, 158, 75)
ORANGE = (247, 168, 35)
PINK = (236, 94, 150)
BLUE = (59, 196, 240)
TILE = (255, 255, 255)
TILE_BORDER = (226, 232, 240)
DOME_TINT = (232, 237, 247)


def draw_glyph(img, s, ox=0, oy=0):
    """Dome camera, designed in 512-space, scaled by s, offset ox/oy."""
    draw = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1):
        return [ox + x0 * s, oy + y0 * s, ox + x1 * s, oy + y1 * s]

    # dome: solid navy bottom half of a circle centred on the mount line
    cx, cy, r = 256, 215, 130
    dome = box(cx - r, cy - r, cx + r, cy + r)
    draw.pieslice(dome, start=0, end=180, fill=NAVY)
    # four-colour ribbon across the dome (clipped to the dome shape)
    ribbon = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(ribbon)
    seg = 2 * r / 4
    for i, col in enumerate((GREEN, ORANGE, PINK, BLUE)):
        rd.rectangle(
            box(cx - r + i * seg, 252, cx - r + (i + 1) * seg, 296), fill=col
        )
    dome_mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(dome_mask).pieslice(dome, start=0, end=180, fill=255)
    img.paste(ribbon, (0, 0), ImageChops.multiply(ribbon.split()[3], dome_mask))
    # lens
    draw.ellipse(box(cx - 14, 232 - 14, cx + 14, 232 + 14), fill=TILE)
    # ceiling mount bar
    draw.rounded_rectangle(box(116, 175, 396, 213), radius=19 * s, fill=NAVY)


def _tile(size):
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    radius = int(size * 100 / 512)
    td.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=TILE)
    td.rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius,
        outline=TILE_BORDER, width=max(1, int(size * 6 / 512)),
    )
    return tile


def make_icon():
    size = 512 * SS
    img = _tile(size)
    draw_glyph(img, SS)
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
    ty0 = (H - tile) // 2
    img.paste(_tile(tile), (0, ty0))
    draw_glyph(img, tile / 512, ox=0, oy=ty0)
    d.text(
        (tile + gap, (H - th) // 2 - bbox[1]),
        text, font=font, fill=NAVY + (255,),
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
