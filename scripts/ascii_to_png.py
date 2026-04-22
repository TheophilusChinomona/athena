#!/usr/bin/env python3
"""Render Athena's ASCII art (logo + hero) to a transparent PNG.

Usage:
    python scripts/ascii_to_png.py [--output assets/athena_ascii.png] [--size 32]
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow required: pip install Pillow", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Art data — sourced from hermes_cli/skin_engine.py "athena" skin
# ---------------------------------------------------------------------------

ATHENA_LOGO = """\
[bold #C0C8D8] █████╗ ████████╗██╗  ██╗███████╗███╗   ██╗ █████╗ [/]
[bold #A8B8CC]██╔══██╗╚══██╔══╝██║  ██║██╔════╝████╗  ██║██╔══██╗[/]
[#7B9EC8]███████║   ██║   ███████║█████╗  ██╔██╗ ██║███████║[/]
[#5A7BA8]██╔══██║   ██║   ██╔══██║██╔══╝  ██║╚██╗██║██╔══██║[/]
[#4A6FA5]██║  ██║   ██║   ██║  ██║███████╗██║ ╚████║██║  ██║[/]
[#2A3D5A]╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝[/]"""

ATHENA_HERO = """\
[#2A3D5A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#4A6FA5]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⠀⠀⠀⠀⠀⠀⣀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#7B9EC8]⠀⠀⠀⠀⠀⠀⠀⢀⣾⣿⣷⣄⠀⠀⣠⣾⣿⣷⡀⠀⠀⠀⠀⠀⠀[/]
[#7B9EC8]⠀⠀⠀⠀⠀⠀⢠⣿⠋⠀⠙⢿⣷⣾⡿⠋⠀⠙⣿⡄⠀⠀⠀⠀⠀[/]
[#C0C8D8]⠀⠀⠀⠀⠀⠀⣿⡟⠀⠀⠀⠀⢻⣿⠀⠀⠀⠀⢻⣿⠀⠀⠀⠀⠀[/]
[#C0C8D8]⠀⠀⠀⠀⠀⠀⣿⡇⠀⠀⠀⠀⢸⣿⠀⠀⠀⠀⢸⣿⠀⠀⠀⠀⠀[/]
[#7B9EC8]⠀⠀⠀⠀⠀⠀⢿⣧⡀⠀⠀⢀⣼⣿⣄⠀⠀⢀⣼⡿⠀⠀⠀⠀⠀[/]
[#4A6FA5]⠀⠀⠀⠀⠀⠀⠈⠻⣿⣿⣿⡿⠟⠘⢿⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀[/]
[#2A3D5A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡿⠀⠀⠀⠀⢿⣿⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#4A6FA5]⠀⠀⠀⠀⠀⠀⠀⣠⣾⡿⠁⠀⠀⠀⠀⠈⢿⣷⣄⠀⠀⠀⠀⠀⠀[/]
[#7B9EC8]⠀⠀⠀⠀⠀⠀⠀⠙⠛⠁⠀⠀⠀⠀⠀⠀⠀⠙⠛⠀⠀⠀⠀⠀⠀[/]
[#2A3D5A]⠀⠀⠀⠀⠀⠀⠀⠀strategy engine ready⠀⠀⠀⠀⠀⠀⠀[/]"""


# ---------------------------------------------------------------------------
# New owl banner — programmatically generated from pixel art
# ---------------------------------------------------------------------------

def build_owl_art() -> str:
    """Build Athena's owl portrait using solid █ block characters.

    Each character cell is a colored pixel, giving clean crisp shapes
    identical in style to the ATHENA block-letter logo above it.
    Grid: 25 chars wide × 20 rows tall.
    """
    W, H = 25, 20

    # Palette — Athena silver/midnight-blue scheme
    HEAD  = "#7B9EC8"   # silver-blue head
    BODY  = "#4A6FA5"   # midnight-blue body
    WING  = "#2A3D5A"   # deep navy wing tips
    TUFT  = "#A8B8CC"   # light silver ear tufts
    ERING = "#C0C8D8"   # silver eye ring
    IRIS  = "#EDF0F5"   # near-white iris
    PUP   = "#1A2D4A"   # near-black pupil
    BEAK  = "#C0C8D8"   # silver beak

    grid: list[list[str | None]] = [[None] * W for _ in range(H)]

    def _px(y: int, x: int, c: str) -> None:
        if 0 <= y < H and 0 <= x < W:
            grid[y][x] = c

    def _ellipse(cy: float, cx: float, rx: float, ry: float, c: str) -> None:
        """Fill an ellipse; rx/ry are in character-cell units."""
        for y in range(H):
            for x in range(W):
                if (x - cx) ** 2 / rx ** 2 + (y - cy) ** 2 / ry ** 2 <= 1.0:
                    _px(y, x, c)

    def _rect(y0: int, y1: int, x0: int, x1: int, c: str) -> None:
        for y in range(max(0, y0), min(H, y1)):
            for x in range(max(0, x0), min(W, x1)):
                _px(y, x, c)

    # Head — fill most of the grid height; rx > ry because chars are ~2× taller than wide
    _ellipse(9, 12, 11.0, 7.5, HEAD)

    # Ear tufts — short, wide spikes (owls have stubby tufts, not tall rabbit ears)
    _rect(0, 4, 4, 9,  TUFT)
    _rect(0, 4, 16, 21, TUFT)

    # Left eye: silver ring → near-white iris → dark pupil
    _ellipse(6.5, 7,  4.2, 2.5, ERING)
    _ellipse(6.5, 7,  2.8, 1.7, IRIS)
    _ellipse(6.5, 7,  1.2, 0.8, PUP)

    # Right eye (mirror)
    _ellipse(6.5, 17, 4.2, 2.5, ERING)
    _ellipse(6.5, 17, 2.8, 1.7, IRIS)
    _ellipse(6.5, 17, 1.2, 0.8, PUP)

    # Beak — pointed diamond centered between eyes
    _rect(11, 12, 11, 14, BEAK)
    _rect(12, 13, 12, 13, BEAK)

    # Wings — wide ellipse, visible beyond the body on both sides
    _ellipse(16, 12, 12.4, 5.5, WING)

    # Body — narrower ellipse layered over the wings
    _ellipse(16, 12,  9.0, 4.5, BODY)

    # Legs (two short columns)
    _rect(19, 20, 9,  11, BODY)
    _rect(19, 20, 14, 16, BODY)

    # --- Encode to Rich markup ---
    lines: list[str] = []
    for row in grid:
        if all(c is None for c in row):
            lines.append(f"[#2A3D5A]{' ' * W}[/]")
            continue
        parts: list[str] = []
        i = 0
        while i < W:
            c = row[i]
            j = i + 1
            while j < W and row[j] == c:
                j += 1
            span = j - i
            if c is None:
                parts.append(f"[#2A3D5A]{' ' * span}[/]")
            else:
                parts.append(f"[{c}]{'█' * span}[/]")
            i = j
        lines.append("".join(parts))

    lines.append("[dim #4A6FA5]  wisdom  ·  strategy  ·  code  [/]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rich markup parser
# ---------------------------------------------------------------------------

_MARKUP_RE = re.compile(r"\[(?:bold\s+|dim\s+)?(#[0-9A-Fa-f]{6})\](.*?)\[/\]", re.DOTALL)
_DIM_RE = re.compile(r"\[dim\s+(#[0-9A-Fa-f]{6})\]")


def parse_rich_markup(art: str) -> list[list[tuple[str, tuple[int, int, int], float]]]:
    """Parse Rich markup into lines of (text, rgb, opacity) segments."""
    parsed_lines = []
    for line in art.split("\n"):
        segments = []
        is_dim = bool(re.search(r"\[dim\s+#", line))
        opacity = 0.55 if is_dim else 1.0
        for match in _MARKUP_RE.finditer(line):
            color_hex, text = match.group(1), match.group(2)
            r = int(color_hex[1:3], 16)
            g = int(color_hex[3:5], 16)
            b = int(color_hex[5:7], 16)
            if text:
                segments.append((text, (r, g, b), opacity))
        if not segments:
            plain = re.sub(r"\[.*?\]", "", line)
            if plain:
                segments.append((plain, (192, 200, 216), 1.0))
        parsed_lines.append(segments)
    return parsed_lines


# ---------------------------------------------------------------------------
# PNG renderer
# ---------------------------------------------------------------------------

_BOLD_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# Athena gradient — silver at top, midnight blue at bottom, one stop per letter
_TITLE_GRADIENT = [
    (192, 200, 216),  # A — silver
    (168, 184, 204),  # T
    (123, 158, 200),  # H
    (90,  123, 168),  # E
    (74,  111, 165),  # N
    (42,   61,  90),  # A — midnight blue
]


def render_title(text: str, target_width: int) -> Image.Image:
    """Render title text in a bold font with the Athena silver→blue gradient.

    The font size is auto-scaled so the text fills ~90% of target_width.
    Returns a transparent RGBA image.
    """
    bold_path = next((p for p in _BOLD_FONT_CANDIDATES if Path(p).exists()), None)
    if bold_path is None:
        # Fallback: render the ASCII logo art at a larger size
        font = _load_font(48)
        cw, ch = _measure_cell(font)
        return render_art_to_image(ATHENA_LOGO, font, cw, ch)

    # Binary-search for the right font size
    lo, hi = 12, 400
    while lo < hi - 1:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(bold_path, mid)
        bb = f.getbbox(text)
        if bb[2] - bb[0] < target_width * 0.90:
            lo = mid
        else:
            hi = mid
    font = ImageFont.truetype(bold_path, lo)

    bb = font.getbbox(text)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad_v = lo // 4
    img_w = max(tw + lo, target_width)
    img_h = th + pad_v * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    x = (img_w - tw) // 2 - bb[0]
    y = pad_v - bb[1]
    gradient = _TITLE_GRADIENT
    for i, ch in enumerate(text):
        color = gradient[i % len(gradient)]
        draw.text((x, y), ch, font=font, fill=(*color, 255))
        x += font.getlength(ch)

    return img


_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/unifont/unifont.otf",
    "/usr/share/fonts/truetype/unifont/unifont.ttf",
    "/usr/share/fonts/opentype/unifont/unifont_jp.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError(
        "No suitable font found. Install unifont: apt-get install fonts-unifont"
    )


def _measure_cell(font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """Return (char_width, line_height) for the font."""
    bbox = font.getbbox("█")
    char_w = bbox[2] - bbox[0]
    # Line height: use a slightly larger value than font size for comfortable spacing
    char_h = font.size + max(2, font.size // 8)
    return char_w, char_h


def render_art_to_image(
    art: str, font: ImageFont.FreeTypeFont, char_w: int, char_h: int
) -> Image.Image:
    """Render a single art string to a transparent RGBA image."""
    lines = parse_rich_markup(art)
    # Calculate canvas size
    max_chars = max(
        (sum(len(t) for t, _, _ in segs) for segs in lines if segs),
        default=1,
    )
    width = max_chars * char_w
    height = len(lines) * char_h
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for row_idx, segments in enumerate(lines):
        x = 0
        y = row_idx * char_h
        for text, (r, g, b), opacity in segments:
            alpha = int(opacity * 255)
            for ch in text:
                # U+2800 braille blank and ASCII space are transparent — skip drawing
                if ch not in (" ", "⠀"):
                    draw.text((x, y), ch, font=font, fill=(r, g, b, alpha))
                x += char_w
    return img


def combine_vertically(
    images: list[Image.Image], gap: int = 8
) -> Image.Image:
    """Stack images vertically, centered horizontally, with a gap between them."""
    max_w = max(im.width for im in images)
    total_h = sum(im.height for im in images) + gap * (len(images) - 1)
    canvas = Image.new("RGBA", (max_w, total_h), (0, 0, 0, 0))
    y = 0
    for im in images:
        x = (max_w - im.width) // 2
        canvas.paste(im, (x, y), im)
        y += im.height + gap
    return canvas


def tight_crop(img: Image.Image, padding: int = 12) -> Image.Image:
    """Crop transparent borders and add uniform padding."""
    bbox = img.getbbox()
    if not bbox:
        return img
    cropped = img.crop(bbox)
    padded = Image.new(
        "RGBA",
        (cropped.width + 2 * padding, cropped.height + 2 * padding),
        (0, 0, 0, 0),
    )
    padded.paste(cropped, (padding, padding), cropped)
    return padded


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Render Athena ASCII art to PNG")
    parser.add_argument(
        "--output", default="assets/athena_ascii.png",
        help="Output PNG path (default: assets/athena_ascii.png)"
    )
    parser.add_argument(
        "--size", type=int, default=16,
        help="Font size in pixels (default: 16 — Unifont native resolution)"
    )
    parser.add_argument(
        "--art", choices=["current", "owl", "both"], default="owl",
        help="Which art to render: current (skin_engine hero), owl (new), both (default: owl)"
    )
    args = parser.parse_args()

    print(f"Loading font at {args.size}px…")
    font = _load_font(args.size)
    char_w, char_h = _measure_cell(font)
    print(f"  cell size: {char_w}×{char_h}px")

    images = []

    # Owl pixel art — measure its width so the title can match it
    owl_art = build_owl_art()
    owl_img = render_art_to_image(owl_art, font, char_w, char_h)

    if args.art in ("current", "both"):
        print("Rendering current Athena art (logo + hero)…")
        logo_img = render_title("ATHENA", owl_img.width)
        hero_img = render_art_to_image(ATHENA_HERO, font, char_w, char_h)
        combined = combine_vertically([logo_img, hero_img], gap=char_h)
        images.append(combined)

    if args.art in ("owl", "both"):
        print("Rendering new owl art…")
        logo_img = render_title("ATHENA", owl_img.width)
        combined = combine_vertically([logo_img, owl_img], gap=char_h // 2)
        images.append(combined)

    if len(images) > 1:
        final = combine_vertically(images, gap=char_h * 2)
    else:
        final = images[0]

    final = tight_crop(final, padding=16)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(out, "PNG")
    print(f"Saved → {out}  ({final.width}×{final.height}px, RGBA)")


if __name__ == "__main__":
    main()
