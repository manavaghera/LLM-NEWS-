import os
import re
from pathlib import Path

from fastapi import APIRouter
from ...core.config import settings
from ...services.news_service import NewsService

router = APIRouter()
news_service = NewsService()


def latest_summary_date() -> str:
    """Newest date that has a summary video, else the newest edition ("" when there is no news yet)"""
    video_dir = Path("static/summary-video")
    with_video = [d for d in news_service.available_dates() if video_dir.exists() and any(video_dir.glob(f"{d}*"))]
    return with_video[0] if with_video else news_service.get_most_recent_date()


def contact_email() -> str:
    """CONTACT_EMAIL for the About page (corrections and privacy questions), if it looks like an address"""
    email = os.getenv("CONTACT_EMAIL", "").strip()
    return email if re.fullmatch(r"[^@\s<>\"]+@[^@\s<>\"]+\.[^@\s<>\"]+", email) else ""


@router.get("/summary-date")
async def get_summary_date():
    """Get the summary video date"""
    date = latest_summary_date()
    return {"date": date, "formatted_date": date}

@router.get("")
async def get_config():
    """Get application configuration"""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "summary_date": latest_summary_date(),
        "default_news_date": news_service.get_most_recent_date(),
        "contact_email": contact_email(),
    }
