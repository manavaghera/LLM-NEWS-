from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel
from ...services.digest_service import DigestService
from ...services.news_service import NewsService

router = APIRouter()

digest_service = DigestService()
news_service = NewsService()


class CategoryDigestRequest(BaseModel):
    date: str
    category: str


@router.get("/daily/{date}")
async def get_daily_digest(
    date: str,
    max_articles: int = Query(20, ge=1, le=50, description="Maximum articles to include"),
):
    """Generate a smart daily news digest for a given date."""
    try:
        result = digest_service.generate_daily_digest(date, max_articles=max_articles)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Digest generation failed: {str(e)}")


@router.get("/daily")
async def get_latest_daily_digest(
    max_articles: int = Query(20, ge=1, le=50, description="Maximum articles to include"),
):
    """Generate a digest for the most recent available date."""
    try:
        date = news_service.get_most_recent_date()
        result = digest_service.generate_daily_digest(date, max_articles=max_articles)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Digest generation failed: {str(e)}")


@router.post("/category")
async def get_category_digest(request: CategoryDigestRequest):
    """Generate a digest for a specific category on a given date."""
    try:
        result = digest_service.generate_category_digest(request.date, request.category)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Category digest generation failed: {str(e)}")
