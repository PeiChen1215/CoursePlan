"""确认与版本（对应 D06 第 9 章 M-07）。

事务顺序：取写锁 → 幂等检查 → 四项基线复核 → 写版本与子项 → 切指针 → 标草案已消费 → 提交。
任一步失败整体回滚，不产生半截版本。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ..core.errors import NotFound, StateError, ValidationError, VersionConflict
from ..db.uow import Database, UnitOfWork
from .capacity import Interval, expand_slots, normalize_availability, normalize_dates
from .planner import Concept, Slice, Task
from . import graph
from .validation import validate

ENGINE_VERSION = "0.1.0"


def _now_iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch_seconds(dt: datetime) -> int:
    """schema 约定：start/end_epoch 为秒，且必须被 60 整除（整分钟）。"""
    return int(dt.timestamp())


@dataclass(frozen=True)
class ConfirmResult:
    plan_id: int
    version_no: int
    version_id: int
    replayed: bool
    diff: Optional[dict]
    metrics: dict


@dataclass(frozen=True)
class VersionView:
    version_no: int
    version_id: int
    change_reason: str
    change_note: str
    created_at: str
    input_hash: str
    tasks: int
    slices: int


class VersionService:
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config

    # ---------------------------------------------------------------- 确认
    def confirm(self, plan_id: int, revision: int, confirm_key: str,
                actor_id: int, now: datetime,
                change_reason: Optional[str] = None,
                change_note: Optional[str] = None) -> ConfirmResult:
        if not confirm_key:
            raise ValidationError("E1001", "缺少幂等键", field="confirm_key")

        with UnitOfWork(self.db) as uow:
            draft = uow.fetch_one(
                "SELECT * FROM plan_draft WHERE plan_id = ? AND revision = ?",
                (plan_id, revision))
            plan = uow.fetch_one("SELECT * FROM study_plan WHERE plan_id = ?", (plan_id,))
            if draft is None or plan is None:
                raise NotFound("E1002", "草案不存在")
            if int(plan["student_id"]) != int(actor_id):
                raise NotFound("E1002", "草案不存在")     # 不泄露他人计划存在性

            if draft["confirm_key"] and draft["confirm_key"] == confirm_key \
                    and draft["result_version_id"]:
                version = uow.fetch_one("SELECT version_no, version_id FROM plan_version"
                                        " WHERE version_id = ?",
                                        (draft["result_version_id"],))
                return ConfirmResult(plan_id, int(version["version_no"]),
                                     int(version["version_id"]), True, None, {})

            if draft["status"] == "consumed":
                raise StateError("E1003", "草案已确认，不能重复提交")

            self._assert_baseline(uow, plan, draft)

            payload = json.loads(draft["payload_json"])
            report = self._revalidate(uow, plan, payload)
            if not report.passed:
                raise StateError("E1003", "草案未通过校验，不能确认", detail={
                    "issues": [i.as_dict() for i in report.errors()]})

            version_id = self._write_version(uow, plan, draft, payload, report.metrics,
                                             actor_id, now,
                                             [i.as_dict() for i in report.issues],
                                             change_reason, change_note)
            prev_no = int(plan["current_version"] or 0)
            version_no = int(uow.fetch_one("SELECT version_no FROM plan_version"
                                           " WHERE version_id = ?", (version_id,))["version_no"])

            uow.execute("UPDATE study_plan SET current_version = ?, status = 'active',"
                        " updated_at = ? WHERE plan_id = ?",
                        (version_no, _now_iso(now), plan_id))
            uow.execute("UPDATE plan_draft SET status = 'consumed', confirm_key = ?,"
                        " result_version_id = ?, updated_at = ?"
                        " WHERE draft_id = ?",
                        (confirm_key, version_id, _now_iso(now), draft["draft_id"]))

            diff = None
            if prev_no:
                prev_id = uow.fetch_one("SELECT version_id FROM plan_version"
                                        " WHERE plan_id = ? AND version_no = ?",
                                        (plan_id, prev_no))["version_id"]
                diff = self._diff_within(uow, int(prev_id), version_id)

            return ConfirmResult(plan_id, version_no, version_id, False, diff,
                                 report.metrics)

    def _assert_baseline(self, uow, plan, draft) -> None:
        course_rev = uow.fetch_one("SELECT content_revision FROM course WHERE course_id = ?",
                                   (plan["course_id"],))
        conflicts = []
        if int(plan["progress_revision"]) != int(draft["base_progress_revision"]):
            conflicts.append("progress_revision")
        if int(plan["current_version"] or 0) != int(draft["base_version"] or 0):
            conflicts.append("current_version")
        if int(course_rev["content_revision"]) != int(draft["course_revision"]):
            conflicts.append("content_revision")
        if conflicts:
            raise VersionConflict("E2004", "计划或课程内容已变化，请重新生成",
                                  detail={"conflicts": conflicts})

    def _revalidate(self, uow, plan, payload: dict):
        course_id = int(plan["course_id"])
        cons = uow.fetch_one("SELECT * FROM plan_constraint WHERE plan_id = ?",
                             (plan["plan_id"],))
        concepts = [Concept(int(r["concept_id"]), r["name"], r["chapter"],
                            int(r["sort_order"]), int(r["reference_minutes"]), r["status"])
                    for r in graph.load_concepts(self.db, course_id, only_enabled=False)]
        by_id = {c.concept_id: c for c in concepts}
        edges = graph.load_edges(self.db, course_id)

        tasks = [Task(t["concept_id"], t["kind"], t["minutes"])
                 for t in payload["tasks"]]
        slices = [Slice(s["concept_id"], s["kind"], s["slice_no"],
                        datetime.strptime(s["start"], "%Y-%m-%dT%H:%M"),
                        datetime.strptime(s["end"], "%Y-%m-%dT%H:%M"))
                  for s in payload["slices"]]
        availability = normalize_availability(json.loads(cons["availability_json"]))
        excluded = normalize_dates(json.loads(cons["excluded_dates_json"]))
        deadline = datetime.strptime(cons["deadline"], "%Y-%m-%d").date()
        base_time = datetime.strptime(payload["base_time"], "%Y-%m-%dT%H:%M:%SZ")
        slots = expand_slots(availability, excluded, base_time, deadline)

        raw = sum(s.minutes for s in slots)
        import math
        buffer = math.ceil(self.config.BUFFER_RATIO * raw)
        selected = {c.concept_id for c in concepts if c.concept_id in set(payload["order"])}
        return validate(tasks, slices, slots, raw - buffer, raw, deadline, edges,
                        [by_id[cid] for cid in selected if cid in by_id], selected,
                        self.config)

    # ---------------------------------------------------------------- 写版本
    def _write_version(self, uow, plan, draft, payload: dict, metrics: dict,
                       actor_id: int, now: datetime,
                       issues: Optional[List[dict]] = None,
                       change_reason: Optional[str] = None,
                       change_note: Optional[str] = None) -> int:
        plan_id = int(plan["plan_id"])
        course_id = int(plan["course_id"])
        stamp = _now_iso(now)

        task_ids: Dict[Tuple[int, str], int] = {}
        for t in payload["tasks"]:
            existing = uow.fetch_one(
                "SELECT task_id FROM plan_task WHERE plan_id = ? AND concept_id = ?"
                " AND task_type = ?", (plan_id, t["concept_id"], t["kind"]))
            if existing:
                task_ids[(t["concept_id"], t["kind"])] = int(existing["task_id"])
            else:
                cur = uow.execute(
                    "INSERT INTO plan_task(plan_id,course_id,concept_id,task_type,created_at)"
                    " VALUES(?,?,?,?,?)",
                    (plan_id, course_id, t["concept_id"], t["kind"], stamp))
                task_ids[(t["concept_id"], t["kind"])] = int(cur.lastrowid)

        version_no = int(uow.fetch_one(
            "SELECT COALESCE(MAX(version_no), 0) + 1 AS n FROM plan_version"
            " WHERE plan_id = ?", (plan_id,))["n"])
        allowed = {"initial", "delay", "goal_change", "availability_change",
                   "duration_change", "manual"}
        first = int(plan["current_version"] or 0) == 0
        if first:
            reason = "initial"
        elif change_reason in allowed - {"initial"}:
            reason = change_reason
        else:
            reason = "manual"
        note = (change_note or ("首次确认" if first else "第 %d 次调整确认" % version_no))[:500]

        cur = uow.execute(
            "INSERT INTO plan_version(plan_id,version_no,change_reason,change_note,"
            "snapshot_json,input_hash,engine_version,operator_id,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (plan_id, version_no, reason, note,
             json.dumps(payload, ensure_ascii=False, sort_keys=True),
             payload.get("input_hash") or ("0" * 64), ENGINE_VERSION, actor_id, stamp))
        version_id = int(cur.lastrowid)

        scheduled = {(s["concept_id"], s["kind"]) for s in payload["slices"]}
        for t in payload["tasks"]:
            tid = task_ids[(t["concept_id"], t["kind"])]
            state = "scheduled" if (t["concept_id"], t["kind"]) in scheduled else "unscheduled"
            uow.execute(
                "INSERT INTO version_task(version_id,task_id,plan_id,in_scope,frozen,"
                "original_minutes,estimated_minutes,schedule_state)"
                " VALUES(?,?,?,1,0,?,?,?)",
                (version_id, tid, plan_id, t["minutes"], t["minutes"], state))

        for s in payload["slices"]:
            tid = task_ids[(s["concept_id"], s["kind"])]
            start = datetime.strptime(s["start"], "%Y-%m-%dT%H:%M")
            end = datetime.strptime(s["end"], "%Y-%m-%dT%H:%M")
            uow.execute(
                "INSERT INTO task_slice(version_id,task_id,slice_no,start_epoch,end_epoch)"
                " VALUES(?,?,?,?,?)",
                (version_id, tid, s["slice_no"], _epoch_seconds(start), _epoch_seconds(end)))

        uow.execute(
            "INSERT INTO plan_validation(version_id,passed,issues_json,metrics_json)"
            " VALUES(?,1,?,?)",
            (version_id, json.dumps(issues or [], ensure_ascii=False),
             json.dumps(metrics, ensure_ascii=False)))
        return version_id

    # ---------------------------------------------------------------- 差异
    def _diff_within(self, uow, old_version_id: int, new_version_id: int) -> dict:
        def load(vid):
            rows = uow.fetch_all(
                "SELECT vt.task_id, vt.estimated_minutes,"
                " (SELECT MIN(ts.start_epoch) FROM task_slice ts"
                "  WHERE ts.version_id = vt.version_id AND ts.task_id = vt.task_id) AS first_start"
                " FROM version_task vt WHERE vt.version_id = ?", (vid,))
            return {int(r["task_id"]): r for r in rows}

        old, new = load(old_version_id), load(new_version_id)
        added = [t for t in new if t not in old]
        removed = [t for t in old if t not in new]
        moved, resized = [], []
        for tid in new.keys() & old.keys():
            o, n = old[tid], new[tid]
            o_day = (o["first_start"] or 0) // 86400
            n_day = (n["first_start"] or 0) // 86400
            if o_day != n_day:
                moved.append(tid)
            if int(o["estimated_minutes"]) != int(n["estimated_minutes"]):
                resized.append(tid)
        return {"added": sorted(added), "removed": sorted(removed),
                "moved": sorted(moved), "resized": sorted(resized)}

    # ---------------------------------------------------------------- 查询
    def list_versions(self, plan_id: int, student_id: int) -> List[VersionView]:
        plan = self.db.query("SELECT student_id FROM study_plan WHERE plan_id = ?",
                             (plan_id,))
        if not plan or int(plan[0]["student_id"]) != int(student_id):
            raise NotFound("E1002", "计划不存在")
        rows = self.db.query(
            "SELECT v.version_id, v.version_no, v.change_reason, v.change_note,"
            " v.created_at, v.input_hash,"
            " (SELECT COUNT(*) FROM version_task vt WHERE vt.version_id = v.version_id) AS tasks,"
            " (SELECT COUNT(*) FROM task_slice ts WHERE ts.version_id = v.version_id) AS slices"
            " FROM plan_version v WHERE v.plan_id = ? ORDER BY v.version_no", (plan_id,))
        return [VersionView(int(r["version_no"]), int(r["version_id"]), r["change_reason"],
                            r["change_note"], r["created_at"], r["input_hash"],
                            int(r["tasks"]), int(r["slices"])) for r in rows]

    def diff(self, plan_id: int, student_id: int, from_no: int, to_no: int) -> dict:
        plan = self.db.query("SELECT student_id FROM study_plan WHERE plan_id = ?",
                             (plan_id,))
        if not plan or int(plan[0]["student_id"]) != int(student_id):
            raise NotFound("E1002", "计划不存在")
        rows = self.db.query("SELECT version_no, version_id FROM plan_version"
                             " WHERE plan_id = ? AND version_no IN (?, ?)",
                             (plan_id, from_no, to_no))
        found = {int(r["version_no"]): int(r["version_id"]) for r in rows}
        if len(found) != 2:
            raise NotFound("E1002", "版本不存在")
        with UnitOfWork(self.db) as uow:
            return self._diff_within(uow, found[from_no], found[to_no])
