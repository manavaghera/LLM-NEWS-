"""Privacy-safe operational events and deduplicated failure alerts."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.request
from datetime import datetime, timedelta, timezone

from .database import connect


logger = logging.getLogger(__name__)
SEVERITIES = {"info", "warning", "error", "critical"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_event(component: str, event: str, severity: str = "error", detail: str = "") -> None:
    if severity not in SEVERITIES:
        raise ValueError("Unsupported event severity")
    safe_component = component[:40] if component.replace("_", "").isalnum() else "application"
    safe_event = event[:80] if event.replace("_", "").isalnum() else "failure"
    with connect("monitoring") as database:
        database.execute(
            "INSERT INTO operational_events(created_at,severity,component,event,detail) VALUES(?,?,?,?,?)",
            (_now().isoformat(timespec="seconds"), severity, safe_component, safe_event, detail[:240]),
        )
        # Keep bounded local telemetry. PostgreSQL and SQLite both support this form.
        database.execute(
            "DELETE FROM operational_events WHERE id NOT IN "
            "(SELECT id FROM operational_events ORDER BY id DESC LIMIT 5000)"
        )


def recent_events(limit: int = 50) -> list[dict]:
    with connect("monitoring") as database:
        return [dict(row) for row in database.execute(
            "SELECT created_at,severity,component,event,detail FROM operational_events "
            "ORDER BY id DESC LIMIT ?", (max(1, min(limit, 200)),),
        )]


def alert(component: str, event: str, message: str, *, severity: str = "error",
          dedup_seconds: int = 3600) -> bool:
    """Record an event and deliver at most one matching webhook alert per window."""
    record_event(component, event, severity)
    target = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not target:
        return False
    fingerprint = hashlib.sha256(f"{component}:{event}".encode()).hexdigest()
    now = _now()
    with connect("monitoring") as database:
        database.write_lock("operational-alert")
        row = database.execute(
            "SELECT last_sent_at,suppressed FROM alert_deliveries WHERE fingerprint=?", (fingerprint,),
        ).fetchone()
        if row:
            try:
                previous = datetime.fromisoformat(row["last_sent_at"])
            except ValueError:
                previous = now - timedelta(days=1)
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            if now - previous < timedelta(seconds=max(60, dedup_seconds)):
                database.execute(
                    "UPDATE alert_deliveries SET suppressed=suppressed+1 WHERE fingerprint=?", (fingerprint,),
                )
                return False
        database.execute(
            "INSERT INTO alert_deliveries(fingerprint,last_sent_at,suppressed,last_error) VALUES(?,?,0,'') "
            "ON CONFLICT(fingerprint) DO UPDATE SET last_sent_at=excluded.last_sent_at,last_error=''",
            (fingerprint, now.isoformat(timespec="seconds")),
        )
    field = "content" if "discord" in target.lower() else "text"
    body = json.dumps({field: message[:1000]}).encode()
    try:
        request = urllib.request.Request(
            target, data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
        return True
    except Exception as exc:
        logger.exception("Operational alert delivery failed component=%s event=%s", component, event)
        with connect("monitoring") as database:
            database.execute(
                "UPDATE alert_deliveries SET last_sent_at=?,last_error=? WHERE fingerprint=?",
                ("1970-01-01T00:00:00+00:00", type(exc).__name__, fingerprint),
            )
        return False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exception"] = record.exc_info[0].__name__
        return json.dumps(data, separators=(",", ":"), ensure_ascii=True)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if os.getenv("LOG_FORMAT", "json").lower() == "json"
                         else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
