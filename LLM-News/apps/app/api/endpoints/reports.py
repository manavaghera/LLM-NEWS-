import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field, field_validator
from ...core.limits import RateLimiter, client_ip
from ...core.admin_auth import require_admin, require_editor
from ...core.admin_accounts import audit
from ...services.news_service import NewsService
from ...services.report_service import KINDS, ReportService

router = APIRouter()
logger = logging.getLogger(__name__)
news_service = NewsService()
report_service = ReportService()
report_limiter = RateLimiter(limit=5, window_seconds=60)  # per visitor; reports are free but shouldn't be spammed


class ReportRequest(BaseModel):
    date: str = Field(max_length=20)
    group_id: str = Field(max_length=50)
    kind: Literal["wrong_fact", "missing_context", "bad_source", "other"]
    message: str = Field(min_length=5, max_length=1000)


class ResolutionRequest(BaseModel):
    status: Literal["open", "resolved", "dismissed"]
    resolution: str = Field(default="", max_length=2000)


class CorrectionRequest(BaseModel):
    text: str = Field(min_length=5, max_length=3000)

    @field_validator("text", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value


def limit_reports(request: Request) -> None:
    report_limiter.check(client_ip(request))


@router.get("/kinds")
async def report_kinds():
    return {"kinds": KINDS}


@router.post("", status_code=201, dependencies=[Depends(limit_reports)])
def create_report(report: ReportRequest):
    """A reader flags a problem with an article"""
    article = news_service.get_article(report.date, report.group_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    report_service.add(report.date, report.group_id, report.kind, report.message, article=article)
    return {"status": "received"}


@router.get("", dependencies=[Depends(require_admin)])
def list_reports():
    """Latest reports and their review status, for the site owner only."""
    try:
        return {"reports": report_service.latest()}
    except Exception:
        logger.exception("Failed to fetch reports")
        raise HTTPException(status_code=500, detail="Failed to fetch reports")


@router.patch("/{report_id}")
def resolve_report(request: ResolutionRequest, report_id: int = Path(ge=1), identity=Depends(require_editor)):
    try:
        result = report_service.resolve(report_id, request.status, request.resolution)
        audit(identity, "report_updated", f"report={report_id} status={request.status}")
        return {"report": result}
    except KeyError:
        raise HTTPException(status_code=404, detail="Report not found")
    except Exception:
        logger.exception("Failed to update report")
        raise HTTPException(status_code=500, detail="Failed to update report")


@router.post("/{report_id}/correction", status_code=201)
def publish_correction(request: CorrectionRequest, report_id: int = Path(ge=1),
                       identity=Depends(require_editor)):
    try:
        correction = report_service.publish_correction(report_id, request.text)
        audit(identity, "correction_published", f"report={report_id}")
        return {"status": "resolved", "correction": correction}
    except KeyError:
        raise HTTPException(status_code=404, detail="Report not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception:
        logger.exception("Failed to publish correction")
        raise HTTPException(status_code=500, detail="Failed to publish correction")


@router.get("/corrections/{date}/{group_id}")
def article_corrections(
    date: str = Path(pattern=r"^\d{4}-\d{2}-\d{2}$", max_length=10),
    group_id: str = Path(pattern=r"^group_\d+$", max_length=50),
):
    try:
        return {"corrections": report_service.corrections_for_article(date, group_id)}
    except Exception:
        logger.exception("Failed to fetch corrections")
        raise HTTPException(status_code=500, detail="Failed to fetch corrections")
