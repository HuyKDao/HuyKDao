"""Render the neofetch-style info card: assets/info-card.svg.

Edit LINES, then run: python scripts/make_info_card.py
"""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "info-card.svg"
W, H = 490, 478  # height matches the portrait so the two columns line up
KEY = "#58a6ff"
TEXT = "#c9d1d9"
LINES = [
    ("Now", "MSE Data Science @ UPenn (May 2028)"),
    ("Prev", "BA Data Science @ UC Berkeley (2025)"),
    ("Focus", "Applied math and modeling"),
    ("Intern", "Data Science @ Oakland Natives Give Back"),
    ("Seeking", "Summer 2027 DS / DA / BI internship"),
    ("Location", "San Jose, CA"),
    None,
    ("Languages", "Python, SQL, Java, MATLAB, JavaScript"),
    ("ML", "pandas, scikit-learn, PyTorch, PyMC"),
    ("Data", "PostgreSQL, DuckDB, MongoDB, Spark, AWS EMR"),
    None,
    ("Featured", "Life expectancy forecast, R² 0.92"),
    ("", "random forest cut error 27% vs baseline"),
    ("Building", "NYC congestion pricing impact"),
    ("", "Pokémon GO IV rank checker"),
    ("", "Air quality and economic mobility in CA"),
    None,
    ("Contact", "linkedin.com/in/huy-dao-250736295"),
]
COLORS = ["#ff5f56", "#ffbd2e", "#27c93f", "#58a6ff", "#bc8cff", "#39c5cf", "#c9d1d9", "#8b949e"]


def render():
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">',
        "<style>",
        ".l{opacity:0;animation:in .4s ease-out forwards}",
        "@keyframes in{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}",
        "</style>",
        f'<rect width="{W}" height="{H}" rx="10" fill="#0d1117" stroke="#30363d"/>',
        '<circle cx="20" cy="18" r="5" fill="#ff5f56"/><circle cx="36" cy="18" r="5" fill="#ffbd2e"/>'
        '<circle cx="52" cy="18" r="5" fill="#27c93f"/>',
        f'<text x="{W / 2}" y="22" text-anchor="middle" fill="#8b949e" font-size="11">huy@github: ~/neofetch</text>',
    ]
    y, n = 62, 0

    def line(svg):
        nonlocal n
        out.append(f'<g class="l" style="animation-delay:{0.4 + n * 0.12:.2f}s">{svg}</g>')
        n += 1

    line(f'<text x="24" y="{y}" font-weight="bold"><tspan fill="{KEY}">huy</tspan>'
         f'<tspan fill="{TEXT}">@</tspan><tspan fill="{KEY}">github</tspan></text>')
    y += 18
    line(f'<text x="24" y="{y}" fill="#30363d">{"-" * 10}</text>')
    y += 24
    for item in LINES:
        if item is None:
            y += 10
            continue
        key, value = item
        label = f"{key}:" if key else ""
        line(f'<text x="24" y="{y}"><tspan fill="{KEY}" font-weight="bold">{escape(label)}</tspan>'
             f'<tspan x="124" fill="{TEXT}">{escape(value)}</tspan></text>')
        y += 20
    y += 8
    line("".join(f'<rect x="{24 + i * 28}" y="{y}" width="24" height="14" rx="2" fill="{c}"/>'
                 for i, c in enumerate(COLORS)))
    assert y + 14 < H, "card content overflows; raise H"
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")
