from app.core import monitoring


class Response:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_alerts_are_recorded_and_deduplicated(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://alerts.example.test/hook")
    sent = []
    monkeypatch.setattr(monitoring.urllib.request, "urlopen", lambda request, timeout: sent.append(request) or Response())

    assert monitoring.alert("updater", "update_failed", "Update failed") is True
    assert monitoring.alert("updater", "update_failed", "Update failed again") is False
    assert len(sent) == 1
    assert monitoring.recent_events()[0]["event"] == "update_failed"


def test_no_webhook_still_records_event(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    assert monitoring.alert("worker", "job_failed", "Job failed") is False
    assert monitoring.recent_events()[0]["component"] == "worker"
