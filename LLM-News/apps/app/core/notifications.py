"""Anonymous Web Push subscriptions and delivery for followed topics."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone

from .database import connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def subscribe(endpoint: str, p256dh: str, auth: str, categories: list[str], keywords: list[str],
              management_token: str = "") -> str:
    filters = json.dumps({"categories": categories[:20], "keywords": keywords[:20]}, separators=(",", ":"))
    now = _now()
    with connect("notifications") as database:
        database.write_lock("push-subscription")
        existing = database.execute(
            "SELECT management_hash,p256dh,auth FROM push_subscriptions WHERE endpoint=?", (endpoint,),
        ).fetchone()
        if existing:
            valid_token = bool(management_token) and secrets.compare_digest(
                existing["management_hash"], _hash(management_token))
            same_browser_keys = secrets.compare_digest(existing["p256dh"], p256dh) and secrets.compare_digest(
                existing["auth"], auth)
            if not valid_token and not same_browser_keys:
                raise PermissionError("Subscription management token is invalid")
            token = management_token if valid_token else secrets.token_urlsafe(32)
        else:
            token = secrets.token_urlsafe(32)
        database.execute(
            "INSERT INTO push_subscriptions(endpoint,p256dh,auth,filters,management_hash,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET "
            "p256dh=excluded.p256dh,auth=excluded.auth,filters=excluded.filters,"
            "management_hash=excluded.management_hash,active=1,failures=0,updated_at=excluded.updated_at,last_error=''",
            (endpoint, p256dh, auth, filters, _hash(token), now, now),
        )
    return token


def unsubscribe(endpoint: str, management_token: str) -> bool:
    with connect("notifications") as database:
        row = database.execute(
            "SELECT management_hash FROM push_subscriptions WHERE endpoint=?", (endpoint,),
        ).fetchone()
        if not row or not secrets.compare_digest(row["management_hash"], _hash(management_token)):
            return False
        database.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))
        return True


def _matches(article: dict, filters: dict) -> bool:
    category = str(article.get("category", "")).lower()
    if category in filters.get("categories", []):
        return True
    text = " ".join(str(article.get(key, "")) for key in ("headline", "subheadline", "summary", "lead")).lower()
    return any(keyword in text for keyword in filters.get("keywords", []))


def _delivery_key(article: dict) -> str:
    """A material article version; verified upgrades may notify again, identical jobs may not."""
    identity = {
        key: article.get(key) for key in
        ("date", "group_id", "story_identity", "content_version", "headline", "summary", "verification_status")
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _reserve_delivery(subscription_id: int, story_key: str) -> bool:
    with connect("notifications") as database:
        database.write_lock(f"push-delivery-{subscription_id}")
        existing = database.execute(
            "SELECT 1 AS found FROM push_deliveries WHERE subscription_id=? AND story_key=?",
            (subscription_id, story_key),
        ).fetchone()
        if existing:
            return False
        database.execute("INSERT INTO push_deliveries VALUES(?,?,?)", (subscription_id, story_key, _now()))
        return True


def deliver(articles: list[dict]) -> dict:
    """Send one matching story to each active browser subscription."""
    private_key = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    subject = os.getenv("VAPID_SUBJECT", "").strip()
    if not private_key or not subject:
        return {"sent": 0, "skipped": True}
    from pywebpush import WebPushException, webpush
    with connect("notifications") as database:
        subscriptions = [dict(row) for row in database.execute(
            "SELECT id,endpoint,p256dh,auth,filters,failures FROM push_subscriptions WHERE active=1 ORDER BY id"
        )]
    sent = 0
    for subscription in subscriptions:
        filters = json.loads(subscription["filters"])
        article = next((item for item in articles if _matches(item, filters)
                        and _reserve_delivery(subscription["id"], _delivery_key(item))), None)
        if not article:
            continue
        story_key = _delivery_key(article)
        date, group_id = str(article.get("date", "")), str(article.get("group_id", ""))
        data = json.dumps({
            "title": "NewsSense update",
            "body": str(article.get("headline", "New coverage is available"))[:180],
            "url": f"/article/{date}/{group_id}" if date and group_id else "/",
            "tag": f"{date}/{group_id}" if date and group_id else "newssense-update",
        })
        try:
            webpush(
                subscription_info={"endpoint": subscription["endpoint"],
                                   "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]}},
                data=data, vapid_private_key=private_key, vapid_claims={"sub": subject}, ttl=3600,
            )
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            failures = int(subscription["failures"]) + 1
            with connect("notifications") as database:
                database.execute("DELETE FROM push_deliveries WHERE subscription_id=? AND story_key=?",
                                 (subscription["id"], story_key))
                database.execute(
                    "UPDATE push_subscriptions SET failures=?,active=?,last_error=?,updated_at=? WHERE id=?",
                    (failures, 0 if status in {404, 410} or failures >= 5 else 1,
                     f"HTTP {status}" if status else type(exc).__name__, _now(), subscription["id"]),
                )
        else:
            sent += 1
            with connect("notifications") as database:
                database.execute(
                    "UPDATE push_subscriptions SET failures=0,last_success_at=?,last_error='',updated_at=? WHERE id=?",
                    (_now(), _now(), subscription["id"]),
                )
                database.execute(
                    "DELETE FROM push_deliveries WHERE subscription_id=? AND story_key NOT IN "
                    "(SELECT story_key FROM push_deliveries WHERE subscription_id=? ORDER BY delivered_at DESC LIMIT 500)",
                    (subscription["id"], subscription["id"]),
                )
    return {"sent": sent, "skipped": False}


def summary() -> dict:
    with connect("notifications") as database:
        row = database.execute(
            "SELECT COUNT(*) AS total,SUM(CASE WHEN active=1 THEN 1 ELSE 0 END) AS active,"
            "SUM(CASE WHEN last_error<>'' THEN 1 ELSE 0 END) AS errors FROM push_subscriptions"
        ).fetchone()
    return {"total": int(row["total"] or 0), "active": int(row["active"] or 0),
            "errors": int(row["errors"] or 0)}
