#!/usr/bin/env python3
"""Generate every Meetbeatz brand asset from the one master artwork.

Run it after changing tools/source/logo.png:

    pip install Pillow
    python3 tools/make_brand_assets.py

Outputs
-------
android/app/src/main/res/mipmap-*/            launcher icons (API 24-25 PNGs)
android/app/src/main/res/mipmap-anydpi-v26/   adaptive icon + monochrome layer
android/app/src/main/res/mipmap-*/            adaptive foreground, 108dp grid
android/app/src/main/res/drawable-nodpi/      the browser splash image
web/public/icons/                             PWA manifest icons
docs/play/                                    Play Store icon and feature graphic

Why it is a script rather than checked-in exports
-------------------------------------------------
The mark, the splash and the two store graphics are all crops, masks and glows of
the same logo. Keeping the derivation in code means a new master artwork is one
`cp` plus one command, instead of a folder of outdated PNGs nobody can trace back.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tools" / "source" / "logo.png"
ANDROID_RES = ROOT / "android" / "app" / "src" / "main" / "res"
WEB_ICONS = ROOT / "web" / "public" / "icons"
PLAY = ROOT / "docs" / "play"

# The website's palette (src/app/globals.css on meetbeatz.com).
INK = (5, 5, 6, 255)
ACID = (198, 241, 53, 255)
CREAM = (244, 241, 234, 255)
DEEP_RED = (200, 30, 34, 255)
MUTED = (139, 139, 149, 255)

# Region of the master that holds the mark only — the neon arc, the metallic MB and
# the equaliser bars underneath — with the MEETBEATZ wordmark cut off below it.
# Chosen by eye against a 10% grid overlaid on the artwork: at launcher size the
# wordmark is an unreadable smear, which is exactly why the site's own favicon
# crops in the same way. Expressed as ratios so a higher-resolution master drops in
# without changing anything.
MARK_BOX_RATIO = (0.065, 0.050, 0.925, 0.642)

# Launcher densities: (directory suffix, legacy icon px, adaptive foreground px).
DENSITIES = [
    ("mdpi", 48, 108),
    ("hdpi", 72, 162),
    ("xhdpi", 96, 216),
    ("xxhdpi", 144, 324),
    ("xxxhdpi", 192, 432),
]


def load_master() -> Image.Image:
    master = Image.open(SOURCE).convert("RGBA")
    if master.size[0] != master.size[1]:
        raise SystemExit(f"{SOURCE} should be square, got {master.size}")
    return master


def feathered_mask(size: tuple[int, int], inset_ratio: float = 0.022, blur_ratio: float = 0.05) -> Image.Image:
    """A rounded rectangle that fades out towards its own edges.

    The master artwork is a lit render: it has a textured background and a red glow
    that would otherwise end in a visible straight edge wherever it is placed on
    the ink background. Feathering the alpha blends those edges away.
    """
    width, height = size
    supersample = 4
    mask = Image.new("L", (width * supersample, height * supersample), 0)
    inset = int(min(width, height) * inset_ratio) * supersample
    ImageDraw.Draw(mask).rounded_rectangle(
        (inset, inset, width * supersample - inset, height * supersample - inset),
        radius=int(min(width, height) * 0.22) * supersample,
        fill=255,
    )
    mask = mask.resize((width, height), Image.LANCZOS)
    return mask.filter(ImageFilter.GaussianBlur(min(width, height) * blur_ratio))


def mark(alpha_feather: bool = True) -> Image.Image:
    """The MB monogram as a transparent-background RGBA image."""
    master = load_master()
    width, height = master.size
    box = (
        int(MARK_BOX_RATIO[0] * width),
        int(MARK_BOX_RATIO[1] * height),
        int(MARK_BOX_RATIO[2] * width),
        int(MARK_BOX_RATIO[3] * height),
    )
    cropped = master.crop(box)
    # Square it up so every consumer can scale it without breaking the aspect ratio.
    side = max(cropped.size)
    square = Image.new("RGBA", (side, side), INK)
    square.alpha_composite(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2))
    if alpha_feather:
        square.putalpha(ImageChops.multiply(square.getchannel("A"), feathered_mask(square.size)))
    return square


def with_glow(canvas: Image.Image, mark_image: Image.Image, scale: float) -> Image.Image:
    """Draw the mark centred on `canvas`, over a soft red glow taken from the mark itself."""
    target = int(min(canvas.size) * scale)
    scaled = mark_image.resize((target, target), Image.LANCZOS)

    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    glow_alpha = scaled.getchannel("A").filter(ImageFilter.GaussianBlur(target * 0.06))
    glow_layer = Image.new("RGBA", scaled.size, (200, 30, 34, 0))
    glow_layer.putalpha(glow_alpha.point(lambda value: int(value * 0.55)))
    glow.alpha_composite(glow_layer, ((canvas.width - target) // 2, (canvas.height - target) // 2))

    out = Image.alpha_composite(canvas, glow)
    out.alpha_composite(scaled, ((canvas.width - target) // 2, (canvas.height - target) // 2))
    return out


def ink_square(size: int, scale: float = 1.0) -> Image.Image:
    return with_glow(Image.new("RGBA", (size, size), INK), MARK, scale)


def circle(size: int) -> Image.Image:
    """Antialiased circular alpha mask, for the legacy round launcher icon."""
    supersample = 4
    mask = Image.new("L", (size * supersample, size * supersample), 0)
    ImageDraw.Draw(mask).ellipse(
        (0, 0, size * supersample - 1, size * supersample - 1), fill=255
    )
    return mask.resize((size, size), Image.LANCZOS)


def write(image: Image.Image, path: Path, shrink: bool = True) -> None:
    """Save `image`, palette-reducing it first.

    Every asset here is a crop of one photographic render, so a 256-colour octree
    keeps the look while cutting the file to a fraction: the 640 px splash goes from
    500 KB to well under 100 KB, which matters because these files are committed and
    the icons are downloaded by every visitor who installs the web app.
    """
    if shrink:
        image = image.quantize(colors=256, method=Image.FASTOCTREE)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    print(f"  {path.relative_to(ROOT)}  {image.size[0]}x{image.size[1]}")


def build_launcher_icons() -> None:
    print("launcher icons")
    for folder, legacy_px, foreground_px in DENSITIES:
        square = ink_square(legacy_px)
        write(square, ANDROID_RES / f"mipmap-{folder}" / "ic_launcher.png")

        round_icon = square.copy()
        round_icon.putalpha(circle(legacy_px))
        write(round_icon, ANDROID_RES / f"mipmap-{folder}" / "ic_launcher_round.png")

        # Adaptive foreground: 108dp grid, of which the middle 72dp is guaranteed
        # visible. The mark is drawn in that safe zone, so no launcher shape eats it.
        foreground = Image.new("RGBA", (foreground_px, foreground_px), (0, 0, 0, 0))
        foreground = with_glow(foreground, MARK, 0.60)
        write(foreground, ANDROID_RES / f"mipmap-{folder}" / "ic_launcher_foreground.png")

        # Themed icons (Android 13+): the launcher recolours a monochrome silhouette,
        # so only the mark's shape is kept.
        silhouette = Image.new("RGBA", (foreground_px, foreground_px), (0, 0, 0, 0))
        scaled = MARK.resize(
            (int(foreground_px * 0.60), int(foreground_px * 0.60)), Image.LANCZOS
        )
        white = Image.new("RGBA", scaled.size, (255, 255, 255, 0))
        white.putalpha(scaled.getchannel("A"))
        silhouette.alpha_composite(
            white,
            ((foreground_px - scaled.width) // 2, (foreground_px - scaled.height) // 2),
        )
        write(silhouette, ANDROID_RES / f"mipmap-{folder}" / "ic_launcher_monochrome.png")


def build_splash() -> None:
    print("splash image")
    # android-browser-helper hands this bitmap to the browser, which draws it centred
    # at its intrinsic size, so a nodpi asset keeps that size identical everywhere
    # (640 px is a little over half the width of a 1080 px phone screen).
    size = 640
    splash = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    splash = with_glow(splash, MARK, 0.92)
    write(splash, ANDROID_RES / "drawable-nodpi" / "splash.png")


def build_web_icons() -> None:
    print("web app icons")
    for size in (192, 512):
        write(ink_square(size), WEB_ICONS / f"icon-{size}.png")
    # Maskable icons are cropped to whatever shape the launcher uses, so the mark is
    # drawn smaller and on a full-bleed background.
    write(ink_square(512, scale=0.62), WEB_ICONS / "maskable-512.png")
    write(ink_square(180), WEB_ICONS / "apple-touch-icon.png")


def feature_graphic() -> None:
    """1024x500 Play Store feature graphic: the mark, the name, and what the app is.

    Play crops this into several aspect ratios and overlays nothing, so every element
    is kept well inside the edges and the two lines of text are short enough to fit
    the 512 px-wide thumbnail the store also renders.
    """
    width, height = 1024, 500
    canvas = Image.new("RGBA", (width, height), INK)

    # The same neon red the logo's arc gives off, washed in from the bottom left.
    wash = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wash)
    for step in range(30):
        radius = int(width * 0.75) - step * 20
        draw.ellipse(
            (-radius // 3, height - radius // 2, radius, height + radius // 2),
            fill=(*DEEP_RED[:3], 8 + step),
        )
    canvas = Image.alpha_composite(canvas, wash.filter(ImageFilter.GaussianBlur(70)))

    mark_size = int(height * 0.9)
    scaled = MARK.resize((mark_size, mark_size), Image.LANCZOS)
    canvas.alpha_composite(scaled, (int(height * 0.04), (height - mark_size) // 2))

    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    text_x = mark_size + int(height * 0.06)
    available = width - text_x - 40

    def fit(font_path: str, text: str, start: int) -> tuple[ImageFont.FreeTypeFont, float]:
        """Largest font size at or below `start` whose rendering fits `available`."""
        size = start
        while size > 8:
            font = ImageFont.truetype(font_path, size)
            thickness = ImageDraw.Draw(canvas).textlength(text, font=font)
            if thickness <= available:
                return font, thickness
            size -= 2
        return ImageFont.truetype(font_path, 8), 0.0

    wordmark_size = 78
    meet_font, meet_width = fit(bold, "MEET", wordmark_size)
    beatz_font, beatz_width = fit(bold, "BEATZ", wordmark_size)
    while meet_width + beatz_width > available and wordmark_size > 12:
        wordmark_size -= 2
        meet_font, meet_width = fit(bold, "MEET", wordmark_size)
        beatz_font, beatz_width = fit(bold, "BEATZ", wordmark_size)

    tagline = "Beats, sound kits and studio time."
    tagline_font, _ = fit(regular, tagline, 34)

    # Vertically centre the three lines as a block.
    line_gap = 10
    block = meet_font.size + line_gap + tagline_font.size
    y = (height - block) // 2

    draw = ImageDraw.Draw(canvas)
    draw.text((text_x, y), "MEET", font=meet_font, fill=CREAM)
    draw.text((text_x + meet_width, y), "BEATZ", font=beatz_font, fill=DEEP_RED)
    draw.text((text_x, y + meet_font.size + line_gap), tagline, font=tagline_font, fill=MUTED)

    write(canvas.convert("RGB"), PLAY / "feature-graphic-1024x500.png")


def main() -> None:
    global MARK

    if not SOURCE.exists():
        raise SystemExit(f"missing master artwork: {SOURCE}")
    MARK = mark()
    write(MARK, ROOT / "tools" / "build" / "mark.png")

    build_launcher_icons()
    build_splash()
    build_web_icons()

    print("play store graphics")
    write(ink_square(512), PLAY / "icon-512.png")
    feature_graphic()
    print("\ndone. The generated PNGs are committed; this script is the source of truth.")


if __name__ == "__main__":
    main()
