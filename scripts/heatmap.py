"""Fetch the public contribution calendar and render assets/contrib-heatmap.svg.

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
X0, Y0 = 44, 64  # grid origin, leaves room for weekday and month labels
W = 860


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


def render(days):
    total, current, longest, best = stats(days)
    weeks = max(col for col, _ in days) + 1
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 232" width="{W}" height="232" '
        'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">',
        "<style>",
        ".c{transform-box:fill-box;transform-origin:center;opacity:0;animation:in .45s ease-out forwards}",
        "@keyframes in{from{opacity:0;transform:translateY(-8px) scale(.4)}to{opacity:1;transform:none}}",
        ".t{fill:#8b949e;font-size:11px}",
        "</style>",
        f'<rect width="{W}" height="232" rx="10" fill="#0d1117" stroke="#30363d"/>',
        '<circle cx="20" cy="18" r="5" fill="#ff5f56"/><circle cx="36" cy="18" r="5" fill="#ffbd2e"/>'
        '<circle cx="52" cy="18" r="5" fill="#27c93f"/>',
        f'<text x="{W / 2}" y="22" text-anchor="middle" class="t">{USER.lower()}@github: ~/contributions</text>',
    ]
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="12" y="{Y0 + row * STEP + 10}" class="t">{name}</text>')
    for col in range(weeks):
        first = min(v[0] for (c, _), v in days.items() if c == col)
        # label a month on its first week, skipping a partial first column
        if first.day <= 7 and col < weeks - 2:
            out.append(f'<text x="{X0 + col * STEP}" y="{Y0 - 8}" class="t">{first:%b}</text>')
    for (col, row), (date, level, count) in sorted(days.items()):
        delay = (col + row) * 0.018  # diagonal sweep from top-left
        out.append(
            f'<rect class="c" style="animation-delay:{delay:.3f}s" x="{X0 + col * STEP}" '
            f'y="{Y0 + row * STEP}" width="{CELL}" height="{CELL}" rx="3" fill="{PALETTE[level]}">'
            f"<title>{count} on {date:%b %d, %Y}</title></rect>"
        )
    footer_y = Y0 + 7 * STEP + 24
    summary = (
        f"{total:,} contributions in the last year · current streak {current}d · "
        f"longest {longest}d · best day {best[2]} ({best[0]:%b %d})"
    )
    out.append(f'<text x="{X0}" y="{footer_y}" class="t">{html.escape(summary)}</text>')
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


if __name__ == "__main__":
    _selfcheck()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(parse(fetch(USER))), encoding="utf-8")
    print(f"wrote {OUT}")
