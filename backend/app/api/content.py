"""课程内容路由（D06 §12.6.1）。写操作仅管理员可用。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..core.errors import envelope
from ..core.security import Claims
from ..services.content import ConceptInput, ContentService
from .deps import current_claims, get_config, get_db, now_utc

router = APIRouter(prefix="/api", tags=["content"])


def get_content(request: Request) -> ContentService:
    return ContentService(get_db(request))


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _admin(claims: Claims = Depends(current_claims)) -> Claims:
    from ..core.errors import Forbidden
    if claims.role != "admin":
        raise Forbidden("E4003", "该操作仅课程管理员可用")
    return claims


class ConceptIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    chapter: str = Field(min_length=1, max_length=100)
    difficulty: int = Field(ge=1, le=5)
    reference_minutes: int = Field(ge=5, le=600)
    objectives: List[str] = []
    pitfalls: List[str] = []


class PrereqBatchIn(BaseModel):
    edges: List[List[int]]


class CourseIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    semester: str = Field(min_length=1, max_length=32)
    total_hours: int = Field(gt=0, le=200)


@router.get("/courses")
def list_courses(request: Request, svc: ContentService = Depends(get_content)):
    rows = [dict(r) for r in svc.list_courses()]
    return envelope("OK", "ok", {"items": rows}, request_id=_rid(request))


@router.post("/courses")
def create_course(body: CourseIn, request: Request,
                  claims: Claims = Depends(_admin),
                  svc: ContentService = Depends(get_content)):
    cid = svc.create_course(claims.sub, body.name, body.semester, body.total_hours)
    return envelope("OK", "ok", {"course_id": cid}, request_id=_rid(request))


@router.get("/courses/{course_id}/concepts")
def list_concepts(course_id: int, request: Request,
                  include_disabled: bool = False,
                  svc: ContentService = Depends(get_content)):
    rows = [dict(r) for r in svc.list_concepts(course_id, include_disabled)]
    return envelope("OK", "ok", {"items": rows}, request_id=_rid(request))


@router.post("/courses/{course_id}/concepts")
def create_concept(course_id: int, body: ConceptIn, request: Request,
                   claims: Claims = Depends(_admin),
                   svc: ContentService = Depends(get_content)):
    cid = svc.save_concept(course_id, ConceptInput(
        name=body.name, chapter=body.chapter, difficulty=body.difficulty,
        reference_minutes=body.reference_minutes,
        objectives=body.objectives, pitfalls=body.pitfalls))
    return envelope("OK", "ok", {"concept_id": cid}, request_id=_rid(request))


@router.get("/courses/{course_id}/prerequisites")
def list_prereqs(course_id: int, request: Request,
                 svc: ContentService = Depends(get_content)):
    rows = [dict(r) for r in svc.list_prereqs(course_id)]
    return envelope("OK", "ok", {"items": rows}, request_id=_rid(request))


@router.post("/courses/{course_id}/prerequisites/batch")
def submit_prereqs(course_id: int, body: PrereqBatchIn, request: Request,
                   claims: Claims = Depends(_admin),
                   svc: ContentService = Depends(get_content)):
    pairs = [(int(e[0]), int(e[1])) for e in body.edges if len(e) == 2]
    n = svc.submit_prereqs(course_id, pairs)
    return envelope("OK", "ok", {"saved": n}, request_id=_rid(request))


@router.get("/concepts/{concept_id}/impact")
def concept_impact(concept_id: int, request: Request,
                   svc: ContentService = Depends(get_content)):
    return envelope("OK", "ok", svc.impact_of(concept_id), request_id=_rid(request))


@router.post("/concepts/{concept_id}/disable")
def disable_concept(concept_id: int, request: Request,
                    claims: Claims = Depends(_admin),
                    svc: ContentService = Depends(get_content)):
    return envelope("OK", "ok", svc.disable_concept(concept_id), request_id=_rid(request))
