from fastapi import APIRouter
from .endpoints import audio, health, news, chat, config, reports, trends, translate, digest

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(news.router, prefix="/news", tags=["news"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(trends.router, prefix="/trends", tags=["trends"])
api_router.include_router(translate.router, prefix="/translate", tags=["translate"])
api_router.include_router(digest.router, prefix="/digest", tags=["digest"])
api_router.include_router(audio.router, prefix="/audio", tags=["audio"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
