"""测评接口（对应 D02 F-16）：管理端出题/发布，学生端作答/报告。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..core.errors import (Busy, Forbidden, NotFound, StateError,
                           ValidationError, envelope)
from ..core.security import Claims
from ..services import assessment as svc
from ..services.provider import build_provider
from .deps import current_claims, get_db, now_utc

router = APIRouter(prefix="/api", tags=["assessment"])


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _admin(claims: Claims = Depends(current_claims)) -> Claims:
    if claims.role != "admin":
        raise Forbidden("E4003", "只有课程管理员可以维护测评")
    return claims


def _provider(request: Request):
    cfg = request.app.state.config
    return build_provider(cfg.PROVIDER_MODE, cfg.PROVIDER_KEY,
                          cfg.MODEL_TIMEOUT_SECONDS, None, cfg.PROVIDER_BASE,
                          cfg.PROVIDER_MODEL, cfg.PROVIDER_THINKING,
                          default_max_tokens=cfg.MAX_TOKENS_AUTHOR)


class GenerateIn(BaseModel):
    count: int = Field(default=svc.ITEMS_PER_PAPER, ge=2, le=6)


class AnswerIn(BaseModel):
    answers: Dict[str, str] = Field(default_factory=dict)


class ApplyIn(BaseModel):
    action: str = Field(default="mark_mastered")


@router.post("/concepts/{concept_id}/assessments/generate")
def generate(concept_id: int, body: GenerateIn, request: Request,
             claims: Claims = Depends(_admin)):
    db = get_db(request)
    rows = db.query("SELECT * FROM concept WHERE concept_id = ?", (concept_id,))
    if not rows:
        raise NotFound("E1002", "知识点不存在")
    concept = rows[0]
    outline = (concept["outline"] or "").strip()
    if not outline:
        raise ValidationError("E1001", "请先填写知识点要点（出题依据）", field="outline")
    resources = db.query(
        "SELECT r.summary FROM resource r JOIN concept_resource cr"
        " ON cr.resource_id = r.resource_id WHERE cr.concept_id = ?"
        " AND r.status = 'enabled'", (concept_id,))
    title, items, mode, reason = svc.generate_items(
        _provider(request), concept, resources,
        max_tokens=request.app.state.config.MAX_TOKENS_AUTHOR)
    if not items:
        raise Busy("E1005", "出题失败（%s），请稍后重试或手工录入" % (reason or "UNKNOWN"))
    paper_id = svc.save_paper(db, concept, title, items, claims.sub, mode)
    return envelope("OK", "ok", {
        "paper_id": paper_id, "title": title, "items": items,
        "mode": mode, "degraded_reason": reason,
    }, request_id=_rid(request))


class PaperPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    items: Optional[List[Dict[str, Any]]] = None


@router.patch("/papers/{paper_id}")
def patch_paper(paper_id: int, body: PaperPatch, request: Request,
                claims: Claims = Depends(_admin)):
    db = get_db(request)
    rows = db.query("SELECT * FROM assessment_paper WHERE paper_id = ?", (paper_id,))
    if not rows or int(rows[0]["created_by"]) != int(claims.sub):
        raise NotFound("E1002", "试卷不存在")
    sets, params = [], []
    if body.title is not None:
        sets.append("title = ?")
        params.append(body.title.strip()[:120])
    if body.items is not None:
        items = svc._normalize_items({"items": body.items})
        if not items:
            raise ValidationError("E1001", "题目格式不合法（需要 4 题、含答案与采分点）",
                                  field="items")
        sets.append("items_json = ?")
        params.append(json.dumps(items, ensure_ascii=False))
    if sets:
        params.append(paper_id)
        with __import__("app.db.uow", fromlist=["UnitOfWork"]).UnitOfWork(db) as uow:
            uow.execute("UPDATE assessment_paper SET %s WHERE paper_id = ?"
                        % ", ".join(sets), tuple(params))
    row = db.query("SELECT * FROM assessment_paper WHERE paper_id = ?", (paper_id,))[0]
    return envelope("OK", "ok", {"paper_id": paper_id, "title": row["title"],
                                 "status": row["status"],
                                 "items": json.loads(row["items_json"])},
                    request_id=_rid(request))


@router.post("/papers/{paper_id}/publish")
def publish(paper_id: int, request: Request, claims: Claims = Depends(_admin)):
    row = svc.publish_paper(get_db(request), paper_id, claims.sub)
    return envelope("OK", "ok", {"paper_id": paper_id, "status": row["status"],
                                 "published_at": row["published_at"]},
                    request_id=_rid(request))


@router.get("/courses/{course_id}/assessments")
def list_papers(course_id: int, request: Request,
                claims: Claims = Depends(current_claims)):
    db = get_db(request)
    if claims.role == "admin":
        rows = db.query(
            "SELECT paper_id, concept_id, title, status, items_json, published_at"
            " FROM assessment_paper WHERE course_id = ? ORDER BY paper_id DESC",
            (course_id,))
        items = [{"paper_id": r["paper_id"], "concept_id": r["concept_id"],
                  "title": r["title"], "status": r["status"],
                  "count": len(json.loads(r["items_json"])),
                  "published_at": r["published_at"]} for r in rows]
    else:
        plan = db.query("SELECT plan_id FROM study_plan WHERE student_id = ?"
                        " AND course_id = ?", (claims.sub, course_id))
        items = []
        for r in svc.published_papers(db, course_id):
            items.append({"paper_id": r["paper_id"], "concept_id": r["concept_id"],
                          "title": r["title"], "status": "published",
                          "count": len(json.loads(r["items_json"])),
                          "published_at": r["published_at"]})
        if not plan:
            items = []
    return envelope("OK", "ok", {"items": items}, request_id=_rid(request))


@router.get("/papers/{paper_id}/stats")
def paper_stats(paper_id: int, request: Request, claims: Claims = Depends(_admin)):
    """单套试卷的班级学情（仅管理员）。"""
    db = get_db(request)
    rows = db.query("SELECT paper_id FROM assessment_paper WHERE paper_id = ?",
                    (paper_id,))
    if not rows:
        raise NotFound("E1002", "试卷不存在")
    data = svc.paper_stats(db, paper_id)
    return envelope("OK", "ok", data, request_id=_rid(request))


@router.get("/courses/{course_id}/assessment-stats")
def course_stats(course_id: int, request: Request, claims: Claims = Depends(_admin)):
    db = get_db(request)
    return envelope("OK", "ok", {"items": svc.course_stats(db, course_id)},
                    request_id=_rid(request))


@router.get("/papers/{paper_id}/items")
def paper_items(paper_id: int, request: Request,
                claims: Claims = Depends(current_claims)):
    db = get_db(request)
    rows = db.query("SELECT * FROM assessment_paper WHERE paper_id = ?", (paper_id,))
    if not rows:
        raise NotFound("E1002", "试卷不存在")
    paper = rows[0]
    if paper["status"] != "published" and claims.role != "admin":
        raise NotFound("E1002", "试卷不存在")
    return envelope("OK", "ok", {"paper_id": paper_id, "title": paper["title"],
                                 "items": svc.public_items(paper["items_json"])},
                    request_id=_rid(request))


@router.post("/papers/{paper_id}/attempts")
def submit(paper_id: int, body: AnswerIn, request: Request,
           claims: Claims = Depends(current_claims)):
    db = get_db(request)
    rows = db.query("SELECT * FROM assessment_paper WHERE paper_id = ?", (paper_id,))
    if not rows or rows[0]["status"] != "published":
        raise NotFound("E1002", "试卷不存在")
    paper = rows[0]
    items = json.loads(paper["items_json"])
    score, max_score, details, status = svc.grade(
        _provider(request), items, body.answers,
        max_tokens=request.app.state.config.MAX_TOKENS_GRADE)
    concept = db.query("SELECT name FROM concept WHERE concept_id = ?",
                       (int(paper["concept_id"]),)) if paper["concept_id"] else []
    report = svc.build_report(concept[0]["name"] if concept else paper["title"],
                              score, max_score, details)
    attempt_id = svc.save_attempt(db, paper, claims.sub, body.answers, score,
                                  max_score, details, status, report,
                                  request.app.state.config.PROVIDER_MODEL)
    return envelope("OK", "ok", {"attempt_id": attempt_id, "score": score,
                                 "max_score": max_score, "status": status,
                                 "report": report}, request_id=_rid(request))


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: int, request: Request,
                claims: Claims = Depends(current_claims)):
    db = get_db(request)
    rows = db.query("SELECT * FROM assessment_attempt WHERE attempt_id = ?",
                    (attempt_id,))
    if not rows or int(rows[0]["student_id"]) != int(claims.sub):
        raise NotFound("E1002", "测评记录不存在")
    row = rows[0]
    return envelope("OK", "ok", {
        "attempt_id": attempt_id, "paper_id": row["paper_id"],
        "score": row["score"], "max_score": row["max_score"],
        "status": row["status"], "created_at": row["created_at"],
        "report": json.loads(row["report_json"]),
    }, request_id=_rid(request))


@router.post("/attempts/{attempt_id}/apply")
def apply(attempt_id: int, body: ApplyIn, request: Request,
          claims: Claims = Depends(current_claims)):
    """采纳建议：把该知识点加入计划的"已掌握"集合。"""
    from ..db.uow import UnitOfWork
    db = get_db(request)
    rows = db.query("SELECT a.*, p.concept_id, p.course_id FROM assessment_attempt a"
                    " JOIN assessment_paper p ON p.paper_id = a.paper_id"
                    " WHERE a.attempt_id = ?", (attempt_id,))
    if not rows or int(rows[0]["student_id"]) != int(claims.sub):
        raise NotFound("E1002", "测评记录不存在")
    row = rows[0]
    if body.action != "mark_mastered":
        raise ValidationError("E1001", "暂只支持 mark_mastered", field="action")
    plan = db.query("SELECT c.constraint_id, c.mastered_concept_ids_json"
                    " FROM plan_constraint c JOIN study_plan p ON p.plan_id = c.plan_id"
                    " WHERE p.student_id = ? AND p.course_id = ?",
                    (claims.sub, int(row["course_id"])))
    if not plan:
        raise StateError("E1003", "还没有该课程的计划，无法写入已掌握")
    mastered = json.loads(plan[0]["mastered_concept_ids_json"] or "[]")
    concept_id = int(row["concept_id"])
    if concept_id not in mastered:
        mastered.append(concept_id)
        with UnitOfWork(db) as uow:
            uow.execute("UPDATE plan_constraint SET mastered_concept_ids_json = ?"
                        " WHERE constraint_id = ?",
                        (json.dumps(mastered), int(plan[0]["constraint_id"])))
    return envelope("OK", "ok", {"mastered_concept_ids": mastered},
                    request_id=_rid(request))
