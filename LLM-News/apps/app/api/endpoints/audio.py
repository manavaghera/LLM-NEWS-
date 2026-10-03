import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from ...core.limits import limit_ai_requests
from ...services.audio_service import VOICES, audio_cache, speak
from ...services.news_service import NewsService
from ...services.translation_service import TranslationService

router = APIRouter()
logger = logging.getLogger(__name__)

news_service = NewsService()
translation_service = TranslationService()


@router.get("/article/{date}/{group_id}/{lang}", dependencies=[Depends(limit_ai_requests)])
async def article_audio(date: str, group_id: str, lang: str):
    """An article's spoken summary in a language. Translations must be requested first (they are an
    LLM call); the speech itself is free and saved after the first time."""
    if lang not in VOICES:
        raise HTTPException(status_code=400, detail=f"No voice for '{lang}'. Supported: {list(VOICES)}")
    article = news_service.get_article(date, group_id)  # also validates date and id
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if lang == "en":
        pipeline_audio = Path(f"static/audio/{date}/{group_id}.mp3")
        if pipeline_audio.is_file():
            return FileResponse(pipeline_audio, media_type="audio/mpeg")
        text = article.get("summary_speech") or article.get("lead")
    else:
        translated = translation_service.cached_translation(date, group_id, lang)
        if not translated:
            raise HTTPException(status_code=404, detail="Translate the article into this language first")
        text = translated.get("summary_speech") or translated.get("lead")

    if not text:
        raise HTTPException(status_code=404, detail="This article has no summary to read aloud")
    path = audio_cache("articles", date, f"{group_id}.{lang}.mp3")
    try:
        await speak(text, path, lang)
    except Exception as e:
        logger.error(f"Article audio failed: {e}")
        raise HTTPException(status_code=502, detail="The voice service had a problem. Please try again.")
    return FileResponse(path, media_type="audio/mpeg")
