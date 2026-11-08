"""校验与确认路由（D06 §12.6.1）。"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from ..core.errors import envelope
from ..core.security import Claims
from ..db.uow import Database
from ..services.version import VersionService
from .deps import current_claims, get_db, now_utc

router = APIRouter(prefix="/api/plans", tags=["version"])


def get_service(request: Request) -> VersionService:
    return VersionService(get_db(request), request.app.state.config)


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "")


class ConfirmIn(BaseModel):
    revision: int = Field(ge=1)


@router.post("/{plan_id}/drafts/{revision}/confirm")
def confirm(plan_id: int, revision: int, request: Request,
            body: Optional[ConfirmIn] = None,
            idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
            claims: Claims = Depends(current_claims),
            svc: VersionService = Depends(get_service)):
    # 未带幂等键时由服务端生成（D06 §12.6.4）：本次点击视为一次操作
    key = idempotency_key or uuid.uuid4().hex
    result = svc.confirm(plan_id, revision, key, claims.sub, now_utc())
    return envelope("OK", "ok", {
        "version_no": result.version_no,
        "version_id": result.version_id,
        "replayed": result.replayed,
        "diff": result.diff,
        "metrics": result.metrics,
    }, request_id=_rid(request))


@router.get("/{plan_id}/versions")
def list_versions(plan_id: int, request: Request,
                  claims: Claims = Depends(current_claims),
                  svc: VersionService = Depends(get_service)):
    items = [{
        "version_no": v.version_no, "version_id": v.version_id,
        "change_reason": v.change_reason, "change_note": v.change_note,
        "created_at": v.created_at, "input_hash": v.input_hash,
        "tasks": v.tasks, "slices": v.slices,
    } for v in svc.list_versions(plan_id, claims.sub)]
    return envelope("OK", "ok", {"items": items}, request_id=_rid(request))


@router.get("/{plan_id}/versions/{from_no}/diff")
def version_diff(plan_id: int, from_no: int, request: Request, against: int,
                 claims: Claims = Depends(current_claims),
                 svc: VersionService = Depends(get_service)):
    return envelope("OK", "ok", svc.diff(plan_id, claims.sub, from_no, against),
                    request_id=_rid(request))
