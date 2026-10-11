from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ...core.admin_auth import COOKIE_NAME, SESSION_SECONDS, create_session, require_admin, valid_password
from ...core.config import settings
from ...core.limits import RateLimiter, client_ip

router = APIRouter()
login_limiter = RateLimiter(limit=8, window_seconds=15 * 60)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=512)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response):
    login_limiter.check(client_ip(request))
    if not valid_password(body.token):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    response.set_cookie(
        COOKIE_NAME, create_session(), max_age=SESSION_SECONDS, httponly=True,
        secure=settings.PUBLIC_BASE_URL.startswith("https://"), samesite="strict", path="/api",
    )
    return {"status": "authenticated", "expires_in": SESSION_SECONDS}


@router.get("/session", dependencies=[Depends(require_admin)])
def session():
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/api", samesite="strict")
    return {"status": "signed_out"}
