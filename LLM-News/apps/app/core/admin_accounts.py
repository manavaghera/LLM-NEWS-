"""Named administrator accounts with scrypt passwords, TOTP MFA, roles and audit records."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone

from .database import connect


ROLES = {"owner", "editor", "viewer"}
SESSION_HOURS = 8


def _now() -> datetime:
    return datetime.now(timezone.utc)


def has_users() -> bool:
    try:
        with connect("admin") as database:
            return database.execute("SELECT 1 AS found FROM admin_users WHERE active=1 LIMIT 1").fetchone() is not None
    except Exception:
        return False


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, work, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "scrypt" or int(work) != 16384:
            return False
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(digest_text)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _totp(secret: str, counter: int) -> str:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    number = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{number:06d}"


def verify_totp(secret: str, code: str, now: int | None = None) -> bool:
    if not secret:
        return True
    if not code or len(code) != 6 or not code.isdigit():
        return False
    counter = (int(time.time()) if now is None else now) // 30
    return any(hmac.compare_digest(code, _totp(secret, counter + offset)) for offset in (-1, 0, 1))


def create_user(username: str, password: str, role: str = "owner", totp_secret: str = "") -> int:
    username = username.strip().lower()
    if not username or len(username) > 80 or not all(c.isalnum() or c in "._-" for c in username):
        raise ValueError("Username may contain letters, numbers, dot, underscore and hyphen")
    if role not in ROLES:
        raise ValueError("Invalid administrator role")
    with connect("admin") as database:
        user_id = database.insert_id(
            "INSERT INTO admin_users(username,password_hash,role,totp_secret,created_at) VALUES(?,?,?,?,?)",
            (username, hash_password(password), role, totp_secret.strip().upper(), _now().isoformat(timespec="seconds")),
        )
        database.execute("INSERT INTO admin_audit(created_at,user_id,action,detail) VALUES(?,?,?,?)",
                         (_now().isoformat(timespec="seconds"), user_id, "account_created", role))
        return user_id


def reset_password(username: str, password: str) -> None:
    with connect("admin") as database:
        row = database.execute("SELECT id FROM admin_users WHERE username=?", (username.strip().lower(),)).fetchone()
        if not row:
            raise KeyError(username)
        database.execute("UPDATE admin_users SET password_hash=? WHERE id=?", (hash_password(password), row["id"]))
        database.execute("DELETE FROM admin_sessions WHERE user_id=?", (row["id"],))
        database.execute("INSERT INTO admin_audit(created_at,user_id,action) VALUES(?,?,?)",
                         (_now().isoformat(timespec="seconds"), row["id"], "password_reset"))


def login(username: str, password: str, otp: str = "") -> tuple[str, dict] | None:
    now = _now()
    with connect("admin") as database:
        row = database.execute("SELECT * FROM admin_users WHERE username=? AND active=1",
                               (username.strip().lower(),)).fetchone()
        if not row or not verify_password(password, row["password_hash"]) or not verify_totp(row["totp_secret"], otp):
            return None
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires = now + timedelta(hours=SESSION_HOURS)
        database.execute("DELETE FROM admin_sessions WHERE expires_at<?", (now.isoformat(timespec="seconds"),))
        database.execute("INSERT INTO admin_sessions VALUES(?,?,?,?)",
                         (token_hash, row["id"], now.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds")))
        database.execute("UPDATE admin_users SET last_login_at=? WHERE id=?",
                         (now.isoformat(timespec="seconds"), row["id"]))
        database.execute("INSERT INTO admin_audit(created_at,user_id,action) VALUES(?,?,?)",
                         (now.isoformat(timespec="seconds"), row["id"], "login"))
        return token, {"id": row["id"], "username": row["username"], "role": row["role"],
                       "mfa_enabled": bool(row["totp_secret"])}


def session_user(token: str | None) -> dict | None:
    if not token or "." in token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with connect("admin") as database:
        row = database.execute(
            "SELECT u.id,u.username,u.role,u.totp_secret FROM admin_sessions s "
            "JOIN admin_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>=? AND u.active=1",
            (token_hash, _now().isoformat(timespec="seconds")),
        ).fetchone()
        return ({"id": row["id"], "username": row["username"], "role": row["role"],
                 "mfa_enabled": bool(row["totp_secret"])} if row else None)


def logout(token: str | None) -> None:
    if not token or "." in token:
        return
    with connect("admin") as database:
        database.execute("DELETE FROM admin_sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


def audit(identity: dict, action: str, detail: str = "") -> None:
    if identity.get("id") is None:
        return
    with connect("admin") as database:
        database.execute("INSERT INTO admin_audit(created_at,user_id,action,detail) VALUES(?,?,?,?)",
                         (_now().isoformat(timespec="seconds"), identity["id"], action[:100], detail[:500]))
