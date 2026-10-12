import io
import json
from pathlib import Path

import pytest

from app.core.object_storage import pull, push


class MissingObject(Exception):
    response = {"Error": {"Code": "404"}}


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.calls = []

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise MissingObject()
        return {"Metadata": self.objects[Key].get("Metadata", {})}

    def upload_file(self, filename, bucket, key, ExtraArgs):
        self.calls.append(("file", key))
        self.objects[key] = {"Body": Path(filename).read_bytes(), **ExtraArgs}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.calls.append(("manifest", Key))
        self.objects[Key] = {"Body": Body, **kwargs}

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key]["Body"])}

    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[key]["Body"])


@pytest.fixture(autouse=True)
def storage_config(monkeypatch):
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "news-test")
    monkeypatch.setenv("OBJECT_STORAGE_PREFIX", "production/news")


def test_push_publishes_manifest_last_and_pull_verifies_files(tmp_path):
    source = tmp_path / "source"
    (source / "articles" / "2026-10-12").mkdir(parents=True)
    article = source / "articles" / "2026-10-12" / "group_1.json"
    article.write_text('{"headline":"Durable"}', encoding="utf-8")
    (source / "model_catalog.json").write_text("{}", encoding="utf-8")
    storage = FakeStorage()

    assert push(source, storage) == 2
    assert storage.calls[-1] == ("manifest", "production/news/manifest.json")
    assert push(source, storage) == 0

    restored = tmp_path / "restored"
    assert pull(restored, storage) == 2
    assert (restored / "articles" / "2026-10-12" / "group_1.json").read_bytes() == article.read_bytes()
    assert pull(restored, storage) == 0


def test_pull_rejects_manifest_path_traversal(tmp_path):
    storage = FakeStorage()
    storage.objects["production/news/manifest.json"] = {
        "Body": json.dumps({"version": 1, "files": [
            {"path": "../escape", "size": 1, "sha256": "0" * 64}
        ]}).encode()
    }
    with pytest.raises(RuntimeError, match="Unsafe object-storage path"):
        pull(tmp_path / "restore", storage)


def test_pull_does_not_publish_corrupt_download(tmp_path):
    storage = FakeStorage()
    storage.objects["production/news/manifest.json"] = {
        "Body": json.dumps({"version": 1, "files": [
            {"path": "articles/item.json", "size": 4, "sha256": "0" * 64}
        ]}).encode()
    }
    storage.objects["production/news/articles/item.json"] = {"Body": b"bad!"}
    destination = tmp_path / "restore"
    with pytest.raises(RuntimeError, match="integrity check failed"):
        pull(destination, storage)
    assert not (destination / "articles" / "item.json").exists()
