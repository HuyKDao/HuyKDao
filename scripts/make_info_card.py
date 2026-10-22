"""Render the neofetch-style info card: assets/info-card.svg.

Featured and Building come from your public repos, so the daily workflow keeps
them current. Featured is the repo with the "featured" topic. Building is the
three most recently pushed other projects. Edit LINES for everything else, then
run: python scripts/make_info_card.py
"""
import base64
import json
import os
import re
import urllib.error
import urllib.request
from html import escape
from pathlib import Path

USER = "HuyKDao"
OUT = Path(__file__).resolve().parent.parent / "assets" / "info-card.svg"
SKIP = re.compile(r"coursework|labs|-plan$", re.I)  # class work and plans are not portfolio projects
FALLBACK_FEATURED = "life-expectancy-forecasting"  # used until a repo has the "featured" topic
# Second Featured line for repos with a result worth stating; otherwise the repo description is used.
HIGHLIGHTS = {"life-expectancy-forecasting": "random forest, R² 0.92, error cut 27%"}
MAX_CHARS = 42  # widest value that fits the card
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
    "PROJECTS",
    None,
    ("Contact", "linkedin.com/in/huy-dao-250736295"),
]
COLORS = ["#ff5f56", "#ffbd2e", "#27c93f", "#58a6ff", "#bc8cff", "#39c5cf", "#c9d1d9", "#8b949e"]


def api(path):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):  # optional: raises the rate limit in Actions
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    req = urllib.request.Request(f"https://api.github.com/{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def clip(text):
    """Cut at a word boundary so long titles still fit the card."""
    if len(text) <= MAX_CHARS:
        return text
    return text[: MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip(" ,:;-") + "…"


def title(repo):
    """README heading, else description, else repo name."""
    try:
        readme = base64.b64decode(api(f"repos/{USER}/{repo['name']}/readme")["content"]).decode("utf-8")
        m = re.search(r"^#\s+(.+?)\s*$", readme, re.M)
        if m:
            return re.sub(r"[*_`\[\]]|<[^>]+>", "", m.group(1)).strip()
    except urllib.error.HTTPError:  # repo has no README
        pass
    return repo["description"] or repo["name"]


def projects():
    repos = [
        r for r in api(f"users/{USER}/repos?sort=pushed&per_page=100")
        if not r["fork"] and not r["archived"] and r["name"] != USER and not SKIP.search(r["name"])
    ]
    if not repos:
        raise SystemExit("No public project repos found.")
    featured = (
        next((r for r in repos if "featured" in r.get("topics", [])), None)
        or next((r for r in repos if r["name"] == FALLBACK_FEATURED), repos[0])
    )
    lines = [("Featured", clip(title(featured)))]
    detail = HIGHLIGHTS.get(featured["name"]) or featured["description"]
    if detail:
        lines.append(("", clip(detail)))
    building = [r for r in repos if r is not featured][:3]
    lines += [("Building" if i == 0 else "", clip(title(r))) for i, r in enumerate(building)]
    return lines


def render(project_lines):
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
    for item in (x for i in LINES for x in (project_lines if i == "PROJECTS" else [i])):
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
    assert clip("Did NYC Congestion Pricing Speed Up Manhattan Trips?") == "Did NYC Congestion Pricing Speed Up…"
    assert clip("short") == "short"
    lines = projects()
    print("\n".join(f"{k:>9} {v}" for k, v in lines))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(lines), encoding="utf-8")
    print(f"wrote {OUT}")
