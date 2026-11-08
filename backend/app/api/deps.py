"""FastAPI 依赖：配置、数据库、当前用户（对应 D06 §12.6）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Request, Header

from ..core.errors import Unauthorized
from ..core.security import Claims
from ..db.uow import Database
from ..services.auth import AuthService


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_config(request: Request):
    return request.app.state.config


def get_auth(request: Request) -> AuthService:
    return AuthService(get_db(request), get_config(request))


def current_claims(request: Request,
                   authorization: Optional[str] = Header(default=None)) -> Claims:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("E4001", "缺少令牌")
    token = authorization.split(" ", 1)[1].strip()
    return get_auth(request).authenticate(token, now_utc())
