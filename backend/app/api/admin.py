"""运维接口：一致性备份与恢复（对应 D02 AT-31）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..core.errors import Forbidden, envelope
from ..core.security import Claims
from ..services.backup import BackupService
from .deps import current_claims, get_config, now_utc

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _admin(claims: Claims = Depends(current_claims)) -> Claims:
    if claims.role != "admin":
        raise Forbidden("E4003", "该操作仅课程管理员可用")
    return claims


def get_backup(request: Request) -> BackupService:
    cfg = get_config(request)
    return BackupService(cfg.db_file, cfg.backup_dir, cfg.BACKUP_KEEP)


@router.post("/backup")
def create_backup(request: Request, claims: Claims = Depends(_admin),
                  svc: BackupService = Depends(get_backup)):
    result = svc.backup(now_utc())
    return envelope("OK", "ok", {
        "path": result.path,
        "name": result.path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1],
        "size_bytes": result.size_bytes,
        "integrity": result.integrity,
        "foreign_key_violations": result.foreign_key_violations,
        "pruned": result.pruned,
    }, request_id=_rid(request))


@router.get("/backups")
def list_backups(request: Request, claims: Claims = Depends(_admin),
                 svc: BackupService = Depends(get_backup)):
    return envelope("OK", "ok", {"items": svc.list_backups()}, request_id=_rid(request))


class RestoreIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@router.post("/restore")
def restore(body: RestoreIn, request: Request, claims: Claims = Depends(_admin),
            svc: BackupService = Depends(get_backup)):
    return envelope("OK", "ok", svc.restore(body.name, now_utc()),
                    request_id=_rid(request))
