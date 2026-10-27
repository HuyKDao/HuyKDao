"""Fetch the public contribution calendar and render assets/contrib-heatmap.svg as a 3D skyline.

Standard library only, so the daily workflow needs no installs and no token.
"""
import datetime as dt
import html
import re
import sys
import urllib.request
from pathlib import Path

USER = "HuyKDao"
OUT = Path(__file__).resolve().parent.parent / "assets" / "contrib-heatmap.svg"
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]  # GitHub levels 0-4
CELL, GAP = 12, 3
STEP = CELL + GAP
W, H = 860, 290
# skyline: weeks run left to right, weekdays run back (Sun) to front (Sat)
COL, FW = 12, 10  # column pitch and building width
ROW_X, ROW_Y = 9, 6  # oblique offset per weekday row
DX, DY = 7, 5  # building depth, a bit less than a row so streets show
XL, FLOOR = 76, 206  # front-left corner of the front row
HMAX = 100  # tallest building, the best day


def fetch(user):
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def parse(page):
    """Return {(week, weekday): (date, level, count)}."""
    counts = {}
    for cell_id, text in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        m = re.match(r"(\d+) contribution", text)
        counts[cell_id] = int(m.group(1)) if m else 0
    days = {}
    for td in re.findall(r"<td[^>]*ContributionCalendar-day[^>]*>", page):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', td))
        if "data-date" not in attrs:
            continue
        row, col = map(int, attrs["id"].rsplit("-", 2)[-2:])
        date = dt.date.fromisoformat(attrs["data-date"])
        days[(col, row)] = (date, int(attrs["data-level"]), counts.get(attrs["id"], 0))
    if not days:
        sys.exit("No contribution cells found: GitHub markup may have changed.")
    return days


def stats(days):
    ordered = sorted(days.values())
    total = sum(c for _, _, c in ordered)
    longest = run = 0
    for _, _, c in ordered:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    # today may have no commits yet, so a streak ending yesterday still counts
    for i, (_, _, c) in enumerate(reversed(ordered)):
        if c:
            current += 1
        elif i > 0 or current:
            break
    best = max(ordered, key=lambda x: x[2])
    return total, current, longest, best


