"""Small durable background queue shared by the API, updater and worker."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .database import connect


KINDS = {"warm_digest", "warm_audio", "email_digest", "deliver_notifications"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(kind: str, payload: dict, max_attempts: int = 5) -> int:
    if kind not in KINDS or not isinstance(payload, dict):
        raise ValueError("Unsupported background job")
    if not 1 <= max_attempts <= 20:
        raise ValueError("Invalid maximum attempts")
    now = _now().isoformat(timespec="seconds")
    with connect("jobs") as database:
        return database.insert_id(
            "INSERT INTO background_jobs(kind,payload,status,max_attempts,run_after,created_at) "
            "VALUES(?,?,'queued',?,?,?)",
            (kind, json.dumps(payload, separators=(",", ":")), max_attempts, now, now),
        )


def claim() -> dict | None:
    now = _now()
    stale = (now - timedelta(minutes=15)).isoformat(timespec="seconds")
    now_text = now.isoformat(timespec="seconds")
    with connect("jobs") as database:
        database.write_lock("background-job-claim")
        database.execute(
            "UPDATE background_jobs SET status='queued',run_after=?,locked_at=NULL,last_error='Worker timed out' "
            "WHERE status='running' AND locked_at<?", (now_text, stale),
        )
        row = database.execute(
            "SELECT * FROM background_jobs WHERE status='queued' AND run_after<=? ORDER BY id LIMIT 1",
            (now_text,),
        ).fetchone()
        if not row:
            return None
        database.execute(
            "UPDATE background_jobs SET status='running',attempts=attempts+1,locked_at=? WHERE id=?",
            (now_text, row["id"]),
        )
        saved = dict(row)
        saved["attempts"] += 1
        saved["payload"] = json.loads(saved["payload"])
        return saved


def complete(job_id: int) -> None:
    with connect("jobs") as database:
        database.execute(
            "UPDATE background_jobs SET status='succeeded',finished_at=?,locked_at=NULL,last_error='' WHERE id=?",
            (_now().isoformat(timespec="seconds"), job_id),
        )


def fail(job_id: int, error: str) -> None:
    with connect("jobs") as database:
        row = database.execute("SELECT attempts,max_attempts FROM background_jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return
        terminal = int(row["attempts"]) >= int(row["max_attempts"])
        delay = min(3600, 30 * 2 ** max(0, int(row["attempts"]) - 1))
        run_after = (_now() + timedelta(seconds=delay)).isoformat(timespec="seconds")
        database.execute(
            "UPDATE background_jobs SET status=?,run_after=?,locked_at=NULL,finished_at=?,last_error=? WHERE id=?",
            ("failed" if terminal else "queued", run_after,
             _now().isoformat(timespec="seconds") if terminal else None,
             type(error).__name__ if isinstance(error, BaseException) else str(error)[:120], job_id),
        )


def summary() -> dict:
    with connect("jobs") as database:
        rows = [dict(row) for row in database.execute(
            "SELECT status,COUNT(*) AS count FROM background_jobs GROUP BY status ORDER BY status"
        )]
        failed = [dict(row) for row in database.execute(
            "SELECT id,kind,attempts,finished_at,last_error FROM background_jobs "
            "WHERE status='failed' ORDER BY id DESC LIMIT 20"
        )]
    return {"counts": {row["status"]: row["count"] for row in rows}, "failed": failed}
