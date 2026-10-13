import re
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core import notifications
from ...core.limits import RateLimiter, client_ip


router = APIRouter()
subscription_limiter = RateLimiter(
    10, 60, "Too many notification changes.", scope="notification-change", persistent=True)


def limit_changes(request: Request) -> None:
    subscription_limiter.check(client_ip(request))


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(min_length=20, max_length=300)
    auth: str = Field(min_length=8, max_length=100)


class PushSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=20, max_length=2000)
    keys: PushKeys
    categories: list[str] = Field(default_factory=list, max_length=20)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    management_token: str | None = Field(default=None, min_length=32, max_length=100)

    @field_validator("endpoint")
    @classmethod
    def secure_endpoint(cls, value: str) -> str:
        host = (urlsplit(value).hostname or "").lower()
        allowed = [item.strip().lower() for item in os.getenv(
            "PUSH_ENDPOINT_HOSTS",
            "fcm.googleapis.com,push.services.mozilla.com,web.push.apple.com,notify.windows.com",
        ).split(",") if item.strip()]
        if not value.startswith("https://") or not any(host == item or host.endswith("." + item) for item in allowed):
            raise ValueError("Push endpoint must use HTTPS")
        return value

    @field_validator("categories")
    @classmethod
    def valid_categories(cls, values: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[a-z0-9_-]{1,40}", value) for value in values):
            raise ValueError("Invalid category")
        return list(dict.fromkeys(values))

    @field_validator("keywords")
    @classmethod
    def valid_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip().lower() for value in values]
        if any(not 2 <= len(value) <= 40 or any(ord(char) < 32 for char in value) for value in cleaned):
            raise ValueError("Invalid keyword")
        return list(dict.fromkeys(cleaned))


class PushRemoval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=20, max_length=2000)
    management_token: str = Field(min_length=32, max_length=100)


@router.post("/push", status_code=status.HTTP_201_CREATED, dependencies=[Depends(limit_changes)])
def save_push(body: PushSubscription):
    if not body.categories and not body.keywords:
        raise HTTPException(status_code=422, detail="Follow at least one category or keyword")
    try:
        token = notifications.subscribe(body.endpoint, body.keys.p256dh, body.keys.auth,
                                        body.categories, body.keywords, body.management_token or "")
    except PermissionError:
        raise HTTPException(status_code=409, detail="Push subscription must be recreated")
    return {"status": "subscribed", "management_token": token}


@router.delete("/push", dependencies=[Depends(limit_changes)])
def delete_push(body: PushRemoval):
    if not notifications.unsubscribe(body.endpoint, body.management_token):
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"status": "unsubscribed"}
