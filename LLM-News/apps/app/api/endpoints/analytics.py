from fastapi import APIRouter, Depends, Request
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...core import analytics
from ...core.limits import RateLimiter, client_ip
from .reports import require_admin

router = APIRouter()
event_limiter = RateLimiter(
    limit=60, window_seconds=60, scope="analytics-event", persistent=True)


class AnalyticsEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal[
        "page_view", "search", "article_saved", "story_followed", "topic_followed",
        "model_compared", "category_view", "return_visit", "onboarding_completed", "alert_enabled", "digest_opened",
    ]
    detail: str = Field(default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")


def limit_events(request: Request) -> None:
    event_limiter.check(client_ip(request))


@router.post("/event", status_code=202, dependencies=[Depends(limit_events)])
def count_event(body: AnalyticsEvent):
    analytics.record_event(body.event, body.detail)
    return {"status": "counted"}


@router.get("", dependencies=[Depends(require_admin)])
def analytics_summary(days: int = 30):
    return analytics.snapshot(days)
