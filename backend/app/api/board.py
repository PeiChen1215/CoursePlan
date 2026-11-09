"""看板、草案查询与生成路由（D06 §12.6.1）。"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..core.errors import NotFound, envelope
from ..core.security import Claims
from ..services.board import BoardService
from ..services.planner import PlannerService
from ..services.progress import ProgressService
from ..services.validation import validate
from ..services import graph
from ..services.capacity import (compute_capacity, expand_slots, normalize_availability,
                                 normalize_dates)
from ..services.planner import Concept, Slice, Task
from .deps import current_claims, get_db, now_utc

router = APIRouter(prefix="/api/plans", tags=["board"])


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _board_service(request: Request) -> BoardService:
    return BoardService(get_db(request), request.app.state.config)


@router.get("")
def list_plans(request: Request, claims: Claims = Depends(current_claims)):
    db = get_db(request)
    rows = db.query(
        "SELECT p.plan_id, p.course_id, p.status, p.current_version, p.progress_revision,"
        " p.updated_at, c.name AS course_name FROM study_plan p"
        " JOIN course c ON c.course_id = p.course_id"
        " WHERE p.student_id = ? ORDER BY p.plan_id", (claims.sub,))
    return envelope("OK", "ok", {"items": [dict(r) for r in rows]},
                    request_id=_rid(request))


@router.get("/{plan_id}/board")
def board(plan_id: int, request: Request, version: Optional[int] = None,
          claims: Claims = Depends(current_claims),
          svc: BoardService = Depends(_board_service)):
    data = svc.build(plan_id, claims.sub, now_utc(), version)
    return envelope("OK", "ok", data, request_id=_rid(request))


@router.post("/{plan_id}/drafts")
def generate_draft(plan_id: int, request: Request,
                   claims: Claims = Depends(current_claims)):
    db = get_db(request)
    cfg = request.app.state.config
    draft = PlannerService(db, cfg).generate(plan_id, claims.sub, now_utc())

    concepts = [Concept(int(r["concept_id"]), r["name"], r["chapter"],
                        int(r["sort_order"]), int(r["reference_minutes"]), r["status"])
                for r in graph.load_concepts(db, 1, only_enabled=False)]
    by_id = {c.concept_id: c for c in concepts}
    edges = graph.load_edges(db, 1)
    row = db.query("SELECT * FROM plan_constraint WHERE plan_id = ?", (plan_id,))[0]
    availability = normalize_availability(json.loads(row["availability_json"]))
    excluded = normalize_dates(json.loads(row["excluded_dates_json"]))
    from datetime import datetime
    deadline = datetime.strptime(row["deadline"], "%Y-%m-%d").date()
    import math
    slots = expand_slots(availability, excluded, draft.base_time, deadline)
    raw = sum(s.minutes for s in slots)
    buffer = math.ceil(cfg.BUFFER_RATIO * raw)
    selected = {c for c in draft.order if c in by_id}
    report = validate(draft.tasks, draft.slices, slots, raw - buffer, raw, deadline,
                      edges, [by_id[c] for c in selected], selected, cfg)
    names = {c.concept_id: c.name for c in concepts}
    proposal_diff = _diff_against_current(db, plan_id, draft)

    return envelope("OK", "ok", {
        "revision": draft.revision,
        "tasks": [{"concept_id": t.concept_id, "name": names.get(t.concept_id, ""),
                   "kind": t.kind, "minutes": t.minutes} for t in draft.tasks],
        "slices": [{"concept_id": s.concept_id, "name": names.get(s.concept_id, ""),
                    "kind": s.kind, "slice_no": s.slice_no,
                    "start": s.start.strftime("%Y-%m-%dT%H:%M"),
                    "end": s.end.strftime("%Y-%m-%dT%H:%M")} for s in draft.slices],
        "unscheduled": [{"concept_id": u.concept_id, "kind": u.kind, "reason": u.reason}
                        for u in draft.unscheduled],
        "metrics": {
            "total_minutes": draft.metrics.total_minutes,
            "raw_minutes": draft.metrics.raw_minutes,
            "buffer_minutes": draft.metrics.buffer_minutes,
            "usable_minutes": draft.metrics.usable_minutes,
            "deficit_minutes": draft.metrics.deficit_minutes,
            "utilization": draft.metrics.utilization,
            "scheduled_minutes": draft.metrics.scheduled_minutes,
            "slices": draft.metrics.slices,
        },
        "report": {"passed": report.passed,
                   "issues": [i.as_dict() for i in report.issues]},
        "diff": proposal_diff,
    }, request_id=_rid(request))


def _diff_against_current(db, plan_id: int, draft) -> dict:
    """把新草案与当前生效版本按 (知识点, 类型) 对比，供调整预览用。"""
    plan = db.query("SELECT current_version FROM study_plan WHERE plan_id = ?", (plan_id,))[0]
    current = int(plan["current_version"] or 0)
    if not current:
        return {"added": [], "removed": [], "moved": [], "resized": []}
    old_rows = db.query(
        "SELECT pt.concept_id, pt.task_type, vt.estimated_minutes,"
        " (SELECT MIN(ts.start_epoch) FROM task_slice ts WHERE ts.version_id = vt.version_id"
        "  AND ts.task_id = vt.task_id) AS first_start"
        " FROM version_task vt JOIN plan_task pt ON pt.task_id = vt.task_id"
        " JOIN plan_version v ON v.version_id = vt.version_id"
        " WHERE v.plan_id = ? AND v.version_no = ?", (plan_id, current))
    old = {(int(r["concept_id"]), r["task_type"]): (int(r["estimated_minutes"]),
                                                    (r["first_start"] or 0) // 86400)
           for r in old_rows}
    new = {(t.concept_id, t.kind): t.minutes for t in draft.tasks}
    first_days = {}
    for s in draft.slices:
        key = (s.concept_id, s.kind)
        day = int(s.start.timestamp()) // 86400
        first_days[key] = min(first_days.get(key, day), day)
    added = sorted("%d-%s" % key for key in new if key not in old)
    removed = sorted("%d-%s" % key for key in old if key not in new)
    moved, resized = [], []
    for key in new.keys() & old.keys():
        old_minutes, old_day = old[key]
        if key in first_days and first_days[key] != old_day:
            moved.append("%d-%s" % key)
        if new[key] != old_minutes:
            resized.append("%d-%s" % key)
    return {"added": added, "removed": removed,
            "moved": sorted(moved), "resized": sorted(resized)}


class OverrideItem(BaseModel):
    concept_id: int = Field(gt=0)
    kind: str = Field(pattern="^(study|practice)$")
    minutes: int = Field(ge=1, le=1440)
    note: Optional[str] = Field(default=None, max_length=500)


class OverridesIn(BaseModel):
    items: list[OverrideItem]


@router.patch("/{plan_id}/drafts/{revision}/tasks")
def override_tasks(plan_id: int, revision: int, body: OverridesIn, request: Request,
                   claims: Claims = Depends(current_claims)):
    """覆盖任务时长并重新装箱，返回新一版草案（对应 D02 AT-17）。"""
    overrides = {(item.concept_id, item.kind): item.minutes for item in body.items}
    draft = PlannerService(get_db(request), request.app.state.config).apply_overrides(
        plan_id, claims.sub, revision, overrides, now_utc())
    return envelope("OK", "ok", {
        "revision": draft.revision,
        "tasks": [{"concept_id": t.concept_id, "kind": t.kind, "minutes": t.minutes}
                  for t in draft.tasks],
        "slices": [{"concept_id": s.concept_id, "kind": s.kind, "slice_no": s.slice_no,
                    "start": s.start.strftime("%Y-%m-%dT%H:%M"),
                    "end": s.end.strftime("%Y-%m-%dT%H:%M")} for s in draft.slices],
        "unscheduled": [{"concept_id": u.concept_id, "kind": u.kind, "reason": u.reason}
                        for u in draft.unscheduled],
        "metrics": {
            "total_minutes": draft.metrics.total_minutes,
            "raw_minutes": draft.metrics.raw_minutes,
            "buffer_minutes": draft.metrics.buffer_minutes,
            "usable_minutes": draft.metrics.usable_minutes,
            "deficit_minutes": draft.metrics.deficit_minutes,
            "utilization": draft.metrics.utilization,
            "scheduled_minutes": draft.metrics.scheduled_minutes,
            "slices": draft.metrics.slices,
        },
    }, request_id=_rid(request))


@router.get("/{plan_id}/drafts/{revision}")
def get_draft(plan_id: int, revision: int, request: Request,
              claims: Claims = Depends(current_claims)):
    db = get_db(request)
    plan = db.query("SELECT student_id FROM study_plan WHERE plan_id = ?", (plan_id,))
    if not plan or int(plan[0]["student_id"]) != int(claims.sub):
        raise NotFound("E1002", "草案不存在")
    rows = db.query("SELECT payload_json, status FROM plan_draft"
                    " WHERE plan_id = ? AND revision = ?", (plan_id, revision))
    if not rows:
        raise NotFound("E1002", "草案不存在")
    payload = json.loads(rows[0]["payload_json"])
    return envelope("OK", "ok", {
        "revision": revision, "status": rows[0]["status"],
        "tasks": payload["tasks"], "slices": payload["slices"],
        "unscheduled": payload.get("unscheduled", []),
        "input_hash": payload.get("input_hash"),
    }, request_id=_rid(request))
