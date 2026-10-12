"""Small SQL compatibility layer for SQLite development and PostgreSQL production.

Set DATABASE_URL to a PostgreSQL connection URL to place all operational tables in one
database. Without it, each namespace keeps its existing SQLite file under CACHE_DIR.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable


_INITIALIZED: set[tuple[str, str, str]] = set()
_INITIALIZE_LOCK = threading.Lock()


SQLITE_SCHEMAS = {
    "generation": """
        CREATE TABLE IF NOT EXISTS generation_settings (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS generation_calls (
            id INTEGER PRIMARY KEY, day TEXT NOT NULL, started_at TEXT NOT NULL,
            scope TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
            status TEXT NOT NULL, prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS generation_costs (
            call_id INTEGER PRIMARY KEY REFERENCES generation_calls(id) ON DELETE CASCADE,
            reserved_microusd INTEGER NOT NULL DEFAULT 0,
            actual_microusd INTEGER,
            priced INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS generation_model_prices (
            provider TEXT NOT NULL, model TEXT NOT NULL,
            input_microusd_per_million INTEGER NOT NULL,
            output_microusd_per_million INTEGER NOT NULL,
            source TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(provider, model));
        CREATE INDEX IF NOT EXISTS generation_calls_day ON generation_calls(day, scope);
        CREATE TABLE IF NOT EXISTS generation_feeds (
            url TEXT NOT NULL, category TEXT NOT NULL, publisher TEXT NOT NULL,
            ok INTEGER NOT NULL, items INTEGER NOT NULL, full_text_items INTEGER NOT NULL,
            error TEXT NOT NULL, last_checked TEXT NOT NULL, PRIMARY KEY(url, category));
        CREATE TABLE IF NOT EXISTS generation_runs (
            id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
            date TEXT NOT NULL, status TEXT NOT NULL, added INTEGER NOT NULL DEFAULT 0,
            held_back INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS generation_holds (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, date TEXT NOT NULL,
            category TEXT NOT NULL, headline TEXT NOT NULL, reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS generation_leases (
            name TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at TEXT NOT NULL);
    """,
    "analytics": """
        CREATE TABLE IF NOT EXISTS analytics_events (
            day TEXT NOT NULL, event TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(day, event));
        CREATE TABLE IF NOT EXISTS runtime_requests (
            day TEXT NOT NULL, route TEXT NOT NULL, method TEXT NOT NULL, status_group TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0, total_ms INTEGER NOT NULL DEFAULT 0,
            max_ms INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(day, route, method, status_group));
        CREATE TABLE IF NOT EXISTS analytics_breakdowns (
            day TEXT NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(day,event,detail));
    """,
    "reports": """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, date TEXT NOT NULL,
            group_id TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS report_articles (
            report_id INTEGER PRIMARY KEY REFERENCES reports(id) ON DELETE CASCADE,
            story_identity TEXT NOT NULL, original_headline TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS report_resolutions (
            report_id INTEGER PRIMARY KEY REFERENCES reports(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('open', 'resolved', 'dismissed')),
            resolution TEXT NOT NULL, resolved_at TEXT);
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL, text TEXT NOT NULL, UNIQUE(report_id, text));
    """,
    "admin": """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','editor','viewer')),
            totp_secret TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, last_login_at TEXT);
        CREATE TABLE IF NOT EXISTS admin_sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            user_id INTEGER REFERENCES admin_users(id) ON DELETE SET NULL,
            action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
    """,
    "jobs": """
        CREATE TABLE IF NOT EXISTS background_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
            attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 5,
            run_after TEXT NOT NULL, created_at TEXT NOT NULL, locked_at TEXT,
            finished_at TEXT, last_error TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS background_jobs_ready ON background_jobs(status,run_after,id);
    """,
}

POSTGRES_SCHEMAS = {
    "generation": """
        CREATE TABLE IF NOT EXISTS storage_migrations (
            name TEXT PRIMARY KEY, completed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS generation_settings (key TEXT PRIMARY KEY, value BIGINT NOT NULL);
        CREATE TABLE IF NOT EXISTS generation_calls (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, day TEXT NOT NULL,
            started_at TEXT NOT NULL, scope TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
            status TEXT NOT NULL, prompt_tokens BIGINT NOT NULL DEFAULT 0,
            completion_tokens BIGINT NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS generation_costs (
            call_id BIGINT PRIMARY KEY REFERENCES generation_calls(id) ON DELETE CASCADE,
            reserved_microusd BIGINT NOT NULL DEFAULT 0,
            actual_microusd BIGINT,
            priced SMALLINT NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS generation_model_prices (
            provider TEXT NOT NULL, model TEXT NOT NULL,
            input_microusd_per_million BIGINT NOT NULL,
            output_microusd_per_million BIGINT NOT NULL,
            source TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(provider, model));
        CREATE INDEX IF NOT EXISTS generation_calls_day ON generation_calls(day, scope);
        CREATE TABLE IF NOT EXISTS generation_feeds (
            url TEXT NOT NULL, category TEXT NOT NULL, publisher TEXT NOT NULL,
            ok SMALLINT NOT NULL, items BIGINT NOT NULL, full_text_items BIGINT NOT NULL,
            error TEXT NOT NULL, last_checked TEXT NOT NULL, PRIMARY KEY(url, category));
        CREATE TABLE IF NOT EXISTS generation_runs (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, started_at TEXT NOT NULL,
            finished_at TEXT, date TEXT NOT NULL, status TEXT NOT NULL, added BIGINT NOT NULL DEFAULT 0,
            held_back BIGINT NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS generation_holds (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, created_at TEXT NOT NULL,
            date TEXT NOT NULL, category TEXT NOT NULL, headline TEXT NOT NULL, reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS generation_leases (
            name TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at TEXT NOT NULL);
    """,
    "analytics": """
        CREATE TABLE IF NOT EXISTS analytics_events (
            day TEXT NOT NULL, event TEXT NOT NULL, count BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY(day, event));
        CREATE TABLE IF NOT EXISTS runtime_requests (
            day TEXT NOT NULL, route TEXT NOT NULL, method TEXT NOT NULL, status_group TEXT NOT NULL,
            count BIGINT NOT NULL DEFAULT 0, total_ms BIGINT NOT NULL DEFAULT 0,
            max_ms BIGINT NOT NULL DEFAULT 0, PRIMARY KEY(day, route, method, status_group));
        CREATE TABLE IF NOT EXISTS analytics_breakdowns (
            day TEXT NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL,
            count BIGINT NOT NULL DEFAULT 0, PRIMARY KEY(day,event,detail));
    """,
    "reports": """
        CREATE TABLE IF NOT EXISTS reports (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, created_at TEXT NOT NULL,
            date TEXT NOT NULL, group_id TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS report_articles (
            report_id BIGINT PRIMARY KEY REFERENCES reports(id) ON DELETE CASCADE,
            story_identity TEXT NOT NULL, original_headline TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS report_resolutions (
            report_id BIGINT PRIMARY KEY REFERENCES reports(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('open', 'resolved', 'dismissed')),
            resolution TEXT NOT NULL, resolved_at TEXT);
        CREATE TABLE IF NOT EXISTS corrections (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            report_id BIGINT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL, text TEXT NOT NULL, UNIQUE(report_id, text));
    """,
    "admin": """
        CREATE TABLE IF NOT EXISTS admin_users (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','editor','viewer')),
            totp_secret TEXT NOT NULL DEFAULT '', active SMALLINT NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, last_login_at TEXT);
        CREATE TABLE IF NOT EXISTS admin_sessions (
            token_hash TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin_audit (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, created_at TEXT NOT NULL,
            user_id BIGINT REFERENCES admin_users(id) ON DELETE SET NULL,
            action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
    """,
    "jobs": """
        CREATE TABLE IF NOT EXISTS background_jobs (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
            attempts BIGINT NOT NULL DEFAULT 0, max_attempts BIGINT NOT NULL DEFAULT 5,
            run_after TEXT NOT NULL, created_at TEXT NOT NULL, locked_at TEXT,
            finished_at TEXT, last_error TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS background_jobs_ready ON background_jobs(status,run_after,id);
    """,
}


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def using_postgres() -> bool:
    return bool(_database_url())


def database_ready() -> bool:
    """Return whether the configured operational database accepts a simple query."""
    try:
        with connect("generation") as database:
            return database.execute("SELECT 1 AS ready").fetchone()["ready"] == 1
    except Exception:
        return False


def sqlite_path(namespace: str) -> Path:
    root = Path(os.getenv("CACHE_DIR", str(Path(__file__).resolve().parents[2] / "cache")))
    return root / f"{namespace}.db"


class Database:
    def __init__(self, connection, dialect: str):
        self.connection = connection
        self.dialect = dialect

    def _sql(self, statement: str) -> str:
        return statement.replace("?", "%s") if self.dialect == "postgres" else statement

    def execute(self, statement: str, parameters=()):
        return self.connection.execute(self._sql(statement), parameters)

    def executemany(self, statement: str, parameters: Iterable):
        if self.dialect == "postgres":
            cursor = self.connection.cursor()
            try:
                cursor.executemany(self._sql(statement), parameters)
            finally:
                cursor.close()
            return None
        return self.connection.executemany(statement, parameters)

    def write_lock(self, name: str) -> None:
        if self.dialect == "postgres":
            self.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (name,))
        else:
            self.execute("BEGIN IMMEDIATE")

    def insert_id(self, statement: str, parameters=()) -> int:
        if self.dialect == "postgres":
            row = self.execute(f"{statement} RETURNING id", parameters).fetchone()
            return int(row["id"])
        return int(self.execute(statement, parameters).lastrowid)


def _initialize(database: Database, namespace: str) -> None:
    schema = POSTGRES_SCHEMAS[namespace] if database.dialect == "postgres" else SQLITE_SCHEMAS[namespace]
    if database.dialect == "sqlite":
        database.connection.executescript(schema)
        return
    for statement in schema.split(";"):
        if statement.strip():
            database.execute(statement)


def _ensure_initialized(database: Database, namespace: str, location: str) -> None:
    key = (database.dialect, namespace, location)
    if key in _INITIALIZED:
        return
    with _INITIALIZE_LOCK:
        if key not in _INITIALIZED:
            _initialize(database, namespace)
            database.connection.commit()
            _INITIALIZED.add(key)


@contextmanager
def connect(namespace: str):
    if namespace not in SQLITE_SCHEMAS:
        raise ValueError(f"Unknown database namespace: {namespace}")
    url = _database_url()
    if url:
        if not url.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must use PostgreSQL")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - only possible in a misbuilt production image
            raise RuntimeError("PostgreSQL support requires psycopg") from exc
        raw = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
        database = Database(raw, "postgres")
        location = url
    else:
        path = sqlite_path(namespace)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(path, timeout=30)
        raw.row_factory = sqlite3.Row
        if namespace == "reports":
            raw.execute("PRAGMA foreign_keys = ON")
        database = Database(raw, "sqlite")
        location = str(path.resolve())
    try:
        _ensure_initialized(database, namespace, location)
        yield database
        raw.commit()
    except BaseException:
        raw.rollback()
        raise
    finally:
        raw.close()
