# 武书剑文章档案 · V2

静态站点1：<https://wushujian.pages.dev/>
静态站点2：<https://wushujian2.pages.dev/>

## V2 做了什么

- 保留现有文章 URL；历史文章 ID 从现有站点索引迁移，新文章永久分配 ID。
- OCR → Markdown 后增加基础清洗，尽量过滤日期/纯符号等 OCR 残留。
- 每篇文章自动生成摘要、字数、预计阅读时间。
- 每篇文章自动生成 Open Graph、X/Twitter Card、canonical、JSON-LD。
- 自动生成 1200×630 PNG 分享封面，适合 X、Facebook/Messenger、LinkedIn、Telegram 等链接预览。
- 搜索索引改为全文索引，并保留摘要。
- 增加阅读设置、深色模式、阅读进度、收藏、随机阅读、分享按钮、目录高亮。
- 自动生成 sitemap.xml 与 feed.xml。
- GitHub Actions 自动完成：安装依赖 → build → validate → Cloudflare Pages deploy。

## 本地构建

需要 Python 3.12+：

```powershell
python -m pip install -r requirements.txt
python build_site.py
python validate_site.py dist
```

生成结果在 `dist/`。

## Windows 一键发布

双击 `publish.cmd`。脚本会：

1. 安装/使用当前 Python 环境中的 Pillow（首次使用前请执行 `pip install -r requirements.txt`）；
2. 重新生成网站与 OG 图片；
3. 验证文章数量、内部链接、SEO/OG 元数据；
4. 提交并推送 GitHub；
5. GitHub Actions 自动部署到 Cloudflare Pages。

## 自定义单篇摘要

在 `data/metadata_overrides.json` 中可以覆盖自动生成的元数据，例如：

```json
{
  "2026-08-21|开门-无奈阶层！": {
    "description": "这里填写人工确认后的分享摘要。"
  }
}
```

如果没有覆盖值，系统会从正文第一段有效文字自动生成摘要。

## GitHub Secrets

仓库的 `Settings → Secrets and variables → Actions` 中需要：

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

Cloudflare API Token 至少需要对应 Pages 项目的编辑权限。敏感值不要写入仓库。

## 部署方式

GitHub Actions 会在 `main` 分支 push 后自动执行：

`source → build_site.py → validate_site.py → dist → Cloudflare Pages`

因此以后主要维护源 Markdown、`data/`、`assets/` 和 Python 构建代码即可；`dist/` 仍然保留，方便本地预览和手动部署。
