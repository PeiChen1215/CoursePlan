"""进度与事件（对应 D06 第 10 章 M-08）。

规则：只追加、幂等、更正指向最新、完成率只看在范围内的必做任务、逾期是派生标记。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence

from ..core.errors import NotFound, StateError, ValidationError
from ..db.uow import Database, UnitOfWork

DONE = "done"
CORRECTION = "correction"
NOTE = "note"
EVENT_TYPES = {DONE, CORRECTION, NOTE}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class SubmitResult:
    event_id: int
    replayed: bool
    completion_rate: float
    overdue: bool


@dataclass(frozen=True)
class Progress:
    total_tasks: int
    done_tasks: int
    completion_rate: float
    planned_minutes: int
    actual_minutes: int
    overdue_tasks: List[int]


class ProgressService:
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config

    # ---------------------------------------------------------------- 归属
    def _require_plan(self, plan_id: int, student_id: int):
        rows = self.db.query("SELECT * FROM study_plan WHERE plan_id = ?", (plan_id,))
        if not rows or int(rows[0]["student_id"]) != int(student_id):
            raise NotFound("E1002", "计划不存在")
        return rows[0]

    def _current_version(self, plan_id: int) -> Optional[int]:
        return self.db.scalar("SELECT current_version FROM study_plan WHERE plan_id = ?",
                              (plan_id,))

    # ---------------------------------------------------------------- 提交事件
    def submit(self, plan_id: int, student_id: int, task_id: int, event_type: str,
               request_key: str, now: datetime, actual_minutes: Optional[int] = None,
               note: Optional[str] = None,
               corrects_event_id: Optional[int] = None) -> SubmitResult:
        plan = self._require_plan(plan_id, student_id)
        if event_type not in EVENT_TYPES:
            raise ValidationError("E1001", "事件类型非法", field="event_type")
        if not request_key:
            raise ValidationError("E1001", "缺少幂等键", field="request_key")
        if actual_minutes is not None and actual_minutes < 0:
            raise ValidationError("E1001", "实际用时不能为负", field="actual_minutes")

        version = int(plan["current_version"] or 0)
        if not version:
            raise StateError("E1003", "计划尚未确认，不能打卡")
        vt = self.db.query("SELECT task_id, in_scope FROM version_task"
                           " WHERE version_id = ? AND task_id = ?", (version, task_id))
        if not vt:
            raise NotFound("E1002", "任务不存在")

        existing = self.db.query("SELECT event_id FROM learning_event"
                                 " WHERE request_key = ?", (request_key,))
        if existing:
            return SubmitResult(int(existing[0]["event_id"]), True,
                                self.completion_rate(plan_id), self._is_overdue(plan, now))

        if event_type == DONE and self._has_done(version, task_id):
            raise StateError("E1003", "该任务已完成，如需改用时请使用更正")
        if event_type == NOTE and corrects_event_id is not None:
            raise ValidationError("E1001", "备注不能指向其他事件", field="corrects_event_id")
        if event_type == CORRECTION:
            self._check_correction(version, task_id, corrects_event_id)

        try:
            with UnitOfWork(self.db) as uow:
                cur = uow.execute(
                    "INSERT INTO learning_event(plan_id,task_id,version_id,event_type,"
                    "actual_minutes,note,operator_id,request_key,corrects_event_id,"
                    "occurred_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (plan_id, task_id, version, event_type, actual_minutes, note,
                     student_id, request_key, corrects_event_id, _iso(now)))
                event_id = int(cur.lastrowid)
        except Exception as exc:  # noqa: BLE001 - 只把唯一约束翻译成业务错误
            text = str(exc)
            if "ux_done_once" in text or "learning_event.task_id" in text:
                raise StateError("E1003", "该任务已经打过卡，不能重复完成",
                                 field="task_id")
            raise

        with UnitOfWork(self.db) as uow:
            uow.execute("UPDATE study_plan SET progress_revision = progress_revision + 1,"
                        " updated_at = ? WHERE plan_id = ?", (_iso(now), plan_id))

        return SubmitResult(event_id, False, self.completion_rate(plan_id),
                            self._is_overdue(plan, now))

    def _has_done(self, version: int, task_id: int) -> bool:
        # 不按版本过滤：同一任务在旧版本打过卡也算完成（schema 的 ux_done_once
        # 按 task_id 唯一，D02 AT-25 要求冻结完成事实）
        return bool(self.db.query(
            "SELECT 1 FROM learning_event WHERE task_id = ?"
            " AND event_type = 'done'", (task_id,)))

    def _latest_completion(self, version: int, task_id: int) -> Optional[int]:
        rows = self.db.query(
            "SELECT event_id FROM learning_event WHERE version_id = ? AND task_id = ?"
            " AND event_type IN ('done','correction') ORDER BY event_id DESC LIMIT 1",
            (version, task_id))
        return int(rows[0]["event_id"]) if rows else None

    def _check_correction(self, version: int, task_id: int,
                          corrects_event_id: Optional[int]) -> None:
        if corrects_event_id is None:
            raise ValidationError("E1001", "更正必须指向被更正的事件",
                                  field="corrects_event_id")
        prev = self.db.query("SELECT * FROM learning_event WHERE event_id = ?",
                             (corrects_event_id,))
        if not prev:
            raise ValidationError("E1001", "被更正的事件不存在", field="corrects_event_id")
        prev = prev[0]
        if int(prev["task_id"]) != int(task_id) or int(prev["version_id"]) != int(version):
            raise ValidationError("E1001", "更正必须指向同一任务的事件",
                                  field="corrects_event_id")
        if prev["event_type"] == NOTE:
            raise ValidationError("E1001", "备注事件不能被更正", field="corrects_event_id")
        if int(prev["event_id"]) != self._latest_completion(version, task_id):
            raise StateError("E1003", "只能更正最新一次完成记录")

    # ---------------------------------------------------------------- 派生量
    def completion_rate(self, plan_id: int) -> float:
        version = self._current_version(plan_id)
        if not version:
            return 0.0
        total = self.db.scalar(
            "SELECT COUNT(*) FROM version_task WHERE version_id = ? AND in_scope = 1",
            (version,)) or 0
        if not total:
            return 0.0
        done = self.db.scalar(
            "SELECT COUNT(DISTINCT task_id) FROM learning_event"
            " WHERE version_id = ? AND event_type = 'done'", (version,)) or 0
        return round(done / total, 3)

    def effective_minutes(self, plan_id: int, task_id: int) -> Optional[int]:
        version = self._current_version(plan_id)
        if not version:
            return None
        rows = self.db.query(
            "SELECT actual_minutes FROM learning_event WHERE version_id = ? AND task_id = ?"
            " AND event_type IN ('done','correction') ORDER BY event_id DESC LIMIT 1",
            (version, task_id))
        if rows and rows[0]["actual_minutes"] is not None:
            return int(rows[0]["actual_minutes"])
        planned = self.db.scalar(
            "SELECT estimated_minutes FROM version_task WHERE version_id = ? AND task_id = ?",
            (version, task_id))
        return int(planned) if planned is not None else None

    def _is_overdue(self, plan, now: datetime) -> bool:
        version = int(plan["current_version"] or 0)
        if not version:
            return False
        rows = self.db.query(
            "SELECT vt.task_id, MIN(ts.end_epoch) AS last_end FROM version_task vt"
            " JOIN task_slice ts ON ts.version_id = vt.version_id"
            "  AND ts.task_id = vt.task_id"
            " WHERE vt.version_id = ? AND vt.in_scope = 1"
            " GROUP BY vt.task_id", (version,))
        done = {int(r["task_id"]) for r in self.db.query(
            "SELECT DISTINCT task_id FROM learning_event"
            " WHERE version_id = ? AND event_type = 'done'", (version,))}
        now_epoch = int(now.timestamp())
        return any(now_epoch > int(r["last_end"]) and int(r["task_id"]) not in done
                   for r in rows)

    def progress(self, plan_id: int, student_id: int, now: datetime) -> Progress:
        self._require_plan(plan_id, student_id)
        version = self._current_version(plan_id)
        if not version:
            return Progress(0, 0, 0.0, 0, 0, [])
        total = self.db.scalar(
            "SELECT COUNT(*) FROM version_task WHERE version_id = ? AND in_scope = 1",
            (version,)) or 0
        rows = self.db.query(
            "SELECT task_id, estimated_minutes FROM version_task"
            " WHERE version_id = ? AND in_scope = 1", (version,))
        done = {int(r["task_id"]) for r in self.db.query(
            "SELECT DISTINCT task_id FROM learning_event"
            " WHERE version_id = ? AND event_type = 'done'", (version,))}
        planned = sum(int(r["estimated_minutes"]) for r in rows)
        actual = 0
        for r in rows:
            m = self.effective_minutes(plan_id, int(r["task_id"]))
            if int(r["task_id"]) in done and m:
                actual += m
        overdue = self._overdue_tasks(version, now, done)
        return Progress(int(total), len(done), round(len(done) / total, 3) if total else 0.0,
                        planned, actual, overdue)

    def _overdue_tasks(self, version: int, now: datetime, done: set) -> List[int]:
        rows = self.db.query(
            "SELECT vt.task_id, MIN(ts.end_epoch) AS last_end FROM version_task vt"
            " JOIN task_slice ts ON ts.version_id = vt.version_id"
            "  AND ts.task_id = vt.task_id"
            " WHERE vt.version_id = ? AND vt.in_scope = 1 GROUP BY vt.task_id",
            (version,))
        now_epoch = int(now.timestamp())
        return sorted(int(r["task_id"]) for r in rows
                      if now_epoch > int(r["last_end"]) and int(r["task_id"]) not in done)
