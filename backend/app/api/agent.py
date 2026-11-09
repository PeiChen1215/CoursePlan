"""追问抽取与进度事件路由（D06 §12.6.1）。"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from ..core.errors import envelope
from ..core.security import Claims
from ..services import graph
from ..services.agent import extract
from ..services.progress import ProgressService
from ..services.timeline import TimelineService
from ..services.provider import MockProvider, build_provider
from .deps import current_claims, get_db, now_utc

router = APIRouter(prefix="/api", tags=["agent", "progress"])


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "")


class ExtractIn(BaseModel):
    utterance: str = Field(min_length=1, max_length=500)
    course_id: int = 1
    filled: dict = {}
    base_date: Optional[str] = None       # YYYY-MM-DD，便于测试与回放


@router.post("/agent/extract")
def agent_extract(body: ExtractIn, request: Request,
                  claims: Claims = Depends(current_claims)):
    db = get_db(request)
    cfg = request.app.state.config
    from datetime import date as _date
    base = (_date.fromisoformat(body.base_date) if body.base_date else _date.today())

    rows = graph.load_concepts(db, body.course_id, only_enabled=True)
    concepts = [{"concept_id": int(r["concept_id"]), "name": r["name"],
                 "aliases": []} for r in rows]
    provider = build_provider(cfg.PROVIDER_MODE, cfg.PROVIDER_KEY,
                              cfg.MODEL_TIMEOUT_SECONDS, None,
                              cfg.PROVIDER_BASE, cfg.PROVIDER_MODEL, cfg.PROVIDER_THINKING)
    result = extract(body.utterance, body.filled, concepts, provider, base,
                     int(body.filled.get("daily_limit") or 480))
    return envelope("OK", "ok", {
        "fields": result.fields,
        "questions": result.questions,
        "candidates": result.candidates,
        "mode": result.mode,
        "degraded_reason": result.degraded_reason,
        "warnings": result.warnings,
    }, request_id=_rid(request))


# ---------------------------------------------------------------- 进度
def get_progress_service(request: Request) -> ProgressService:
    return ProgressService(get_db(request), request.app.state.config)


class EventIn(BaseModel):
    task_id: int = Field(gt=0)
    event_type: str = Field(pattern="^(done|correction|note)$")
    actual_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    note: Optional[str] = Field(default=None, max_length=500)
    corrects_event_id: Optional[int] = None


@router.post("/plans/{plan_id}/events")
def submit_event(plan_id: int, body: EventIn, request: Request,
                 idempotency_key: Optional[str] = Header(default=None,
                                                          alias="Idempotency-Key"),
                 claims: Claims = Depends(current_claims),
                 svc: ProgressService = Depends(get_progress_service)):
    result = svc.submit(plan_id, claims.sub, body.task_id, body.event_type,
                        idempotency_key or uuid.uuid4().hex, now_utc(), body.actual_minutes,
                        body.note, body.corrects_event_id)
    return envelope("OK", "ok", {
        "event_id": result.event_id,
        "replayed": result.replayed,
        "completion_rate": result.completion_rate,
        "overdue": result.overdue,
    }, request_id=_rid(request))


def get_timeline_service(request: Request) -> TimelineService:
    return TimelineService(get_db(request), request.app.state.config)


@router.get("/plans/{plan_id}/events")
def list_events(plan_id: int, request: Request,
                claims: Claims = Depends(current_claims),
                svc: TimelineService = Depends(get_timeline_service)):
    return envelope("OK", "ok", {"items": svc.events(plan_id, claims.sub)},
                    request_id=_rid(request))


class ExplainIn(BaseModel):
    codes: List[str] = []


@router.post("/plans/{plan_id}/explain")
def explain(plan_id: int, body: ExplainIn, request: Request,
            claims: Claims = Depends(current_claims),
            svc: TimelineService = Depends(get_timeline_service)):
    return envelope("OK", "ok", {"items": svc.explain(body.codes)},
                    request_id=_rid(request))


@router.get("/plans/{plan_id}/progress")
def get_progress(plan_id: int, request: Request,
                 claims: Claims = Depends(current_claims),
                 svc: ProgressService = Depends(get_progress_service)):
    p = svc.progress(plan_id, claims.sub, now_utc())
    return envelope("OK", "ok", {
        "total_tasks": p.total_tasks,
        "done_tasks": p.done_tasks,
        "completion_rate": p.completion_rate,
        "planned_minutes": p.planned_minutes,
        "actual_minutes": p.actual_minutes,
        "overdue_tasks": p.overdue_tasks,
    }, request_id=_rid(request))
