"""Copy legacy operational SQLite data into the configured PostgreSQL database.

The import only inserts missing primary keys, so it is safe to retry and never replaces
newer PostgreSQL records. A completion marker makes normal container restarts inexpensive.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# The script is executed from /app in the backend container and from apps/ in local use.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import _initialize, connect, using_postgres  # noqa: E402


MIGRATION_NAME = "legacy-sqlite-operational-v1"
TABLES = {
    "generation": {
        "generation_settings": (("key", "value"), ("key",)),
        "generation_calls": (("id", "day", "started_at", "scope", "provider", "model", "status",
                              "prompt_tokens", "completion_tokens"), ("id",)),
        "generation_feeds": (("url", "category", "publisher", "ok", "items", "full_text_items",
                              "error", "last_checked"), ("url", "category")),
        "generation_runs": (("id", "started_at", "finished_at", "date", "status", "added",
                             "held_back", "error"), ("id",)),
        "generation_holds": (("id", "created_at", "date", "category", "headline", "reason"), ("id",)),
    },
    "analytics": {
        "analytics_events": (("day", "event", "count"), ("day", "event")),
        "runtime_requests": (("day", "route", "method", "status_group", "count", "total_ms", "max_ms"),
                             ("day", "route", "method", "status_group")),
        "analytics_breakdowns": (("day", "event", "detail", "count"), ("day", "event", "detail")),
    },
    "reports": {
        "reports": (("id", "created_at", "date", "group_id", "kind", "message"), ("id",)),
        "report_articles": (("report_id", "story_identity", "original_headline"), ("report_id",)),
        "report_resolutions": (("report_id", "status", "resolution", "resolved_at"), ("report_id",)),
        "corrections": (("id", "report_id", "created_at", "text"), ("id",)),
    },
}
IDENTITY_TABLES = ("generation_calls", "generation_runs", "generation_holds", "reports", "corrections")


def _sqlite_rows(path: Path, table: str, columns: tuple[str, ...]) -> list[tuple]:
    if not path.is_file():
        return []
    with sqlite3.connect(path) as source:
        exists = source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            return []
        names = {row[1] for row in source.execute(f'PRAGMA table_info("{table}")')}
        if not set(columns).issubset(names):
            missing = ", ".join(sorted(set(columns) - names))
            raise RuntimeError(f"{path.name}:{table} is missing columns: {missing}")
        selected = ",".join(f'"{column}"' for column in columns)
        return source.execute(f'SELECT {selected} FROM "{table}"').fetchall()


def migrate(cache_dir: Path, if_present: bool = False) -> dict[str, int]:
    if not using_postgres():
        if if_present:
            return {}
        raise RuntimeError("DATABASE_URL must point to PostgreSQL before migration")

    sources = {namespace: cache_dir / f"{namespace}.db" for namespace in TABLES}
    if not any(path.is_file() for path in sources.values()):
        if if_present:
            return {}
        raise RuntimeError(f"No legacy SQLite databases found under {cache_dir}")

    imported: dict[str, int] = {}
    # One PostgreSQL transaction and advisory lock cover all namespaces. This prevents two
    # backend replicas from racing through the first deployment migration.
    with connect("generation") as target:
        target.write_lock("sqlite-operational-migration")
        if target.execute("SELECT 1 AS found FROM storage_migrations WHERE name=?", (MIGRATION_NAME,)).fetchone():
            return {}
        for namespace, tables in TABLES.items():
            if namespace != "generation":
                _initialize(target, namespace)
            for table, (columns, primary_key) in tables.items():
                rows = _sqlite_rows(sources[namespace], table, columns)
                if not rows:
                    imported[table] = 0
                    continue
                fields = ",".join(columns)
                values = ",".join("?" for _ in columns)
                conflict = ",".join(primary_key)
                target.executemany(
                    f"INSERT INTO {table} ({fields}) VALUES ({values}) ON CONFLICT ({conflict}) DO NOTHING",
                    rows,
                )
                imported[table] = len(rows)

            for table in IDENTITY_TABLES:
                if table in tables:
                    target.execute(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table}"
                    )
        target.execute(
            "INSERT INTO storage_migrations(name,completed_at) VALUES(?,?) ON CONFLICT(name) DO NOTHING",
            (MIGRATION_NAME, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=Path(os.getenv("CACHE_DIR", "cache")))
    parser.add_argument("--if-present", action="store_true", help="succeed when no legacy database exists")
    args = parser.parse_args()
    try:
        imported = migrate(args.cache_dir, args.if_present)
    except (OSError, RuntimeError, sqlite3.DatabaseError) as exc:
        print(f"SQLite migration failed: {exc}", file=sys.stderr)
        return 1
    if imported:
        print("Imported legacy operational rows: " + ", ".join(f"{key}={value}" for key, value in imported.items()))
    else:
        print("No legacy operational rows require migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
