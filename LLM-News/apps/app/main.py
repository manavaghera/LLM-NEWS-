from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import logging
from pathlib import Path
from .core.config import settings
from .core.limits import BudgetExceeded, RateLimited
from .api.api import api_router
from .api.endpoints import public

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


@app.exception_handler(RateLimited)
async def rate_limited(request: Request, exc: RateLimited):
    return JSONResponse(status_code=429, content={"detail": str(exc)}, headers={"Retry-After": str(exc.retry_after)})


@app.exception_handler(BudgetExceeded)
async def budget_exceeded(request: Request, exc: BudgetExceeded):
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
