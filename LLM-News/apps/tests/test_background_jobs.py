from concurrent.futures import ThreadPoolExecutor

from app.core import jobs


def test_jobs_are_claimed_once_and_completed(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    job_id = jobs.enqueue("warm_digest", {"date": "2026-10-12"})

    with ThreadPoolExecutor(max_workers=4) as workers:
        claimed = list(workers.map(lambda _: jobs.claim(), range(4)))
    saved = [item for item in claimed if item]
    assert len(saved) == 1 and saved[0]["id"] == job_id
    assert saved[0]["payload"] == {"date": "2026-10-12"}
    jobs.complete(job_id)
    assert jobs.summary()["counts"] == {"succeeded": 1}


def test_terminal_failure_is_inspectable_without_private_error_text(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    job_id = jobs.enqueue("warm_audio", {"date": "2026-10-12"}, max_attempts=1)
    assert jobs.claim()["id"] == job_id
    assert jobs.fail(job_id, RuntimeError("secret provider response")) is True
    saved = jobs.summary()
    assert saved["counts"] == {"failed": 1}
    assert saved["failed"][0]["last_error"] == "RuntimeError"


def test_news_update_is_unique_and_exposes_only_progress(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    first, created = jobs.enqueue_unique(
        "news_update", {"secret": "never expose", "progress": {"phase": "queued", "percent": 0}},
        max_attempts=1,
    )
    second, second_created = jobs.enqueue_unique("news_update", {"progress": {"phase": "queued"}})
    assert (second, second_created) == (first, False)

    assert jobs.claim()["id"] == first
    jobs.update_progress(first, {"phase": "generating", "percent": 25, "category": "tech"})
    saved = jobs.latest("news_update")
    assert saved["status"] == "running"
    assert saved["progress"] == {"phase": "generating", "percent": 25, "category": "tech"}
    assert "secret" not in str(saved)

    jobs.complete(first)
    assert jobs.latest("news_update")["status"] == "succeeded"
