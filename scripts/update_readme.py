"""Auto-updates marked sections of README.md using the GitHub API.

Sections (put these markers in README.md):
  <!--START_SECTION:name--> ... <!--END_SECTION:name-->
Supported names: activity, projects, summary, updated
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "anjalitiwarics27-coder")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"
MAX_PROJECTS = 6
MAX_ACTIVITY = 6


def api(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "readme-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def esc(s):
    return (s or "—").replace("|", "\\|").replace("\n", " ")


def fmt_date(iso):
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")


def get_repos():
    repos = api(f"/users/{USER}/repos?per_page=100&sort=pushed&type=owner")
    return [
        r for r in repos
        if not r["fork"] and not r["archived"] and r["name"].lower() != USER.lower()
    ]


def projects_section():
    repos = sorted(
        get_repos(),
        key=lambda r: (r["stargazers_count"], r["pushed_at"]),
        reverse=True,
    )[:MAX_PROJECTS]
    if not repos:
        return "_No public projects yet._"
    rows = [
        "| 🚀 Project | 📝 Description | 💻 Language | ⭐ Stars | 🕒 Updated |",
        "|:---|:---|:---:|:---:|:---:|",
    ]
    for r in repos:
        rows.append(
            f"| [**{r['name']}**]({r['html_url']}) | {esc(r['description'])} | "
            f"{esc(r['language'])} | {r['stargazers_count']} | {fmt_date(r['pushed_at'])} |"
        )
    return "\n".join(rows)


def activity_section():
    events = api(f"/users/{USER}/events/public?per_page=50")
    lines = []
    for e in events:
        repo = e["repo"]["name"]
        link = f"[{repo}](https://github.com/{repo})"
        p = e.get("payload", {})
        t = e["type"]
        if t == "PushEvent":
            n = len(p.get("commits", []))
            text = f"🔨 Pushed {n} commit{'s' if n != 1 else ''} to {link}" if n else f"🔨 Pushed to {link}"
        elif t == "CreateEvent" and p.get("ref_type") == "repository":
            text = f"🆕 Created repository {link}"
        elif t == "PullRequestEvent":
            text = f"🔀 {p.get('action', 'updated').capitalize()} a pull request in {link}"
        elif t == "IssuesEvent":
            text = f"🐛 {p.get('action', 'updated').capitalize()} an issue in {link}"
        elif t == "WatchEvent":
            text = f"⭐ Starred {link}"
        elif t == "ForkEvent":
            text = f"🍴 Forked {link}"
        else:
            continue
        lines.append(f"- {text} · `{fmt_date(e['created_at'])}`")
        if len(lines) >= MAX_ACTIVITY:
            break
    return "\n".join(lines) or "_No recent public activity._"


def summary_section():
    u = api(f"/users/{USER}")
    stars = sum(r["stargazers_count"] for r in get_repos())
    return (
        f"📦 **{u['public_repos']}** public repos · "
        f"⭐ **{stars}** stars earned · "
        f"👥 **{u['followers']}** followers · "
        f"🤝 **{u['following']}** following"
    )


def updated_section():
    ist = timezone(timedelta(hours=5, minutes=30))
    return f"<sub>🤖 Auto-updated on {datetime.now(ist).strftime('%d %b %Y, %I:%M %p')} IST</sub>"


SECTIONS = {
    "activity": activity_section,
    "projects": projects_section,
    "summary": summary_section,
    "updated": updated_section,
}


def replace(text, name, content):
    pattern = re.compile(
        rf"(<!--START_SECTION:{name}-->)(.*?)(<!--END_SECTION:{name}-->)", re.S
    )
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}", text)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    for name, fn in SECTIONS.items():
        try:
            text = replace(text, name, fn())
            print(f"updated: {name}")
        except Exception as ex:  # keep going if one section fails
            print(f"skipped {name}: {ex}")
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
