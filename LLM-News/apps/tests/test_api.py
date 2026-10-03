"""API tests. Run from LLM-News/apps: python -m pytest tests"""
import json
import os
import zlib

from fastapi.testclient import TestClient

from app.main import app
from conftest import write_article

client = TestClient(app)
DATE = "2026-01-01"


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_no_articles_means_empty_lists(static_root):
    assert client.get("/api/news/dates").json() == {"dates": [], "total": 0}
    assert client.get("/api/news").json() == []


def test_news_list_article_and_categories(static_root):
    write_article(static_root, DATE, "group_1", "Chip launch", "tech")
    write_article(static_root, DATE, "group_2", "Film festival", "entertainment")

    assert client.get("/api/news/dates").json()["dates"] == [DATE]
    news = client.get("/api/news").json()
    assert {item["headline"]: item["category"] for item in news} == {
        "Chip launch": "tech",
        "Film festival": "entertainment",
    }
    assert [i["headline"] for i in client.get("/api/news", params={"category": "tech"}).json()] == ["Chip launch"]
    assert client.get(f"/api/news/articles/{DATE}/group_1").json()["headline"] == "Chip launch"
    assert client.get(f"/api/news/articles/{DATE}/group_9").status_code == 404


def test_article_ids_are_stable(static_root):
    write_article(static_root, DATE, "group_1", "Stable")
    item = client.get("/api/news", params={"date": DATE}).json()[0]
    # Same value in every process (Python's hash() of a str changes on each restart)
    assert item["id"] == zlib.crc32(f"{DATE}/group_1".encode())


def test_cache_refreshes_when_articles_change(static_root):
    date = "2026-01-02"
    path = write_article(static_root, date, "group_1", "Old headline")
    assert client.get(f"/api/news/articles/{date}/group_1").json()["headline"] == "Old headline"

    article = json.loads(path.read_text(encoding="utf-8"))
    article["headline"] = "New headline"
    path.write_text(json.dumps(article), encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))  # guarantee a new mtime
    assert client.get(f"/api/news/articles/{date}/group_1").json()["headline"] == "New headline"

    write_article(static_root, date, "group_2", "Added later")
    assert len(client.get("/api/news", params={"date": date}).json()) == 2


def test_invalid_dates_are_rejected(static_root):
    write_article(static_root, DATE, "group_1", "Anything")
    assert client.get("/api/news", params={"date": "../.."}).json() == []
    assert client.get("/api/news/articles/not-a-date/group_1").status_code == 404


def test_static_serves_files_inside_static(static_root):
    image = static_root / "static" / "images" / DATE / "group_1.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"fake image")
    response = client.get(f"/static/images/{DATE}/group_1.jpg")
    assert response.status_code == 200
    assert response.content == b"fake image"


def test_static_blocks_path_traversal(static_root):
    (static_root / ".env").write_text("OPENROUTER_API_KEY=secret")
    for path in ("/static/..%2F.env", "/static/images%2F..%2F..%2F.env"):
        response = client.get(path)
        assert response.status_code == 404, path
        assert b"secret" not in response.content


def test_trends_topics_ignore_citation_markup(static_root):
    path = write_article(static_root, DATE, "group_1", "Quantum computing breakthrough announced")
    article = json.loads(path.read_text(encoding="utf-8"))
    article["lead"] = ""
    article["body"][0]["content"] = ("Five teams at the Bank of England and IBM tested chips. "
                                     "Police said the U.S. Supreme Court agreed.<a href='https://www.example.com/rss/x'>[1]</a>")
    path.write_text(json.dumps(article), encoding="utf-8")

    response = client.get("/api/trends/topics")
    assert response.status_code == 200
    topics = {t["keyword"]: t["total_count"] for t in response.json()["trending_topics"]}
    assert topics == {"Bank of England": 1, "IBM": 1, "U.S. Supreme Court": 1}  # names, counted per story
    # Not citation markup, sentence-start words ("Five", "Police") or the Title Case headline


