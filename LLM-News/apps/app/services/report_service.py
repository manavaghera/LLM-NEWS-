"""Reader reports ("Report a problem") stored in SQLite in the writable cache folder.

Only what the reader typed is kept: no IP address, account or other personal data.
"""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Dict, Iterable, List

from ..core.config import settings

KINDS = {
    "wrong_fact": "A fact is wrong",
    "missing_context": "Important context is missing",
    "bad_source": "A source doesn't say this",
    "other": "Something else",
}


class ReportService:
    def __init__(self):
        self.path = settings.CACHE_DIR / "reports.db"

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute(
            """CREATE TABLE IF NOT EXISTS reports (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   created_at TEXT NOT NULL,
                   date TEXT NOT NULL,
                   group_id TEXT NOT NULL,
                   kind TEXT NOT NULL,
                   message TEXT NOT NULL
               )"""
        )
        return connection

    def add(self, date: str, group_id: str, kind: str, message: str) -> int:
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "INSERT INTO reports (created_at, date, group_id, kind, message) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), date, group_id, kind, message.strip()),
            )
            return int(cursor.lastrowid)

    def counts_by_date(self, dates: Iterable[str]) -> Dict[str, int]:
        dates = list(dates)
        if not dates or not self.path.exists():
            return {}
        marks = ",".join("?" for _ in dates)
        with closing(self._connect()) as db:
            rows = db.execute(f"SELECT date, COUNT(*) FROM reports WHERE date IN ({marks}) GROUP BY date", dates)
            return {date: count for date, count in rows}

    def latest(self, limit: int = 200) -> List[Dict]:
        if not self.path.exists():
            return []
        with closing(self._connect()) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in rows]
