"""认证路由（D06 第 12 章 §12.6.1 路由表）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..core.errors import envelope
from ..core.security import Claims
from .deps import current_claims, get_auth, now_utc

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
def login(body: LoginIn, request: Request):
    auth = get_auth(request)
    result = auth.login(body.username, body.password, now_utc())
    return envelope("OK", "ok", {
        "token": result.token,
        "role": result.role,
        "expires_at": result.expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user_id": result.user_id,
    }, request_id=getattr(request.state, "request_id", ""))


@router.get("/me")
def me(request: Request, claims: Claims = Depends(current_claims)):
    auth = get_auth(request)
    row = auth.ensure_enabled(claims.sub)
    return envelope("OK", "ok", {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
    }, request_id=getattr(request.state, "request_id", ""))
