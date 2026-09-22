#!/usr/bin/env python3
"""
Link and asset checker for the built site (stdlib only).

Walks dist/**/*.html, extracts href/src attributes that start with "/",
and checks that the referenced file exists in dist/ (either directly or
as <path>/index.html). Also flags in-page anchors (href="#id") whose
target id does not exist on that page.

Usage: python tools/checklinks.py [dist_dir]
Exits 1 if any broken links/assets/anchors are found.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ATTR_RE = re.compile(r'''(?:href|src)\s*=\s*["']([^"']+)["']''', re.I)
ID_RE = re.compile(r'''\bid\s*=\s*["']([^"']+)["']''', re.I)


def resolve_path(dist: Path, url_path: str) -> Path:
    clean = url_path.split("#", 1)[0].split("?", 1)[0]
    rel = clean.lstrip("/")
    if rel == "":
        return dist / "index.html"
    p = dist / rel
    return p


def check_file(dist: Path, html_path: Path):
    """Returns (broken_links, broken_anchors) for one page."""
    text = html_path.read_text(encoding="utf-8", errors="replace")
    ids = set(ID_RE.findall(text))
    broken_links = []
    broken_anchors = []

    for m in ATTR_RE.finditer(text):
        target = m.group(1).strip()

        if target.startswith("#"):
            anchor = target[1:]
            if anchor and anchor not in ids:
                broken_anchors.append(target)
            continue

        if not target.startswith("/"):
            continue  # external, relative, mailto:, tel:, javascript:, data: — not our concern
        if target.startswith("//"):
            continue  # protocol-relative external URL

        clean = target.split("#", 1)[0].split("?", 1)[0]
        p = resolve_path(dist, clean)
        exists = p.exists() and p.is_file()
        if not exists and not clean.endswith((".html", ".xml", ".txt", ".json", ".ico", ".png", ".jpg",
                                               ".jpeg", ".svg", ".webp", ".css", ".js", ".webmanifest",
                                               ".woff", ".woff2", ".pdf")):
            # extensionless "clean" URL -> try <path>/index.html
            exists = (p / "index.html").exists()
        if not exists:
            broken_links.append(target)

    return broken_links, broken_anchors


def main(argv) -> int:
    dist = Path(argv[1]) if len(argv) > 1 else ROOT / "dist"
    if not dist.exists():
        print(f"error: {dist} does not exist — run `python build.py` first", file=sys.stderr)
        return 1

    pages = sorted(dist.rglob("*.html"))
    if not pages:
        print(f"error: no .html files found under {dist}", file=sys.stderr)
        return 1

    total_broken_links = 0
    total_broken_anchors = 0
    pages_with_issues = 0

    for page in pages:
        rel = page.relative_to(dist)
        broken_links, broken_anchors = check_file(dist, page)
        if broken_links or broken_anchors:
            pages_with_issues += 1
            print(f"\n{rel}")
            for link in broken_links:
                print(f"  BROKEN LINK   -> {link}")
            for anchor in broken_anchors:
                print(f"  BROKEN ANCHOR -> {anchor}")
            total_broken_links += len(broken_links)
            total_broken_anchors += len(broken_anchors)

    print(f"\nChecked {len(pages)} page(s) in {dist}")
    print(f"Broken links: {total_broken_links}  Broken anchors: {total_broken_anchors}  "
          f"Pages with issues: {pages_with_issues}")

    return 1 if (total_broken_links or total_broken_anchors) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
