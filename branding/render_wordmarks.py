"""Render Slidoxa wordmark + mark PNGs directly, using the OFL Plus
Jakarta Sans font shipped in assets/fonts/. Pillow is reliable across
hosts; ImageMagick's librsvg fallback often can't find system fonts.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
FONT_PATH = REPO / "assets" / "fonts" / "PlusJakartaSans" / "PlusJakartaSans-VariableFont_wght.ttf"

PRIMARY = "#7A5AF8"
DARK = "#0F1020"
ACCENT = "#60A5FA"
WHITE = "#FFFFFF"


def draw_mark(canvas: ImageDraw.ImageDraw, x: float, y: float, scale: float, on_dark: bool) -> None:
    def rect(cx, cy, w, h, color, alpha=255, radius=None):
        r = radius if radius is not None else 16 * scale
        box = (x + cx * scale, y + cy * scale, x + (cx + w) * scale, y + (cy + h) * scale)
        if alpha < 255:
            overlay = Image.new("RGBA", canvas._image.size, (0, 0, 0, 0))
            ImageDraw.Draw(overlay).rounded_rectangle(box, radius=r * scale, fill=color + f"{alpha:02x}")
            canvas._image.alpha_composite(overlay)
        else:
            canvas.rounded_rectangle(box, radius=r * scale, fill=color)

    def hex_a(c, a):
        return c + f"{a:02x}"

    def rr(cx, cy, w, h, fill, radius):
        canvas.rounded_rectangle(
            (x + cx * scale, y + cy * scale, x + (cx + w) * scale, y + (cy + h) * scale),
            radius=radius * scale, fill=fill,
        )

    rr(20, 20, 110, 80, hex_a(ACCENT, int(0.55 * 255) if on_dark else int(0.65 * 255)), 16)
    rr(12, 42, 110, 80, hex_a(PRIMARY, int(0.92 * 255)), 16)
    rr(4, 64, 110, 80, WHITE if on_dark else DARK, 16)
    rr(22, 86, 60, 8, PRIMARY, 4)
    accent_row = hex_a(DARK, int(0.55 * 255)) if on_dark else hex_a(WHITE, int(0.65 * 255))
    accent_row2 = hex_a(DARK, int(0.40 * 255)) if on_dark else hex_a(WHITE, int(0.45 * 255))
    rr(22, 104, 44, 6, accent_row, 3)
    rr(22, 118, 52, 6, accent_row2, 3)


def render_logo(dark: bool, out: Path, size_px: tuple[int, int]) -> None:
    w, h = size_px
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # Virtual canvas is 900x220 in the SVG.
    scale = h / 220.0
    draw = ImageDraw.Draw(img)
    draw._image = img  # back-ref so helpers can alpha-composite
    draw_mark(draw, 20 * scale, 30 * scale, scale, on_dark=dark)

    font_px = int(112 * scale)
    font = ImageFont.truetype(str(FONT_PATH), font_px)
    # font variation (Plus Jakarta Sans is variable); Pillow 10+ supports set_variation
    try:
        font.set_variation_by_axes([700])
    except Exception:
        pass

    text_color = WHITE if dark else DARK
    text_x = int(190 * scale)
    text_y = int((138 - 112) * scale)  # baseline tweak so visually centered
    draw.text((text_x, text_y), "Slidoxa", font=font, fill=text_color)
    img.save(out)


def main() -> int:
    stage = Path("/tmp/slidoxa-brand")
    stage.mkdir(exist_ok=True)
    render_logo(dark=False, out=stage / "logo-with-bg.png", size_px=(900, 166))
    render_logo(dark=True,  out=stage / "logo-white.png",   size_px=(2250, 938))
    render_logo(dark=False, out=stage / "Logo.png",         size_px=(204, 48))
    print("wordmarks rendered:", stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
