"""Draw the Braun-style star-history chart (light + dark SVG).

Data source:
  1. GitHub REST API with GITHUB_TOKEN (stargazers, star+json timestamps) — used by the weekly Action.
  2. Fallback: assets/star-times.json {"created_at", "starred_at": [...]} or {"created_at", "count"}.
"""
import json
import os
import pathlib
import urllib.request
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[2]
ASSETS = REPO / "assets"
SLUG = os.environ.get("REPO_SLUG", "Xarfa/White-Feather-Fountain-Pen")


def next_page_url(resp):
    """Parse the Link response header for rel="next" (urllib has no .links)."""
    link = resp.headers.get("Link") or ""
    for part in link.split(","):
        seg = part.split(";")
        if len(seg) >= 2 and 'rel="next"' in seg[1]:
            return seg[0].strip().strip("<>")
    return None


def fetch_stars():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    url = f"https://api.github.com/repos/{SLUG}/stargazers?per_page=100&page=1"
    times = []
    while url:
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github.star+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "star-chart",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.load(r)
            times += [s["starred_at"] for s in batch]
            url = next_page_url(r)
    req = urllib.request.Request(f"https://api.github.com/repos/{SLUG}", headers={
        "Authorization": f"Bearer {token}", "User-Agent": "star-chart"})
    with urllib.request.urlopen(req, timeout=30) as r:
        created = json.load(r)["created_at"]
    return created, sorted(times)


def load_fallback():
    data = json.loads((ASSETS / "star-times.json").read_text())
    if "starred_at" in data:
        return data["created_at"], sorted(data["starred_at"])
    count = int(data["count"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return data["created_at"], [now] * count


def parse(t):
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


W, H = 1200, 420
ML, MR, MT, MB = 64, 48, 74, 56


def nice_ymax(n):
    for c in (2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000):
        if n <= c:
            return c
    return n * 2


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def chart(created, times, dark):
    if dark:
        bg, grid, axis, line, sub = "#0D1117", "#21262D", "#8B949E", "#E6EDF3", "#6E7681"
    else:
        bg, grid, axis, line, sub = "#FFFFFF", "#ECEBE6", "#6E6F6B", "#1A1B1D", "#9A9B95"
    orange = "#E8571A"

    t0, t1 = parse(created).timestamp(), datetime.now(timezone.utc).timestamp()
    span = max(t1 - t0, 3600)
    ymax = nice_ymax(len(times))
    iw, ih = W - ML - MR, H - MT - MB
    X = lambda t: ML + iw * (t - t0) / span
    Y = lambda v: MT + ih * (1 - v / ymax)

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="Helvetica,Arial,sans-serif">']
    p.append(f'<rect width="{W}" height="{H}" fill="{bg}"/>')
    # header
    p.append(f'<text x="{ML}" y="34" font-size="15" letter-spacing="2.4" fill="{axis}">STARS</text>')
    p.append(f'<text x="{ML + 74}" y="34" font-size="15" letter-spacing="0.4" fill="{sub}">{esc(SLUG)}</text>')
    p.append(f'<text x="{W - MR}" y="34" font-size="22" font-weight="bold" fill="{line}" text-anchor="end">{len(times)}</text>')
    # horizontal gridlines + y labels
    for gv in range(0, ymax + 1, max(1, ymax // 4 if ymax <= 10 else ymax // 5)):
        if ymax > 10 and gv % 5:
            continue
        y = Y(gv)
        p.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{W - MR}" y2="{y:.1f}" stroke="{grid}" stroke-width="1"/>')
        p.append(f'<text x="{ML - 10}" y="{y + 4:.1f}" font-size="12" fill="{axis}" text-anchor="end">{gv}</text>')
    # x labels: start / end dates
    d0 = datetime.fromtimestamp(t0, timezone.utc).strftime("%b %d, %Y")
    d1 = datetime.fromtimestamp(t1, timezone.utc).strftime("%b %d, %Y")
    p.append(f'<text x="{ML}" y="{H - MB + 26}" font-size="12" fill="{axis}">{d0}</text>')
    p.append(f'<text x="{W - MR}" y="{H - MB + 26}" font-size="12" fill="{axis}" text-anchor="end">{d1}</text>')
    # step line: one vertical step per star
    pts = [(X(t0), Y(0))]
    v = 0
    for t in times:
        tx = X(parse(t).timestamp())
        pts.append((tx, Y(v)))
        v += 1
        pts.append((tx, Y(v)))
    pts.append((X(t1), Y(v)))
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    p.append(f'<path d="{d}" fill="none" stroke="{line}" stroke-width="2.5" stroke-linejoin="miter"/>')
    # orange end dot
    ex, ey = pts[-1]
    p.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{orange}"/>')
    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    data = fetch_stars() or load_fallback()
    created, times = data
    (ASSETS / "star-history.svg").write_text(chart(created, times, dark=False))
    (ASSETS / "star-history-dark.svg").write_text(chart(created, times, dark=True))
    print(f"chart written: {len(times)} stars, since {created}")
