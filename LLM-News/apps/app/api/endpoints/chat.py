import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from ...core.limits import BudgetExceeded, limit_ai_requests
from ...schemas.chat import ChatStreamRequest
from ...services.chat_service import ChatService
from ...services.llm_service import LLMService
from ...services.news_service import NewsService

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
llm_service = LLMService()
news_service = NewsService()
chat_service = ChatService(llm_service, news_service)

@router.post("/stream", dependencies=[Depends(limit_ai_requests)])
async def chat_stream(request: ChatStreamRequest):
    """Stream a reply as server-sent events: {"type": "meta" | "delta" | "error" | "done", ...}"""
    async def events():
        try:
            async for event in chat_service.stream_chat(request):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Chat stream failed: {e}")
            readable = isinstance(e, BudgetExceeded) or (isinstance(e, RuntimeError) and "No AI provider" in str(e))
            message = str(e) if readable else "The AI service had a problem answering. Please try again."
            yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # X-Accel-Buffering stops nginx from holding the stream until it ends
    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.get("/models")
async def get_available_models():
    """Models the chat can use (only providers with an API key)"""
    try:
        models = llm_service.get_available_models()
        return {
            "models": models,
            "default": llm_service.get_default_model(),
            "total": len(models)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get available models")
