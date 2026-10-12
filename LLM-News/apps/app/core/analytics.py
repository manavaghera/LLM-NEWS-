"""Small, privacy-preserving product and runtime counters.

Only allow-listed event names and normalized API route patterns are stored. The database
contains no IP addresses, cookies, user agents, search text, story ids, or account profiles.
"""
from contextlib import contextmanager
from datetime import date, timedelta

from .database import connect


PUBLIC_EVENTS = {
    "page_view", "search", "article_saved", "story_followed", "topic_followed",
    "model_compared", "category_view", "return_visit", "onboarding_completed", "alert_enabled", "digest_opened",
}
PUBLIC_CATEGORIES = {"ai_models", "social", "tech", "science", "business", "startups", "cybersecurity",
                     "health", "climate", "space", "sports", "gaming", "entertainment"}


@contextmanager
def _db():
    with connect("analytics") as db:
        yield db


def record_event(event: str, detail: str = "") -> None:
    if event not in PUBLIC_EVENTS:
        raise ValueError("Unsupported analytics event")
    with _db() as db:
        db.execute("""INSERT INTO analytics_events(day,event,count) VALUES(?,?,1)
                   ON CONFLICT(day,event) DO UPDATE SET count=analytics_events.count+1""",
                   (date.today().isoformat(), event))
        safe_detail = ""
        if event == "category_view" and detail in PUBLIC_CATEGORIES:
            safe_detail = detail
        elif event == "model_compared" and 1 <= len(detail) <= 80 and all(c.isalnum() or c in "-_" for c in detail):
            safe_detail = detail
        if safe_detail:
            db.execute("""INSERT INTO analytics_breakdowns(day,event,detail,count) VALUES(?,?,?,1)
                       ON CONFLICT(day,event,detail) DO UPDATE SET
                       count=analytics_breakdowns.count+1""",
                       (date.today().isoformat(), event, safe_detail))


def record_request(route: str, method: str, status: int, duration_ms: int) -> None:
    # route comes from Starlette's matched route template, avoiding IDs and query text.
    route = route[:160] if route.startswith("/") else "/unmatched"
    method = method[:8].upper()
    status_group = f"{max(1, min(5, status // 100))}xx"
    elapsed = max(0, min(int(duration_ms), 3_600_000))
    with _db() as db:
        db.execute("""INSERT INTO runtime_requests(day,route,method,status_group,count,total_ms,max_ms)
                   VALUES(?,?,?,?,1,?,?) ON CONFLICT(day,route,method,status_group) DO UPDATE SET
                   count=runtime_requests.count+1,
                   total_ms=runtime_requests.total_ms+excluded.total_ms,
                   max_ms=CASE WHEN runtime_requests.max_ms > excluded.max_ms
                               THEN runtime_requests.max_ms ELSE excluded.max_ms END""",
                   (date.today().isoformat(), route, method, status_group, elapsed, elapsed))


def snapshot(days: int = 30) -> dict:
    days = max(1, min(days, 90))
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with _db() as db:
        events = [dict(row) for row in db.execute(
            "SELECT event,SUM(count) AS count FROM analytics_events WHERE day>=? GROUP BY event ORDER BY count DESC,event",
            (since,))]
        requests = [dict(row) for row in db.execute("""
            SELECT route,method,status_group,SUM(count) AS count,SUM(total_ms) AS total_ms,MAX(max_ms) AS max_ms
            FROM runtime_requests WHERE day>=? GROUP BY route,method,status_group ORDER BY count DESC LIMIT 50
        """, (since,))]
        breakdown = [dict(row) for row in db.execute("""
            SELECT event,detail,SUM(count) AS count FROM analytics_breakdowns WHERE day>=?
            GROUP BY event,detail ORDER BY count DESC,event,detail LIMIT 50
        """, (since,))]
    for row in requests:
        row["average_ms"] = round(row.pop("total_ms") / row["count"]) if row["count"] else 0
    return {"days": days, "since": since, "events": events, "breakdown": breakdown, "requests": requests,
            "privacy": "Aggregate counters only; no visitor identifiers or query text are stored."}
