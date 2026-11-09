"""看板数据（对应 D06 第 11 章 M-09）。

只读装配：版本任务 + 时间片 + 学习事件 + 校验报告 → 前端可直接渲染的结构。
分组与渲染在前端做，后端只保证数据完整与归属正确。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..core.errors import NotFound
from ..db.uow import Database


def _iso(epoch: int) -> str:
    """返回**本地墙上时间**（与草案 payload 口径一致，前端直接按本地渲染）。"""
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%dT%H:%M")


@dataclass(frozen=True)
class BoardTask:
    task_id: int
    concept_id: int
    concept_name: str
    kind: str
    minutes: int
    start: str
    end: str
    done: bool
    overdue: bool
    issue_codes: List[str]


class BoardService:
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config

    def build(self, plan_id: int, student_id: int, now: datetime,
              version_no: Optional[int] = None) -> dict:
        plan = self.db.query("SELECT * FROM study_plan WHERE plan_id = ?", (plan_id,))
        if not plan or int(plan[0]["student_id"]) != int(student_id):
            raise NotFound("E1002", "计划不存在")
        plan = plan[0]
        current = int(plan["current_version"] or 0)

        if version_no is None:
            version_no = current
        if not version_no:
            return {"plan_id": plan_id, "version_no": None, "readonly": False,
                    "tasks": [], "unscheduled": [], "issues": [], "progress": {
                        "total_tasks": 0, "done_tasks": 0, "completion_rate": 0.0,
                        "planned_minutes": 0, "actual_minutes": 0,
                        "overdue_tasks": []}}

        version = self.db.query(
            "SELECT version_id, version_no FROM plan_version WHERE plan_id = ? AND version_no = ?",
            (plan_id, version_no))
        if not version:
            raise NotFound("E1002", "版本不存在")
        version_id = int(version[0]["version_id"])
        readonly = int(version_no) != current

        # 完成事实是跨版本冻结的：同一任务在旧版本打过卡，新版本里仍算完成
        # （schema 的 ux_done_once 按 task_id 唯一，两者必须同口径）
        done_ids = {int(r["task_id"]) for r in self.db.query(
            "SELECT DISTINCT task_id FROM learning_event"
            " WHERE event_type = 'done'")}

        actual = {}
        for r in self.db.query(
                "SELECT task_id, actual_minutes, occurred_at FROM learning_event"
                " WHERE event_type IN ('done','correction')"
                " ORDER BY occurred_at"):
            actual[int(r["task_id"])] = r["actual_minutes"]
        actual: Dict[int, int] = {}
        for r in self.db.query(
                "SELECT task_id, actual_minutes FROM learning_event"
                " WHERE version_id = ? AND event_type IN ('done','correction')"
                " ORDER BY event_id", (version_id,)):
            if r["actual_minutes"] is not None:
                actual[int(r["task_id"])] = int(r["actual_minutes"])

        issues = self._issues(version_id)
        code_by_concept: Dict[int, List[str]] = {}
        for issue in issues:
            cid = issue.get("concept_id")
            if cid is not None:
                code_by_concept.setdefault(int(cid), []).append(issue["code"])

        rows = self.db.query(
            "SELECT vt.task_id, vt.estimated_minutes, pt.concept_id, pt.task_type,"
            " c.name AS concept_name, ts.start_epoch, ts.end_epoch, ts.slice_no"
            " FROM version_task vt"
            " JOIN plan_task pt ON pt.task_id = vt.task_id AND pt.plan_id = vt.plan_id"
            " JOIN concept c ON c.concept_id = pt.concept_id"
            " LEFT JOIN task_slice ts ON ts.version_id = vt.version_id"
            "  AND ts.task_id = vt.task_id"
            " WHERE vt.version_id = ?"
            " ORDER BY ts.start_epoch IS NULL, ts.start_epoch, ts.slice_no", (version_id,))

        totals: Dict[int, int] = {}
        for r in rows:
            if r["start_epoch"] is not None:
                totals[int(r["task_id"])] = totals.get(int(r["task_id"]), 0) + 1

        now_epoch = int(now.timestamp())
        tasks: List[dict] = []
        unscheduled: List[dict] = []
        seen_unscheduled = set()
        for r in rows:
            cid = int(r["concept_id"])
            if r["start_epoch"] is None:
                if (cid, r["task_type"]) not in seen_unscheduled:
                    seen_unscheduled.add((cid, r["task_type"]))
                    unscheduled.append({
                        "task_id": int(r["task_id"]), "concept_id": cid,
                        "concept_name": r["concept_name"], "kind": r["task_type"],
                        "minutes": int(r["estimated_minutes"]),
                        "reason": "CAPACITY",
                    })
                continue
            done = int(r["task_id"]) in done_ids
            overdue = (not readonly) and (not done) and now_epoch > int(r["end_epoch"])
            tasks.append({
                "task_id": int(r["task_id"]), "concept_id": cid,
                "concept_name": r["concept_name"], "kind": r["task_type"],
                "minutes": int((int(r["end_epoch"]) - int(r["start_epoch"])) // 60),
                "start": _iso(int(r["start_epoch"])), "end": _iso(int(r["end_epoch"])),
                "done": done, "overdue": overdue,
                "issue_codes": code_by_concept.get(cid, []),
                "actual_minutes": actual.get(int(r["task_id"])),
                "slice_no": int(r["slice_no"]),
                "slice_total": totals.get(int(r["task_id"]), 1),
            })

        lateness = [
            (now_epoch - int(r["end_epoch"])) // 3600
            for r in rows
            if r["start_epoch"] is not None
            and int(r["task_id"]) not in done_ids
            and (not readonly)
            and now_epoch > int(r["end_epoch"])
        ]
        worst = max(lateness) if lateness else 0
        adjust_hint = None
        if worst >= self.config.DELAY_THRESHOLD_HOURS:
            adjust_hint = {
                "reason": "DELAY",
                "overdue_tasks": len(lateness),
                "worst_lateness_hours": worst,
                "threshold_hours": self.config.DELAY_THRESHOLD_HOURS,
                "message": "有 %d 个任务已逾期 %d 小时，建议调整计划"
                           % (len(lateness), worst),
            }

        total_tasks = self.db.scalar(
            "SELECT COUNT(*) FROM version_task WHERE version_id = ? AND in_scope = 1",
            (version_id,)) or 0
        done_count = len(done_ids & self._in_scope_ids(version_id))
        planned = sum(t["minutes"] for t in tasks)
        return {
            "plan_id": plan_id, "version_no": int(version_no), "readonly": readonly,
            "tasks": tasks, "unscheduled": unscheduled, "issues": issues,
            "adjust_hint": adjust_hint,
            "progress": {
                "total_tasks": int(total_tasks), "done_tasks": done_count,
                "completion_rate": round(done_count / total_tasks, 3) if total_tasks else 0.0,
                "planned_minutes": planned,
                "actual_minutes": sum(actual.values()),
                "overdue_tasks": sorted({t["task_id"] for t in tasks if t["overdue"]}),
            },
        }

    def _in_scope_ids(self, version_id: int) -> set:
        return {int(r["task_id"]) for r in self.db.query(
            "SELECT task_id FROM version_task WHERE version_id = ? AND in_scope = 1",
            (version_id,))}

    def _issues(self, version_id: int) -> List[dict]:
        row = self.db.query("SELECT issues_json FROM plan_validation WHERE version_id = ?",
                            (version_id,))
        if not row:
            return []
        # schema 保证 issues_json 是合法 JSON（CHECK json_valid），无需再兜底
        return json.loads(row[0]["issues_json"])
