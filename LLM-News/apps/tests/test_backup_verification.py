import io
import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from scripts.verify_backup import BackupVerificationError, verify


def archive_directory(source: Path, destination: Path) -> None:
    with tarfile.open(destination, "w:gz") as bundle:
        for path in source.rglob("*"):
            bundle.add(path, arcname=path.relative_to(source))


def valid_archives(tmp_path: Path) -> tuple[Path, Path]:
    static = tmp_path / "static"
    article_dir = static / "articles" / "2026-10-12"
    article_dir.mkdir(parents=True)
    (static / "model_catalog.json").write_text(json.dumps({"models": []}), encoding="utf-8")
    (article_dir / "group_1.json").write_text(json.dumps({"headline": "Verified"}), encoding="utf-8")
    (article_dir / "group_categories.json").write_text(json.dumps({"group_1": "tech"}), encoding="utf-8")

    cache = tmp_path / "cache"
    cache.mkdir()
    with sqlite3.connect(cache / "generation.db") as database:
        database.execute("CREATE TABLE runs(id INTEGER PRIMARY KEY)")

    static_archive, cache_archive = tmp_path / "static.tar.gz", tmp_path / "cache.tar.gz"
    archive_directory(static, static_archive)
    archive_directory(cache, cache_archive)
    return static_archive, cache_archive


def test_valid_backup_is_restorable(tmp_path):
    assert verify(*valid_archives(tmp_path), working_directory=tmp_path) == (1, 1)


def test_archive_path_traversal_is_rejected(tmp_path):
    static_archive, cache_archive = valid_archives(tmp_path)
    with tarfile.open(static_archive, "w:gz") as bundle:
        payload = b"escape"
        member = tarfile.TarInfo("../outside.txt")
        member.size = len(payload)
        bundle.addfile(member, io.BytesIO(payload))
    with pytest.raises(BackupVerificationError, match="Unsafe archive entry"):
        verify(static_archive, cache_archive, working_directory=tmp_path)


def test_corrupt_database_is_rejected(tmp_path):
    static_archive, cache_archive = valid_archives(tmp_path)
    cache = tmp_path / "bad-cache"
    cache.mkdir()
    (cache / "generation.db").write_bytes(b"not a sqlite database")
    archive_directory(cache, cache_archive)
    with pytest.raises(BackupVerificationError, match="Unreadable SQLite database"):
        verify(static_archive, cache_archive, working_directory=tmp_path)


def test_missing_declared_media_is_rejected(tmp_path):
    static_archive, cache_archive = valid_archives(tmp_path)
    article = tmp_path / "static" / "articles" / "2026-10-12" / "group_1.json"
    article.write_text(json.dumps({"headline": "Verified", "image_file": "group_1.webp"}), encoding="utf-8")
    archive_directory(tmp_path / "static", static_archive)
    with pytest.raises(BackupVerificationError, match="Article image is missing"):
        verify(static_archive, cache_archive, working_directory=tmp_path)
