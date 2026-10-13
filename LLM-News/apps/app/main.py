from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
import logging
import os
import time
from pathlib import Path
from .core.config import settings
from .core.limits import BudgetExceeded, RateLimited
from .core import analytics
from .core.monitoring import configure_logging, record_event
from .core.generation import PipelineSpendExceeded
from .api.api import api_router
from .api.endpoints import public

# Configure structured logs before the application starts serving requests.
configure_logging()
logger = logging.getLogger(__name__)

if os.getenv("SENTRY_DSN", "").strip():
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=os.environ["SENTRY_DSN"],
            environment=os.getenv("APP_ENV", "development"),
            traces_sample_rate=max(0.0, min(1.0, float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")))),
            send_default_pii=False,
        )
    except Exception:
        logger.exception("Could not initialize exception reporting")

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG
)

# Configure CORS (no cookies or credentials are used, so none are allowed cross-origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)


@app.middleware("http")
async def production_guardrails(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > settings.MAX_REQUEST_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body is too large"})
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = round((time.perf_counter() - started) * 1000)
        route = getattr(request.scope.get("route"), "path", "/unmatched")
        try:
            analytics.record_request(route, request.method, 500, elapsed)
        except Exception:
            logger.exception("Could not record aggregate request metric")
        try:
            record_event("backend", "unhandled_request_error", "error", f"{request.method} {route}")
        except Exception:
            logger.exception("Could not record operational event")
        raise
    elapsed = round((time.perf_counter() - started) * 1000)
    route = getattr(request.scope.get("route"), "path", "/unmatched")
    try:
        analytics.record_request(route, request.method, response.status_code, elapsed)
    except Exception:
        logger.exception("Could not record aggregate request metric")
    if elapsed >= settings.SLOW_REQUEST_MS:
        logger.warning("Slow request route=%s method=%s duration_ms=%d", route, request.method, elapsed)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    return response


@app.exception_handler(RateLimited)
async def rate_limited(request: Request, exc: RateLimited):
    return JSONResponse(status_code=429, content={"detail": str(exc)}, headers={"Retry-After": str(exc.retry_after)})


@app.exception_handler(BudgetExceeded)
async def budget_exceeded(request: Request, exc: BudgetExceeded):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(PipelineSpendExceeded)
async def spending_exceeded(request: Request, exc: PipelineSpendExceeded):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# Custom static file handler with CORS headers
@app.get("/static/{path:path}")
async def static_files(request: Request, path: str):
    """Serve static files with CORS headers"""
    static_dir = Path("static").resolve()
    file_path = (static_dir / path).resolve()

    # Reject paths like "..%2F..%2F.env" that resolve outside the static directory
    if file_path.is_relative_to(static_dir) and file_path.is_file():
        return FileResponse(
            file_path,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    raise HTTPException(status_code=404, detail="File not found")

# Include API routes
app.include_router(api_router, prefix="/api")
# Share pages with link previews (/share/...) and the RSS feed (/feed.xml)
app.include_router(public.router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": f"{settings.APP_NAME} is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
