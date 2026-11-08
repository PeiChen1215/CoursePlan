"""可用时段展开与容量计算（对应 D06 第 5 章 M-03 §5.6）。

区间约定：[base_time, 截止日 23:59:59]，与 D06 表 5.6 的「排除日期含截止日」用例一致。
公式：C = Σ⌊段长(分钟)⌋，B = ⌈BUFFER_RATIO × C⌉，C′ = C − B。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..core.errors import ValidationError

WEEKDAY_ALIASES = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}
MAX_SEGMENTS_PER_DAY = 3
MAX_DAILY_MINUTES = 8 * 60
MAX_EXCLUDED_DATES = 30
MIN_DEADLINE_DAYS = 1
MAX_DEADLINE_DAYS_CAP = 180

EMPTY_AVAILABILITY = "EMPTY_AVAILABILITY"
ALL_EXCLUDED = "ALL_EXCLUDED"
NOTHING_TO_PLAN = "NOTHING_TO_PLAN"


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True)
class Capacity:
    raw_minutes: int      # C
    buffer_minutes: int   # B
    usable_minutes: int   # C′
    slots: int


# ---------------------------------------------------------------- 解析
def parse_time(text: str) -> time:
    try:
        hh, mm = text.split(":")
        return time(int(hh), int(mm))
    except (ValueError, AttributeError):
        raise ValidationError("E1001", "时间格式应为 HH:MM", field="availability")


def normalize_availability(raw: Dict[str, Sequence[Sequence[str]]]) -> Dict[int, List[Tuple[time, time]]]:
    """把 {"mon": [["19:00","21:00"]]} 规范化为 {0: [(19:00,21:00)]}，并做边界校验。"""
    if raw is None:
        raise ValidationError("E1001", "缺少可用时间", field="availability")
    if isinstance(raw, list):
        raw = {str(i): v for i, v in enumerate(raw)}

    result: Dict[int, List[Tuple[time, time]]] = {d: [] for d in range(7)}
    for key, segs in raw.items():
        if str(key).isdigit():
            day = int(key)
            if not 0 <= day <= 6:
                raise ValidationError("E1001", "星期序号应为 0–6", field="availability")
        elif key in WEEKDAY_ALIASES:
            day = WEEKDAY_ALIASES[key]
        else:
            raise ValidationError("E1001", "星期取值应为 mon–sun", field="availability")
        segs = list(segs or [])
        if len(segs) > MAX_SEGMENTS_PER_DAY:
            raise ValidationError("E1001", "每天最多 %d 段" % MAX_SEGMENTS_PER_DAY,
                                  field="availability")
        book: List[Tuple[time, time]] = []
        for seg in segs:
            if len(seg) != 2:
                raise ValidationError("E1001", "每段需为 [开始, 结束]", field="availability")
            s, e = parse_time(seg[0]), parse_time(seg[1])
            if s >= e:
                raise ValidationError("E1001", "开始时间必须早于结束时间",
                                      field="availability")
            book.append((s, e))
        book.sort()
        for (s1, e1), (s2, e2) in zip(book, book[1:]):
            if s2 < e1:
                raise ValidationError("E1001", "同一天的时段不能重叠", field="availability")
        total = sum(int((datetime.combine(date(2000, 1, 1), e)
                         - datetime.combine(date(2000, 1, 1), s)).total_seconds() // 60)
                    for s, e in book)
        if total > MAX_DAILY_MINUTES:
            raise ValidationError("E1001", "单日可用时间不得超过 8 小时",
                                  field="availability")
        result[day] = book
    return result


def normalize_dates(values: Optional[Iterable[str]], field: str = "excluded_dates") -> List[date]:
    out: List[date] = []
    for v in values or []:
        try:
            out.append(datetime.strptime(str(v), "%Y-%m-%d").date())
        except ValueError:
            raise ValidationError("E1001", "日期格式应为 YYYY-MM-DD", field=field)
    return sorted(set(out))


# ---------------------------------------------------------------- 展开
def as_naive_utc(dt: datetime) -> datetime:
    """统一成“无时区的 UTC”，避免 aware/naive 混用。"""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def expand_slots(availability: Dict[int, List[Tuple[time, time]]],
                 excluded: Sequence[date], base_time: datetime,
                 deadline: date) -> List[Interval]:
    """把周模板展开为 [base_time, 截止日 23:59:59] 内的具体区间。"""
    base_time = as_naive_utc(base_time)
    hard_end = datetime.combine(deadline, time(23, 59, 59))
    if hard_end <= base_time:
        return []
    excluded_set = set(excluded)
    out: List[Interval] = []
    day = base_time.date()
    while day <= deadline:
        if day not in excluded_set:
            for s, e in availability.get(day.weekday(), []):
                start = datetime.combine(day, s)
                end = datetime.combine(day, e)
                start = max(start, base_time)
                end = min(end, hard_end)
                if start < end:
                    out.append(Interval(start, end))
        day += timedelta(days=1)
    out.sort(key=lambda i: i.start)
    return out


def compute_capacity(slots: Sequence[Interval], buffer_ratio: float) -> Capacity:
    raw = sum(s.minutes for s in slots)
    buf = math.ceil(buffer_ratio * raw)
    return Capacity(raw_minutes=raw, buffer_minutes=buf,
                    usable_minutes=raw - buf, slots=len(slots))


# ---------------------------------------------------------------- 规范化与汇总
@dataclass(frozen=True)
class ConstraintInput:
    target_concept_id: int
    deadline: str
    availability: Dict[str, Sequence[Sequence[str]]]
    extra_concept_ids: Sequence[int] = ()
    excluded_dates: Sequence[str] = ()
    mastered_concept_ids: Sequence[int] = ()


@dataclass(frozen=True)
class NormalizedConstraint:
    target_concept_id: int
    extra_concept_ids: List[int]
    deadline: date
    availability: Dict[int, List[Tuple[time, time]]]
    excluded_dates: List[date]
    mastered_concept_ids: List[int]


@dataclass(frozen=True)
class CapacitySummary:
    raw_minutes: int
    buffer_minutes: int
    usable_minutes: int
    slots: int
    path_minutes: int
    goals: List[int]
    reject_reason: Optional[str] = None


def normalize(raw: ConstraintInput, today: date) -> NormalizedConstraint:
    target = int(raw.target_concept_id)
    if target <= 0:
        raise ValidationError("E1001", "缺少主目标", field="target_concept_id")

    try:
        deadline = datetime.strptime(str(raw.deadline), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError("E1001", "截止日期格式应为 YYYY-MM-DD", field="deadline")
    delta = (deadline - today).days
    if delta < MIN_DEADLINE_DAYS:
        raise ValidationError("E1001", "截止日期至少为明天", field="deadline")
    if delta > MAX_DEADLINE_DAYS_CAP:
        raise ValidationError("E1001", "截止日期不得超过 %d 天" % MAX_DEADLINE_DAYS_CAP,
                              field="deadline")

    availability = normalize_availability(raw.availability)
    excluded = normalize_dates(raw.excluded_dates)
    if len(excluded) > MAX_EXCLUDED_DATES:
        raise ValidationError("E1001", "排除日期最多 %d 个" % MAX_EXCLUDED_DATES,
                              field="excluded_dates")

    extras = [int(x) for x in raw.extra_concept_ids or []]
    goals = [target] + [x for x in extras if x != target]
    goals = list(dict.fromkeys(goals))
    if len(goals) > 11:
        raise ValidationError("E1001", "目标数量过多（主目标 + 最多 10 个附加）",
                              field="extra_concept_ids")

    mastered = list(dict.fromkeys(int(x) for x in raw.mastered_concept_ids or []))
    return NormalizedConstraint(target_concept_id=target, extra_concept_ids=goals[1:],
                                deadline=deadline, availability=availability,
                                excluded_dates=excluded, mastered_concept_ids=mastered)


def summarize(constraint: NormalizedConstraint, base_time: datetime,
              buffer_ratio: float, path_minutes: int = 0) -> CapacitySummary:
    """展开时段并给出容量；容量为零时给出原因，不抛异常（供界面回显）。"""
    base_time = as_naive_utc(base_time)
    goals = [constraint.target_concept_id] + constraint.extra_concept_ids
    remaining = [g for g in goals if g not in set(constraint.mastered_concept_ids)]
    slots = expand_slots(constraint.availability, constraint.excluded_dates,
                         base_time, constraint.deadline)
    cap = compute_capacity(slots, buffer_ratio)

    reason = None
    if not any(constraint.availability.values()):
        reason = EMPTY_AVAILABILITY
    elif not slots:
        reason = ALL_EXCLUDED
    elif not remaining:
        reason = NOTHING_TO_PLAN

    return CapacitySummary(raw_minutes=cap.raw_minutes,
                           buffer_minutes=cap.buffer_minutes,
                           usable_minutes=cap.usable_minutes, slots=cap.slots,
                           path_minutes=path_minutes, goals=remaining,
                           reject_reason=reason)
