"""Providers, AI limits, archive, search, share previews and RSS. Run from LLM-News/apps: python -m pytest tests"""
import json
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.core import limits, providers
from app.main import app
from conftest import write_article

client = TestClient(app)


def test_providers_use_current_endpoints_and_models():
    assert providers.PROVIDERS["GEMINI"].base_url.endswith("/v1beta/openai")
    assert providers.PROVIDERS["GEMINI"].model == "gemini-2.5-flash"
    assert providers.PROVIDERS["PERPLEXITY"].model == "sonar"
    assert providers.PROVIDERS["NVIDIA"].base_url == "https://integrate.api.nvidia.com/v1"
    assert providers.PROVIDERS["NVIDIA"].key_env == "NVIDIA_API_KEY"


def test_browser_tests_blank_every_provider_key():
    """The Playwright backend must not pick up a real key from .env, or its chat test calls a real AI"""
    from pathlib import Path
    config = (Path(__file__).resolve().parents[1] / "web" / "playwright.config.ts").read_text(encoding="utf-8")
    assert [p.key_env for p in providers.PROVIDERS.values() if f"{p.key_env}: ''" not in config] == []


def test_providers_prefer_llm_publisher_and_allow_model_override(monkeypatch):
    for provider in providers.PROVIDERS.values():
        monkeypatch.delenv(provider.key_env, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "a")
    monkeypatch.setenv("GEMINI_API_KEY", "b")
    monkeypatch.setenv("LLM_PUBLISHER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    assert [(pid, model) for pid, _, _, model in providers.configured()] == [
        ("GEMINI", "gemini-3-flash-preview"), ("OPENAI", "gpt-4o-mini")]


def test_rate_limiter_blocks_then_reports_wait():
    limiter = limits.RateLimiter(limit=2, window_seconds=60)
    limiter.check("1.2.3.4")
    limiter.check("1.2.3.4")
    with pytest.raises(limits.RateLimited) as blocked:
        limiter.check("1.2.3.4")
    assert 1 <= blocked.value.retry_after <= 60
    limiter.check("5.6.7.8")  # other visitors are unaffected


def test_daily_budget_caps_calls():
    budget = limits.DailyBudget(limit=2)
    budget.consume()
    budget.consume()
    with pytest.raises(limits.BudgetExceeded):
        budget.consume()
    limits.DailyBudget(limit=0).consume(10_000)  # 0 disables the cap


def test_visitor_ip_counts_our_proxies_from_the_end(monkeypatch):
    from starlette.requests import Request

    def ip(forwarded):
        headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
        return limits.client_ip(Request({"type": "http", "headers": headers, "client": ("10.0.0.9", 1)}))

    assert ip("6.6.6.6, 1.2.3.4") == "10.0.0.9"  # headers not trusted by default
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    assert ip("6.6.6.6, 1.2.3.4") == "1.2.3.4"   # nginx only: its entry is last; the first was forged
    monkeypatch.setenv("PROXY_COUNT", "2")
    assert ip("6.6.6.6, 1.2.3.4, 172.18.0.5") == "1.2.3.4"  # Caddy, then nginx
    assert ip("172.18.0.5") == "10.0.0.9"        # shorter than expected: didn't come through our proxies
    monkeypatch.setenv("PROXY_COUNT", "oops")
    assert ip("6.6.6.6, 1.2.3.4") == "1.2.3.4"


def test_ai_endpoints_return_429_when_rate_limited(monkeypatch):
    monkeypatch.setattr(limits, "ai_rate_limiter", limits.RateLimiter(limit=1))
    from app.api.endpoints import chat
    monkeypatch.setattr(chat.llm_service, "pick_client", lambda model=None: None)
    assert client.post("/api/chat/stream", json={"message": "hi"}).status_code == 200
    response = client.post("/api/chat/stream", json={"message": "hi"})
    assert response.status_code == 429
    assert "Too many requests" in response.json()["detail"]
    assert int(response.headers["Retry-After"]) >= 1


