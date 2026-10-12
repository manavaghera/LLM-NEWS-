"""Persistent generation usage and feed/run health, shared by the updater and admin API.

Only operational metadata is recorded: no API keys, prompts, article text or visitor identity.
The daily limit counts attempted pipeline calls, including failed calls, across processes/restarts.
"""
import os
import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .database import connect


class PipelineBudgetExceeded(RuntimeError):
    pass


class PipelineSpendExceeded(RuntimeError):
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


def _usd_to_microusd(value) -> int:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Spending limits and prices must be valid currency amounts")
    if amount < 0 or amount > Decimal("1000000"):
        raise ValueError("Currency amount must be between 0 and 1000000 USD")
    return int((amount * 1_000_000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _microusd_to_usd(value: int | None) -> float:
    return round(int(value or 0) / 1_000_000, 6)


def _currency_limit(db, key: str, env_name: str, fallback: str) -> int:
    saved = db.execute("SELECT value FROM generation_settings WHERE key=?", (key,)).fetchone()
    if saved:
        return max(0, int(saved["value"]))
    try:
        return _usd_to_microusd(os.getenv(env_name, fallback))
    except ValueError:
        return _usd_to_microusd(fallback)


def _provider_key(provider: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", provider.upper()).strip("_")


def _model_price(db, provider: str, model: str):
    saved = db.execute(
        "SELECT input_microusd_per_million,output_microusd_per_million FROM generation_model_prices "
        "WHERE provider=? AND model=?", (provider, model),
    ).fetchone()
    if saved:
        return int(saved["input_microusd_per_million"]), int(saved["output_microusd_per_million"]), True
    prefix = _provider_key(provider)
    input_value = os.getenv(f"{prefix}_INPUT_USD_PER_MTOK", "").strip()
    output_value = os.getenv(f"{prefix}_OUTPUT_USD_PER_MTOK", "").strip()
    if not input_value or not output_value:
        return 0, 0, False
    input_price, output_price = _usd_to_microusd(input_value), _usd_to_microusd(output_value)
    db.execute(
        "INSERT INTO generation_model_prices(provider,model,input_microusd_per_million,"
        "output_microusd_per_million,source,updated_at) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(provider,model) DO UPDATE SET input_microusd_per_million=excluded.input_microusd_per_million,"
        "output_microusd_per_million=excluded.output_microusd_per_million,source=excluded.source,"
        "updated_at=excluded.updated_at",
        (provider, model, input_price, output_price, "environment", _now()),
    )
    return input_price, output_price, True


def _reserved_cost(input_price: int, output_price: int) -> int:
    try:
        input_tokens = max(0, int(os.getenv("AI_RESERVE_INPUT_TOKENS", "10000")))
        output_tokens = max(0, int(os.getenv("AI_RESERVE_OUTPUT_TOKENS", "3000")))
    except ValueError:
        input_tokens, output_tokens = 10_000, 3_000
    # Prices are micro-USD per million tokens.
    return (input_price * input_tokens + output_price * output_tokens + 999_999) // 1_000_000


def _spent(db, pattern: str) -> int:
    row = db.execute(
        "SELECT COALESCE(SUM(CASE WHEN c.actual_microusd IS NULL THEN c.reserved_microusd "
        "ELSE c.actual_microusd END),0) AS spent FROM generation_calls g "
        "JOIN generation_costs c ON c.call_id=g.id WHERE g.day LIKE ?", (pattern,),
    ).fetchone()
    return int(row["spent"])


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
        input_price, output_price, priced = _model_price(db, str(provider), str(model))
        reserved = _reserved_cost(input_price, output_price) if priced else 0
        daily_spend_limit = _currency_limit(db, "daily_spend_microusd", "AI_DAILY_SPEND_LIMIT_USD", "10")
        monthly_spend_limit = _currency_limit(db, "monthly_spend_microusd", "AI_MONTHLY_SPEND_LIMIT_USD", "100")
        if daily_spend_limit and _spent(db, today) + reserved > daily_spend_limit:
            raise PipelineSpendExceeded("The daily AI spending limit would be exceeded by this request.")
        if monthly_spend_limit and _spent(db, month + "-%") + reserved > monthly_spend_limit:
            raise PipelineSpendExceeded("The monthly AI spending limit would be exceeded by this request.")
        call_id = db.insert_id(
            "INSERT INTO generation_calls(day,started_at,scope,provider,model,status) VALUES(?,?,?,?,?,'running')",
            (today, _now(), scope, str(provider), str(model)))
        db.execute("INSERT INTO generation_costs(call_id,reserved_microusd,priced) VALUES(?,?,?)",
                   (call_id, reserved, int(priced)))
        return call_id


def finish_call(call_id, response=None, failed=False):
    usage = getattr(response, "usage", None)
    def tokens(name):
        value = usage.get(name, 0) if isinstance(usage, dict) else getattr(usage, name, 0)
        return max(0, value) if type(value) is int else 0
    with _db() as db:
        db.execute("UPDATE generation_calls SET status=?,prompt_tokens=?,completion_tokens=? WHERE id=?",
                   ("failed" if failed else "success", tokens("prompt_tokens"), tokens("completion_tokens"), call_id))
        price = db.execute(
            "SELECT p.input_microusd_per_million,p.output_microusd_per_million FROM generation_calls g "
            "JOIN generation_model_prices p ON p.provider=g.provider AND p.model=g.model WHERE g.id=?", (call_id,)
        ).fetchone()
        if price and (tokens("prompt_tokens") or tokens("completion_tokens")):
            actual = (int(price["input_microusd_per_million"]) * tokens("prompt_tokens")
                      + int(price["output_microusd_per_million"]) * tokens("completion_tokens") + 999_999) // 1_000_000
            db.execute("UPDATE generation_costs SET actual_microusd=?,priced=1 WHERE call_id=?", (actual, call_id))


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
        daily_spent = _spent(db, today)
        monthly_spent = _spent(db, month + "-%")
        daily_spend_limit = _currency_limit(db, "daily_spend_microusd", "AI_DAILY_SPEND_LIMIT_USD", "10")
        monthly_spend_limit = _currency_limit(db, "monthly_spend_microusd", "AI_MONTHLY_SPEND_LIMIT_USD", "100")
        models = db.execute("""SELECT provider,model,COUNT(*) AS calls,
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(prompt_tokens) AS prompt_tokens,SUM(completion_tokens) AS completion_tokens,
                    COALESCE(SUM(CASE WHEN c.actual_microusd IS NULL THEN c.reserved_microusd
                    ELSE c.actual_microusd END),0) AS spent_microusd,
                    SUM(CASE WHEN c.call_id IS NULL OR c.priced=0 THEN 1 ELSE 0 END) AS unpriced_calls
                    FROM generation_calls g LEFT JOIN generation_costs c ON c.call_id=g.id
                    WHERE day=? GROUP BY provider,model ORDER BY calls DESC,model""", (today,))
        model_rows = []
        for row in models:
            saved = dict(row)
            saved["spent_usd"] = _microusd_to_usd(saved.pop("spent_microusd"))
            model_rows.append(saved)
        return {"date": today, "month": month, "pipeline_calls": used, "pipeline_limit": limit,
                "remaining": max(0, limit - used) if limit else None,
                "monthly_calls": monthly_used, "monthly_limit": monthly_limit,
                "monthly_remaining": max(0, monthly_limit - monthly_used) if monthly_limit else None,
                "daily_spent_usd": _microusd_to_usd(daily_spent),
                "daily_spend_limit_usd": _microusd_to_usd(daily_spend_limit),
                "daily_spend_remaining_usd": _microusd_to_usd(max(0, daily_spend_limit - daily_spent))
                if daily_spend_limit else None,
                "monthly_spent_usd": _microusd_to_usd(monthly_spent),
                "monthly_spend_limit_usd": _microusd_to_usd(monthly_spend_limit),
                "monthly_spend_remaining_usd": _microusd_to_usd(max(0, monthly_spend_limit - monthly_spent))
                if monthly_spend_limit else None,
                "models": model_rows}



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


def set_spending_limits(daily_usd, monthly_usd):
    daily, monthly = _usd_to_microusd(daily_usd), _usd_to_microusd(monthly_usd)
    with _db() as db:
        db.executemany(
            "INSERT INTO generation_settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (("daily_spend_microusd", daily), ("monthly_spend_microusd", monthly)),
        )
    return usage_summary()


def set_model_price(provider: str, model: str, input_usd_per_mtok, output_usd_per_mtok):
    if not provider.strip() or not model.strip():
        raise ValueError("Provider and model are required")
    with _db() as db:
        db.execute(
            "INSERT INTO generation_model_prices(provider,model,input_microusd_per_million,"
            "output_microusd_per_million,source,updated_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(provider,model) DO UPDATE SET input_microusd_per_million=excluded.input_microusd_per_million,"
            "output_microusd_per_million=excluded.output_microusd_per_million,source=excluded.source,"
            "updated_at=excluded.updated_at",
            (provider.strip(), model.strip(), _usd_to_microusd(input_usd_per_mtok),
             _usd_to_microusd(output_usd_per_mtok), "admin", _now()),
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
