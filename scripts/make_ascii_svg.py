"""Turn a photo into a self-typing ASCII portrait that looks around: assets/ascii-portrait.svg.

Run locally only when the photo changes (needs Pillow):
    python scripts/make_ascii_svg.py photo.png
Or re-render the current portrait without the photo, e.g. after a style change:
    python scripts/make_ascii_svg.py assets/ascii-portrait.svg
"""
import re
import sys
from html import escape, unescape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

OUT = Path(__file__).resolve().parent.parent / "assets" / "ascii-portrait.svg"
RAMP = ".:-=+*cs#%@"  # dark (sparse) -> bright (dense); background becomes spaces
COLS, ROWS = 88, 48  # monospace glyphs are ~2x taller than wide
FONT, LINE, CHAR_W = 8, 9, 5
BG_THRESHOLD = 215  # near-white pixels touching the border count as background
PAD, TOP = 16, 40
LOOK_X, LOOK_Y = 10, 4  # px the face slides when glancing sideways / up
LOOK_START = 0.3 + ROWS * 0.07 + 0.4  # after the last row has typed in


def to_grid(path):
    img = ImageOps.exif_transpose(Image.open(path)).convert("L")
    img = ImageOps.autocontrast(img, cutoff=1).resize((COLS, ROWS), Image.LANCZOS)
    # flood the light backdrop from every edge pixel so only the subject prints
    mask = img.point(lambda v: 255 if v >= BG_THRESHOLD else 0)
    for x in range(COLS):
        for y in (0, ROWS - 1):
            if mask.getpixel((x, y)) == 255:
                ImageDraw.floodfill(mask, (x, y), 128)
    for y in range(ROWS):
        for x in (0, COLS - 1):
            if mask.getpixel((x, y)) == 255:
                ImageDraw.floodfill(mask, (x, y), 128)
    # stretch contrast over the subject only, so the backdrop doesn't eat the tonal range
    subject = sorted(v for v, m in zip(img.tobytes(), mask.tobytes()) if m != 128)
    lo, hi = subject[len(subject) // 50], subject[-len(subject) // 50]
    face = img.filter(ImageFilter.UnsharpMask(radius=1, percent=160, threshold=2))
    face = face.point(lambda v: max(0, min(255, (v - lo) * 255 // max(1, hi - lo))))
    rows = []
    for y in range(ROWS):
        line = ""
        for x in range(COLS):
            if mask.getpixel((x, y)) == 128:
                line += " "
            else:
                line += RAMP[face.getpixel((x, y)) * (len(RAMP) - 1) // 255]
        rows.append(line.rstrip())
    return rows


def from_svg(text):
    """Recover the rows from a rendered portrait, so it can be re-rendered without the photo."""
    rows = [""] * ROWS
    for i, line in re.findall(r'clip-path="url\(#r(\d+)\)"[^>]*>([^<]*)</text>', text):
        rows[int(i)] = unescape(line)
    return rows


def turn(i):
    """How far row i moves when the head turns: shoulders stay put, the nose band leads."""
    neck, shoulders = 0.6 * ROWS, 0.68 * ROWS
    if i >= shoulders:
        return 0.0
    nose = max(0.0, 1 - abs(i - 0.45 * ROWS) / (0.2 * ROWS))
    w = 0.7 + 0.3 * nose
    return w * min(1.0, (shoulders - i) / (shoulders - neck))


def render(rows):
    w = COLS * CHAR_W + 2 * PAD
    h = TOP + ROWS * LINE + PAD
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="{FONT}">',
        "<style>",
        # glance left, back, right, back, up: each row slides by its own --x/--y so the head turns on the neck
        f".h{{transform-origin:{w / 2}px 0;animation:look 9s ease-in-out {LOOK_START:.1f}s infinite}}",
        "@keyframes look{0%,12%,48%,55%,100%{transform:none}"
        "22%,38%{transform:translateX(calc(var(--x)*-1px)) scaleX(.97)}"
        "65%,80%{transform:translateX(calc(var(--x)*1px)) scaleX(.97)}"
        "90%{transform:translateY(calc(var(--y)*-1px))}}",
        "@media (prefers-reduced-motion:reduce){.h{animation:none}}",
        "</style>",
        f'<rect width="{w}" height="{h}" rx="10" fill="#0d1117" stroke="#30363d"/>',
        '<circle cx="20" cy="18" r="5" fill="#ff5f56"/><circle cx="36" cy="18" r="5" fill="#ffbd2e"/>'
        '<circle cx="52" cy="18" r="5" fill="#27c93f"/>',
        f'<text x="{w / 2}" y="22" text-anchor="middle" fill="#8b949e" font-size="11">huy@github: ~/portrait</text>',
        "<defs>",
    ]
    row_w = COLS * CHAR_W
    for i in range(ROWS):
        begin = 0.3 + i * 0.07
        out.append(
            f'<clipPath id="r{i}"><rect x="{PAD}" y="{TOP + i * LINE}" width="0" height="{LINE}">'
            f'<animate attributeName="width" from="0" to="{row_w}" begin="{begin:.2f}s" dur="0.25s" fill="freeze"/>'
            "</rect></clipPath>"
        )
    out.append("</defs>")
    for i, line in enumerate(rows):
        if not line.strip():
            continue
        y = TOP + i * LINE + LINE - 2
        t = turn(i)
        look = f' class="h" style="--x:{LOOK_X * t:.2f};--y:{LOOK_Y * t:.2f}"' if t else ""
        # textLength pins each row to the grid whatever monospace font the viewer has
        out.append(
            f'<text x="{PAD}" y="{y}" fill="#c9d1d9" clip-path="url(#r{i})"{look} xml:space="preserve" '
            f'textLength="{len(line) * CHAR_W}" lengthAdjust="spacingAndGlyphs">{escape(line)}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    rows = from_svg(src.read_text(encoding="utf-8")) if src.suffix == ".svg" else to_grid(src)
    assert len(rows) == ROWS and all(len(r) <= COLS for r in rows)
    assert any(rows), "no portrait rows found"
    assert from_svg(render(rows)) == rows  # re-rendering from the SVG is lossless
    assert 0 < turn(0) < turn(int(0.45 * ROWS)) and turn(ROWS - 1) == 0  # head moves, nose most, shoulders not
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(rows), encoding="utf-8")
    print("\n".join(rows))
    print(f"wrote {OUT}")
