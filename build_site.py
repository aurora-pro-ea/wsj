from __future__ import annotations

import html
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from extra_articles import parse_extra_articles
from wechat_imports import parse_downloaded_articles, title_key

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist"
SITE_URL = "https://wushujian.pages.dev"
SOURCE_FILES = [
    ROOT / "2024年文章整理.md",
    ROOT / "2025年图片文章整理.md",
    ROOT / "2026年图片文章整理.md",
]
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_REGULAR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\ufeff", "")
    text = text.replace("．", "。").replace("，", "，")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def clean_ocr_line(line: str) -> str:
    line = normalize_text(line)
    if not line:
        return ""
    # Common OCR-only date/header remnants. Keep real prose intact.
    if re.fullmatch(r"[\d\s:/·•．\-—_~]+", line) and len(line) <= 32:
        return ""
    if re.fullmatch(r"[\d\s:：./·•．\-—_~]+[卜一二三四五六七八九十]?", line) and len(line) <= 32:
        return ""
    return line


def slug_for(year: int, article_date: str, ordinal: int) -> str:
    return f"{year}-{article_date[5:]}-{ordinal:03d}"


def inline_md(text: str) -> str:
    value = esc(text.strip())
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", value)
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', value)
    return value


def render_fragment(lines: list[str]) -> tuple[str, list[tuple[str, str]]]:
    blocks: list[str] = []
    toc: list[tuple[str, str]] = []
    paragraph: list[str] = []
    quote: list[str] = []
    list_items: list[str] = []
    heading_number = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = "".join(part.strip() for part in paragraph).strip()
            if text:
                blocks.append(f"<p>{inline_md(text)}</p>")
        paragraph = []

    def flush_quote() -> None:
        nonlocal quote
        if quote:
            text = "<br>".join(inline_md(part) for part in quote)
            blocks.append(f"<blockquote>{text}</blockquote>")
        quote = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            body = "".join(f"<li>{inline_md(item)}</li>" for item in list_items)
            blocks.append(f"<ol>{body}</ol>")
        list_items = []

    for raw in lines:
        line = clean_ocr_line(raw)
        if not line or line == "---":
            flush_paragraph(); flush_quote(); flush_list(); continue
        if line.startswith("### "):
            flush_paragraph(); flush_quote(); flush_list()
            heading = line[4:].strip()
            heading_number += 1
            anchor = f"section-{heading_number}"
            toc.append((anchor, heading))
            blocks.append(f'<h3 id="{anchor}">{inline_md(heading)}</h3>')
            continue
        if line.startswith("> ") or line == ">":
            flush_paragraph(); flush_list()
            quote.append(line[2:] if line.startswith("> ") else "")
            continue
        list_match = re.match(r"^(?:[-*]|\d+[.)])\s+(.+)$", line)
        if list_match:
            flush_paragraph(); flush_quote(); list_items.append(list_match.group(1)); continue
        flush_quote(); flush_list(); paragraph.append(line)
    flush_paragraph(); flush_quote(); flush_list()
    return "\n".join(blocks), toc


def parse_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    source = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^##\s+(\d{4}-\d{2}-\d{2})｜(.+?)\s*$", source, re.M))
    articles: list[dict] = []
    year = int(path.name[:4])
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        raw_body = source[match.end():end]
        raw_body = re.sub(r"^\s*---\s*$", "", raw_body, flags=re.M)
        body_lines = [clean_ocr_line(x) for x in raw_body.strip().splitlines()]
        body_lines = [x for x in body_lines]
        article_date = match.group(1)
        title = match.group(2).strip()
        text = " ".join(line.strip() for line in body_lines if line.strip())
        articles.append({"year": year, "date": article_date, "month": int(article_date[5:7]), "title": title,
                         "body_lines": body_lines, "text": text, "author": "", "account": "", "source_file": path.name})
    return articles


def make_excerpt(text: str, length: int = 120) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"[`*_>#]+", "", text)).strip()
    return text if len(text) <= length else text[:length].rstrip() + "…"


def make_description(article: dict, length: int = 150) -> str:
    # Prefer the first substantial prose paragraph instead of OCR headers/noise.
    for raw in article["body_lines"]:
        line = re.sub(r"^#+\s*", "", raw).strip()
        line = re.sub(r"^>\s*", "", line)
        if len(line) >= 28 and not re.fullmatch(r"[\d\s:/：·•．\-—_~]+", line):
            return make_excerpt(line, length)
    return make_excerpt(article["text"], length)


