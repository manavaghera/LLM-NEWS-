import os
import secrets
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import PlainTextResponse
from ...services.llm_service import LLMService
from ...services.update_status import read_update_status
from ...core.config import settings
from ...core.database import database_ready
from ...core import analytics, jobs

router = APIRouter()

# Initialize LLM service for health checks
llm_service = LLMService()

@router.get("")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "api_configured": True,
        "llm_services": llm_service.get_health_status(),
        "message": "API is running successfully",
        "update": read_update_status(),
    }


@router.get("/live")
async def liveness():
    return {"status": "alive"}


@router.get("/ready")
async def readiness(response: Response):
    update = read_update_status()
    articles = Path("static/articles")
    cache_target = settings.CACHE_DIR if settings.CACHE_DIR.exists() else settings.CACHE_DIR.parent
    published_news = articles.is_dir() and any(
        path.stem.removeprefix("group_").isdigit() for path in articles.glob("*/group_*.json")
    )
    checks = {
        "database": database_ready(),
        "static_directory": Path("static").is_dir(),
        "cache_writable": cache_target.is_dir() and os.access(cache_target, os.W_OK),
        "published_news": published_news,
        "news_fresh": not update["stale"],
    }
    production_issues = settings.production_issues() if not settings.DEBUG else []
    ready = all(checks.values()) and not production_issues
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "checks": checks,
            "configuration_issues": production_issues, "update": update}


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(authorization: str | None = Header(default=None)):
    """Prometheus text metrics protected by a dedicated bearer token."""
    token = os.getenv("METRICS_TOKEN", "")
    supplied = authorization or ""
    if len(token) < 24 or not secrets.compare_digest(supplied, f"Bearer {token}"):
        raise HTTPException(status_code=404, detail="Not found")
    snapshot = analytics.snapshot(1)
    job_counts = jobs.summary()["counts"]
    lines = [
        "# HELP newssense_http_requests_total API requests recorded today.",
        "# TYPE newssense_http_requests_total counter",
    ]
    for row in snapshot["requests"]:
        labels = f'method="{row["method"]}",route="{row["route"]}",status="{row["status_group"]}"'
        lines.append(f"newssense_http_requests_total{{{labels}}} {row['count']}")
        lines.append(f"newssense_http_request_max_milliseconds{{{labels}}} {row['max_ms']}")
    lines += [
        "# HELP newssense_background_jobs Jobs by current state.",
        "# TYPE newssense_background_jobs gauge",
    ]
    for name, count in sorted(job_counts.items()):
        lines.append(f'newssense_background_jobs{{status="{name}"}} {count}')
    lines.append("")
    return "\n".join(lines)
