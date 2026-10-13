"""Persistent call caps and operational metrics never require an AI provider."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from apps.app.core import generation
from llm_client import LLMClient


@pytest.fixture(autouse=True)
def usage_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("PIPELINE_DAILY_CALL_LIMIT", "3")


def test_failed_calls_still_consume_persistent_allowance():
    for _ in range(3):
        call = generation.start_call("Mock", "writer")
        generation.finish_call(call, failed=True)
    with pytest.raises(generation.PipelineBudgetExceeded):
        generation.start_call("Mock", "writer")
    usage = generation.usage_summary()
    assert usage["pipeline_calls"] == 3 and usage["remaining"] == 0
    assert usage["models"][0]["failed"] == 3


def test_parallel_process_reservations_cannot_exceed_cap():
    def reserve(_):
        try:
            return generation.start_call("Mock", "writer")
        except generation.PipelineBudgetExceeded:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        calls = list(pool.map(reserve, range(12)))
    assert len([call for call in calls if call is not None]) == 3
    assert generation.usage_summary()["pipeline_calls"] == 3


def test_budget_change_survives_new_connections_and_can_be_disabled():
    generation.set_pipeline_limit(1)
    generation.start_call("Mock", "writer")
    with pytest.raises(generation.PipelineBudgetExceeded):
        generation.start_call("Mock", "writer")
    assert generation.set_pipeline_limit(0)["remaining"] is None
    generation.start_call("Mock", "writer")


def test_website_metrics_do_not_consume_pipeline_allowance():
    call = generation.start_call("Mock", "chat", scope="website")
    generation.finish_call(call, SimpleNamespace(usage=SimpleNamespace(prompt_tokens=25, completion_tokens=10)))
    usage = generation.usage_summary()
    assert usage["pipeline_calls"] == 0
    assert usage["models"][0]["prompt_tokens"] == 25


def test_daily_allowance_resets_at_local_midnight(monkeypatch):
    real_date = generation.date
    generation.set_pipeline_limit(1)
    generation.start_call("Mock", "writer")
    next_day = real_date(2099, 1, 1)
    monkeypatch.setattr(generation, "date", SimpleNamespace(today=lambda: next_day))
    assert generation.usage_summary()["pipeline_calls"] == 0
    generation.start_call("Mock", "writer")


def test_pipeline_client_reserves_before_contacting_provider():
    requests = []
    def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=15, completion_tokens=5))
    client = LLMClient.__new__(LLMClient)
    client.publisher = "Mock"
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    generation.set_pipeline_limit(1)
    client.generate("a prompt", model="writer")
    with pytest.raises(generation.PipelineBudgetExceeded):
        client.generate("another prompt", model="writer")
    assert len(requests) == 1
    assert generation.usage_summary()["models"][0]["completion_tokens"] == 5


def test_feed_failures_and_held_back_runs_are_recorded_without_raw_error_text():
    generation.record_feed("Outlet", "https://example.com/feed", "tech", False)
    run = generation.start_run("2026-10-09")
    generation.finish_run(run, False, held_back=2)
    assert generation.feed_statuses()[0]["ok"] is False
    assert generation.recent_runs()[0]["held_back"] == 2
    assert generation.recent_runs()[0]["status"] == "failed"
    generation.record_hold("2026-10-09", "tech", "Draft headline", "held back (fact-check failed)")
    assert generation.held_stories()[0]["headline"] == "Draft headline"
    assert generation.held_stories()[0]["reason"] == "held back (fact-check failed)"


def test_update_lease_prevents_overlapping_generators():
    assert generation.acquire_update_lease("worker-one", 60) is True
    assert generation.acquire_update_lease("worker-two", 60) is False
    generation.release_update_lease("worker-two")
    assert generation.acquire_update_lease("worker-two", 60) is False
    generation.release_update_lease("worker-one")
    assert generation.acquire_update_lease("worker-two", 60) is True


def test_failed_telemetry_does_not_discard_paid_response(monkeypatch):
    import llm_client
    response = SimpleNamespace(usage=None)
    client = LLMClient.__new__(LLMClient)
    client.publisher = "Mock"
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response)))
    def broken_record(*args, **kwargs):
        raise OSError("cache unavailable")
    monkeypatch.setattr(llm_client, "finish_call", broken_record)
    assert client.generate("prompt", model="writer") is response
    assert generation.usage_summary()["pipeline_calls"] == 1


def test_currency_limit_reserves_then_reconciles_actual_token_cost(monkeypatch):
    monkeypatch.setenv("MOCK_INPUT_USD_PER_MTOK", "1")
    monkeypatch.setenv("MOCK_OUTPUT_USD_PER_MTOK", "2")
    monkeypatch.setenv("AI_DAILY_SPEND_LIMIT_USD", "0.02")
    monkeypatch.setenv("AI_MONTHLY_SPEND_LIMIT_USD", "1")
    first = generation.start_call("Mock", "writer")  # reserves $0.016
    generation.finish_call(first, SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=1000, completion_tokens=100)))  # reconciles to $0.0012
    second = generation.start_call("Mock", "writer")
    with pytest.raises(generation.PipelineSpendExceeded, match="daily"):
        generation.start_call("Mock", "writer")
    saved = generation.usage_summary()
    assert saved["daily_spent_usd"] == 0.0172
    assert saved["models"][0]["unpriced_calls"] == 0
    generation.finish_call(second, failed=True)  # no usage keeps the conservative reservation


def test_unpriced_calls_are_visible_to_the_owner():
    generation.start_call("Unknown Provider", "unknown-model")
    saved = generation.usage_summary()
    assert saved["models"][0]["unpriced_calls"] == 1
    assert saved["models"][0]["spent_usd"] == 0
