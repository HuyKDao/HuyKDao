"""Rewrite the README's Today-on-GitHub section from my public activity.

The old Featured project block never changed, so this replaces it: it pulls
the day's public events (Pacific time, since that's where I am) from the
GitHub API and rewrites whatever sits between the TODAY markers. If today is
quiet so far, it falls back to the most recent active day so the section never
goes stale. Run: python scripts/today.py
"""
import datetime as dt
import json
import os
import urllib.request
import zoneinfo
from pathlib import Path

USER = "HuyKDao"
README = Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- TODAY:START -->", "<!-- TODAY:END -->"
MAX_BULLETS = 6
CLIP = {"commit": 60, "title": 56}
try:
    HOME = zoneinfo.ZoneInfo("America/Los_Angeles")  # San Jose local time
except zoneinfo.ZoneInfoNotFoundError:  # bare container without tzdata
    HOME = dt.timezone.utc


def api(path):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):  # optional: raises the rate limit in Actions
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    req = urllib.request.Request(f"https://api.github.com/{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_events():
    """Up to 300 public events, newest first (the API keeps ~90 days)."""
    out = []
    for page in range(1, 4):
        batch = api(f"users/{USER}/events/public?per_page=100&page={page}")
        out.extend(batch)
        if len(batch) < 100:
            break
    return out


def when(event):
    return dt.datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))


def clip(text, kind):
    """Collapse to one line, drop markdown breakers, trim to fit a bullet."""
    text = " ".join((text or "").split()).replace("[", "").replace("]", "").replace("`", "")
    if len(text) <= CLIP[kind]:
        return text
    return text[: CLIP[kind] - 1].rsplit(" ", 1)[0].rstrip(" ,:;-") + "…"


def describe(event):
    """(time, group key, bullet parts) for events worth listing, else None."""
    kind, p = event["type"], event.get("payload") or {}
    repo = event["repo"]["name"]  # "HuyKDao/name"
    if repo == f"{USER}/{USER}":
        return None  # profile-README housekeeping is not project work
    link = f"[{repo.split('/', 1)[1]}](https://github.com/{repo})"
    t = when(event)
    if kind == "PushEvent":
        commits = p.get("commits") or []
        return t, ("push", repo), {
            "link": link,
            "n": p.get("size") or len(commits) or 1,
            "msg": commits[-1]["message"] if commits else "",
        }
    if kind == "PullRequestEvent" and p.get("action") in ("opened", "closed") and p.get("pull_request"):
        pr = p["pull_request"]
        verb = "merged" if p["action"] == "closed" and pr.get("merged") else p["action"]
        return t, ("pr", repo, pr["number"]), {
            "link": link, "verb": verb, "n": pr["number"],
            "title": clip(pr.get("title"), "title"), "url": pr["html_url"],
        }
    if kind == "IssuesEvent" and p.get("action") in ("opened", "closed", "reopened") and p.get("issue"):
        i = p["issue"]
        return t, ("issue", repo, i["number"]), {
            "link": link, "verb": p["action"], "n": i["number"],
            "title": clip(i.get("title"), "title"), "url": i["html_url"],
        }
    if kind == "IssueCommentEvent" and p.get("issue"):
        i = p["issue"]
        return t, ("note", repo, i["number"]), {
            "link": link, "verb": "Commented on", "n": i["number"],
            "title": clip(i.get("title"), "title"), "url": i["html_url"],
        }
    if kind == "PullRequestReviewEvent" and p.get("pull_request"):
        pr = p["pull_request"]
        return t, ("note", repo, pr["number"]), {
            "link": link, "verb": "Reviewed", "n": pr["number"],
            "title": clip(pr.get("title"), "title"), "url": pr["html_url"],
        }
    if kind == "CreateEvent":
        if p.get("ref_type") == "repository":
            return t, ("made", repo), {"link": link}
        if p.get("ref_type") == "tag":
            return t, ("tag", repo, p.get("ref") or ""), {"link": link, "ref": p.get("ref") or ""}
    if kind == "ReleaseEvent" and p.get("release"):
        ref = p["release"].get("tag_name") or ""
        return t, ("tag", repo, ref), {"link": link, "ref": ref}
    if kind == "PublicEvent":
        return t, ("made", repo), {"link": link}
    return None  # stars, forks, branch creates and the rest stay off the list


