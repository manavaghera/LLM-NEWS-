from pathlib import Path

from fastapi import APIRouter, Response, status
from ...services.llm_service import LLMService
from ...services.update_status import read_update_status
from ...core.config import settings

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
    checks = {
        "static_directory": Path("static").is_dir(),
        "cache_writable": settings.CACHE_DIR.exists() or settings.CACHE_DIR.parent.exists(),
    }
    production_issues = settings.production_issues() if not settings.DEBUG else []
    ready = all(checks.values()) and not production_issues
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "checks": checks,
            "configuration_issues": production_issues, "update": read_update_status()}
