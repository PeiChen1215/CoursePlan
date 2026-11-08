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
        "report": {"passed": report.passed,
                   "issues": [i.as_dict() for i in report.issues]},
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
