import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from ...core.limits import BudgetExceeded, limit_ai_requests
from ...services.audio_service import audio_cache, briefing_script, speak
from ...services.digest_service import DigestService
from ...services.news_service import NewsService

router = APIRouter()
logger = logging.getLogger(__name__)

# Endpoints are plain `def`: FastAPI runs them in a worker thread, so slow LLM calls don't block the server
digest_service = DigestService()
news_service = NewsService()


class CategoryDigestRequest(BaseModel):
    date: str = Field(max_length=20)
    category: str = Field(max_length=50)


def daily_digest(date: str, max_articles: int = 20) -> dict:
    try:
        return digest_service.generate_daily_digest(date, max_articles=max_articles)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.error(f"Digest generation failed: {e}")
        raise HTTPException(status_code=500, detail="Digest generation failed. Please try again.")


@router.get("/daily/{date}", dependencies=[Depends(limit_ai_requests)])
def get_daily_digest(
    date: str,
    max_articles: int = Query(20, ge=1, le=50, description="Maximum articles to include"),
):
    """Generate a smart daily news digest for a given date (saved after the first time)."""
    return daily_digest(date, max_articles)


@router.get("/daily", dependencies=[Depends(limit_ai_requests)])
def get_latest_daily_digest(
    max_articles: int = Query(20, ge=1, le=50, description="Maximum articles to include"),
):
    """Generate a digest for the most recent available date."""
    date = news_service.get_most_recent_date()
    if not date:
        raise HTTPException(status_code=404, detail="No news has been generated yet")
    return daily_digest(date, max_articles)


@router.get("/daily/{date}/audio", dependencies=[Depends(limit_ai_requests)])
async def get_daily_briefing_audio(date: str):
    """The day's digest read aloud (an mp3, generated once)"""
    digest = await run_in_threadpool(daily_digest, date)
    if digest.get("error") or not digest.get("total_articles"):
        raise HTTPException(status_code=404, detail="No briefing is available for this date")
    path = audio_cache("briefings", f"{date}.mp3")
    try:
        await speak(briefing_script(digest), path)
    except Exception as e:
        logger.error(f"Briefing audio failed: {e}")
        raise HTTPException(status_code=502, detail="The voice service had a problem. Please try again.")
    return FileResponse(path, media_type="audio/mpeg")


@router.post("/category", dependencies=[Depends(limit_ai_requests)])
def get_category_digest(request: CategoryDigestRequest):
    """Generate a digest for a specific category on a given date."""
    try:
        return digest_service.generate_category_digest(request.date, request.category)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.error(f"Category digest failed: {e}")
        raise HTTPException(status_code=500, detail="Category digest generation failed. Please try again.")
