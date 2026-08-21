from __future__ import annotations

import re
from pathlib import Path


READER_PROMPTS = {
    "在小说阅读器读本章",
    "去阅读",
    "在小说阅读器中沉浸阅读",
}


def title_key(title: str) -> str:
    value = title.replace("〔引用摘要〕", "")
    return re.sub(r"[\s!！?？·，,。:：]+", "", value).casefold()


def normalize_title(title: str) -> str:
    title = title.strip().lstrip("#").strip()
    title = re.sub(r"\s*[!！]\s*$", "！", title)
    return title


def normalize_line(line: str) -> str:
    line = line.replace("&nbsp;", "").replace("\u00a0", " ").strip()
    return re.sub(r"[ \t]+", " ", line)


def parse_downloaded_markdown(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    raw_lines = source.splitlines()
    title_line = next((line for line in raw_lines if line.strip().startswith("#")), "")
    title = normalize_title(title_line)

    date_match = re.search(
        r"_(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日(?:\s+(\d{1,2}:\d{2}))?_",
        source,
    )
    if not date_match:
        raise ValueError(f"Cannot find article date in {path.name}")
    year, month, day = (int(date_match.group(i)) for i in range(1, 4))
    publish_time = date_match.group(4) or ""

    metadata_line = next((normalize_line(line) for line in raw_lines if line.strip().startswith("原创")), "")
    metadata_parts = metadata_line.split()
    author = metadata_parts[1] if len(metadata_parts) > 1 else ""
    account = metadata_parts[-1] if len(metadata_parts) > 2 else ""

    body_lines: list[str] = []
    for raw in raw_lines:
        line = normalize_line(raw)
        if not line:
            body_lines.append("")
            continue
        if raw == title_line or line.startswith("原创") or (line.startswith("_") and "年" in line):
            continue
        if line in READER_PROMPTS:
            continue
        if "扫描下方二维码" in line or "扫下方二维码" in line or line.startswith("!["):
            break
        if line == author or re.fullmatch(r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日", line):
            continue
        section = re.match(r"^[（(]\s*([一二三四五六七八九十\d]+)\s*[）)]\s*(.*)$", line)
        if section:
            suffix = section.group(2).strip()
            body_lines.append(f"### （{section.group(1)}）{suffix}".rstrip())
        else:
            body_lines.append(line)

    while body_lines and not body_lines[0]:
        body_lines.pop(0)
    while body_lines and not body_lines[-1]:
        body_lines.pop()

    source_note = f"> 原文作者：{author or '未注明'}"
    if account:
        source_note += f" · 公众号：{account}"
    source_note += f" · 发布于 {year}年{month}月{day}日"
    if publish_time:
        source_note += f" {publish_time}"
    body_lines.extend(["", source_note])

    text = " ".join(line.strip() for line in body_lines if line.strip())
    return {
        "year": year,
        "date": f"{year:04d}-{month:02d}-{day:02d}",
        "month": month,
        "title": title,
        "body_lines": body_lines,
        "text": text,
        "author": author,
        "account": account,
        "source_file": path.name,
    }


def parse_downloaded_articles(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    articles: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for path in sorted(directory.glob("*.md")):
        article = parse_downloaded_markdown(path)
        key = (article["year"], title_key(article["title"]))
        if key in seen:
            raise ValueError(f"Duplicate imported article title: {article['title']}")
        seen.add(key)
        articles.append(article)
    return articles