def bullet(kind, p):
    if kind == "push":
        n, msg = p["n"], clip(p["msg"], "commit")
        tail = f" — *{msg}*" if msg else ""
        return f"🚀 Pushed **{n} commit{'s' if n != 1 else ''}** to {p['link']}{tail}"
    if kind == "pr":
        return f"🔀 **{p['verb'].capitalize()}** PR [#{p['n']} {p['title']}]({p['url']}) in {p['link']}"
    if kind == "issue":
        return f"🐛 **{p['verb'].capitalize()}** issue [#{p['n']} {p['title']}]({p['url']}) in {p['link']}"
    if kind == "note":
        return f"💬 {p['verb']} [#{p['n']} {p['title']}]({p['url']}) in {p['link']}"
    if kind == "made":
        return f"✨ Started a new project: {p['link']}"
    return f"🏷️ Tagged **{p['ref']}** in {p['link']}"  # kind == "tag"


def summarize(events):
    """One bullet per activity, newest first; pushes to the same repo add up."""
    groups = {}
    for e in events:  # newest first, so the first sighting wins ordering and "latest"
        d = describe(e)
        if not d:
            continue
        t, key, parts = d
        if key not in groups:
            groups[key] = [t, parts]
        elif key[0] == "push":
            groups[key][1]["n"] += parts["n"]
    ranked = sorted(groups.items(), key=lambda kv: kv[1][0], reverse=True)
    return [bullet(key[0], parts) for key, (_, parts) in ranked[:MAX_BULLETS]]


def block(events):
    """The full markdown section: today's activity, or the last active day."""
    days = {}
    for e in events:
        days.setdefault(when(e).astimezone(HOME).date(), []).append(e)
    today = dt.datetime.now(HOME).date()
    day = today if today in days else max(days) if days else None
    shown = day or today
    body = summarize(days[day]) if day else []
    body = body or ["🌱 Nothing public yet — new commits are on the way."]
    label = "Today" if shown == today else "Last active"
    lines = [f"### {label} on GitHub · {shown:%a, %b %d}", ""]
    lines += [f"- {b}" for b in body]
    lines += ["", "<sub>Updated automatically from my public activity every few hours.</sub>"]
    return "\n".join(lines)


def splice(text, section):
    """Swap the block between the markers, leaving the rest of the file alone."""
    i, j = text.index(START) + len(START), text.index(END)
    return text[:i] + "\n" + section + "\n" + text[j:]


def _selfcheck():
    assert clip("short message", "commit") == "short message"
    long = clip("add time-aware interpolation for gaps longer than five years in panel data", "commit")
    assert long.endswith("…") and len(long) <= 60
    assert clip("drop [wip] `notes`", "commit") == "drop wip notes"
    push = {"type": "PushEvent", "created_at": "2026-10-24T18:00:00Z", "repo": {"name": "HuyKDao/x"},
            "payload": {"size": 2, "commits": [{"message": "latest\n\nbody"}]}}
    again = dict(push, created_at="2026-10-24T20:00:00Z")
    pr = {"type": "PullRequestEvent", "created_at": "2026-10-24T19:00:00Z", "repo": {"name": "HuyKDao/x"},
          "payload": {"action": "opened", "pull_request": {"number": 4, "title": "Fix gaps", "merged": False,
                                                           "html_url": "https://github.com/HuyKDao/x/pull/4"}}}
    star = {"type": "WatchEvent", "created_at": "2026-10-24T21:00:00Z", "repo": {"name": "someone/y"}, "payload": {}}
    bullets = summarize([star, again, pr, push])  # newest first, star skipped
    assert len(bullets) == 2 and bullets[0].startswith("🚀")  # push group is newest (20:00)
    assert bullets[0].startswith("🚀 Pushed **4 commits**") and "latest" in bullets[0]
    assert bullets[1].startswith("🔀")
    old = f"intro\n\n{START}\nstale\n{END}\n\noutro"
    assert splice(old, "fresh") == f"intro\n\n{START}\nfresh\n{END}\n\noutro"


if __name__ == "__main__":
    _selfcheck()
    section = block(fetch_events())
    print(section)
    try:
        readme = README.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"{README} not found.")
    try:
        README.write_text(splice(readme, section), encoding="utf-8")
    except ValueError:
        raise SystemExit(f"{START} / {END} markers missing from {README}.")
    print(f"\nwrote {README}")
