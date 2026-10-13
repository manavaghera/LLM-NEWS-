"""Validate backup contents in a temporary directory without modifying live data."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import tarfile
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory


class BackupVerificationError(RuntimeError):
    pass


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    root = destination.resolve()
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle.getmembers():
                target = (root / member.name).resolve()
                if (not target.is_relative_to(root) or member.issym() or member.islnk()
                        or not (member.isfile() or member.isdir())):
                    raise BackupVerificationError(f"Unsafe archive entry: {member.name}")
            bundle.extractall(root)
    except (OSError, tarfile.TarError) as exc:
        raise BackupVerificationError(f"Unreadable archive {archive.name}: {exc}") from exc


def verify(static_archive: Path, cache_archive: Path, working_directory: Path | None = None) -> tuple[int, int]:
    with TemporaryDirectory(prefix="newssense-restore-", dir=working_directory) as temporary:
        root = Path(temporary)
        static_dir, cache_dir = root / "static", root / "cache"
        _safe_extract(static_archive, static_dir)
        _safe_extract(cache_archive, cache_dir)

        catalog = static_dir / "model_catalog.json"
        if not catalog.is_file():
            raise BackupVerificationError("Static backup is missing model_catalog.json")
        try:
            json.loads(catalog.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BackupVerificationError("model_catalog.json is unreadable or invalid") from exc

        articles = [path for path in (static_dir / "articles").glob("*/group_*.json")
                    if re.fullmatch(r"group_\d+\.json", path.name)]
        if not articles:
            raise BackupVerificationError("Static backup contains no published articles")
        for article in articles:
            try:
                saved = json.loads(article.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise BackupVerificationError(f"Invalid article JSON: {article.name}") from exc
            if not isinstance(saved, dict) or not str(saved.get("headline", "")).strip():
                raise BackupVerificationError(f"Article has no headline: {article.name}")
            try:
                categories = json.loads((article.parent / "group_categories.json").read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise BackupVerificationError(f"Missing or invalid categories for {article.parent.name}") from exc
            if not isinstance(categories, dict) or article.stem not in categories:
                raise BackupVerificationError(f"Category mapping is missing {article.stem}")
            image_name = str(saved.get("image_file") or "")
            if image_name:
                image = (static_dir / "images" / article.parent.name / image_name).resolve()
                image_root = (static_dir / "images" / article.parent.name).resolve()
                if not image.is_relative_to(image_root) or not image.is_file():
                    raise BackupVerificationError(f"Article image is missing: {image_name}")

        databases = list(cache_dir.glob("*.db"))
        for database in databases:
            try:
                with closing(sqlite3.connect(database)) as connection:
                    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            except sqlite3.DatabaseError as exc:
                raise BackupVerificationError(f"Unreadable SQLite database: {database.name}") from exc
            if result != "ok":
                raise BackupVerificationError(f"SQLite integrity check failed for {database.name}: {result}")
        return len(articles), len(databases)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: verify_backup.py STATIC_ARCHIVE CACHE_ARCHIVE", file=sys.stderr)
        return 2
    try:
        configured_work = os.getenv("BACKUP_VERIFY_WORK_DIR")
        articles, databases = verify(Path(sys.argv[1]), Path(sys.argv[2]),
                                      Path(configured_work) if configured_work else None)
    except BackupVerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"verified {articles} articles and {databases} databases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
