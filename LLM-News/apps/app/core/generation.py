"""Persistent generation usage and feed/run health, shared by the updater and admin API.

Only operational metadata is recorded: no API keys, prompts, article text or visitor identity.
The daily limit counts attempted pipeline calls, including failed calls, across processes/restarts.
"""
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

from .database import connect


class PipelineBudgetExceeded(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _db():
    with connect("generation") as db:
        yield db


def _setting_limit(db, key, env_name, fallback):
    saved = db.execute("SELECT value FROM generation_settings WHERE key=?", (key,)).fetchone()
    if saved:
        return int(saved["value"])
    try:
        return max(0, int(os.getenv(env_name, str(fallback))))
    except ValueError:
        return fallback


def _limit(db):
    return _setting_limit(db, "pipeline_limit", "PIPELINE_DAILY_CALL_LIMIT", 200)


def _monthly_limit(db):
    return _setting_limit(db, "pipeline_monthly_limit", "PIPELINE_MONTHLY_CALL_LIMIT", 4000)


def start_call(provider, model, scope="pipeline"):
    """Reserve a call atomically before contacting the provider; failures still consume allowance."""
    today = date.today().isoformat()
    month = today[:7]
    with _db() as db:
        db.write_lock("generation-budget")
        if scope == "pipeline":
            limit = _limit(db)
            used = db.execute("SELECT COUNT(*) AS count FROM generation_calls WHERE day=? AND scope='pipeline'",
                              (today,)).fetchone()["count"]
            if limit and used >= limit:
                raise PipelineBudgetExceeded(f"The daily news-generation limit ({limit} AI calls) has been reached.")
            monthly_limit = _monthly_limit(db)
            monthly_used = db.execute("""SELECT COUNT(*) AS count FROM generation_calls
                                       WHERE day LIKE ? AND scope='pipeline'""",
                                      (month + "-%",)).fetchone()["count"]
            if monthly_limit and monthly_used >= monthly_limit:
                raise PipelineBudgetExceeded(
                    f"The monthly news-generation limit ({monthly_limit} AI calls) has been reached."
                )
        return db.insert_id(
            "INSERT INTO generation_calls(day,started_at,scope,provider,model,status) VALUES(?,?,?,?,?,'running')",
            (today, _now(), scope, str(provider), str(model)))


def finish_call(call_id, response=None, failed=False):
    usage = getattr(response, "usage", None)
    def tokens(name):
        value = usage.get(name, 0) if isinstance(usage, dict) else getattr(usage, name, 0)
        return max(0, value) if type(value) is int else 0
    with _db() as db:
        db.execute("UPDATE generation_calls SET status=?,prompt_tokens=?,completion_tokens=? WHERE id=?",
                   ("failed" if failed else "success", tokens("prompt_tokens"), tokens("completion_tokens"), call_id))


def usage_summary():
    today = date.today().isoformat()
    month = today[:7]
    with _db() as db:
        used = db.execute("SELECT COUNT(*) AS count FROM generation_calls WHERE day=? AND scope='pipeline'",
                          (today,)).fetchone()["count"]
        limit = _limit(db)
        monthly_used = db.execute("""SELECT COUNT(*) AS count FROM generation_calls
                                   WHERE day LIKE ? AND scope='pipeline'""",
                                  (month + "-%",)).fetchone()["count"]
        monthly_limit = _monthly_limit(db)
        models = db.execute("""SELECT provider,model,COUNT(*) AS calls,
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(prompt_tokens) AS prompt_tokens,SUM(completion_tokens) AS completion_tokens
                    FROM generation_calls WHERE day=? GROUP BY provider,model ORDER BY calls DESC,model""", (today,))
        return {"date": today, "month": month, "pipeline_calls": used, "pipeline_limit": limit,
                "remaining": max(0, limit - used) if limit else None,
                "monthly_calls": monthly_used, "monthly_limit": monthly_limit,
                "monthly_remaining": max(0, monthly_limit - monthly_used) if monthly_limit else None,
                "models": [dict(row) for row in models]}



def set_pipeline_limit(limit):
    if type(limit) is not int or not 0 <= limit <= 100000:
        raise ValueError("Daily call limit must be between 0 and 100000")
    with _db() as db:
        db.execute("INSERT INTO generation_settings(key,value) VALUES('pipeline_limit',?) "
                   "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (limit,))
    return usage_summary()


def set_pipeline_limits(daily_limit, monthly_limit):
    if type(daily_limit) is not int or not 0 <= daily_limit <= 100000:
        raise ValueError("Daily call limit must be between 0 and 100000")
    if type(monthly_limit) is not int or not 0 <= monthly_limit <= 2_000_000:
        raise ValueError("Monthly call limit must be between 0 and 2000000")
    with _db() as db:
        db.executemany(
            "INSERT INTO generation_settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (("pipeline_limit", daily_limit), ("pipeline_monthly_limit", monthly_limit)),
        )
    return usage_summary()


def record_feed(publisher, url, category, ok, items=0, full_text_items=0):
    with _db() as db:
        db.execute("""INSERT INTO generation_feeds VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(url,category) DO UPDATE SET publisher=excluded.publisher,ok=excluded.ok,
                   items=excluded.items,full_text_items=excluded.full_text_items,
                   error=excluded.error,last_checked=excluded.last_checked""",
                   (url, category, publisher, int(ok), items, full_text_items,
                    "" if ok else "Feed could not be fetched", _now()))


def feed_statuses():
    with _db() as db:
        rows = db.execute("SELECT * FROM generation_feeds ORDER BY category,publisher")
        return [{**dict(row), "ok": bool(row["ok"])} for row in rows]


def start_run(edition_date):
    with _db() as db:
        return db.insert_id("INSERT INTO generation_runs(started_at,date,status) VALUES(?,?,'running')",
                            (_now(), edition_date))


def finish_run(run_id, ok, added=0, held_back=0):
    with _db() as db:
        db.execute("UPDATE generation_runs SET finished_at=?,status=?,added=?,held_back=?,error=? WHERE id=?",
                   (_now(), "success" if ok else "failed", added, held_back,
                    "" if ok else "News generation did not complete; the published edition was preserved", run_id))


def recent_runs():
    with _db() as db:
        return [dict(row) for row in db.execute("SELECT * FROM generation_runs ORDER BY id DESC LIMIT 30")]


def record_hold(edition_date, category, headline, reason):
    """Keep the editor's title and local rejection label, without provider errors or source text."""
    with _db() as db:
        db.execute("INSERT INTO generation_holds(created_at,date,category,headline,reason) VALUES(?,?,?,?,?)",
                   (_now(), edition_date, category, str(headline)[:500], str(reason)[:300]))
        db.execute("DELETE FROM generation_holds WHERE id NOT IN (SELECT id FROM generation_holds ORDER BY id DESC LIMIT 200)")


def held_stories():
    with _db() as db:
        return [dict(row) for row in db.execute(
            "SELECT created_at,date,category,headline,reason FROM generation_holds ORDER BY id DESC LIMIT 50")]


def acquire_update_lease(owner: str, ttl_seconds: int = 7200) -> bool:
    """Atomically acquire the updater lease shared through the operations database."""
    if not owner or not 60 <= ttl_seconds <= 86_400:
        raise ValueError("Invalid updater lease")
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")
    with _db() as db:
        db.write_lock("news-updater")
        saved = db.execute("SELECT owner,expires_at FROM generation_leases WHERE name='news-updater'").fetchone()
        if saved:
            try:
                active = datetime.fromisoformat(saved["expires_at"]) > now
            except (TypeError, ValueError):
                active = False
            if active and saved["owner"] != owner:
                return False
        db.execute("""INSERT INTO generation_leases(name,owner,expires_at)
                   VALUES('news-updater',?,?) ON CONFLICT(name) DO UPDATE SET
                   owner=excluded.owner,expires_at=excluded.expires_at""", (owner, expires))
        return True


def release_update_lease(owner: str) -> None:
    with _db() as db:
        db.execute("DELETE FROM generation_leases WHERE name='news-updater' AND owner=?", (owner,))
