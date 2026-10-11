from fastapi import APIRouter, HTTPException, Path as PathParam, Query
import json
from typing import Optional
from ...services import archive
from ...services.news_service import NewsService
from ...services.report_service import ReportService
from ...services.story_identity import story_identity
from ...services.update_status import read_update_status
from ...core.config import settings
from pathlib import Path

router = APIRouter()

DEFAULT_CATEGORIES = {
    "ai_models": "ai_models", "social": "social", "tech": "tech", "science": "science",
    "business": "business", "startups": "startups", "cybersecurity": "cybersecurity",
    "health": "health", "climate": "climate", "space": "space", "sports": "sports",
    "gaming": "gaming", "entertainment": "entertainment",
}

# Initialize news service
news_service = NewsService()

@router.get("")
async def get_news(
    category: Optional[str] = None,
    search: Optional[str] = None,
    date: Optional[str] = None,
    fuzzy: bool = Query(False, description="Enable fuzzy search")  # Add fuzzy parameter
):
    """Get news articles with optional filtering"""
    try:
        # Use most recent date if no date specified
        if not date:
            date = news_service.get_most_recent_date()
        
        return news_service.get_filtered_news(date, category, search, fuzzy)  # Pass fuzzy parameter
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch news")

@router.get("/search")
async def search_archive(
    q: str = Query(..., min_length=2, max_length=200, description="Words to find in any edition"),
    limit: int = Query(40, ge=1, le=100),
):
    """Stories from every edition containing all the words, newest edition first"""
    return archive.search_archive(news_service, q, limit)

@router.get("/articles/{date}/{group_id}/related")
async def related_articles(date: str, group_id: str):
    """Earlier coverage of the same story in previous editions"""
    return archive.related_articles(news_service, date, group_id)


@router.get("/articles/{date}/{group_id}/updates")
def followed_story_updates(
    date: str = PathParam(pattern=r"^\d{4}-\d{2}-\d{2}$", max_length=10),
    group_id: str = PathParam(pattern=r"^group_\d+$", max_length=50),
    limit: int = Query(20, ge=1, le=20),
):
    """Material article version and later related coverage for locally followed stories."""
    try:
        return archive.story_updates(news_service, date, group_id, limit=limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Article not found")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch story updates")


@router.get("/articles/{date}/{group_id}")
async def get_article(date: str, group_id: str):
    """Get a specific article by date and group ID"""
    try:
        article = news_service.get_article(date, group_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        corrections = ReportService().corrections_for_article(date, group_id, article=article)
        return {**article, "content_version": archive.content_version(article, corrections),
                "story_identity": story_identity(article)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch article")

@router.get("/categories")
async def get_categories():
    """Get all available news categories"""
    try:
        # Get the most recent date from available data
        static_dir = Path("static/articles")
        if not static_dir.exists():
            return {"categories": DEFAULT_CATEGORIES, "total": len(DEFAULT_CATEGORIES)}
        
        # Find the most recent date directory
        date_dirs = [d for d in static_dir.iterdir() if d.is_dir()]
        if not date_dirs:
            return {"categories": DEFAULT_CATEGORIES, "total": len(DEFAULT_CATEGORIES)}
        
        latest_date = max(date_dirs, key=lambda x: x.name)
        return news_service.get_categories(latest_date.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch categories")

@router.get("/categories/{date}")
async def get_categories_by_date(date: str):
    """Get categories for a specific date"""
    try:
        return news_service.get_categories(date)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch categories")

@router.get("/status")
async def get_update_status():
    """Last and next news update (pipeline/daily_update.py --interval); all null without a schedule"""
    return read_update_status()


@router.get("/models/catalog")
def get_model_catalog():
    """Dated, source-linked API model price and context snapshot used by the AI Models desk."""
    path = Path("static/model_catalog.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise ValueError("invalid model catalog")
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Model catalog is not available")
    except (OSError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Failed to read model catalog")


@router.get("/dates")
async def get_available_dates(
    limit: int = Query(0, ge=0, le=3650, description="Newest N editions; 0 = the whole archive"),
):
    """Every edition that has articles, newest first"""
    try:
        dates = news_service.available_dates()
        if limit:
            dates = dates[:limit]
        return {"dates": dates, "total": len(dates)}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching available dates: {str(e)}"
        )