def reading_time(text: str) -> int:
    # Chinese long-form reading estimate: ~420 Chinese chars/minute.
    chars = len(re.sub(r"\s+", "", text))
    return max(1, round(chars / 420))


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


_FONT_CACHE = {}

def _font(path: str, size: int):
    from PIL import ImageFont
    key=(path,size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key]=ImageFont.truetype(path,size)
    return _FONT_CACHE[key]

def make_og_image(article: dict, target: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    W, H = 1200, 630
    bg, ink, accent, muted = (244, 240, 232), (27, 27, 26), (164, 59, 45), (116, 111, 102)
    image = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(image)
    regular_path = FONT_REGULAR if Path(FONT_REGULAR).exists() else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold_path = FONT_BOLD if Path(FONT_BOLD).exists() else regular_path
    font_brand = _font(bold_path, 34)
    font_title = _font(bold_path, 58)
    font_date = _font(regular_path, 25)
    font_desc = _font(regular_path, 24)
    draw.rounded_rectangle((38, 38, W - 38, H - 38), radius=28, outline=(217, 210, 197), width=2)
    draw.text((78, 72), "WSJ · 文章档案", font=font_brand, fill=ink)
    draw.text((78, 140), article["title"][:34], font=font_title, fill=ink)
    draw.text((78, 218), article["date"], font=font_date, fill=accent)
    desc = make_description(article, 78)
    words = []
    current = ""
    for ch in desc:
        if len(current) >= 38:
            words.append(current); current = ""
        current += ch
    if current: words.append(current)
    y = 280
    for line in words[:3]:
        draw.text((78, y), line, font=font_desc, fill=muted)
        y += 40
    draw.line((78, 530, W - 78, 530), fill=(217, 210, 197), width=2)
    draw.text((78, 550), "把文章，留在时间里。", font=font_date, fill=muted)
    image.save(target, format="PNG", optimize=True)


def shell_page(title: str, description: str, body: str, active_year: str = "", *, article: dict | None = None) -> str:
    year_links = []
    for year in (2024, 2025, 2026):
        active = ' class="active"' if str(year) == active_year else ""
        year_links.append(f'<a{active} href="/{year}/">{year}</a>')
    canonical = f"{SITE_URL}{article['url']}" if article else SITE_URL + (f"/{active_year}/" if active_year else "/")
    desc = description or "WSJ文章档案"
    og_image = f"{SITE_URL}{article['og_image']}" if article else f"{SITE_URL}/assets/og-default.png"
    og_type = "article" if article else "website"
    article_meta = ""
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Article" if article else "WebSite",
        "name": title,
        "url": canonical,
        "description": desc,
    }
    if article:
        article_meta = f'<meta property="article:published_time" content="{esc(article["date"])}">\n  <meta property="article:author" content="{esc(article.get("author") or "")}">'
        jsonld.update({"headline": article["title"], "datePublished": article["date"], "dateModified": article["date"],
                       "author": {"@type": "Person", "name": article.get("author") or "武书剑"},
                       "image": [og_image], "isPartOf": {"@type": "WebSite", "name": "WSJ文章档案", "url": SITE_URL}})
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} · WSJ文章档案</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{esc(canonical)}">
  <meta name="theme-color" content="#171717">
  <meta property="og:type" content="{og_type}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:image" content="{esc(og_image)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{esc(title)}">
  <meta property="og:site_name" content="WSJ文章档案">
  {article_meta}
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(desc)}">
  <meta name="twitter:image" content="{esc(og_image)}">
  <meta name="twitter:image:alt" content="{esc(title)}">
  <link rel="stylesheet" href="/assets/style.css">
  <link rel="manifest" href="/site.webmanifest">
  <script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False, separators=(",", ":"))}</script>
