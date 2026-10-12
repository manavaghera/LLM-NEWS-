from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core import admin_accounts
from ...core.admin_auth import COOKIE_NAME, SESSION_SECONDS, create_session, require_admin, valid_password
from ...core.config import settings
from ...core.limits import RateLimiter, client_ip

router = APIRouter()
login_limiter = RateLimiter(limit=8, window_seconds=15 * 60)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str | None = Field(default=None, min_length=1, max_length=512)
    username: str | None = Field(default=None, min_length=1, max_length=80)
    password: str | None = Field(default=None, min_length=1, max_length=512)
    otp: str = Field(default="", max_length=12)

    @model_validator(mode="after")
    def credentials(self):
        if bool(self.token) == bool(self.username and self.password):
            raise ValueError("Provide either a legacy token or username and password")
        return self


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response):
    login_limiter.check(client_ip(request))
    identity = None
    if body.token:
        if not valid_password(body.token):
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        session_token = create_session()
    else:
        result = admin_accounts.login(body.username or "", body.password or "", body.otp)
        if not result:
            raise HTTPException(status_code=401, detail="Invalid admin credentials or one-time code")
        session_token, identity = result
    response.set_cookie(
        COOKIE_NAME, session_token, max_age=SESSION_SECONDS, httponly=True,
        secure=settings.PUBLIC_BASE_URL.startswith("https://"), samesite="strict", path="/api",
    )
    return {"status": "authenticated", "expires_in": SESSION_SECONDS, "user": identity}


@router.get("/session")
def session(identity=Depends(require_admin)):
    saved = {"authenticated": True}
    if identity.get("id") is not None:
        saved["user"] = identity
    return saved


@router.post("/logout")
def logout(request: Request, response: Response):
    admin_accounts.logout(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/api", samesite="strict")
    return {"status": "signed_out"}
