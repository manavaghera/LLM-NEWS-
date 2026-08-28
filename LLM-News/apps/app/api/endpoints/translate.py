from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from ...services.translation_service import TranslationService, SUPPORTED_LANGUAGES
from ...services.news_service import NewsService

router = APIRouter()

translation_service = TranslationService()
news_service = NewsService()


class TranslateRequest(BaseModel):
    date: str
    group_id: str
    target_languages: List[str]
    source_language: str = "en"


class TranslateTextRequest(BaseModel):
    text: str
    target_language: str
    source_language: str = "en"


@router.get("/languages")
async def get_supported_languages():
    """Get list of supported translation languages."""
    return {
        "languages": SUPPORTED_LANGUAGES,
        "total": len(SUPPORTED_LANGUAGES),
    }


@router.post("/article")
async def translate_article_endpoint(request: TranslateRequest):
    """Translate a full article to one or more target languages."""
    try:
        article = news_service.get_article(request.date, request.group_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        if len(request.target_languages) == 1:
            result = translation_service.translate_article(
                article, request.target_languages[0], request.source_language
            )
            return {
                "status": "success",
                "language": request.target_languages[0],
                "translation": result,
            }
        else:
            results = translation_service.translate_article_to_multiple(
                article, request.target_languages, request.source_language
            )
            return {
                "status": "success",
                "translations": results,
                "languages_requested": request.target_languages,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@router.post("/text")
async def translate_text_endpoint(request: TranslateTextRequest):
    """Translate arbitrary text to a target language."""
    try:
        if request.target_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {request.target_language}. Supported: {list(SUPPORTED_LANGUAGES.keys())}",
            )
        translated = translation_service._translate_text(
            request.text, request.target_language, request.source_language
        )
        return {
            "status": "success",
            "source_language": request.source_language,
            "target_language": request.target_language,
            "original": request.text,
            "translated": translated,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")
