#!/usr/bin/env python3
"""Draw a printable install card with a QR code for a release's APK.

Scanning a QR code is how you get a build onto a phone without retyping a URL or
emailing yourself a link, so every release ships one of these next to the APK.

    python3 tools/make_install_qr.py --url https://…/meetbeatz-1.0.0-1-debug.apk \
        --out meetbeatz-v1.0.0-install-qr.png

Requires `segno` and `pillow`:

    pip install segno pillow
"""

from __future__ import annotations

import argparse
import pathlib
import textwrap

import segno
from PIL import Image, ImageDraw, ImageFont

# The site's palette, so the card looks like the product rather than like a utility.
INK = (5, 5, 6)
CREAM = (244, 241, 234)
ACID = (198, 241, 53)
MUTED = (139, 139, 149)
WHITE = (255, 255, 255)

FONTS = {
    "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
}

CARD_W, CARD_H = 1200, 1560
QR_BOX = 800


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONTS[kind], size)
    except OSError as exc:  # pragma: no cover - fonts ship with every Linux runner
        raise SystemExit(
            f"Could not load {FONTS[kind]}. Install fonts-dejavu (Debian/Ubuntu: "
            f"apt-get install fonts-dejavu-core)."
        ) from exc


def draw_card(url: str, *, version: str, size_note: str, min_android: str = "Android 7.0+") -> Image.Image:
    img = Image.new("RGB", (CARD_W, CARD_H), CREAM)
    draw = ImageDraw.Draw(img)

    def center(text: str, font: ImageFont.FreeTypeFont, y: float, fill=INK) -> None:
        draw.text((CARD_W / 2, y), text, font=font, fill=fill, anchor="mm")

    draw.rectangle([0, 0, CARD_W, 14], fill=ACID)
    center(f"MEETBEATZ  ·  ANDROID TEST BUILD  ·  {version}".upper(), _font("bold", 26), 70, MUTED)
    center("Scan to install on your phone", _font("bold", 66), 150, INK)

    # Module-by-module, deliberately. Rescaling a rendered QR bitmap softens module edges,
    # and a softened module is a code that will not scan on a cheap camera.
    qr = segno.make(url, error="m")
    rows = list(qr.matrix_iter(border=4))
    modules = len(rows[0])
    module_px = QR_BOX // modules
    box = module_px * modules
    left, top = (CARD_W - box) // 2, 250

    pad = 28
    draw.rectangle([left - pad, top - pad, left + box + pad, top + box + pad], fill=WHITE)
    for r, row in enumerate(rows):
        for c, bit in enumerate(row):
            if bit:
                x, y = left + c * module_px, top + r * module_px
                draw.rectangle([x, y, x + module_px - 1, y + module_px - 1], fill=INK)

    y = top + box + pad + 70
    for line in textwrap.wrap(url, width=58):
        center(line, _font("mono", 25), y, MUTED)
        y += 36

    y += 30
    steps = [
        "1  Scan the code, open the link",
        "2  Download anyway",
        "3  Allow from this source  →  Install",
    ]
    for i, step in enumerate(steps):
        center(step, _font("bold" if i == 0 else "regular", 34), y, INK if i == 0 else MUTED)
        y += 54

    draw.rectangle([0, CARD_H - 14, CARD_W, CARD_H], fill=ACID)
    center(
        f"{size_note}  ·  {min_android}  ·  no login needed  ·  debug build, for testing",
        _font("regular", 24),
        CARD_H - 52,
        MUTED,
    )
    return img


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="the APK download URL to encode")
    parser.add_argument("--version", default="test build", help="shown in the header")
    parser.add_argument("--size-note", default="", help="e.g. '4.8 MB'")
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args()

    img = draw_card(args.url, version=args.version, size_note=args.size_note or "APK")
    img.save(args.out)
    print(f"Wrote {args.out} ({img.width}x{img.height}) encoding:\n  {args.url}")


if __name__ == "__main__":
    main()
