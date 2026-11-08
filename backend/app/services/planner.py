"""分解与排程（对应 D06 第 7 章 M-05）。

流水线：A2 闭包 → A3 7:3 拆分 → A4 稳定拓扑排序 → A5 装箱 → A6 拆片。
纯函数为主，编排函数只负责取数、调用与汇总指标。
"""
from __future__ import annotations

import hashlib
import heapq
import json
from fractions import Fraction
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ..core.errors import NotFound, PrereqCycle, StateError
from ..db.uow import Database, UnitOfWork
from . import graph
from .capacity import (Interval, as_naive_utc, compute_capacity, expand_slots,
                       normalize_availability, normalize_dates)

STUDY = "study"
PRACTICE = "practice"

CAPACITY_REASON = "CAPACITY"
TOO_MANY_SLICES = "TOO_MANY_SLICES"


@dataclass(frozen=True)
class Concept:
    concept_id: int
    name: str
    chapter: str
    sort_order: int
    reference_minutes: int
    status: str = "enabled"

    @property
    def key(self) -> Tuple[str, int, int]:
        return (self.chapter, self.sort_order, self.concept_id)


@dataclass(frozen=True)
class Task:
    concept_id: int
    kind: str
    minutes: int

    @property
    def task_no(self) -> str:
        return "C%d-%s" % (self.concept_id, self.kind)


@dataclass(frozen=True)
class Slice:
    concept_id: int
    kind: str
    slice_no: int
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True)
class Unscheduled:
    concept_id: int
    kind: str
    reason: str

    @property
    def task_no(self) -> str:
        return "C%d-%s" % (self.concept_id, self.kind)


@dataclass(frozen=True)
class Metrics:
    total_minutes: int      # T
    raw_minutes: int        # C
    buffer_minutes: int     # B
    usable_minutes: int     # C′
    deficit_minutes: int    # D
    utilization: float      # U
    scheduled_minutes: int
    slices: int


# ---------------------------------------------------------------- A3 拆分
def split_tasks(concepts: Iterable[Concept], mastered: Set[int], config) -> List[Task]:
    tasks: List[Task] = []
    for c in sorted(concepts, key=lambda x: x.key):
        if c.concept_id in mastered or c.status != "enabled":
            continue
        total = c.reference_minutes
        # 用分数运算：int(total * 0.7) 在 total=90 时会得到 62（0.7 的二进制误差）
        study = int(Fraction(total) * Fraction(str(config.STUDY_RATIO)))
        practice = total - study
        if practice < config.MIN_TASK_MINUTES:
            study, practice = total, 0
        tasks.append(Task(c.concept_id, STUDY, study))
        if practice:
            tasks.append(Task(c.concept_id, PRACTICE, practice))
    return tasks


