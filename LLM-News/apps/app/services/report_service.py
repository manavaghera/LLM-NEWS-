"""Reader reports and corrections stored in SQLite or the configured PostgreSQL database.

Only what the reader typed is kept: no IP address, account or other personal data.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Iterable, List

from ..core.database import connect, sqlite_path, using_postgres
from .news_service import NewsService
from .story_identity import story_identity

KINDS = {
    "wrong_fact": "A fact is wrong",
    "missing_context": "Important context is missing",
    "bad_source": "A source doesn't say this",
    "other": "Something else",
}


class ReportService:
    def __init__(self):
        self.news = NewsService()

    @contextmanager
    def _connect(self):
        with connect("reports") as database:
            yield database

    def _storage_exists(self) -> bool:
        # CACHE_DIR changes between tests and can change between deployment environments.
        # Resolve it when queried instead of caching a path when this service is imported.
        return using_postgres() or sqlite_path("reports").exists()

    def add(self, date: str, group_id: str, kind: str, message: str, article: Dict = None) -> int:
        with self._connect() as db:
            report_id = db.insert_id(
                "INSERT INTO reports (created_at, date, group_id, kind, message) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), date, group_id, kind, message.strip()),
            )
            if article:
                db.execute("INSERT INTO report_articles VALUES (?, ?, ?)",
                           (report_id, story_identity(article), str(article.get("headline", ""))))
            return report_id

    def counts_by_date(self, dates: Iterable[str]) -> Dict[str, int]:
        dates = list(dates)
        if not dates or not self._storage_exists():
            return {}
        marks = ",".join("?" for _ in dates)
        with self._connect() as db:
            rows = db.execute(f"SELECT date, COUNT(*) AS count FROM reports WHERE date IN ({marks}) GROUP BY date",
                              dates)
            return {row["date"]: row["count"] for row in rows}

    def latest(self, limit: int = 200) -> List[Dict]:
        if not self._storage_exists():
            return []
        with self._connect() as db:
            rows = db.execute(
                """SELECT r.*, COALESCE(s.status, 'open') AS status,
                          COALESCE(s.resolution, '') AS resolution, s.resolved_at,
                          a.story_identity, a.original_headline
                   FROM reports r LEFT JOIN report_resolutions s ON s.report_id = r.id
                   LEFT JOIN report_articles a ON a.report_id = r.id
                   ORDER BY r.id DESC LIMIT ?""", (limit,))
            return [self._decorate_report(dict(row)) for row in rows]

    def _decorate_report(self, report: Dict) -> Dict:
        current = self.news.get_article(report["date"], report["group_id"])
        return {**report, "article_matches": bool(current and report.get("story_identity")
                                                  and story_identity(current) == report["story_identity"])}

    def resolve(self, report_id: int, status: str, resolution: str) -> Dict:
        with self._connect() as db:
            report = db.execute("""SELECT r.*, a.story_identity, a.original_headline FROM reports r
                                  LEFT JOIN report_articles a ON a.report_id = r.id WHERE r.id = ?""",
                                (report_id,)).fetchone()
            if report is None:
                raise KeyError(report_id)
            resolved_at = None if status == "open" else datetime.now(timezone.utc).isoformat(timespec="seconds")
            db.execute(
                """INSERT INTO report_resolutions (report_id, status, resolution, resolved_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(report_id) DO UPDATE SET status = excluded.status,
                   resolution = excluded.resolution, resolved_at = excluded.resolved_at""",
                (report_id, status, resolution.strip(), resolved_at),
            )
            return self._decorate_report({**dict(report), "status": status, "resolution": resolution.strip(),
                                          "resolved_at": resolved_at})

    def publish_correction(self, report_id: int, text: str) -> Dict:
        """Publish and resolve in one transaction; a retried request reuses the original note."""
        text = text.strip()
        with self._connect() as db:
            report = db.execute("""SELECT r.*, a.story_identity, a.original_headline FROM reports r
                                  LEFT JOIN report_articles a ON a.report_id = r.id WHERE r.id = ?""",
                                (report_id,)).fetchone()
            if report is None:
                raise KeyError(report_id)
            if not self._decorate_report(dict(report))["article_matches"]:
                raise ValueError("The article was replaced or this report's original story cannot be verified")
            created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            db.execute("""INSERT INTO corrections (report_id, created_at, text) VALUES (?, ?, ?)
                       ON CONFLICT(report_id, text) DO NOTHING""",
                       (report_id, created_at, text))
            correction = db.execute(
                "SELECT id, created_at, text FROM corrections WHERE report_id = ? AND text = ?", (report_id, text)
            ).fetchone()
            db.execute(
                """INSERT INTO report_resolutions (report_id, status, resolution, resolved_at)
                   VALUES (?, 'resolved', ?, ?) ON CONFLICT(report_id) DO UPDATE SET
                   status = excluded.status, resolution = excluded.resolution, resolved_at = excluded.resolved_at""",
                (report_id, text, correction["created_at"]),
            )
            return dict(correction)

    def corrections_for_article(self, date: str, group_id: str, article: Dict = None) -> List[Dict]:
        if not self._storage_exists():
            return []
        current = article if article is not None else self.news.get_article(date, group_id)
        if not current:
            return []
        with self._connect() as db:
            rows = db.execute(
                """SELECT c.id, c.created_at, c.text FROM corrections c
                   JOIN reports r ON r.id = c.report_id WHERE r.date = ? AND r.group_id = ?
                   AND EXISTS (SELECT 1 FROM report_articles a WHERE a.report_id = r.id AND a.story_identity = ?)
                   ORDER BY c.id""", (date, group_id, story_identity(current)))
            return [dict(row) for row in rows]
