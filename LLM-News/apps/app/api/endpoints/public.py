"""Pages for other apps rather than the website: link previews (/share/...), the RSS feed (/feed.xml),
and robots.txt and sitemap.xml for search engines.

Chat apps and social sites don't run JavaScript, so they can't read the single-page app's titles.
A shared /share/{date}/{group} link serves the preview tags they look for, then forwards people
to the article itself.
"""
import json
import os
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ...core.config import settings
from ...services.news_service import NewsService, group_number

router = APIRouter()
news_service = NewsService()

FEED_SIZE = 30
SITEMAP_LIMIT = 50_000  # the sitemap protocol's maximum
SITE_NAME = "NewsSense"


def site_url(request: Request) -> str:
    """Public base URL: PUBLIC_BASE_URL, else the address the request came in on"""
    if settings.PUBLIC_BASE_URL:
        return settings.PUBLIC_BASE_URL
    scheme = request.url.scheme
    if os.getenv("TRUST_PROXY_HEADERS", "").lower() == "true":
        scheme = request.headers.get("x-forwarded-proto", scheme).split(",")[0].strip()
    host = request.headers.get("host", request.url.netloc)
    return f"{scheme}://{host}"


def description_of(article: dict) -> str:
    text = article.get("subheadline") or article.get("lead") or ""
    return text if len(text) <= 200 else text[:197].rsplit(" ", 1)[0] + "..."


