import hmac
import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from ...core.limits import RateLimiter, client_ip
from ...services.news_service import NewsService
from ...services.report_service import KINDS, ReportService

router = APIRouter()
news_service = NewsService()
report_service = ReportService()
report_limiter = RateLimiter(limit=5, window_seconds=60)  # per visitor; reports are free but shouldn't be spammed


class ReportRequest(BaseModel):
    date: str = Field(max_length=20)
    group_id: str = Field(max_length=50)
    kind: Literal["wrong_fact", "missing_context", "bad_source", "other"]
    message: str = Field(min_length=5, max_length=1000)


def limit_reports(request: Request) -> None:
    report_limiter.check(client_ip(request))


@router.get("/kinds")
async def report_kinds():
    return {"kinds": KINDS}


@router.post("", status_code=201, dependencies=[Depends(limit_reports)])
def create_report(report: ReportRequest):
    """A reader flags a problem with an article"""
    if not news_service.get_article(report.date, report.group_id):
        raise HTTPException(status_code=404, detail="Article not found")
    report_service.add(report.date, report.group_id, report.kind, report.message)
    return {"status": "received"}


@router.get("")
def list_reports(x_admin_token: Optional[str] = Header(default=None)):
    """Latest reports with their text, for the site owner only (ADMIN_TOKEN in .env, sent as X-Admin-Token)"""
    expected = os.getenv("ADMIN_TOKEN", "")
    if not expected or not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=404, detail="Not found")
    return {"reports": report_service.latest()}