</head>
<body{ ' class="article-page" data-article-url="' + esc(article['url']) + '"' if article else ''}>
  <div class="reading-progress" id="reading-progress"></div>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="/">WSJ<span>·</span>文章档案</a>
      <nav class="year-nav" aria-label="年度导航">{''.join(year_links)}</nav>
      <div class="header-actions">
        <label class="search-box" aria-label="搜索文章"><span aria-hidden="true">⌕</span><input id="site-search" type="search" placeholder="搜索标题或正文" autocomplete="off"></label>
        <button class="icon-button" id="theme-toggle" type="button" aria-label="切换深色模式">☾</button>
        <button class="icon-button" id="reader-settings" type="button" aria-label="阅读设置">Aa</button>
        {('<button class="icon-button" id="share-button" type="button" aria-label="分享文章">↗</button>' if article else '')}
        <button class="icon-button menu-button" id="menu-toggle" type="button" aria-label="打开菜单">☰</button>
      </div>
    </div>
    <div class="search-panel" id="search-panel" hidden><div class="search-panel-meta" id="search-meta"></div><div id="search-results" class="search-results"></div></div>
  </header>
  <div class="reader-panel" id="reader-panel" hidden>
    <div><b>阅读设置</b><button id="reader-close" type="button">×</button></div>
    <label>字号 <input id="font-size-range" type="range" min="15" max="22" step="1"><output id="font-size-value"></output></label>
    <label>行距 <input id="line-height-range" type="range" min="1.7" max="2.3" step="0.1"><output id="line-height-value"></output></label>
    <button id="reader-reset" type="button">恢复默认</button>
  </div>
  <div class="share-panel" id="share-panel" hidden>
    <div><b>分享这篇文章</b><button id="share-close" type="button">×</button></div>
    <a id="share-x" target="_blank" rel="noopener">𝕏 X</a><a id="share-facebook" target="_blank" rel="noopener">f Facebook</a><a id="share-telegram" target="_blank" rel="noopener">✈ Telegram</a><button id="copy-link" type="button">🔗 复制链接</button>
  </div>
  <main>{body}</main>
  <footer class="site-footer"><div>WSJ文章档案 · 2024—2026</div><div>静态发布 · 适配桌面与移动设备</div></footer>
  <script src="/assets/script.js" defer></script>