@router.get("/share/{date}/{group_id}", response_class=HTMLResponse)
def share_article(date: str, group_id: str, request: Request):
    article = news_service.get_article(date, group_id) if re.fullmatch(r"group_\d+", group_id) else None
    base = site_url(request)
    if not article:
        return HTMLResponse(f'<!doctype html><meta charset="utf-8"><title>Not found</title>'
                            f'<p>Article not found. <a href="{escape(base)}/">Go to today\'s news</a></p>', status_code=404)

    page = f"{base}/article/{date}/{group_id}"
    title = escape(f"{article.get('headline', '')} · {SITE_NAME}")
    description = escape(description_of(article))
    preview_image = base + "/social-preview.svg"
    if Path(article["image_url"].lstrip("/")).is_file():
        preview_image = base + article["image_url"]
    image = escape(preview_image)
    image_tags = (f'<meta property="og:image" content="{image}">'
                  f'<meta name="twitter:image" content="{image}">')
    structured = json.dumps({
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": str(article.get("headline", ""))[:110], "description": description_of(article),
        "datePublished": article.get("added_at") or date, "mainEntityOfPage": page,
        "publisher": {"@type": "Organization", "name": SITE_NAME},
    }, ensure_ascii=False).replace("<", "\\u003c")

    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{escape(page)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{escape(page)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
{image_tags}
<script type="application/ld+json">{structured}</script>
<meta http-equiv="refresh" content="0; url={escape(page)}">
</head><body><p><a href="{escape(page)}">Continue to the article</a></p></body></html>""")


def published_at(item: dict) -> datetime:
    """When the update that added the story ran; 06:00 UTC on its date for stories from before updates had times"""
    try:
        added = datetime.fromisoformat(item.get("added_at") or "")
        if added.tzinfo:
            return added
    except ValueError:
        pass
    return datetime.strptime(item["date"], "%Y-%m-%d").replace(hour=6, tzinfo=timezone.utc)


@router.get("/feed.xml")
def rss_feed(request: Request, category: str | None = Query(None, max_length=50, pattern=r"^[a-z0-9_]+$")):
    """RSS 2.0 feed of the newest stories across editions"""
    base = site_url(request)
    items = []
    for date in news_service.available_dates():
        # newest update first within an edition (stories without a time came first that day)
        edition = news_service.get_filtered_news(date)
        if category:
            edition = [item for item in edition if item.get("category") == category]
        items += sorted(edition, key=lambda i: i.get("added_at") or "", reverse=True)
        if len(items) >= FEED_SIZE:
            break

    entries = []
    for item in items[:FEED_SIZE]:
        link = escape(f"{base}/article/{item['date']}/{item['group_id']}")
        published = format_datetime(published_at(item))
        entries.append(f"""    <item>
      <title>{escape(item['headline'])}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{link}</guid>
      <pubDate>{published}</pubDate>
      <category>{escape(item['category'])}</category>
      <description>{escape(item['summary'])}</description>
    </item>""")

    category_label = "AI Models" if category == "ai_models" else category.replace("_", " ").title() if category else ""
    feed_title = f"{SITE_NAME} · {category_label}" if category else SITE_NAME
    self_link = f"{base}/feed.xml?category={category}" if category else f"{base}/feed.xml"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(feed_title)}</title>
    <link>{escape(base)}/</link>
    <description>AI-written daily news; every section links to its sources.</description>
    <language>en</language>
    <atom:link href="{escape(self_link)}" rel="self" type="application/rss+xml"/>
{chr(10).join(entries)}
  </channel>
</rss>
"""
    return Response(content=xml, media_type="application/rss+xml")


def _model_catalog() -> dict:
    path = Path("static/model_catalog.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"updated_at": "", "currency": "USD", "price_unit": "per million tokens", "models": []}
    return data if isinstance(data, dict) and isinstance(data.get("models"), list) else {"models": []}


@router.get("/models/catalog.json")
def public_model_catalog():
    """CORS-enabled, cacheable model catalog for small integrations and dashboards."""
    return JSONResponse(_model_catalog(), headers={"Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*"})


@router.get("/models/{model_id}/share", response_class=HTMLResponse)
def share_model(model_id: str, request: Request):
    model = next((item for item in _model_catalog().get("models", []) if item.get("id") == model_id), None)
    if not model or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,79}", model_id):
        return HTMLResponse("<!doctype html><title>Model not found</title>", status_code=404)
    base = site_url(request)
    page = f"{base}/ai-models/{model_id}"
    title = escape(f"{model.get('name', model_id)} price, context and details · {SITE_NAME}")
    description = escape(
        f"{model.get('provider', '')} model: ${model.get('input_price', 0)}/MTok input, "
        f"${model.get('output_price', 0)}/MTok output, {int(model.get('context_tokens', 0)):,} token context."
    )
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<meta name="description" content="{description}"><link rel="canonical" href="{escape(page)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{description}">
<meta property="og:url" content="{escape(page)}"><meta name="twitter:card" content="summary_large_image">
<meta property="og:image" content="{escape(base)}/social-preview.svg"><meta name="twitter:image" content="{escape(base)}/social-preview.svg">
<meta http-equiv="refresh" content="0; url={escape(page)}"></head><body><a href="{escape(page)}">View model details</a></body></html>""")


@router.get("/widgets/models", response_class=HTMLResponse)
def models_widget(ids: str = Query("", max_length=500)):
    """Small embeddable price and context table. The optional ids query is comma-separated."""
    models = _model_catalog().get("models", [])
    wanted = {item.strip() for item in ids.split(",") if item.strip()}
    if wanted:
        models = [model for model in models if model.get("id") in wanted]
    rows = "".join(
        f"<tr><th>{escape(str(model.get('name', '')))}</th>"
        f"<td>{escape(str(model.get('provider', '')))}</td>"
        f"<td>${float(model.get('input_price', 0)):g}</td>"
        f"<td>${float(model.get('output_price', 0)):g}</td>"
        f"<td>{int(model.get('context_tokens', 0)):,}</td></tr>" for model in models
    ) or '<tr><td colspan="5">No matching models.</td></tr>'
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>{SITE_NAME} model prices</title>
<style>body{{font:14px system-ui;margin:0;color:#191919}}table{{border-collapse:collapse;width:100%}}caption{{font-weight:700;text-align:left;padding:12px 8px}}th,td{{border-bottom:1px solid #ddd;padding:9px 8px;text-align:left}}thead th{{font-size:12px;color:#666}}tbody th{{font-weight:600}}small{{display:block;padding:8px;color:#666}}</style></head>
<body><table><caption>AI model price and context snapshot</caption><thead><tr><th>Model</th><th>Provider</th><th>Input / MTok</th><th>Output / MTok</th><th>Context</th></tr></thead><tbody>{rows}</tbody></table><small>Source-linked data from {SITE_NAME}. Prices may change.</small></body></html>""")


@router.get("/robots.txt")
def robots_txt(request: Request):
    """Search engines may read everything but the API; the sitemap lists every article"""
    return Response(f"User-agent: *\nDisallow: /api/\n\nSitemap: {site_url(request)}/sitemap.xml\n", media_type="text/plain")


@router.get("/sitemap.xml")
def sitemap(request: Request):
    """The site's main pages and every article in the archive"""
    base = escape(site_url(request))
    dates = news_service.available_dates()
    pages = ("digest", "trends", "ai-models", "about", "privacy", "terms", "cookies", "sources", "corrections-policy")
    urls = [(f"{base}/", dates[0] if dates else None)] + [(f"{base}/{page}", None) for page in pages]
    catalog = _model_catalog()
    for model in catalog.get("models", []):
        model_id = model.get("id")
        if isinstance(model_id, str) and re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,79}", model_id):
            urls.append((f"{base}/ai-models/{escape(model_id)}", catalog.get("updated_at")))
    for date in dates:
        for group_id in sorted(news_service.load_articles_for_date(date), key=group_number):
            urls.append((f"{base}/article/{date}/{group_id}", date))
    entries = "".join(
        f"  <url><loc>{loc}</loc>{f'<lastmod>{day}</lastmod>' if day else ''}</url>\n" for loc, day in urls[:SITEMAP_LIMIT]
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}</urlset>\n'
    return Response(content=xml, media_type="application/xml")
