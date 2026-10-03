"""Pages for other apps rather than the website: link previews (/share/...) and the RSS feed (/feed.xml).

Chat apps and social sites don't run JavaScript, so they can't read the single-page app's titles.
A shared /share/{date}/{group} link serves the preview tags they look for, then forwards people
to the article itself.
"""
import os
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from ...core.config import settings
from ...services.news_service import NewsService

router = APIRouter()
news_service = NewsService()

FEED_SIZE = 30
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
    image_tags = ""
    if Path(article["image_url"].lstrip("/")).is_file():
        image = escape(base + article["image_url"])
        image_tags = (f'<meta property="og:image" content="{image}">'
                      f'<meta name="twitter:image" content="{image}">')

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
<meta name="twitter:card" content="{'summary_large_image' if image_tags else 'summary'}">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
{image_tags}
<meta http-equiv="refresh" content="0; url={escape(page)}">
</head><body><p><a href="{escape(page)}">Continue to the article</a></p></body></html>""")


@router.get("/feed.xml")
def rss_feed(request: Request):
    """RSS 2.0 feed of the newest stories across editions"""
    base = site_url(request)
    items = []
    for date in news_service.available_dates():
        items += news_service.get_filtered_news(date)
        if len(items) >= FEED_SIZE:
            break

    entries = []
    for item in items[:FEED_SIZE]:
        link = escape(f"{base}/article/{item['date']}/{item['group_id']}")
        published = format_datetime(datetime.strptime(item["date"], "%Y-%m-%d").replace(hour=6, tzinfo=timezone.utc))
        entries.append(f"""    <item>
      <title>{escape(item['headline'])}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{link}</guid>
      <pubDate>{published}</pubDate>
      <category>{escape(item['category'])}</category>
      <description>{escape(item['summary'])}</description>
    </item>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{SITE_NAME}</title>
    <link>{escape(base)}/</link>
    <description>AI-written daily news; every section links to its sources.</description>
    <language>en</language>
    <atom:link href="{escape(base)}/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(entries)}
  </channel>
</rss>
"""
    return Response(content=xml, media_type="application/rss+xml")
