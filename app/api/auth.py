"""Authentication.

Two ways in:
  * login session (web UI): POST /api/auth/login sets an HttpOnly cookie; API clients
    may also pass the returned token as `Authorization: Bearer <token>`;
  * static API token (`security.api_token` in settings) for scripts and integrations:
    `Authorization: Bearer <token>`, `X-API-Key: <token>` or `?token=<token>`.
"""
import asyncio
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket
from pydantic import BaseModel, Field

from .. import auth, db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _bearer(headers, query) -> str:
    h = headers.get("authorization", "")
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return headers.get("x-api-key") or query.get("token") or ""


def _api_token_ok(provided: str) -> bool:
    expected = db.setting("security.api_token", "")
    return bool(expected and provided) and secrets.compare_digest(str(provided), str(expected))


def _resolve(headers, query, cookies) -> tuple[dict | None, str]:
    """Return (user, session_token). user is {'api': True} for the static API token."""
    cookie = cookies.get(auth.COOKIE, "")
    user = auth.session_user(cookie)
    if user:
        return user, cookie
    bearer = _bearer(headers, query)
    user = auth.session_user(bearer)
    if user:
        return user, bearer
    if _api_token_ok(bearer):
        return {"api": True}, ""
    return None, ""


async def require_auth(request: Request):
    user, token = _resolve(request.headers, request.query_params, request.cookies)
    if not user:
        raise HTTPException(401, "authentication required")
    request.state.user = user
    request.state.session = token


def ws_authorized(ws: WebSocket) -> bool:
    user, _ = _resolve(ws.headers, ws.query_params, ws.cookies)
    return user is not None


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=5, max_length=128)
    new_username: str | None = Field(None, min_length=1, max_length=64)


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    user = await asyncio.to_thread(auth.authenticate, body.username, body.password)
    if not user:
        await asyncio.sleep(1.0)  # slow down password guessing
        raise HTTPException(401, "Неверный логин или пароль")
    token = auth.create_session(user["id"], request.client.host if request.client else "")
    response.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_TTL, httponly=True, samesite="lax")
    return {"token": token, "user": auth.public_user(user)}


@router.post("/logout")
def logout(request: Request, response: Response):
    user, token = _resolve(request.headers, request.query_params, request.cookies)
    if token:
        auth.delete_session(token)
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@router.get("/me", dependencies=[Depends(require_auth)])
def me(request: Request):
    user = request.state.user
    if user.get("api"):
        return {"username": "api-token", "api": True, "default_password": False}
    return auth.public_user(user)


@router.post("/password", dependencies=[Depends(require_auth)])
async def change_password(body: PasswordIn, request: Request):
    user = request.state.user
    if user.get("api"):
        raise HTTPException(400, "Смена пароля доступна только после входа по логину")
    if not await asyncio.to_thread(auth.verify_password, body.current_password, user["password_hash"]):
        raise HTTPException(400, "Текущий пароль указан неверно")
    if body.new_username and body.new_username.strip() != user["username"]:
        if db.scalar("SELECT COUNT(*) FROM users WHERE username=?", (body.new_username.strip(),)):
            raise HTTPException(409, "Такой логин уже занят")
    await asyncio.to_thread(auth.change_credentials, user["id"], body.new_password,
                            body.new_username, request.state.session)
    return {"ok": True, "user": auth.public_user(db.get("users", user["id"]))}
