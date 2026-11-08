"""约束与容量业务（对应 D06 第 5 章 M-03）。

职责：校验并规范化学生填写的约束 → 展开时段 → 算 C / B / C′ → 估算目标路径时长。
不排程、不校验方案，只回答「能排多少分钟」。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Sequence, Tuple

from ..core.errors import NotFound, ValidationError
from ..db.uow import Database, UnitOfWork
from . import graph
from .capacity import (CapacitySummary, ConstraintInput, NormalizedConstraint,
                       normalize, summarize)


@dataclass(frozen=True)
class SavedConstraint:
    constraint_id: int
    summary: CapacitySummary


class ConstraintService:
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config

    # ---------------- 计划归属
    def require_plan(self, plan_id: int, student_id: int):
        rows = self.db.query(
            "SELECT plan_id, student_id, course_id, status FROM study_plan"
            " WHERE plan_id = ?", (plan_id,))
        if not rows or int(rows[0]["student_id"]) != int(student_id):
            raise NotFound("E1002", "计划不存在")
        return rows[0]

    # ---------------- 目标路径时长
    def path_minutes(self, course_id: int, goals: Sequence[int]) -> int:
        edges = graph.load_edges(self.db, course_id)
        closure = graph.prereq_closure(edges, goals)
        rows = graph.load_concepts(self.db, course_id, only_enabled=False)
        minutes = {int(r["concept_id"]): int(r["reference_minutes"]) for r in rows}
        return sum(minutes.get(cid, 0) for cid in closure)

    def _check_goals(self, course_id: int, goals: Sequence[int]) -> None:
        rows = graph.load_concepts(self.db, course_id, only_enabled=True)
        valid = {int(r["concept_id"]) for r in rows}
        for g in goals:
            if g not in valid:
                raise ValidationError("E1001", "目标知识点不属于本课程或已停用",
                                      field="target_concept_id")

    # ---------------- 保存
    def save(self, plan_id: int, student_id: int, raw: ConstraintInput,
             base_time: datetime) -> SavedConstraint:
        plan = self.require_plan(plan_id, student_id)
        course_id = int(plan["course_id"])
        norm = normalize(raw, base_time.date())

        goals = [norm.target_concept_id] + norm.extra_concept_ids
        self._check_goals(course_id, goals)
        for m in norm.mastered_concept_ids:
            if m not in goals:
                raise ValidationError("E1001", "已掌握集合只能包含目标中的知识点",
                                      field="mastered_concept_ids")

        pm = self.path_minutes(course_id, goals)
        summary = summarize(norm, base_time, self.config.BUFFER_RATIO, pm)
        if summary.reject_reason:
            # 容量为零不入库：让学生先改约束（D06 §5.2 阻断分支）
            raise ValidationError("E1003", "容量为零：%s" % summary.reject_reason,
                                  field="availability", detail={
                                      "reason": summary.reject_reason})

        with UnitOfWork(self.db) as uow:
            uow.execute(
                "INSERT INTO plan_constraint(plan_id,course_id,target_concept_id,"
                "extra_concept_ids_json,deadline,availability_json,excluded_dates_json,"
                "mastered_concept_ids_json,base_time) VALUES(?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(plan_id) DO UPDATE SET target_concept_id=excluded."
                "target_concept_id, extra_concept_ids_json=excluded.extra_concept_ids_json,"
                " deadline=excluded.deadline, availability_json=excluded.availability_json,"
                " excluded_dates_json=excluded.excluded_dates_json,"
                " mastered_concept_ids_json=excluded.mastered_concept_ids_json,"
                " base_time=excluded.base_time",
                (plan_id, course_id, norm.target_concept_id,
                 json.dumps(norm.extra_concept_ids), norm.deadline.isoformat(),
                 _availability_json(norm), json.dumps([d.isoformat() for d in norm.excluded_dates]),
                 json.dumps(norm.mastered_concept_ids),
                 base_time.strftime("%Y-%m-%dT%H:%M:%SZ")))
            row = uow.fetch_one("SELECT constraint_id FROM plan_constraint"
                                " WHERE plan_id = ?", (plan_id,))
        return SavedConstraint(constraint_id=int(row["constraint_id"]), summary=summary)

    # ---------------- 预览（不落库）
    def preview(self, plan_id: int, student_id: int, raw: ConstraintInput,
                base_time: datetime) -> CapacitySummary:
        plan = self.require_plan(plan_id, student_id)
        norm = normalize(raw, base_time.date())
        goals = [norm.target_concept_id] + norm.extra_concept_ids
        self._check_goals(int(plan["course_id"]), goals)
        pm = self.path_minutes(int(plan["course_id"]), goals)
        return summarize(norm, base_time, self.config.BUFFER_RATIO, pm)

    # ---------------- 读取
    def load(self, plan_id: int, student_id: int) -> Optional[dict]:
        self.require_plan(plan_id, student_id)
        rows = self.db.query("SELECT * FROM plan_constraint WHERE plan_id = ?", (plan_id,))
        if not rows:
            return None
        r = rows[0]
        return {
            "constraint_id": r["constraint_id"],
            "target_concept_id": r["target_concept_id"],
            "extra_concept_ids": json.loads(r["extra_concept_ids_json"]),
            "deadline": r["deadline"],
            "availability": json.loads(r["availability_json"]),
            "excluded_dates": json.loads(r["excluded_dates_json"]),
            "mastered_concept_ids": json.loads(r["mastered_concept_ids_json"]),
            "base_time": r["base_time"],
        }


def _availability_json(norm: NormalizedConstraint) -> str:
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    out = {}
    for day, segs in norm.availability.items():
        if segs:
            out[names[day]] = [[s.strftime("%H:%M"), e.strftime("%H:%M")] for s, e in segs]
    return json.dumps(out, ensure_ascii=False)
