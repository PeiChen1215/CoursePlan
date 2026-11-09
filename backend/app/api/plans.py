"""学习计划与约束路由（D06 §12.6.1：/api/plans/*）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..core.errors import ValidationError, envelope
from ..core.security import Claims
from ..db.uow import UnitOfWork
from ..services.capacity import ConstraintInput
from ..services.constraint import ConstraintService
from .deps import current_claims, get_db, now_utc

router = APIRouter(prefix="/api/plans", tags=["plans"])


def get_service(request: Request) -> ConstraintService:
    return ConstraintService(get_db(request), request.app.state.config)


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _parse_base(text: Optional[str], default: datetime) -> datetime:
    if not text:
        return default
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValidationError("E1001", "base_time 格式应为 YYYY-MM-DDTHH:MM:SSZ",
                              field="base_time")


class PlanIn(BaseModel):
    course_id: int = Field(gt=0)


class ConstraintIn(BaseModel):
    target_concept_id: int = Field(gt=0)
    extra_concept_ids: List[int] = []
    deadline: str
    availability: Dict[str, List[List[str]]] = {}
    excluded_dates: List[str] = []
    mastered_concept_ids: List[int] = []
    base_time: Optional[str] = None


@router.post("")
def create_plan(body: PlanIn, request: Request, claims: Claims = Depends(current_claims)):
    db = get_db(request)
    now = now_utc()
    rows = db.query("SELECT course_id, status FROM course WHERE course_id = ?",
                    (body.course_id,))
    if not rows:
        raise ValidationError("E1001", "课程不存在", field="course_id")
    if rows[0]["status"] != "enabled":
        raise ValidationError("E1003", "课程已停用，不能新建学习计划", field="course_id")
    with UnitOfWork(db) as uow:
        cur = uow.execute(
            "INSERT INTO study_plan(student_id,course_id,status,created_at,updated_at)"
            " VALUES(?,?,'draft',?,?)",
            (claims.sub, body.course_id, now.strftime("%Y-%m-%dT%H:%M:%SZ"),
             now.strftime("%Y-%m-%dT%H:%M:%SZ")))
        plan_id = int(cur.lastrowid)
    return envelope("OK", "ok", {"plan_id": plan_id, "status": "draft"},
                    request_id=_rid(request))


def _to_input(body: ConstraintIn) -> ConstraintInput:
    return ConstraintInput(
        target_concept_id=body.target_concept_id,
        extra_concept_ids=body.extra_concept_ids,
        deadline=body.deadline,
        availability=body.availability,
        excluded_dates=body.excluded_dates,
        mastered_concept_ids=body.mastered_concept_ids)


@router.put("/{plan_id}/constraint")
def put_constraint(plan_id: int, body: ConstraintIn, request: Request,
                   claims: Claims = Depends(current_claims),
                   svc: ConstraintService = Depends(get_service)):
    base = _parse_base(body.base_time, now_utc())
    saved = svc.save(plan_id, claims.sub, _to_input(body), base)
    s = saved.summary
    return envelope("OK", "ok", {
        "constraint_id": saved.constraint_id,
        "C": s.raw_minutes, "B": s.buffer_minutes, "C_prime": s.usable_minutes,
        "slots": s.slots, "path_minutes": s.path_minutes, "goals": s.goals,
    }, request_id=_rid(request))


@router.get("/{plan_id}/constraint")
def get_constraint(plan_id: int, request: Request,
                   claims: Claims = Depends(current_claims),
                   svc: ConstraintService = Depends(get_service)):
    data = svc.load(plan_id, claims.sub)
    return envelope("OK", "ok", data, request_id=_rid(request))


@router.post("/{plan_id}/capacity/preview")
def preview_capacity(plan_id: int, body: ConstraintIn, request: Request,
                     claims: Claims = Depends(current_claims),
                     svc: ConstraintService = Depends(get_service)):
    base = _parse_base(body.base_time, now_utc())
    s = svc.preview(plan_id, claims.sub, _to_input(body), base)
    return envelope("OK", "ok", {
        "C": s.raw_minutes, "B": s.buffer_minutes, "C_prime": s.usable_minutes,
        "slots": s.slots, "path_minutes": s.path_minutes, "goals": s.goals,
        "reject_reason": s.reject_reason,
    }, request_id=_rid(request))
