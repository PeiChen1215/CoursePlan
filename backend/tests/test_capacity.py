"""M3 · 时段展开与容量计算单元测试（对齐 D06 表 5.6 的 12 条用例）。"""
from datetime import date, datetime, time

import pytest

from app.core.errors import ValidationError
from app.services.capacity import (ALL_EXCLUDED, EMPTY_AVAILABILITY, NOTHING_TO_PLAN,
                                   Capacity, ConstraintInput, Interval, compute_capacity,
                                   expand_slots, normalize, normalize_availability,
                                   normalize_dates, parse_time, summarize)

BASE = datetime(2026, 11, 9, 9, 0)          # 2026-11-09 是周一
TODAY = BASE.date()
MON = 0


def avail(day="mon", start="19:00", end="21:00"):
    return {day: [[start, end]]}


# ---------------- 解析与规范化
def test_parse_time_ok():
    assert parse_time("19:30") == time(19, 30)


def test_parse_time_bad():
    with pytest.raises(ValidationError) as e:
        parse_time("19点")
    assert e.value.field == "availability"


def test_normalize_availability_alias_and_list_form():
    a = normalize_availability({"mon": [["19:00", "21:00"]]})
    assert a[MON][0] == (time(19, 0), time(21, 0))
    b = normalize_availability([[], [["20:00", "21:00"]], [], [], [], [], []])
    assert b[1][0] == (time(20, 0), time(21, 0))


def test_normalize_availability_rejects_bad_weekday():
    with pytest.raises(ValidationError):
        normalize_availability({"周一": [["19:00", "21:00"]]})


def test_normalize_availability_rejects_reverse_range():
    with pytest.raises(ValidationError):
        normalize_availability({"mon": [["21:00", "19:00"]]})


def test_normalize_availability_rejects_overlap():
    with pytest.raises(ValidationError):
        normalize_availability({"mon": [["19:00", "21:00"], ["20:00", "22:00"]]})


def test_normalize_availability_rejects_more_than_three_segments():
    with pytest.raises(ValidationError):
        normalize_availability({"mon": [["08:00", "09:00"], ["10:00", "11:00"],
                                        ["12:00", "13:00"], ["14:00", "15:00"]]})


def test_normalize_availability_rejects_daily_over_8h():
    with pytest.raises(ValidationError):
        normalize_availability({"mon": [["08:00", "13:00"], ["13:00", "16:01"]]})


def test_normalize_availability_requires_value():
    with pytest.raises(ValidationError):
        normalize_availability(None)


def test_normalize_availability_bad_segment_shape():
    with pytest.raises(ValidationError):
        normalize_availability({"mon": [["19:00"]]})


def test_normalize_dates_dedup_and_sort():
    out = normalize_dates(["2026-11-12", "2026-11-10", "2026-11-12"])
    assert out == [date(2026, 11, 10), date(2026, 11, 12)]


def test_normalize_dates_rejects_bad_format():
    with pytest.raises(ValidationError) as e:
        normalize_dates(["2026/11/10"])
    assert e.value.field == "excluded_dates"


# ---------------- 展开（T-03-06、T-03-12）
def test_expand_includes_deadline_day():
    slots = expand_slots({MON: [(time(19, 0), time(21, 0))]}, [],
                         BASE, date(2026, 11, 9))
    assert len(slots) == 1 and slots[0].minutes == 120


def test_expand_excludes_named_date_even_if_deadline():
    slots = expand_slots({MON: [(time(19, 0), time(21, 0))]}, [date(2026, 11, 9)],
                         BASE, date(2026, 11, 9))
    assert slots == []


def test_expand_clips_slot_started_before_base():
    """基准时刻在时段中间时，只计剩余分钟。"""
    slots = expand_slots({MON: [(time(8, 0), time(10, 0))]}, [], BASE,
                         date(2026, 11, 9))
    assert slots[0].minutes == 60


def test_expand_skips_slot_entirely_in_past():
    late = datetime(2026, 11, 9, 22, 0)
    slots = expand_slots({MON: [(time(19, 0), time(21, 0))]}, [], late, date(2026, 11, 9))
    assert slots == []


def test_expand_returns_empty_when_deadline_before_base():
    assert expand_slots({MON: [(time(19, 0), time(21, 0))]}, [],
                        BASE, date(2026, 11, 8)) == []