# ---------------------------------------------------------------- A4 排序
def topo_order_concepts(concepts: Sequence[Concept],
                        edges: Iterable[Tuple[int, int]]) -> List[int]:
    by_id = {c.concept_id: c for c in concepts}
    indeg: Dict[int, int] = {c.concept_id: 0 for c in concepts}
    adj: Dict[int, List[int]] = {c.concept_id: [] for c in concepts}
    for u, v in edges:
        if u in by_id and v in by_id:
            adj[u].append(v)
            indeg[v] += 1

    heap = [(by_id[cid].key, cid) for cid, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    order: List[int] = []
    while heap:
        _, cid = heapq.heappop(heap)
        order.append(cid)
        for nxt in adj[cid]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                heapq.heappush(heap, (by_id[nxt].key, nxt))
    if len(order) != len(by_id):
        from .content import detect_cycle
        raise PrereqCycle("E2001", "先修关系成环",
                          detail={"cycle": detect_cycle(list(edges), list(by_id))})
    return order


# ---------------------------------------------------------------- A5+A6 装箱与拆片
def pack(tasks: Sequence[Task], intervals: Sequence[Interval],
         config) -> Tuple[List[Slice], List[Unscheduled]]:
    """逐任务填充时段；跨段切分，单片不超过 MAX_SLICE_SECONDS。"""
    pool = [[i.start, i.end] for i in intervals]
    cur = 0
    slices: List[Slice] = []
    unscheduled: List[Unscheduled] = []
    max_slice = config.MAX_SLICE_SECONDS // 60

    for task in tasks:
        need = task.minutes
        pieces: List[Tuple[datetime, datetime]] = []
        blocked = False
        while need > 0:
            if cur >= len(pool):
                unscheduled.append(Unscheduled(task.concept_id, task.kind, CAPACITY_REASON))
                blocked = True
                break
            lo, hi = pool[cur]
            avail = int((hi - lo).total_seconds() // 60)
            if avail < config.MIN_TASK_MINUTES:
                if avail > 0:
                    # 不足一分钟的残段直接丢弃，避免产生 0 分钟片
                    pool[cur][1] = lo
                cur += 1
                continue
            take = min(need, avail, max_slice)
            start = lo
            end = start + timedelta(minutes=take)
            pieces.append((start, end))
            pool[cur][0] = end
            need -= take
        if blocked:
            continue
        if len(pieces) > config.MAX_SLICES_PER_TASK:
            unscheduled.append(Unscheduled(task.concept_id, task.kind, TOO_MANY_SLICES))
            continue
        for idx, (start, end) in enumerate(pieces, start=1):
            slices.append(Slice(task.concept_id, task.kind, idx, start, end))
    return slices, unscheduled


# ---------------------------------------------------------------- 指标
def metrics_of(tasks: Sequence[Task], slices: Sequence[Slice],
               raw: int, buffer: int, usable: int) -> Metrics:
    total = sum(t.minutes for t in tasks)
    scheduled = sum(s.minutes for s in slices)
    deficit = max(0, total - usable)
    util = round(total / raw, 4) if raw else 0.0
    return Metrics(total_minutes=total, raw_minutes=raw, buffer_minutes=buffer,
                   usable_minutes=usable, deficit_minutes=deficit,
                   utilization=util, scheduled_minutes=scheduled, slices=len(slices))


def input_hash(payload: dict) -> str:
    """规范化摘要：键排序、UTF-8，用于判断输入是否真的变了。"""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 编排
@dataclass
class Draft:
    plan_id: int
    revision: int
    tasks: List[Task]
    slices: List[Slice]
    unscheduled: List[Unscheduled]
    metrics: Metrics
    goals: List[int]
    order: List[int]
    hash: str
    base_time: datetime
    deadline: str


class PlannerService:
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config

    def generate(self, plan_id: int, student_id: int,
                 base_time: datetime) -> Draft:
        rows = self.db.query(
            "SELECT p.plan_id, p.student_id, p.course_id, p.status,"
            " c.constraint_id, c.target_concept_id, c.extra_concept_ids_json,"
            " c.deadline, c.availability_json, c.excluded_dates_json,"
            " c.mastered_concept_ids_json"
            " FROM study_plan p LEFT JOIN plan_constraint c ON c.plan_id = p.plan_id"
            " WHERE p.plan_id = ?", (plan_id,))
        if not rows or int(rows[0]["student_id"]) != int(student_id):
            raise NotFound("E1002", "计划不存在")
        row = rows[0]
        if row["constraint_id"] is None:
            raise StateError("E1003", "请先填写学习约束")

        course_id = int(row["course_id"])
        target = int(row["target_concept_id"])
        extras = json.loads(row["extra_concept_ids_json"])
        mastered = {int(x) for x in json.loads(row["mastered_concept_ids_json"])}
        deadline = datetime.strptime(row["deadline"], "%Y-%m-%d").date()

        concepts = [Concept(int(r["concept_id"]), r["name"], r["chapter"],
                            int(r["sort_order"]), int(r["reference_minutes"]),
                            r["status"])
                    for r in graph.load_concepts(self.db, course_id, only_enabled=False)]
        edges = graph.load_edges(self.db, course_id)

        goals = [target] + [int(x) for x in extras]
        closure = graph.prereq_closure(edges, goals)
        selected = [c for c in concepts if c.concept_id in closure]
        order = topo_order_concepts(selected, edges)
        ordered_concepts = [next(c for c in selected if c.concept_id == cid)
                            for cid in order]
        tasks = split_tasks(ordered_concepts, mastered, self.config)
        if not tasks:
            raise StateError("E1003", "目标已全部掌握，没有需要排的任务")

        availability = normalize_availability(json.loads(row["availability_json"]))
        excluded = normalize_dates(json.loads(row["excluded_dates_json"]))
        slots = expand_slots(availability, excluded, base_time, deadline)
        cap = compute_capacity(slots, self.config.BUFFER_RATIO)
        if cap.raw_minutes <= 0:
            raise StateError("E1003", "容量为零，无法排程")

        slices, unscheduled = pack(tasks, slots, self.config)
        metrics = metrics_of(tasks, slices, cap.raw_minutes, cap.buffer_minutes,
                             cap.usable_minutes)

        payload = {
            "plan_id": plan_id,
            "base_time": as_naive_utc(base_time).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "deadline": deadline.isoformat(),
            "goals": goals,
            "order": order,
            "tasks": [{"concept_id": t.concept_id, "kind": t.kind, "minutes": t.minutes}
                      for t in tasks],
            "slices": [{"concept_id": s.concept_id, "kind": s.kind,
                        "slice_no": s.slice_no,
                        "start": s.start.strftime("%Y-%m-%dT%H:%M"),
                        "end": s.end.strftime("%Y-%m-%dT%H:%M")} for s in slices],
            "unscheduled": [{"concept_id": u.concept_id, "kind": u.kind,
                             "reason": u.reason} for u in unscheduled],
        }
        digest = input_hash(payload)

        revision = self._next_revision(plan_id)
        self._save_draft(plan_id, revision, payload, digest)
        return Draft(plan_id=plan_id, revision=revision, tasks=tasks, slices=slices,
                     unscheduled=unscheduled, metrics=metrics, goals=goals, order=order,
                     hash=digest, base_time=base_time,
                     deadline=deadline.isoformat())

    def _next_revision(self, plan_id: int) -> int:
        value = self.db.scalar("SELECT COALESCE(MAX(revision), 0) FROM plan_draft"
                               " WHERE plan_id = ?", (plan_id,))
        return int(value or 0) + 1

    def _save_draft(self, plan_id: int, revision: int, payload: dict,
                    digest: str) -> None:
        row = self.db.query("SELECT course_id, progress_revision FROM study_plan"
                            " WHERE plan_id = ?", (plan_id,))[0]
        course_rev = self.db.scalar("SELECT content_revision FROM course"
                                    " WHERE course_id = ?", (row["course_id"],)) or 0
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = "ready" if payload["unscheduled"] == [] else "invalid"
        with UnitOfWork(self.db) as uow:
            uow.execute(
                "INSERT INTO plan_draft(plan_id,revision,base_progress_revision,"
                "course_revision,payload_json,status,updated_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (plan_id, revision, int(row["progress_revision"]), int(course_rev),
                 json.dumps(payload, ensure_ascii=False), status, now))