</body>
</html>'''


def article_card(article: dict) -> str:
    return f'''<article class="article-card"><div class="card-date">{article['date']}</div><h3><a href="{article['url']}">{esc(article['title'])}</a></h3><p>{esc(article['description'])}</p><div class="card-meta">{article['word_count']} 字 · 约 {article['reading_time']} 分钟</div><a class="read-more" href="{article['url']}">继续阅读 <span>→</span></a></article>'''


def build() -> tuple[list[dict], Path]:
    og_jobs: list[tuple[dict, Path]] = []
    old_ids = load_json(ROOT / "article_ids.json", {})
    overrides = load_json(ROOT / "data" / "metadata_overrides.json", {})
    if OUT.exists():
        for child in OUT.iterdir():
            if child.name in {"_headers"}:
                continue
            if child.is_dir(): shutil.rmtree(child)
            else: child.unlink()
    (OUT / "assets" / "og").mkdir(parents=True, exist_ok=True)
    # Source assets are canonical; fall back to the current dist assets during migration.
    assets_src = ROOT / "assets"
    if assets_src.exists():
        for p in assets_src.iterdir():
            target = OUT / "assets" / p.name
            if p.is_dir(): shutil.copytree(p, target, dirs_exist_ok=True)
            else: shutil.copy2(p, target)
    else:
        for name in ("style.css", "script.js"):
            src = ROOT / "dist" / "assets" / name
            if src.exists(): shutil.copy2(src, OUT / "assets" / name)
    if (ROOT / "_headers").exists():
        shutil.copy2(ROOT / "_headers", OUT / "_headers")

    articles: list[dict] = []
    for source in SOURCE_FILES:
        articles.extend(parse_file(source))
    articles.extend(parse_extra_articles())
    downloaded_articles = parse_downloaded_articles(ROOT / "wechat-imports")
    downloaded_keys = {(a["year"], title_key(a["title"])) for a in downloaded_articles}
    articles = [a for a in articles if (a["year"], title_key(a["title"])) not in downloaded_keys]
    articles.extend(downloaded_articles)
    articles.sort(key=lambda a: (a["date"], a["title"]))

    used = set(old_ids.values())
    counters: defaultdict[int, int] = defaultdict(int)
    seen_keys: defaultdict[str, int] = defaultdict(int)
    for article in articles:
        key = f"{article['date']}|{article['title']}"
        seen_keys[key] += 1
        map_key = key if seen_keys[key] == 1 else f"{key}#{seen_keys[key]}"
        slug = old_ids.get(map_key)
        if not slug:
            counters[article["year"]] = max(counters[article["year"]], max([int(x.split("-")[-1]) for x in used if x.startswith(str(article["year"])+"-")] or [0]))
            counters[article["year"]] += 1
            slug = slug_for(article["year"], article["date"], counters[article["year"]])
            while slug in used:
                counters[article["year"]] += 1
                slug = slug_for(article["year"], article["date"], counters[article["year"]])
            old_ids[map_key] = slug
            used.add(slug)
        article["slug"] = slug
        article["url"] = f"/articles/{slug}/"
        override = overrides.get(key, {}) if isinstance(overrides, dict) else {}
        article.update({k: v for k, v in override.items() if k in {"title", "description", "author", "account"}})
        article["html_body"], article["toc"] = render_fragment(article["body_lines"])
        if not article["html_body"]:
            article["text"] = "该条目未识别到有效正文内容。"
            article["html_body"] = "<p>该条目未识别到有效正文内容。</p>"
        article["description"] = article.get("description") or make_description(article)
        article["word_count"] = len(re.sub(r"\s+", "", article["text"]))
        article["reading_time"] = reading_time(article["text"])
        article["og_image"] = f"/assets/og/{slug}.png"
        og_jobs.append((article, OUT / article["og_image"].lstrip("/")))

    if og_jobs:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda pair: make_og_image(*pair), og_jobs))

    save_json(ROOT / "article_ids.json", old_ids)
    by_year: defaultdict[int, list[dict]] = defaultdict(list)
    for a in articles: by_year[a["year"]].append(a)

    search_index = [{"id": a["slug"], "year": a["year"], "date": a["date"], "month": a["month"], "title": a["title"], "excerpt": a["description"], "url": a["url"], "search": f"{a['title']} {a['text']}"} for a in articles]
    (OUT / "search-index.json").write_text(json.dumps(search_index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    stats = "".join(f'<div class="stat"><strong>{len(by_year[y])}</strong><span>{y}年文章</span></div>' for y in (2024, 2025, 2026))
    latest = "".join(article_card(a) for a in reversed(articles[-12:]))
    home_body = f'''<section class="hero-wrap"><div class="hero-copy"><p class="eyebrow">PERSONAL ARCHIVE · 2024—2026</p><h1>把文章，<em>留在时间里。</em></h1><p class="hero-lede">三年的文字，按日期、月份和阅读路径重新编排。适合慢慢读，也方便随时查找。</p><div class="hero-actions"><a class="button primary" href="/2026/">浏览最新文章</a><a class="button ghost" href="#latest">查看最近更新</a><button class="button ghost" id="random-article" type="button">🎲 随机阅读</button></div></div><div class="hero-mark"><span>WSJ</span><small>READ<br>THINK<br>REMEMBER</small></div></section><section class="stats-row" aria-label="文章统计">{stats}<div class="stat"><strong>{len(articles)}</strong><span>篇文章</span></div></section><section class="archive-intro"><div><p class="eyebrow">ARCHIVE MAP</p><h2>按年份进入</h2></div><p>每篇文章都有稳定的独立地址；年度页按月份分组，文章页保留章节锚点与阅读进度。</p></section><section class="year-grid">{''.join(f'<a class="year-card year-{y}" href="/{y}/"><span>{y}</span><small>{len(by_year[y])} 篇 · 按月浏览</small><b>进入档案 →</b></a>' for y in (2024,2025,2026))}</section><section class="section-heading" id="latest"><div><p class="eyebrow">LATEST NOTES</p><h2>最近更新</h2></div><a href="/2026/">查看 2026 全部 →</a></section><section class="article-grid">{latest}</section>'''
    (OUT / "index.html").write_text(shell_page("首页", "2024—2026 年度文章档案，按日期与月份浏览。", home_body), encoding="utf-8")

    for year in (2024, 2025, 2026):
        months: defaultdict[int, list[dict]] = defaultdict(list)
        for a in by_year[year]: months[a["month"]].append(a)
        month_nav = "".join(f'<a href="#month-{year}-{m}">{m:02d}月</a>' for m in sorted(months))
        sections = []
        for m in sorted(months):
            sections.append(f'<section class="month-section" id="month-{year}-{m}"><div class="month-heading"><h2>{m:02d}月</h2><span>{len(months[m])} 篇</span></div><div class="article-grid">{"".join(article_card(a) for a in months[m])}</div></section>')
        body = f'<section class="archive-hero"><p class="eyebrow">YEAR ARCHIVE</p><h1>{year}</h1><p>{len(by_year[year])} 篇文章，按月份编排。</p></section><nav class="month-nav">{month_nav}</nav><div class="archive-toolbar"><span>点击标题进入独立阅读页</span><a href="/">← 返回总览</a></div>{"".join(sections)}'
        d = OUT / str(year); d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(shell_page(f"{year}年文章", f"{year} 年文章档案，共 {len(by_year[year])} 篇。", body, str(year)), encoding="utf-8")

    for i, article in enumerate(articles):
        toc_links = "".join(f'<a href="#{a}">{esc(label)}</a>' for a, label in article["toc"]) or "<span>正文</span>"
        prev_a = articles[i-1] if i else None
        next_a = articles[i+1] if i+1 < len(articles) else None
        author = article.get("author") or "武书剑"
        account = article.get("account") or ""
        meta_right = f"{article['word_count']} 字 · 约 {article['reading_time']} 分钟"
        body = f'''<div class="article-layout"><aside class="article-sidebar"><a class="back-link" href="/{article['year']}/">← {article['year']} 年档案</a><div class="toc-label">本文目录</div><nav class="article-toc">{toc_links}</nav></aside><article class="reading-article" data-article-id="{esc(article['slug'])}"><div class="article-kicker">{article['date']} · {article['year']} ARCHIVE</div><h1>{esc(article['title'])}</h1><div class="article-meta"><span>{esc(author)}</span>{f'<span>·</span><span>{esc(account)}</span>' if account else ''}<span>·</span><span>{meta_right}</span><button class="save-article" id="save-article" type="button">♡ 收藏</button></div><div class="article-description">{esc(article['description'])}</div><div class="article-content">{article['html_body']}</div><div class="article-footer-nav">{f'<a href="{prev_a["url"]}">← {esc(prev_a["title"])}</a>' if prev_a else '<span></span>'}{f'<a href="{next_a["url"]}">{esc(next_a["title"])} →</a>' if next_a else '<span></span>'}</div></article></div>'''
        d = OUT / "articles" / article["slug"]; d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(shell_page(article["title"], article["description"], body, str(article["year"]), article=article), encoding="utf-8")

    (OUT / "404.html").write_text(shell_page("页面未找到", "你访问的文章页面不存在。", '<section class="not-found"><p class="eyebrow">404</p><h1>这篇文章走丢了。</h1><p>可以返回年度档案，或者用顶部搜索重新查找。</p><a class="button primary" href="/">回到首页</a></section>'), encoding="utf-8")
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n", encoding="utf-8")
    sitemap_urls = ["/", "/2024/", "/2025/", "/2026/"] + [a["url"] for a in articles]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{SITE_URL}{u}</loc><lastmod>{a['date']}</lastmod></url>" if u.startswith("/articles/") else f"<url><loc>{SITE_URL}{u}</loc></url>" for u, a in [(u, next((x for x in articles if x["url"]==u), {"date":""})) for u in sitemap_urls]) + "</urlset>\n"
    (OUT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    rss_items = "".join(f'<item><title>{esc(a["title"])}</title><link>{SITE_URL}{a["url"]}</link><guid>{SITE_URL}{a["url"]}</guid><pubDate>{datetime.fromisoformat(a["date"]).strftime("%a, %d %b %Y 00:00:00 +0800")}</pubDate><description>{esc(a["description"])}</description></item>' for a in reversed(articles[-30:]))
    rss = f'''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>WSJ文章档案</title><link>{SITE_URL}/</link><description>WSJ文章档案最新文章</description><language>zh-CN</language>{rss_items}</channel></rss>'''
    (OUT / "feed.xml").write_text(rss, encoding="utf-8")
    (OUT / "site.webmanifest").write_text(json.dumps({"name":"WSJ文章档案","short_name":"WSJ档案","start_url":"/","display":"standalone","background_color":"#f4f0e8","theme_color":"#171717","lang":"zh-CN"},ensure_ascii=False),encoding="utf-8")
    (OUT / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#171717"/><text x="7" y="42" fill="#f7f2e9" font-size="21" font-family="Georgia,serif">WSJ</text></svg>',encoding="utf-8")
    return articles, OUT


if __name__ == "__main__":
    built, output = build()
    print(f"Built {len(built)} articles into {output}")