def test_chat_reports_daily_cap(monkeypatch, static_root):
    from app.api.endpoints import chat
    from app.services import llm_service
    exhausted = limits.DailyBudget(limit=1)
    exhausted.consume()
    monkeypatch.setattr(llm_service, "ai_budget", exhausted)
    monkeypatch.setattr(chat.llm_service, "pick_client",
                        lambda model=None: ("Fake", llm_service.HTTPLLMClient("http://unused", "k"), "m"))
    body = client.post("/api/chat/stream", json={"message": "hi"}).text
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert any(e["type"] == "error" and "daily AI limit" in e["message"] for e in events)


def test_dates_cover_the_whole_archive(static_root):
    for day in range(1, 10):
        write_article(static_root, f"2026-01-{day:02d}", "group_1", f"Story {day}")
    (static_root / "static" / "articles" / "not-a-date").mkdir()
    dates = client.get("/api/news/dates").json()["dates"]
    assert len(dates) == 9 and dates[0] == "2026-01-09"
    assert client.get("/api/news/dates", params={"limit": 3}).json()["total"] == 3


def test_archive_search_finds_words_across_editions(static_root):
    write_article(static_root, "2026-01-01", "group_1", "Haiti force mandate extended")
    write_article(static_root, "2026-01-02", "group_1", "Chip launch")
    write_article(static_root, "2026-01-03", "group_2", "New Haiti vote")
    results = client.get("/api/news/search", params={"q": "haiti"}).json()
    assert [(r["date"], r["headline"]) for r in results] == [
        ("2026-01-03", "New Haiti vote"), ("2026-01-01", "Haiti force mandate extended")]
    assert client.get("/api/news/search", params={"q": "haiti chip"}).json() == []
    assert client.get("/api/news/search", params={"q": "x"}).status_code == 422


def test_article_image_uses_recorded_file(static_root):
    path = write_article(static_root, "2026-01-01", "group_1", "Pictured")
    article = json.loads(path.read_text(encoding="utf-8"))
    article["image_file"] = "group_1.webp"
    path.write_text(json.dumps(article), encoding="utf-8")
    assert client.get("/api/news/articles/2026-01-01/group_1").json()["image_url"] == "/static/images/2026-01-01/group_1.webp"
    article["image_file"] = "../../.env"  # never trusted as a path
    path.write_text(json.dumps(article), encoding="utf-8")
    assert client.get("/api/news").json()[0]["image_url"] == "/static/images/2026-01-01/group_1.jpg"


def test_summary_date_follows_the_data(static_root):
    assert client.get("/api/config/summary-date").json()["date"] == ""
    write_article(static_root, "2026-01-05", "group_1", "Latest")
    assert client.get("/api/config/summary-date").json()["date"] == "2026-01-05"


def test_share_page_has_escaped_preview_tags(static_root):
    write_article(static_root, "2026-01-01", "group_1", 'Quotes "and" <script>alert(1)</script>')
    image = static_root / "static" / "images" / "2026-01-01" / "group_1.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"x")
    html = client.get("/share/2026-01-01/group_1", headers={"host": "news.example"}).text
    assert '<meta property="og:title" content="Quotes &quot;and&quot; &lt;script&gt;' in html
    assert "<script>" not in html
    assert 'content="http://news.example/static/images/2026-01-01/group_1.jpg"' in html
    assert 'url=http://news.example/article/2026-01-01/group_1' in html
    assert client.get("/share/2026-01-01/group_9").status_code == 404
    assert client.get("/share/2026-01-01/x%3Cy").status_code == 404


def test_rss_feed_is_valid_xml(static_root):
    write_article(static_root, "2026-01-01", "group_1", "Older & wiser")
    write_article(static_root, "2026-01-02", "group_1", "Newest")
    response = client.get("/feed.xml", headers={"host": "news.example"})
    assert response.headers["content-type"].startswith("application/rss+xml")
    items = ET.fromstring(response.content).findall("./channel/item")
    assert [i.findtext("title") for i in items] == ["Newest", "Older & wiser"]
    assert items[0].findtext("link") == "http://news.example/article/2026-01-02/group_1"
