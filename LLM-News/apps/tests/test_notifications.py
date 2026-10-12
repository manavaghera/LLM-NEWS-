import sys
from types import SimpleNamespace

from app.core import notifications


def test_push_subscription_update_and_token_protected_removal(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    endpoint = "https://push.example.test/subscription/one"
    first = notifications.subscribe(endpoint, "p" * 40, "a" * 20, ["tech"], ["chips"])
    second = notifications.subscribe(endpoint, "q" * 40, "b" * 20, ["science"], ["fusion"], first)
    assert first == second
    assert notifications.summary() == {"total": 1, "active": 1, "errors": 0}
    assert notifications.unsubscribe(endpoint, "invalid-management-token-value-000000") is False
    assert notifications.unsubscribe(endpoint, second) is True
    assert notifications.summary()["total"] == 0


def test_delivery_only_sends_matching_topics(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:owner@example.test")
    notifications.subscribe("https://push.example.test/one", "p" * 40, "a" * 20, ["tech"], [])
    notifications.subscribe("https://push.example.test/two", "q" * 40, "b" * 20, ["science"], [])
    sent = []

    class WebPushException(Exception):
        pass

    monkeypatch.setitem(sys.modules, "pywebpush", SimpleNamespace(
        WebPushException=WebPushException,
        webpush=lambda **kwargs: sent.append(kwargs),
    ))
    result = notifications.deliver([{
        "date": "2026-10-12", "group_id": "group_1", "category": "tech", "headline": "New chip",
    }])
    assert result == {"sent": 1, "skipped": False}
    assert len(sent) == 1
