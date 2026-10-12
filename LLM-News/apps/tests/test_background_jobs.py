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
    jobs.fail(job_id, RuntimeError("secret provider response"))
    saved = jobs.summary()
    assert saved["counts"] == {"failed": 1}
    assert saved["failed"][0]["last_error"] == "RuntimeError"
