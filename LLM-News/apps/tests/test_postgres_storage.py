"""Production storage checks. CI supplies TEST_POSTGRES_URL; local runs skip safely."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os

import pytest

from app.core import analytics, generation
from app.core.database import connect, database_ready
from app.services.report_service import ReportService
from scripts.migrate_sqlite_to_postgres import migrate


pytestmark = pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"),
                                reason="TEST_POSTGRES_URL is not configured")


ALL_TABLES = (
    "corrections", "report_resolutions", "report_articles", "reports",
    "analytics_breakdowns", "runtime_requests", "analytics_events",
    "generation_leases", "generation_holds", "generation_runs", "generation_feeds",
    "generation_calls", "generation_settings", "storage_migrations",
)


@pytest.fixture(autouse=True)
def clean_postgres(monkeypatch):
    url = os.environ["TEST_POSTGRES_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("PIPELINE_DAILY_CALL_LIMIT", "3")
    monkeypatch.setenv("PIPELINE_MONTHLY_CALL_LIMIT", "30")
    # Initialize every namespace before truncating the shared production database.
    for namespace in ("generation", "analytics", "reports"):
        with connect(namespace):
            pass
    with connect("generation") as database:
        database.execute(f"TRUNCATE {','.join(ALL_TABLES)} RESTART IDENTITY CASCADE")
    yield


def test_postgres_coordinates_budget_analytics_reports_and_updater_lease(monkeypatch):
    def reserve(_):
        try:
            return generation.start_call("TEST", "model")
        except generation.PipelineBudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=8) as workers:
        calls = list(workers.map(reserve, range(10)))
    assert len([call for call in calls if call is not None]) == 3
    assert generation.usage_summary()["remaining"] == 0

    assert generation.acquire_update_lease("one", 60) is True
    assert generation.acquire_update_lease("two", 60) is False
    generation.release_update_lease("one")
    assert generation.acquire_update_lease("two", 60) is True

    analytics.record_event("category_view", "tech")
    analytics.record_request("/api/news/{date}", "GET", 200, 25)
    saved = analytics.snapshot()
    assert saved["events"] == [{"event": "category_view", "count": 1}]
    assert saved["requests"][0]["average_ms"] == 25

    article = {"headline": "A verified report", "body": [{"sources": ["https://example.com/source"]}]}
    reports = ReportService()
    monkeypatch.setattr(reports.news, "get_article", lambda *_: article)
    report_id = reports.add("2026-10-12", "group_1", "wrong_fact", "Please check", article)
    correction = reports.publish_correction(report_id, "The corrected fact.")
    assert correction["text"] == "The corrected fact."
    assert reports.latest()[0]["status"] == "resolved"
    assert database_ready() is True


def test_legacy_sqlite_data_migrates_once(monkeypatch, tmp_path):
    postgres_url = os.environ["TEST_POSTGRES_URL"]
    cache = tmp_path / "legacy-cache"
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setenv("CACHE_DIR", str(cache))
    call_id = generation.start_call("LEGACY", "model")
    generation.finish_call(call_id, failed=True)
    analytics.record_event("page_view")
    legacy_reports = ReportService()
    legacy_reports.add("2026-10-11", "group_2", "other", "Legacy report")

    monkeypatch.setenv("DATABASE_URL", postgres_url)
    first = migrate(cache)
    second = migrate(cache)
    assert first["generation_calls"] == 1
    assert first["analytics_events"] == 1
    assert first["reports"] == 1
    assert second == {}
    with connect("generation") as database:
        assert database.execute("SELECT COUNT(*) AS count FROM generation_calls").fetchone()["count"] == 1
    assert ReportService().latest()[0]["message"] == "Legacy report"
