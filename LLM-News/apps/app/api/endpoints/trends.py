from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ...services.report_service import ReportService
from ...services.trend_service import TrendService

router = APIRouter()

trend_service = TrendService()
report_service = ReportService()


@router.get("/topics")
async def get_trending_topics(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    top_n: int = Query(10, ge=1, le=50, description="Number of top topics to return"),
):
    """Get trending topics with growth analysis across recent dates."""
    try:
        return trend_service.get_trending_topics(days=days, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch trending topics: {str(e)}")


@router.get("/categories")
async def get_category_trends(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
):
    """Get article count trends per category over time."""
    try:
        return trend_service.get_category_trends(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch category trends: {str(e)}")


@router.get("/sentiment")
async def get_sentiment_trends(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
):
    """Track average sentiment per category over time."""
    try:
        return trend_service.get_sentiment_over_time(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sentiment trends: {str(e)}")


@router.get("/publishers")
async def get_publisher_diversity(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (default: latest)"),
):
    """Analyze publisher and regional diversity for a given date."""
    try:
        return trend_service.get_publisher_diversity(date=date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch publisher diversity: {str(e)}")


@router.get("/accuracy")
async def get_accuracy(days: int = Query(30, ge=1, le=365, description="Number of days to analyze")):
    """Fact-check results per day and per model: share of statements removed as unsupported."""
    try:
        result = trend_service.get_accuracy(days=days)
        reports = report_service.counts_by_date(day["date"] for day in result["days"])
        for day in result["days"]:
            day["reader_reports"] = reports.get(day["date"], 0)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch accuracy: {str(e)}")
