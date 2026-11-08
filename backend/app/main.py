"""应用入口：装配配置、日志、数据库与路由（D06 第 12、14 章）。"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .core import config as config_mod
from .core.config import PROJECT_ROOT
from .core.errors import AppError, envelope
from .core.logging import log_event, setup_logging
from .db.uow import Database
from .api.auth import router as auth_router
from .api.content import router as content_router
from .api.plans import router as plans_router

SCHEMA_FILE = PROJECT_ROOT / "scripts" / "schema.sql"


def create_app(overrides: Dict[str, Any] | None = None) -> FastAPI:
    cfg = config_mod.load(overrides)
    setup_logging(cfg.LOG_LEVEL)
    db = Database(cfg.db_file)
    if SCHEMA_FILE.exists():
        db.init_schema(SCHEMA_FILE.read_text(encoding="utf-8"))

    app = FastAPI(title="学径 StudyPath", version="0.1.0", docs_url="/api/docs",
                  openapi_url="/api/openapi.json")
    app.state.config = cfg
    app.state.db = db

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        rid = getattr(request.state, "request_id", "")
        log_event("app_error", level="WARNING", code=exc.code, message=exc.message,
                  request_id=rid)
        return JSONResponse(status_code=exc.http_status,
                            content=envelope(exc.code, exc.message, None, exc.field,
                                             exc.detail, rid))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", "")
        first = (exc.errors() or [{}])[0]
        field = ".".join(str(x) for x in first.get("loc", [])[1:]) or None
        return JSONResponse(status_code=400,
                            content=envelope("E1001", first.get("msg", "参数不合法"),
                                             None, field, None, rid))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "")
        log_event("internal_error", level="ERROR", error=str(exc), request_id=rid)
        return JSONResponse(status_code=500,
                            content=envelope("E9000", "内部错误", None, None, None, rid))

    register_routes(app)
    app.include_router(auth_router)
    app.include_router(content_router)
    app.include_router(plans_router)
    return app


def register_routes(app: FastAPI) -> None:
    @app.get("/api/health")
    def health(request: Request):
        cfg = request.app.state.config
        db: Database = request.app.state.db
        db_state = "ok"
        try:
            db.scalar("SELECT 1")
            db.scalar("PRAGMA quick_check")
        except Exception:
            db_state = "error"
        backup_age = _backup_age_hours()
        return envelope("OK", "ok", {
            "service": "ok",
            "database": db_state,
            "provider": cfg.PROVIDER_MODE,
            "backup": "warn" if backup_age is None or backup_age > 24 else "ok",
            "backup_age_hours": backup_age,
        }, request_id=getattr(request.state, "request_id", ""))

    @app.get("/api/meta")
    def meta(request: Request):
        cfg = request.app.state.config
        return envelope("OK", "ok", {
            "project": "学径 StudyPath",
            "course": "软件工程综合实训",
            "config": cfg.as_dict(),
        }, request_id=getattr(request.state, "request_id", ""))


def _backup_age_hours(root: Path | None = None):
    root = root or (PROJECT_ROOT / "backups")
    if not root.exists():
        return None
    files = sorted(root.glob("*.db"), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    import time
    return round((time.time() - files[-1].stat().st_mtime) / 3600, 2)


app = create_app()
