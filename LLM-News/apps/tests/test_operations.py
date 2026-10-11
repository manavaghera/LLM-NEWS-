"""Authentication, spending controls and safe owner-facing operational details."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.endpoints import operations
from app.core import analytics, generation
from app.main import app
from app.services import operations_service


client = TestClient(app)
ADMIN = {"X-Admin-Token": "operations-test-token"}


@pytest.fixture(autouse=True)
def admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN["X-Admin-Token"])


@pytest.fixture
def telemetry(monkeypatch):
    usage = {"date": "2026-10-09", "pipeline_calls": 7, "pipeline_limit": 100, "remaining": 93,
             "models": [{"provider": "GEMINI", "model": "configured-model", "calls": 7, "failed": 1,
                         "prompt_tokens": 120, "completion_tokens": 90, "api_key": "never-expose-this"}],
             "prompts": ["never-expose-this"]}
    monkeypatch.setattr(generation, "usage_summary", lambda: usage)
    monkeypatch.setattr(generation, "feed_statuses", lambda: [
        {"publisher": "Example", "url": "https://example.com/feed.xml", "category": "tech",
         "ok": False, "items": 0, "full_text_items": 0, "last_checked": "2026-10-09T10:00:00+05:30",
         "error": "Provider response contained never-expose-this", "raw_response": "never-expose-this"}])
    monkeypatch.setattr(generation, "recent_runs", lambda: [
        {"date": "2026-10-09", "started_at": "2026-10-09T09:00:00+05:30",
         "finished_at": "2026-10-09T09:01:00+05:30", "status": "failed", "added": 0, "held_back": 1,
         "error": "Key never-expose-this failed", "prompt": "never-expose-this"}])
    monkeypatch.setattr(generation, "held_stories", lambda: [
        {"date": "2026-10-09", "category": "tech", "headline": "A held-back story",
         "reason": "The headline was unsupported by its sources", "created_at": "2026-10-09T09:00:00+00:00",
         "raw_prompt": "never-expose-this"}])
    return usage


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong"}])
def test_operations_requires_owner_authentication(headers, monkeypatch):
    def should_not_read():
        raise AssertionError("Unauthenticated calls must not read operational data")

    monkeypatch.setattr(operations, "operations_snapshot", should_not_read)
    assert client.get("/api/operations", headers=headers).status_code == 404
    assert client.patch("/api/operations/budget", headers=headers,
                        json={"daily_call_limit": 100}).status_code == 404


def test_operations_hidden_without_configured_token(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert client.get("/api/operations", headers=ADMIN).status_code == 404


def test_operations_returns_health_and_usage_without_sensitive_details(telemetry, static_root):
    response = client.get("/api/operations", headers=ADMIN)
    assert response.status_code == 200
    saved = response.json()
    assert set(saved) == {"update", "feeds", "runs", "held_stories", "usage", "analytics"}
    assert "visitor identifiers" in saved["analytics"]["privacy"]
    assert saved["update"]["ok"] is False
    assert saved["feeds"][0]["error"] == "Feed fetch failed."
    assert saved["runs"][0]["error"] == "Update failed."
    assert saved["usage"]["pipeline_calls"] == 7
    assert saved["usage"]["models"][0]["completion_tokens"] == 90
    assert saved["held_stories"][0]["headline"] == "A held-back story"
    assert saved["held_stories"][0]["reason"] == "The headline was unsupported by its sources"
    assert "never-expose-this" not in json.dumps(saved)


@pytest.mark.parametrize("status,expected", [("success", True), ("failed", False), ("running", None)])
def test_update_health_distinguishes_pending_and_completed_runs(telemetry, monkeypatch, static_root, status, expected):
    monkeypatch.setattr(generation, "recent_runs", lambda: [{"status": status}])
    assert operations_service.operations_snapshot()["update"]["ok"] is expected
    monkeypatch.setattr(generation, "recent_runs", lambda: [])
    assert operations_service.operations_snapshot()["update"]["ok"] is None


def test_readiness_fails_when_news_is_stale(monkeypatch, static_root):
    from app.api.endpoints import health
    from fastapi import Response

    def call_readiness():
        response = Response()
        coroutine = health.readiness(response)
        try:
            coroutine.send(None)
        except StopIteration as completed:
            return response, completed.value
        raise AssertionError("Readiness unexpectedly yielded")

    monkeypatch.setattr(health.settings, "production_issues", lambda: [])
    status_file = static_root / "static" / "update_status.json"
    old = datetime.now(timezone.utc) - timedelta(hours=4)
    status_file.write_text(json.dumps({"date": old.date().isoformat(), "last_update": old.isoformat(),
                                       "next_update": (old + timedelta(hours=1)).isoformat(),
                                       "interval_minutes": 60, "added": 1, "ok": True}))
    response, body = call_readiness()
    assert response.status_code == 503 and body["checks"]["news_fresh"] is False

    now = datetime.now(timezone.utc)
    status_file.write_text(json.dumps({"date": now.date().isoformat(), "last_update": now.isoformat(),
                                       "next_update": (now + timedelta(hours=1)).isoformat(),
                                       "interval_minutes": 60, "added": 0, "ok": True}))
    response, body = call_readiness()
    assert response.status_code == 200 and body["checks"]["news_fresh"] is True


@pytest.mark.parametrize("limit", [0, 100_000])
def test_owner_can_change_pipeline_budget(telemetry, monkeypatch, limit):
    saved = []

    def set_limit(value):
        saved.append(value)
        telemetry["pipeline_limit"] = value
        telemetry["remaining"] = max(0, value - telemetry["pipeline_calls"]) if value else None

    monkeypatch.setattr(generation, "set_pipeline_limit", set_limit)
    response = client.patch("/api/operations/budget", headers=ADMIN, json={"daily_call_limit": limit})
    assert response.status_code == 200
    assert saved == [limit]
    assert response.json()["pipeline_limit"] == limit
    assert "never-expose-this" not in response.text


@pytest.mark.parametrize("body", [{}, {"daily_call_limit": -1}, {"daily_call_limit": 100_001},
                                  {"daily_call_limit": "100"}, {"daily_call_limit": True},
                                  {"daily_call_limit": 1.5}, {"daily_call_limit": 1, "extra": "value"}])
def test_budget_rejects_invalid_input_without_mutating_settings(monkeypatch, body):
    def should_not_update(value):
        raise AssertionError("Invalid input must not update the pipeline cap")

    monkeypatch.setattr(operations, "update_pipeline_budget", should_not_update)
    assert client.patch("/api/operations/budget", headers=ADMIN, json=body).status_code == 422


def test_operations_errors_do_not_echo_storage_or_provider_messages(monkeypatch):
    def fail(*args):
        raise OSError("secret-token-in-private-path")

    monkeypatch.setattr(operations, "operations_snapshot", fail)
    response = client.get("/api/operations", headers=ADMIN)
    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to fetch operations"}
    monkeypatch.setattr(operations, "update_pipeline_budget", fail)
    response = client.patch("/api/operations/budget", headers=ADMIN, json={"daily_call_limit": 100})
    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to update pipeline budget"}


def test_operations_supports_fresh_installation_without_feeds_or_runs(monkeypatch, static_root):
    monkeypatch.setenv("CACHE_DIR", str(static_root / "cache"))
    response = client.get("/api/operations", headers=ADMIN)
    assert response.status_code == 200
    saved = response.json()
    assert saved["feeds"] == [] and saved["runs"] == []
    assert saved["held_stories"] == []
    assert saved["update"]["ok"] is None
    assert saved["usage"]["pipeline_calls"] == 0
    assert saved["usage"]["models"] == []


def test_changed_budget_controls_subsequent_pipeline_calls(monkeypatch, static_root):
    monkeypatch.setenv("CACHE_DIR", str(static_root / "cache"))
    response = client.patch("/api/operations/budget", headers=ADMIN, json={"daily_call_limit": 1})
    assert response.status_code == 200
    call_id = generation.start_call("GEMINI", "test-model")
    generation.finish_call(call_id, failed=True)
    with pytest.raises(generation.PipelineBudgetExceeded):
        generation.start_call("GEMINI", "test-model")

    saved = client.get("/api/operations", headers=ADMIN).json()["usage"]
    assert saved["pipeline_limit"] == 1
    assert saved["pipeline_calls"] == 1 and saved["remaining"] == 0
    assert saved["models"][0]["failed"] == 1


def test_monthly_budget_stops_generation_across_days(monkeypatch, static_root):
    monkeypatch.setenv("CACHE_DIR", str(static_root / "cache"))
    generation.set_pipeline_limits(0, 1)
    call_id = generation.start_call("GEMINI", "test-model")
    generation.finish_call(call_id)
    with pytest.raises(generation.PipelineBudgetExceeded, match="monthly"):
        generation.start_call("GEMINI", "test-model")
    saved = generation.usage_summary()
    assert saved["monthly_calls"] == 1 and saved["monthly_remaining"] == 0


def test_admin_login_uses_expiring_http_only_session(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "a-secure-test-token-that-is-long")
    with TestClient(app) as browser:
        login = browser.post("/api/admin/login", json={"token": "a-secure-test-token-that-is-long"})
        assert login.status_code == 200
        cookie = login.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert browser.get("/api/admin/session").json() == {"authenticated": True}
        assert browser.post("/api/admin/logout").status_code == 200
        assert browser.get("/api/admin/session").status_code == 404


def test_analytics_are_aggregate_and_allow_listed(monkeypatch, static_root):
    monkeypatch.setenv("CACHE_DIR", str(static_root / "cache"))
    assert client.post("/api/analytics/event", json={"event": "category_view", "detail": "tech"}).status_code == 202
    assert client.post("/api/analytics/event", json={"event": "model_compared", "detail": "safe-model"}).status_code == 202
    assert client.post("/api/analytics/event", json={"event": "made_up", "detail": "secret"}).status_code == 422
    assert client.post("/api/analytics/event", json={"event": "search", "detail": "email@example.com"}).status_code == 422
    saved = analytics.snapshot()
    assert {row["detail"] for row in saved["breakdown"]} == {"tech", "safe-model"}
    assert "visitor identifiers" in saved["privacy"]