def test_expand_sorted_by_start():
    slots = expand_slots({MON: [(time(19, 0), time(20, 0))],
                          6: [(time(9, 0), time(10, 0))]}, [],
                         BASE, date(2026, 11, 15))
    assert [s.start for s in slots] == sorted(s.start for s in slots)


# ---------------- 容量（T-03-01、T-03-11）
def test_capacity_basic():
    slots = [Interval(datetime(2026, 11, 9, 19), datetime(2026, 11, 9, 21))]
    cap = compute_capacity(slots, 0.10)
    assert (cap.raw_minutes, cap.buffer_minutes, cap.usable_minutes) == (120, 12, 108)


def test_capacity_buffer_rounds_up():
    slots = [Interval(datetime(2026, 11, 9, 8), datetime(2026, 11, 9, 8))]
    cap = compute_capacity([Interval(datetime(2026, 11, 9, 8),
                                     datetime(2026, 11, 9, 8) + __import__("datetime").timedelta(minutes=1321))], 0.10)
    assert cap.raw_minutes == 1321
    assert cap.buffer_minutes == 133
    assert cap.usable_minutes == 1188


def test_capacity_zero_when_no_slots():
    cap = compute_capacity([], 0.10)
    assert (cap.raw_minutes, cap.buffer_minutes, cap.usable_minutes) == (0, 0, 0)


# ---------------- 规范化与汇总（T-03-02..T-03-05、T-03-07..T-03-10）
def make_input(**kw):
    d = dict(target_concept_id=1, deadline="2026-11-20",
             availability={"mon": [["19:00", "21:00"]]})
    d.update(kw)
    return ConstraintInput(**d)


def test_deadline_yesterday_rejected():
    with pytest.raises(ValidationError) as e:
        normalize(make_input(deadline="2026-11-08"), TODAY)
    assert e.value.field == "deadline"


def test_deadline_180_days_ok():
    assert normalize(make_input(deadline="2027-05-08"), TODAY).deadline


def test_deadline_181_days_rejected():
    with pytest.raises(ValidationError):
        normalize(make_input(deadline="2027-05-09"), TODAY)


def test_deadline_bad_format():
    with pytest.raises(ValidationError):
        normalize(make_input(deadline="2026/11/20"), TODAY)


def test_target_required():
    with pytest.raises(ValidationError) as e:
        normalize(make_input(target_concept_id=0), TODAY)
    assert e.value.field == "target_concept_id"


def test_goals_deduped():
    n = normalize(make_input(target_concept_id=3, extra_concept_ids=[3, 4, 4]), TODAY)
    assert n.target_concept_id == 3 and n.extra_concept_ids == [4]


def test_too_many_goals():
    with pytest.raises(ValidationError):
        normalize(make_input(extra_concept_ids=list(range(2, 13))), TODAY)


def test_excluded_dates_limit():
    dates = ["2026-11-%02d" % d for d in range(1, 31)]
    with pytest.raises(ValidationError):
        normalize(make_input(excluded_dates=dates + ["2026-12-01"]), TODAY)


def test_summary_normal():
    n = normalize(make_input(), TODAY)
    s = summarize(n, BASE, 0.10, path_minutes=300)
    assert s.raw_minutes > 0 and s.usable_minutes < s.raw_minutes
    assert s.reject_reason is None and s.path_minutes == 300


def test_summary_empty_availability():
    n = normalize(make_input(availability={}), TODAY)
    s = summarize(n, BASE, 0.10)
    assert s.reject_reason == EMPTY_AVAILABILITY


def test_summary_all_excluded():
    days = ["2026-11-%02d" % d for d in range(9, 21)]
    n = normalize(make_input(excluded_dates=days), TODAY)
    s = summarize(n, BASE, 0.10)
    assert s.reject_reason == ALL_EXCLUDED and s.raw_minutes == 0


def test_summary_nothing_to_plan_when_all_mastered():
    n = normalize(make_input(mastered_concept_ids=[1]), TODAY)
    s = summarize(n, BASE, 0.10)
    assert s.reject_reason == NOTHING_TO_PLAN and s.goals == []


def test_summary_keeps_unmastered_goals():
    n = normalize(make_input(extra_concept_ids=[2], mastered_concept_ids=[2]), TODAY)
    s = summarize(n, BASE, 0.10)
    assert s.goals == [1] and s.reject_reason is None
