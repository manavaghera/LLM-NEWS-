"""Short-lived admin sessions signed with the configured admin secret."""
import base64
import hashlib
import hmac
import os
import time

from fastapi import Header, HTTPException, Request

COOKIE_NAME = "news_admin_session"
SESSION_SECONDS = 8 * 60 * 60


def configured_secret() -> str:
    return os.getenv("ADMIN_TOKEN", "")


def valid_password(candidate: str | None) -> bool:
    expected = configured_secret()
    return bool(expected and candidate and hmac.compare_digest(candidate.encode(), expected.encode()))


def create_session() -> str:
    secret = configured_secret()
    expires = str(int(time.time()) + SESSION_SECONDS)
    signature = hmac.new(secret.encode(), expires.encode(), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{expires}.{encoded}"


def valid_session(token: str | None) -> bool:
    if not token or "." not in token or not configured_secret():
        return False
    expires, supplied = token.split(".", 1)
    try:
        if int(expires) < int(time.time()):
            return False
    except ValueError:
        return False
    expected = base64.urlsafe_b64encode(
        hmac.new(configured_secret().encode(), expires.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    return hmac.compare_digest(supplied, expected)


def require_admin(request: Request, x_admin_token: str | None = Header(default=None)) -> None:
    """Accept an HTTP-only session for the browser and the header for maintenance clients."""
    if valid_password(x_admin_token) or valid_session(request.cookies.get(COOKIE_NAME)):
        return
    # Owner endpoints stay undiscoverable when administration is disabled or authentication fails.
    raise HTTPException(status_code=404, detail="Not found")
