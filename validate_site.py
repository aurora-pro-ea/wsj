from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from build_site import SITE_URL


def internal_target(root: Path, href: str) -> Path | None:
    if not href.startswith("/") or href.startswith("//"):
        return None
    path = href.split("#", 1)[0].split("?", 1)[0]
    if path == "/": return root / "index.html"
    if path.endswith("/"): return root / path.lstrip("/") / "index.html"
    return root / path.lstrip("/")


def meta(source: str, prop: str, name: bool = False) -> str:
    attr = "name" if name else "property"
    m = re.search(rf'<meta\s+{attr}="{re.escape(prop)}"\s+content="([^"]*)"', source)
    return html.unescape(m.group(1)) if m else ""


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "dist").resolve()
    errors: list[str] = []
    required = ["index.html", "2024/index.html", "2025/index.html", "2026/index.html", "assets/style.css", "assets/script.js", "search-index.json", "sitemap.xml", "feed.xml", "_headers"]
    for relative in required:
        if not (root / relative).is_file(): errors.append(f"missing required file: {relative}")

    try: records = json.loads((root / "search-index.json").read_text(encoding="utf-8"))
    except Exception as exc: records = []; errors.append(f"invalid search-index.json: {exc}")
    article_pages = list((root / "articles").glob("*/index.html"))
    if len(records) != len(article_pages): errors.append(f"article count mismatch: index={len(records)}, html={len(article_pages)}")
    ids = [r.get("id") for r in records]
    if len(ids) != len(set(ids)): errors.append("duplicate article ids in search index")

    content_pattern = re.compile(r'<div class="article-content">(.*?)</div>\s*<div class="article-footer-nav">', re.S)
    for page in article_pages:
        source = page.read_text(encoding="utf-8")
        match = content_pattern.search(source)
        text = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() if match else ""
        if not text: errors.append(f"empty article body: {page.relative_to(root).as_posix()}")
        if meta(source, "og:title") == "": errors.append(f"missing og:title: {page.relative_to(root).as_posix()}")
        if meta(source, "og:description") == "": errors.append(f"missing og:description: {page.relative_to(root).as_posix()}")
        if meta(source, "og:image") == "": errors.append(f"missing og:image: {page.relative_to(root).as_posix()}")
        if meta(source, "twitter:card", True) != "summary_large_image": errors.append(f"missing twitter card: {page.relative_to(root).as_posix()}")
        image = meta(source, "og:image")
        if image.startswith("https://"):
            rel = image.split(SITE_URL, 1)[-1].lstrip("/")
            if not (root / rel).is_file(): errors.append(f"missing OG image: {rel}")

    for page in root.rglob("*.html"):
        source = page.read_text(encoding="utf-8")
        for href in re.findall(r'href="([^"]+)"', source):
            target = internal_target(root, href)
            if target is not None and not target.exists(): errors.append(f"broken link: {page.relative_to(root).as_posix()} -> {href}")

    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8") if (root / "sitemap.xml").exists() else ""
    if "__SITE_URL__" in sitemap: errors.append("sitemap still contains __SITE_URL__ placeholder")
    if not sitemap.count("<url>") >= len(records) + 4: errors.append("sitemap has fewer URLs than expected")

    if errors:
        print("Validation failed:")
        for error in errors[:80]: print(f"- {error}")
        if len(errors) > 80: print(f"- ... and {len(errors)-80} more")
        return 1
    print(f"Validation passed: {len(records)} articles, {len(list(root.rglob('*')))} paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
