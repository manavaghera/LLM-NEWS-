import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ...core.limits import BudgetExceeded, limit_ai_requests, limit_uncached_ai_requests
from ...services.translation_service import TranslationService, SUPPORTED_LANGUAGES
from ...services.news_service import NewsService

router = APIRouter()
logger = logging.getLogger(__name__)

# Endpoints are plain `def`: FastAPI runs them in a worker thread, so slow LLM calls don't block the server
translation_service = TranslationService()
news_service = NewsService()


class TranslateRequest(BaseModel):
    date: str = Field(max_length=20)
    group_id: str = Field(max_length=50)
    target_languages: List[str] = Field(min_length=1, max_length=3)
    source_language: str = "en"


class TranslateTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    target_language: str
    source_language: str = "en"


@router.get("/languages")
async def get_supported_languages():
    """Get list of supported translation languages."""
    return {
        "languages": SUPPORTED_LANGUAGES,
        "total": len(SUPPORTED_LANGUAGES),
    }


@router.post("/article", dependencies=[Depends(limit_ai_requests)])
def translate_article_endpoint(request: TranslateRequest):
    """Translate a full article (one LLM call per language; saved for reuse)."""
    article = news_service.get_article(request.date, request.group_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    try:
        results = {
            lang: translation_service.translate_article(
                article, lang, request.source_language, date=request.date, group_id=request.group_id
            )
            for lang in request.target_languages
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise HTTPException(status_code=502, detail="Translation failed: the AI service had a problem. Please try again.")

    if len(request.target_languages) == 1:
        lang = request.target_languages[0]
        return {"status": "success", "language": lang, "translation": results[lang]}
    return {"status": "success", "translations": results, "languages_requested": request.target_languages}


@router.post("/text", dependencies=[Depends(limit_uncached_ai_requests)])
def translate_text_endpoint(request: TranslateTextRequest):
    """Translate arbitrary text to a target language."""
    if request.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {request.target_language}. Supported: {list(SUPPORTED_LANGUAGES.keys())}",
        )
    try:
        translated = translation_service._translate_text(
            request.text, request.target_language, request.source_language
        )
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise HTTPException(status_code=502, detail="Translation failed: the AI service had a problem. Please try again.")
    return {
        "status": "success",
        "source_language": request.source_language,
        "target_language": request.target_language,
        "original": request.text,
        "translated": translated,
    }