def shade(color, toward, amount):
    a, b = (int(color[i:i + 2], 16) for i in (1, 3, 5)), (int(toward[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def height(count, peak):
    # square root so one huge day does not flatten the rest of the year
    return max(3.0, HMAX * (count / peak) ** 0.5) if count else 0.0


def base(col, row):
    """Front-left ground corner of a day's building."""
    depth = 6 - row
    return XL + col * COL + depth * ROW_X, FLOOR - depth * ROW_Y


def pts(*xy):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)


def render(days):
    total, current, longest, best = stats(days)
    weeks = max(col for col, _ in days) + 1
    peak = max(best[2], 1)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">',
        "<style>",
        ".b{transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);"
        "animation:rise .7s cubic-bezier(.3,1.35,.5,1) forwards}",
        "@keyframes rise{to{transform:scaleY(1)}}",
        ".f,.l{opacity:0;animation:fade .5s ease-out forwards}",
        "@keyframes fade{to{opacity:1}}",
        "@media (prefers-reduced-motion:reduce){.b,.f,.l{animation:none;transform:none;opacity:1}}",
        ".t{fill:#8b949e;font-size:11px}",
        "</style>",
        f'<rect width="{W}" height="{H}" rx="10" fill="#0d1117" stroke="#30363d"/>',
        '<circle cx="20" cy="18" r="5" fill="#ff5f56"/><circle cx="36" cy="18" r="5" fill="#ffbd2e"/>'
        '<circle cx="52" cy="18" r="5" fill="#27c93f"/>',
        f'<text x="{W / 2}" y="22" text-anchor="middle" class="t">{USER.lower()}@github: ~/contributions</text>',
    ]
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        x, y = base(0, row)
        out.append(f'<text x="{x - 6}" y="{y}" text-anchor="end" class="t">{name}</text>')
    for col in range(weeks):
        first = min(v[0] for (c, _), v in days.items() if c == col)
        # label a month on its first week, skipping a partial first column
        if first.day <= 7 and col < weeks - 2:
            out.append(f'<text x="{base(col, 6)[0]}" y="{FLOOR + 16}" class="t">{first:%b}</text>')
    # painter's order: back row first, left to right, so nearer buildings cover farther ones
    for (col, row), (date, level, count) in sorted(days.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        x, y = base(col, row)
        h = height(count, peak)
        tip = f"<title>{count} on {date:%b %d, %Y}</title>"
        roof = pts((x, y - h), (x + FW, y - h), (x + FW + DX, y - h - DY), (x + DX, y - h - DY))
        if not h:
            delay = col * 0.012 + (6 - row) * 0.03
            out.append(f'<polygon class="f" style="animation-delay:{delay:.3f}s" points="{roof}" fill="{PALETTE[0]}">{tip}</polygon>')
            continue
        delay = col * 0.02 + (6 - row) * 0.05  # wave from the front-left corner
        c = PALETTE[level]
        side = pts((x + FW, y), (x + FW + DX, y - DY), (x + FW + DX, y - h - DY), (x + FW, y - h))
        out.append(
            f'<g class="b" style="animation-delay:{delay:.3f}s">{tip}'
            f'<rect x="{x}" y="{y - h:.1f}" width="{FW}" height="{h:.1f}" fill="{c}"/>'
            f'<polygon points="{side}" fill="{shade(c, "#000000", .4)}"/>'
            f'<polygon points="{roof}" fill="{shade(c, "#ffffff", .3)}"/></g>'
        )
    if best[2]:
        bcol, brow = next(k for k, v in days.items() if v == best)
        x, y = base(bcol, brow)
        tx, ty = x + (FW + DX) / 2, y - height(best[2], peak) - DY / 2 - 4
        anchor = "end" if tx > W - 140 else "start" if tx < 140 else "middle"
        out.append(
            f'<g class="l" style="animation-delay:{weeks * 0.02 + 1.2:.2f}s">'
            f'<line x1="{tx:.1f}" y1="{ty:.1f}" x2="{tx:.1f}" y2="48" stroke="#8b949e" stroke-dasharray="2 2"/>'
            f'<text x="{tx:.1f}" y="42" text-anchor="{anchor}" class="t">best day · {best[2]} ({best[0]:%b %d})</text></g>'
        )
    footer_y = FLOOR + 44
    summary = (
        f"{total:,} contributions in the last year · current streak {current}d · "
        f"longest {longest}d · best day {best[2]} ({best[0]:%b %d})"
    )
    out.append(f'<text x="{XL}" y="{footer_y}" class="t">{html.escape(summary)}</text>')
    lx = W - 44 - 5 * STEP - 70
    out.append(f'<text x="{lx}" y="{footer_y + 22}" class="t">Less</text>')
    for i, color in enumerate(PALETTE):
        out.append(f'<rect x="{lx + 34 + i * STEP}" y="{footer_y + 12}" width="{CELL}" height="{CELL}" rx="3" fill="{color}"/>')
    out.append(f'<text x="{lx + 40 + 5 * STEP}" y="{footer_y + 22}" class="t">More</text>')
    out.append("</svg>")
    return "\n".join(out)


def _selfcheck():
    d = dt.date(2026, 1, 1)
    days = {(i, 0): (d + dt.timedelta(i), 1, c) for i, c in enumerate([1, 2, 0, 3, 4, 5, 0])}
    assert stats(days)[:3] == (15, 3, 3)  # today empty, streak through yesterday still counts
    days[(7, 0)] = (d + dt.timedelta(7), 0, 0)
    days[(6, 0)] = (d + dt.timedelta(6), 1, 2)
    assert stats(days)[1] == 4
    days[(8, 0)] = (d + dt.timedelta(8), 0, 0)
    assert stats(days)[1] == 0  # two empty days in a row break the streak
    assert height(0, 9) == 0 and height(9, 9) == HMAX and height(1, 10_000) == 3
    assert shade("#000000", "#ffffff", .5) == "#808080"
    import xml.etree.ElementTree as ET
    ET.fromstring(render(days))  # well-formed SVG


if __name__ == "__main__":
    _selfcheck()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(parse(fetch(USER))), encoding="utf-8")
    print(f"wrote {OUT}")
