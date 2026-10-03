"""Accuracy tracking, reader reports and earlier coverage. Run from LLM-News/apps: python -m pytest tests"""
import json
import sqlite3

from fastapi.testclient import TestClient

from app.core import limits
from app.main import app
from conftest import write_article

client = TestClient(app)


def set_article(path, **fields):
    article = json.loads(path.read_text(encoding="utf-8"))
    article.update(fields)
    path.write_text(json.dumps(article), encoding="utf-8")


def test_accuracy_counts_removed_statements_per_day_and_model(static_root):
    a = write_article(static_root, "2026-01-02", "group_1", "Checked")
    set_article(a, generated_by="quick_news (OPENROUTER / writer-model)",
                claim_check={"checked": True, "statements": 10, "removed": [{"text": "x", "reason": "y"}] * 3, "model": "checker-model"})
    b = write_article(static_root, "2026-01-02", "group_2", "Also checked")
    set_article(b, generated_by="quick_news (OPENROUTER / writer-model)",
                claim_check={"checked": True, "statements": 10, "removed": [], "model": "checker-model"})
    write_article(static_root, "2026-01-01", "group_1", "Older, never checked")

    body = client.get("/api/trends/accuracy").json()
    assert [(d["date"], d["checked"], d["statements"], d["removed"], d["removed_pct"]) for d in body["days"]] == [
        ("2026-01-01", 0, 0, 0, None), ("2026-01-02", 2, 20, 3, 15.0)]
    assert body["models"] == [{"writer": "writer-model", "checker": "checker-model", "articles": 2,
                               "statements": 20, "removed": 3, "removed_pct": 15.0}]


def test_reader_report_is_stored_without_personal_data(static_root, monkeypatch):
    write_article(static_root, "2026-01-01", "group_1", "Story")
    response = client.post("/api/reports", json={"date": "2026-01-01", "group_id": "group_1",
                                                 "kind": "wrong_fact", "message": "The vote was 14-1, not 15-0."})
    assert response.status_code == 201
    columns = [c[1] for c in sqlite3.connect(static_root / "cache" / "reports.db").execute("PRAGMA table_info(reports)")]
    assert columns == ["id", "created_at", "date", "group_id", "kind", "message"]  # no IP or identity
    assert client.get("/api/trends/accuracy").json()["days"][0]["reader_reports"] == 1


def test_reader_reports_are_validated_and_rate_limited(static_root, monkeypatch):
    from app.api.endpoints import reports
    write_article(static_root, "2026-01-01", "group_1", "Story")
    ok = {"date": "2026-01-01", "group_id": "group_1", "kind": "other", "message": "Typo in the lead."}
    assert client.post("/api/reports", json={**ok, "kind": "spam"}).status_code == 422
    assert client.post("/api/reports", json={**ok, "message": "x"}).status_code == 422
    assert client.post("/api/reports", json={**ok, "group_id": "group_9"}).status_code == 404

    monkeypatch.setattr(reports, "report_limiter", limits.RateLimiter(limit=2))
    assert [client.post("/api/reports", json=ok).status_code for _ in range(3)] == [201, 201, 429]


def test_report_list_needs_the_admin_token(static_root, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert client.get("/api/reports").status_code == 404  # no token configured: hidden
    monkeypatch.setenv("ADMIN_TOKEN", "s3cret")
    assert client.get("/api/reports", headers={"X-Admin-Token": "wrong"}).status_code == 404
    assert client.get("/api/reports", headers={"X-Admin-Token": "s3cret"}).json() == {"reports": []}


def test_earlier_coverage_links_the_same_running_story(static_root):
    today = write_article(static_root, "2026-01-03", "group_1", "Haiti vote")
    set_article(today, lead="The UN Security Council extended the Haiti mission run by Kenya.")
    same = write_article(static_root, "2026-01-01", "group_1", "Earlier Haiti vote")
    set_article(same, lead="The UN Security Council debated the Haiti mission led by Kenya.")
    unrelated = write_article(static_root, "2026-01-02", "group_1", "Kenya marathon")
    set_article(unrelated, lead="A runner from Kenya won the marathon.")  # one shared name is not enough

    related = client.get("/api/news/articles/2026-01-03/group_1/related").json()
    assert [(r["date"], r["group_id"]) for r in related] == [("2026-01-01", "group_1")]
    assert related[0]["shared_topics"][0] == "UN Security Council"
    assert client.get("/api/news/articles/2026-01-01/group_1/related").json() == []  # only looks back


def test_earlier_coverage_by_a_shared_headline_subject(static_root):
    today = write_article(static_root, "2026-01-03", "group_1", "G7 Prepares to Release Oil Reserves")
    set_article(today, lead="Under pressure from Washington, the G7 agreed to release oil, avoiding a US export ban.")
    same = write_article(static_root, "2026-01-02", "group_1", "G7 Agrees to Release 100 Million Barrels")
    set_article(same, lead="The G7 will release oil after fighting between the US and Iran.")
    other = write_article(static_root, "2026-01-02", "group_2", "Five Men Released on Bail")
    set_article(other, lead="Police said the men worked for Iran and had links to the US.")  # names, not subject

    related = client.get("/api/news/articles/2026-01-03/group_1/related").json()
    assert [(r["date"], r["group_id"]) for r in related] == [("2026-01-02", "group_1")]
    assert related[0]["shared_topics"] == ["G7", "US"]