def test_chat_models_only_lists_usable_models():
    from app.api.endpoints import chat
    body = client.get("/api/chat/models").json()
    # The Knowledge Graph needs its own key and app id, which these tests don't set
    assert all(model["value"] != "knowledge-graph" for model in body["models"])
    assert [m["value"] for m in body["models"]] == [model for _, _, model in chat.llm_service.clients]
    assert body["default"] == (body["models"][0] if body["models"] else None)


def stream_events(payload: dict) -> list:
    body = client.post("/api/chat/stream", json=payload).text
    return [json.loads(line[len("data: "):]) for line in body.splitlines() if line.startswith("data: ")]


class FakeStreamClient:
    """Stands in for a provider: records the messages it was sent and streams a fixed reply."""
    def __init__(self):
        self.messages = None

    async def stream(self, messages, model):
        self.messages = messages
        for text in ("Hi", " there"):
            yield text


def test_chat_stream_sends_history_and_streams_reply(monkeypatch, static_root):
    from app.api.endpoints import chat
    write_article(static_root, DATE, "group_1", "Chip launch")
    fake = FakeStreamClient()
    monkeypatch.setattr(chat.llm_service, "pick_client", lambda model=None: ("Fake", fake, "fake-model"))

    events = stream_events({"message": "Hello", "history": [{"role": "user", "content": "Earlier question"}]})
    assert events[0] == {
        "type": "meta", "provider": "Fake", "model": "fake-model",
        "sources": [{"label": "1", "title": "Chip launch", "url": f"/article/{DATE}/group_1"}],
    }
    assert "[1] (tech) Chip launch" in fake.messages[0]["content"]  # stories are numbered for citing
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "Hi there"
    assert events[-1] == {"type": "done"}
    assert [m["role"] for m in fake.messages] == ["system", "user", "user"]
    assert fake.messages[-1]["content"] == "Hello"


def test_article_context_does_not_invent_scores(static_root):
    from app.api.endpoints.chat import news_service
    write_article(static_root, DATE, "group_1", "Unscored story")
    context = news_service.get_article_context("group_1", DATE)
    assert "Average Fake News Probability: not scored" in context
    assert "0.00" not in context


def test_chat_stream_reports_missing_provider(monkeypatch):
    from app.api.endpoints import chat
    monkeypatch.setattr(chat.llm_service, "pick_client", lambda model=None: None)
    events = stream_events({"message": "Hello"})
    assert events[0]["type"] == "error"
    assert "No AI provider" in events[0]["message"]
    assert events[-1] == {"type": "done"}


def test_chat_stream_validates_input():
    too_long_history = [{"role": "user", "content": "x"}] * 13
    assert client.post("/api/chat/stream", json={"message": "Hi", "history": too_long_history}).status_code == 422
    assert client.post("/api/chat/stream", json={"message": ""}).status_code == 422
    assert client.post("/api/chat/stream", json={"message": "Hi", "history": [{"role": "system", "content": "x"}]}).status_code == 422


def test_stalled_ai_stream_gives_up_with_a_clear_message():
    import asyncio

    import aiohttp
    import pytest
    from aiohttp import web

    from app.services.llm_service import AIServiceSlow, HTTPLLMClient

    async def stall(request):  # starts the reply, then sends nothing
        response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        await asyncio.sleep(5)
        return response

    async def run():
        server = web.Application()
        server.router.add_post("/chat/completions", stall)
        runner = web.AppRunner(server)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        client = HTTPLLMClient(f"http://127.0.0.1:{port}", "key")
        client.timeout = aiohttp.ClientTimeout(total=5, sock_read=0.3)
        try:
            with pytest.raises(AIServiceSlow, match="taking too long"):
                async for _ in client.stream([{"role": "user", "content": "hi"}], "model"):
                    pass
        finally:
            await runner.cleanup()

    asyncio.run(run())
