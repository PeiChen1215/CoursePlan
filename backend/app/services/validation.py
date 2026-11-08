"""计划校验（对应 D06 第 8 章 M-06）。

五项检查固定顺序，遇 ERROR 即停；WARN/INFO 累积后仍可确认。
纯函数：只读草案、约束与内容，不改任何数据。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .capacity import Interval, as_naive_utc
from .planner import Concept, Slice, Task

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"

SLOT_INVALID = "SLOT_INVALID"
CAP_EXCEEDED = "CAP_EXCEEDED"
TIME_OVERLAP = "TIME_OVERLAP"
PREREQ_VIOLATED = "PREREQ_VIOLATED"
DEADLINE_UNREACHABLE = "DEADLINE_UNREACHABLE"
CAP_TIGHT = "CAP_TIGHT"
ISOLATED_CONCEPT = "ISOLATED_CONCEPT"

SUGGESTIONS = {
    CAP_EXCEEDED: "延后截止日期、减少附加目标，或增加每周可用时段",
    TIME_OVERLAP: "重新生成草案（手工改时长也可能导致重叠）",
    PREREQ_VIOLATED: "检查先修关系是否正确，或重新生成草案",
    DEADLINE_UNREACHABLE: "延后截止日期或减少目标",
    SLOT_INVALID: "检查排除日期与可用时间是否覆盖了该时段",
    CAP_TIGHT: "余量不足 20%，建议预留一两天缓冲",
    ISOLATED_CONCEPT: "该知识点既无先修也无后继，确认是否遗漏关联",
}


@dataclass(frozen=True)
class Issue:
    code: str
    level: str
    message: str
    concept_id: Optional[int] = None
    kind: Optional[str] = None
    detail: Optional[dict] = None

    def as_dict(self) -> dict:
        return {"code": self.code, "level": self.level, "message": self.message,
                "concept_id": self.concept_id, "kind": self.kind,
                "suggestion": SUGGESTIONS.get(self.code, ""), "detail": self.detail}


@dataclass(frozen=True)
class Report:
    passed: bool
    issues: List[Issue]
    metrics: dict

    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.level == ERROR]


def _slot_end(deadline: date) -> datetime:
    return datetime.combine(deadline, time(23, 59, 59))


# ---------------------------------------------------------------- 五项检查
def check_slots(slices: Sequence[Slice], slots: Sequence[Interval],
                max_slice_minutes: int) -> List[Issue]:
    issues: List[Issue] = []
    for s in slices:
        if s.minutes <= 0:
            issues.append(Issue(SLOT_INVALID, ERROR, "时间片长度非正", s.concept_id, s.kind,
                                {"slice_no": s.slice_no}))
            continue
        if s.minutes > max_slice_minutes:
            issues.append(Issue(SLOT_INVALID, ERROR, "时间片超过单片上限", s.concept_id,
                                s.kind, {"slice_no": s.slice_no, "minutes": s.minutes}))
            continue
        if not any(slot.start <= s.start and s.end <= slot.end for slot in slots):
            issues.append(Issue(SLOT_INVALID, ERROR, "时间片不在可用时段内", s.concept_id,
                                s.kind, {"slice_no": s.slice_no,
                                         "start": s.start.isoformat()}))
    return issues


def check_capacity(tasks: Sequence[Task], usable_minutes: int) -> List[Issue]:
    total = sum(t.minutes for t in tasks)
    if total > usable_minutes:
        return [Issue(CAP_EXCEEDED, ERROR,
                      "任务总时长 %d 分钟超过可排容量 %d 分钟" % (total, usable_minutes),
                      detail={"total": total, "usable": usable_minutes,
                              "deficit": total - usable_minutes})]
    return []


def check_overlap(slices: Sequence[Slice]) -> List[Issue]:
    ordered = sorted(slices, key=lambda s: (s.start, s.end))
    issues: List[Issue] = []
    for a, b in zip(ordered, ordered[1:]):
        if a.start < b.end and b.start < a.end:
            issues.append(Issue(
                TIME_OVERLAP, ERROR, "时间片重叠",
                detail={"a": {"concept_id": a.concept_id, "kind": a.kind,
                              "slice_no": a.slice_no, "start": a.start.isoformat(),
                              "end": a.end.isoformat()},
                        "b": {"concept_id": b.concept_id, "kind": b.kind,
                              "slice_no": b.slice_no, "start": b.start.isoformat(),
                              "end": b.end.isoformat()}}))
    return issues


def check_prereq(tasks: Sequence[Task], slices: Sequence[Slice],
                 edges: Iterable[Tuple[int, int]]) -> List[Issue]:
    issues: List[Issue] = []
    first_start: Dict[Tuple[int, str], datetime] = {}
    last_end: Dict[Tuple[int, str], datetime] = {}
    for s in slices:
        key = (s.concept_id, s.kind)
        first_start[key] = min(first_start.get(key, s.start), s.start)
        last_end[key] = max(last_end.get(key, s.end), s.end)

    for u, v in edges:
        u_ends = [last_end[k] for k in last_end if k[0] == u]
        v_starts = [first_start[k] for k in first_start if k[0] == v]
        if u_ends and v_starts and max(u_ends) > min(v_starts):
            issues.append(Issue(PREREQ_VIOLATED, ERROR,
                                "先修知识点排在后继之后",
                                detail={"from": u, "to": v,
                                        "from_end": max(u_ends).isoformat(),
                                        "to_start": min(v_starts).isoformat()}))

    # 同一知识点内：学习先于练习
    for cid in {k[0] for k in first_start}:
        study = first_start.get((cid, "study"))
        practice = last_end.get((cid, "practice"))
        if study and practice:
            p_first = first_start.get((cid, "practice"))
            s_last = last_end.get((cid, "study"))
            if p_first and s_last and p_first < s_last:
                issues.append(Issue(PREREQ_VIOLATED, ERROR,
                                    "练习排在对应学习之前", cid, "practice",
                                    {"practice_start": p_first.isoformat(),
                                     "study_end": s_last.isoformat()}))
    return issues


def check_deadline(slices: Sequence[Slice], deadline: date) -> List[Issue]:
    if not slices:
        return []
    end = _slot_end(deadline)
    late = [s for s in slices if s.end > end]
    if late:
        return [Issue(DEADLINE_UNREACHABLE, ERROR, "存在超出截止日期的时间片",
                      detail={"deadline": deadline.isoformat(),
                              "last_end": max(s.end for s in slices).isoformat()})]
    return []


def check_tight(tasks: Sequence[Task], raw_minutes: int,
                threshold: float) -> List[Issue]:
    if raw_minutes <= 0:
        return []
    total = sum(t.minutes for t in tasks)
    ratio = total / raw_minutes
    if ratio > threshold:
        return [Issue(CAP_TIGHT, WARN,
                      "任务量占原始容量的 %.0f%%，余量偏紧" % (ratio * 100),
                      detail={"ratio": round(ratio, 4), "threshold": threshold})]
    return []


def check_isolated(concepts: Sequence[Concept], edges: Iterable[Tuple[int, int]],
                   selected: Set[int]) -> List[Issue]:
    linked = {u for u, _ in edges} | {v for _, v in edges}
    issues = []
    for c in concepts:
        if c.concept_id in selected and c.concept_id not in linked:
            issues.append(Issue(ISOLATED_CONCEPT, INFO, "知识点既不前置也不后继",
                                c.concept_id))
    return issues


# ---------------------------------------------------------------- 汇总
def validate(tasks: Sequence[Task], slices: Sequence[Slice],
             slots: Sequence[Interval], usable_minutes: int, raw_minutes: int,
             deadline: date, edges: Iterable[Tuple[int, int]],
             concepts: Sequence[Concept], selected: Set[int],
             config) -> Report:
    edges = list(edges)
    metrics = {
        "T": sum(t.minutes for t in tasks),
        "C": raw_minutes,
        "C_prime": usable_minutes,
        "slices": len(slices),
        "scheduled": sum(s.minutes for s in slices),
        "U": round(sum(t.minutes for t in tasks) / raw_minutes, 4) if raw_minutes else 0.0,
    }

    checks = [
        ("slots", lambda: check_slots(slices, slots, config.MAX_SLICE_SECONDS // 60)),
        ("capacity", lambda: check_capacity(tasks, usable_minutes)),
        ("overlap", lambda: check_overlap(slices)),
        ("prereq", lambda: check_prereq(tasks, slices, edges)),
        ("deadline", lambda: check_deadline(slices, deadline)),
    ]
    issues: List[Issue] = []
    for _, fn in checks:
        found = fn()
        if any(i.level == ERROR for i in found):
            issues.extend(found)
            return Report(passed=False, issues=issues, metrics=metrics)
        issues.extend(found)

    issues.extend(check_tight(tasks, raw_minutes, config.CAP_TIGHT_THRESHOLD))
    issues.extend(check_isolated(concepts, edges, selected))
    return Report(passed=True, issues=issues, metrics=metrics)
