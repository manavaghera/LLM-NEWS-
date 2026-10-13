"""The cloud updater can refresh an ephemeral backend without exposing storage controls."""
import pytest
from fastapi import HTTPException

from app.api.endpoints import storage


TOKEN = "storage-sync-token-that-is-long-enough"


def test_storage_sync_is_hidden_without_the_dedicated_token(monkeypatch):
    monkeypatch.setenv("STORAGE_SYNC_TOKEN", TOKEN)
    monkeypatch.setattr(storage, "pull", lambda _root: (_ for _ in ()).throw(
        AssertionError("Unauthorized requests must not access object storage")
    ))

    with pytest.raises(HTTPException) as missing:
        storage.sync_storage(None)
    assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as wrong:
        storage.sync_storage("Bearer wrong")
    assert wrong.value.status_code == 404


def test_storage_sync_pulls_the_signed_manifest(monkeypatch, static_root):
    roots = []
    monkeypatch.setenv("STORAGE_SYNC_TOKEN", TOKEN)
    monkeypatch.setattr(storage, "configured", lambda: True)
    monkeypatch.setattr(storage, "pull", lambda root: roots.append(root) or 4)

    response = storage.sync_storage(f"Bearer {TOKEN}")

    assert response == {"status": "synchronized", "files_changed": 4}
    assert roots == [storage.Path("static")]


def test_storage_sync_reports_unavailable_storage(monkeypatch):
    monkeypatch.setenv("STORAGE_SYNC_TOKEN", TOKEN)
    monkeypatch.setattr(storage, "configured", lambda: False)

    with pytest.raises(HTTPException) as unavailable:
        storage.sync_storage(f"Bearer {TOKEN}")
    assert unavailable.value.status_code == 503
    assert unavailable.value.detail == "Object storage is not configured"
