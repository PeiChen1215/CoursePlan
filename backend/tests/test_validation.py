"""M5 · 计划校验单元测试（对齐 D06 表 8.10 的用例）。"""
from datetime import date, datetime, time, timedelta

import pytest

from app.core import config as C
from app.services.capacity import Interval
from app.services.planner import Concept, Slice, Task
from app.services.validation import (CAP_EXCEEDED, CAP_TIGHT, DEADLINE_UNREACHABLE,
                                     ERROR, ISOLATED_CONCEPT, PREREQ_VIOLATED,
                                     SLOT_INVALID, TIME_OVERLAP, WARN, validate)

CFG = C.load({})
DEADLINE = date(2026, 11, 22)


def slot(day, h1, h2):
    return Interval(datetime(2026, 11, day, h1), datetime(2026, 11, day, h2))


def sl(concept_id, kind, no, day, h1, h2):
    return Slice(concept_id, kind, no, datetime(2026, 11, day, h1),
                 datetime(2026, 11, day, h2))


def run(tasks, slices, slots, usable, raw, edges=(), concepts=None, selected=None):
    return validate(tasks, slices, slots, usable, raw, DEADLINE, list(edges),
                    concepts or [], selected or set(), CFG)


# ---------------- ① 时段合法性
def test_slot_outside_availability_is_error():
    rep = run([Task(1, "study", 60)], [sl(1, "study", 1, 21, 22, 23)],
              [slot(21, 19, 21)], usable=120, raw=120)
    assert not rep.passed
    assert rep.errors()[0].code == SLOT_INVALID


def test_slot_longer_than_limit_is_error():
    rep = run([Task(1, "study", 200)], [sl(1, "study", 1, 21, 8, 12)],
              [slot(21, 8, 13)], usable=300, raw=300)
    assert rep.errors()[0].code == SLOT_INVALID


def test_zero_length_slice_is_error():
    rep = run([Task(1, "study", 0)], [sl(1, "study", 1, 21, 9, 9)],
              [slot(21, 8, 12)], usable=240, raw=240)
    assert rep.errors()[0].code == SLOT_INVALID


# ---------------- ② 容量
def test_capacity_exceeded():
    rep = run([Task(1, "study", 100)], [sl(1, "study", 1, 21, 9, 10)],
              [slot(21, 8, 12)], usable=50, raw=60)
    assert rep.errors()[0].code == CAP_EXCEEDED
    assert rep.errors()[0].detail["deficit"] == 50


def test_capacity_within_limit_passes():
    rep = run([Task(1, "study", 60)], [sl(1, "study", 1, 21, 9, 10)],
              [slot(21, 8, 12)], usable=300, raw=330)
    assert rep.passed


# ---------------- ③ 重叠
def test_overlap_detected():
    rep = run([Task(1, "study", 60), Task(2, "study", 60)],
              [sl(1, "study", 1, 21, 9, 11), sl(2, "study", 1, 21, 10, 12)],
              [slot(21, 8, 13)], usable=300, raw=300)
    err = rep.errors()[0]
    assert err.code == TIME_OVERLAP and err.detail["a"] and err.detail["b"]


def test_adjacent_slices_do_not_overlap():
    rep = run([Task(1, "study", 60), Task(2, "study", 60)],
              [sl(1, "study", 1, 21, 9, 10), sl(2, "study", 1, 21, 10, 11)],
              [slot(21, 8, 12)], usable=300, raw=300)
    assert rep.passed


# ---------------- ④ 先修与学习先于练习
def test_prereq_violation():
    rep = run([Task(1, "study", 60), Task(2, "study", 60)],
              [sl(2, "study", 1, 21, 9, 10), sl(1, "study", 1, 21, 10, 11)],
              [slot(21, 8, 12)], usable=300, raw=300, edges=[(1, 2)])
    assert rep.errors()[0].code == PREREQ_VIOLATED


def test_prereq_satisfied():
    rep = run([Task(1, "study", 60), Task(2, "study", 60)],
              [sl(1, "study", 1, 21, 9, 10), sl(2, "study", 1, 21, 10, 11)],
              [slot(21, 8, 12)], usable=300, raw=300, edges=[(1, 2)])
    assert rep.passed


def test_practice_before_study_is_error():
    rep = run([Task(1, "study", 60), Task(1, "practice", 30)],
              [sl(1, "practice", 1, 21, 9, 10), sl(1, "study", 1, 21, 10, 11)],
              [slot(21, 8, 12)], usable=300, raw=300)
    assert rep.errors()[0].code == PREREQ_VIOLATED


# ---------------- ⑤ 截止
def test_deadline_unreachable():
    rep = run([Task(1, "study", 60)], [sl(1, "study", 1, 25, 9, 10)],
              [slot(25, 8, 12)], usable=300, raw=300)
    assert rep.errors()[0].code == DEADLINE_UNREACHABLE


def test_deadline_same_day_ok():
    rep = run([Task(1, "study", 60)], [sl(1, "study", 1, 22, 21, 22)],
              [slot(22, 20, 23)], usable=300, raw=300)
    assert rep.passed


# ---------------- 短路与 WARN/INFO
def test_short_circuits_after_capacity_error():
    """容量错时不继续检查重叠，报错只到第二项。"""
    rep = run([Task(1, "study", 200), Task(2, "study", 200)],
              [sl(1, "study", 1, 21, 9, 11), sl(2, "study", 1, 21, 10, 12)],
              [slot(21, 8, 13)], usable=10, raw=20)
    codes = [i.code for i in rep.issues]
    assert codes == [CAP_EXCEEDED]


def test_cap_tight_warn_at_boundary():
    tasks = [Task(1, "study", 80)]
    rep = run(tasks, [sl(1, "study", 1, 21, 9, 10, )], [slot(21, 8, 12)],
              usable=100, raw=100)     # 80/100 = 0.80，不超阈值
    assert not [i for i in rep.issues if i.code == CAP_TIGHT]
    rep2 = run([Task(1, "study", 81)], [sl(1, "study", 1, 21, 9, 10)],
               [slot(21, 8, 12)], usable=100, raw=100)
    warn = [i for i in rep2.issues if i.code == CAP_TIGHT]
    assert warn and warn[0].level == WARN and rep2.passed


def test_isolated_concept_info():
    concepts = [Concept(1, "A", "第1章", 1, 60), Concept(2, "B", "第1章", 2, 60)]
    rep = run([Task(1, "study", 42), Task(1, "practice", 18)],
              [sl(1, "study", 1, 21, 9, 10)], [slot(21, 8, 12)],
              usable=300, raw=300, concepts=concepts, selected={1, 2})
    info = [i for i in rep.issues if i.code == ISOLATED_CONCEPT]
    assert len(info) == 2 and info[0].level == "INFO"


def test_report_metrics_shape():
    rep = run([Task(1, "study", 60)], [sl(1, "study", 1, 21, 9, 10)],
              [slot(21, 8, 12)], usable=300, raw=330)
    assert set(rep.metrics) == {"T", "C", "C_prime", "slices", "scheduled", "U"}
    assert rep.metrics["T"] == 60 and rep.metrics["slices"] == 1


def test_issue_has_suggestion():
    rep = run([Task(1, "study", 100)], [sl(1, "study", 1, 21, 9, 10)],
              [slot(21, 8, 12)], usable=50, raw=60)
    d = rep.errors()[0].as_dict()
    assert d["suggestion"] and d["code"] == CAP_EXCEEDED
