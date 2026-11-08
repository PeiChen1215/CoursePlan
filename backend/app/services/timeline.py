"""学习事件时间线与问题解释（对应 D06 §10.6、§6 解释文本）。"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from ..core.errors import NotFound
from ..db.uow import Database

# 问题码 → 人话（D06 表 8.5 的建议动作）
EXPLAIN = {
    "CAP_EXCEEDED": ("任务总时长超过了你能排的时间", "延后截止日期、减少目标，或每周多留一段时间"),
    "TIME_OVERLAP": ("有两个任务排在了同一时间段", "重新生成一次草案通常就能解决"),
    "PREREQ_VIOLATED": ("先修内容排在了后继内容之后", "检查先修关系是否设反了，或重新生成"),
    "DEADLINE_UNREACHABLE": ("有任务落到了截止日期之后", "把截止日期往后挪，或减少目标"),
    "SLOT_INVALID": ("有任务落在了你没有标为可用的时间", "检查排除日期与每周可用时间"),
    "CAP_TIGHT": ("时间安排得很满，几乎没有缓冲", "建议给某一天留白，避免一次跟不上就全线延后"),
    "ISOLATED_CONCEPT": ("这个知识点既没有先修也没有后继", "确认是不是漏了关联；孤立点不影响排程"),
    "NOTHING_TO_PLAN": ("目标都已经标为已掌握", "没有需要排的内容，换一个目标即可"),
    "EMPTY_AVAILABILITY": ("你没有填任何可用时间", "在每周可用时间里点几个时间段"),
    "ALL_EXCLUDED": ("排除日期把整个规划区间都盖住了", "少排除几天，或把截止日期往后延"),
    "PREREQ_CYCLE": ("先修关系里出现了环", "环路上的知识点互相要求先学，需要删掉其中一条"),
}

EVENT_LABEL = {"done": "完成", "correction": "更正", "note": "备注"}


class TimelineService:
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config

    def _require_plan(self, plan_id: int, student_id: int):
        rows = self.db.query("SELECT * FROM study_plan WHERE plan_id = ?", (plan_id,))
        if not rows or int(rows[0]["student_id"]) != int(student_id):
            raise NotFound("E1002", "计划不存在")
        return rows[0]

    def events(self, plan_id: int, student_id: int) -> List[dict]:
        plan = self._require_plan(plan_id, student_id)
        current = int(plan["current_version"] or 0)
        rows = self.db.query(
            "SELECT e.event_id, e.task_id, e.version_id, e.event_type, e.actual_minutes,"
            " e.note, e.corrects_event_id, e.occurred_at, pt.concept_id,"
            " c.name AS concept_name, pt.task_type, v.version_no"
            " FROM learning_event e"
            " LEFT JOIN version_task vt ON vt.version_id = e.version_id"
            "  AND vt.task_id = e.task_id"
            " LEFT JOIN plan_task pt ON pt.task_id = e.task_id"
            " LEFT JOIN concept c ON c.concept_id = pt.concept_id"
            " LEFT JOIN plan_version v ON v.version_id = e.version_id"
            " WHERE e.plan_id = ? ORDER BY e.event_id DESC", (plan_id,))
        out = []
        for r in rows:
            out.append({
                "event_id": int(r["event_id"]),
                "task_id": int(r["task_id"]),
                "concept_name": r["concept_name"] or "",
                "task_type": r["task_type"] or "",
                "event_type": r["event_type"],
                "label": EVENT_LABEL.get(r["event_type"], r["event_type"]),
                "actual_minutes": None if r["actual_minutes"] is None else int(r["actual_minutes"]),
                "note": r["note"],
                "corrects_event_id": None if r["corrects_event_id"] is None else int(r["corrects_event_id"]),
                "occurred_at": r["occurred_at"],
                "version_no": None if r["version_no"] is None else int(r["version_no"]),
                "is_current_version": int(r["version_id"]) == current,
            })
        return out

    def explain(self, codes: List[str]) -> List[dict]:
        out = []
        for code in codes:
            title, action = EXPLAIN.get(code, (code, "暂无建议"))
            out.append({"code": code, "title": title, "action": action})
        return out
