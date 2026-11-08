"""M4 · 排程引擎单元测试（对齐 D06 表 7.5 的 12 条用例）。"""
from datetime import date, datetime, time, timedelta

import pytest

from app.core import config as C
from app.core.errors import PrereqCycle, StateError
from app.services.capacity import Interval
from app.services.planner import (CAPACITY_REASON, PRACTICE, STUDY, TOO_MANY_SLICES,
                                  Concept, PlannerService, Task, input_hash, metrics_of,
                                  pack, split_tasks, topo_order_concepts)

CFG = C.load({})
BASE = datetime(2026, 11, 9, 9, 0)


def concept(cid, chapter="第1章", order=1, minutes=100, status="enabled"):
    return Concept(cid, "K%d" % cid, chapter, order, minutes, status)


def slot(start_h, end_h, day=9):
    return Interval(datetime(2026, 11, day, start_h), datetime(2026, 11, day, end_h))


# ---------------- A3 拆分（T-05-01..T-05-04）
def test_split_seventy_thirty():
    tasks = split_tasks([concept(1, minutes=100)], set(), CFG)
    assert [(t.kind, t.minutes) for t in tasks] == [(STUDY, 70), (PRACTICE, 30)]


def test_split_sum_equals_reference():
    tasks = split_tasks([concept(1, minutes=97)], set(), CFG)
    assert sum(t.minutes for t in tasks) == 97
    assert tasks[0].minutes == int(97 * 0.7)


def test_split_floor_not_round():
    """70% 向下取整，练习取差值。"""
    tasks = split_tasks([concept(1, minutes=95)], set(), CFG)
    assert tasks[0].minutes == 66 and tasks[1].minutes == 29


def test_split_merges_tiny_practice():
    """练习时长低于 MIN_TASK_MINUTES 时并入学习，只产出一条任务。"""
    cfg = C.load({"MIN_TASK_MINUTES": 5})
    tasks = split_tasks([concept(1, minutes=5)], set(), cfg)
    assert len(tasks) == 1 and tasks[0].kind == STUDY and tasks[0].minutes == 5


def test_split_skips_mastered_and_disabled():
    tasks = split_tasks([concept(1), concept(2), concept(3, status="disabled")],
                        {1}, CFG)
    assert {t.concept_id for t in tasks} == {2}


def test_split_ordered_by_chapter_key():
    cs = [concept(3, chapter="第2章"), concept(1, chapter="第1章", order=2),
          concept(2, chapter="第1章", order=1)]
    tasks = split_tasks(cs, set(), CFG)
    assert [t.concept_id for t in tasks] == [2, 2, 1, 1, 3, 3]


# ---------------- A4 拓扑（T-05-05..T-05-07）
def test_topo_respects_prereq():
    cs = [concept(1, chapter="第1章"), concept(2, chapter="第1章")]
    assert topo_order_concepts(cs, [(1, 2)]) == [1, 2]


def test_topo_stable_by_chapter_then_id():
    cs = [concept(3, chapter="第2章"), concept(1, chapter="第1章"),
          concept(2, chapter="第1章")]
    assert topo_order_concepts(cs, []) == [1, 2, 3]


def test_topo_raises_on_cycle():
    cs = [concept(1), concept(2)]
    with pytest.raises(PrereqCycle):
        topo_order_concepts(cs, [(1, 2), (2, 1)])


def test_topo_ignores_edges_outside_selection():
    cs = [concept(1)]
    assert topo_order_concepts(cs, [(1, 9)]) == [1]


# ---------------- A5/A6 装箱与拆片（T-05-08..T-05-11）
def test_pack_single_slot_enough():
    tasks = [Task(1, STUDY, 60)]
    slices, unsched = pack(tasks, [slot(19, 21)], CFG)
    assert len(slices) == 1 and slices[0].minutes == 60
    assert unsched == []


def test_pack_splits_at_120_minutes():
    """单片上限 120 分钟：180 分钟的任务要切成 120 + 60。"""
    tasks = [Task(1, STUDY, 180)]
    slices, _ = pack(tasks, [slot(8, 12)], CFG)
    assert [s.minutes for s in slices] == [120, 60]
    assert [s.slice_no for s in slices] == [1, 2]


def test_pack_spans_multiple_slots():
    tasks = [Task(1, STUDY, 100)]
    slices, _ = pack(tasks, [slot(19, 20, 9), slot(19, 20, 10)], CFG)
    assert [s.minutes for s in slices] == [60, 40]
    assert slices[1].start.day == 10


def test_pack_capacity_shortage_marks_unscheduled():
    tasks = [Task(1, STUDY, 300)]
    slices, unsched = pack(tasks, [slot(19, 20)], CFG)
    assert unsched and unsched[0].reason == CAPACITY_REASON
    assert slices == []


def test_pack_too_many_slices():
    """需要超过 100 片时判为不可排（用 1 分钟上限逼出来）。"""
    cfg = C.load({"MAX_SLICES_PER_TASK": 1})
    tasks = [Task(1, STUDY, 180)]
    slices, unsched = pack(tasks, [slot(8, 12)], cfg)
    assert unsched[0].reason == TOO_MANY_SLICES
    assert slices == []


def test_pack_skips_slot_shorter_than_minimum():
    tasks = [Task(1, STUDY, 30)]
    slices, _ = pack(tasks, [slot(9, 9), slot(19, 20)], CFG)
    assert slices and slices[0].start.hour == 19


def test_pack_does_not_double_buffer():
    """缓冲已在 C′ 里预留，片内不再扣。"""
    tasks = [Task(1, STUDY, 120)]
    slices, _ = pack(tasks, [slot(19, 21)], CFG)
    assert slices[0].minutes == 120


# ---------------- 指标（T-05-12）
def test_metrics_deficit_and_utilization():
    tasks = [Task(1, STUDY, 70), Task(1, PRACTICE, 30)]
    slices, _ = pack(tasks, [slot(19, 21)], CFG)
    m = metrics_of(tasks, slices, raw=120, buffer=12, usable=108)
    assert m.total_minutes == 100
    assert m.deficit_minutes == 0
    assert m.utilization == 0.8333
    assert m.scheduled_minutes == 100


def test_metrics_deficit_when_over_capacity():
    tasks = [Task(1, STUDY, 200)]
    slices, _ = pack(tasks, [slot(19, 20)], CFG)
    m = metrics_of(tasks, slices, raw=60, buffer=6, usable=54)
    assert m.deficit_minutes == 146
    # 任务排不下时整条不排入，不留半截片
    assert slices == [] and m.scheduled_minutes == 0


def test_metrics_utilization_zero_when_no_capacity():
    assert metrics_of([], [], 0, 0, 0).utilization == 0.0


# ---------------- 摘要稳定性
def test_input_hash_is_stable_and_order_independent():
    a = {"a": 1, "b": [1, 2]}
    b = {"b": [1, 2], "a": 1}
    assert input_hash(a) == input_hash(b)
    assert input_hash(a) != input_hash({"a": 2, "b": [1, 2]})


# ---------------- 编排（需要库）
@pytest.fixture()
def plan_env(seeded):
    conn = seeded.connect()
    conn.execute("INSERT INTO study_plan(student_id,course_id,status,created_at,updated_at)"
                 " VALUES(1,1,'draft','2026-11-01T00:00:00Z','2026-11-01T00:00:00Z')")
    conn.execute("INSERT INTO plan_constraint(plan_id,course_id,target_concept_id,"
                 "extra_concept_ids_json,deadline,availability_json,excluded_dates_json,"
                 "mastered_concept_ids_json,base_time) VALUES"
                 "(1,1,2,'[]','2026-11-20',?,'[]','[]','2026-11-09T09:00:00Z')",
                 ('{"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]}',))
    conn.commit()
    conn.close()
    return seeded


def test_generate_writes_draft(plan_env):
    svc = PlannerService(plan_env, CFG)
    draft = svc.generate(1, 1, BASE)
    assert draft.revision == 1
    assert draft.metrics.total_minutes > 0
    assert len(draft.hash) == 64
    row = plan_env.query("SELECT status, revision FROM plan_draft WHERE plan_id=1")[0]
    assert row["revision"] == 1 and row["status"] in ("ready", "invalid")


def test_generate_increments_revision(plan_env):
    svc = PlannerService(plan_env, CFG)
    svc.generate(1, 1, BASE)
    d2 = svc.generate(1, 1, BASE)
    assert d2.revision == 2


def test_generate_requires_constraint(seeded):
    conn = seeded.connect()
    conn.execute("INSERT INTO study_plan(student_id,course_id,status,created_at,updated_at)"
                 " VALUES(1,1,'draft','2026-11-01T00:00:00Z','2026-11-01T00:00:00Z')")
    conn.commit()
    conn.close()
    with pytest.raises(StateError) as e:
        PlannerService(seeded, CFG).generate(1, 1, BASE)
    assert "约束" in e.value.message


def test_generate_rejects_other_students_plan(plan_env):
    from app.core.errors import NotFound
    with pytest.raises(NotFound):
        PlannerService(plan_env, CFG).generate(1, 99, BASE)


def test_generate_with_zero_capacity(plan_env):
    conn = plan_env.connect()
    conn.execute("UPDATE plan_constraint SET availability_json='{}' WHERE plan_id=1")
    conn.commit()
    conn.close()
    with pytest.raises(StateError):
        PlannerService(plan_env, CFG).generate(1, 1, BASE)


# ---------------- 任务编号与边界
def test_task_and_unscheduled_labels():
    assert Task(3, STUDY, 10).task_no == "C3-study"
    from app.services.planner import Unscheduled
    assert Unscheduled(3, PRACTICE, "CAPACITY").task_no == "C3-practice"


def test_pack_drops_residual_shorter_than_minimum():
    """段内剩余不足 MIN_TASK_MINUTES 时丢弃该残段，转下一段。"""
    cfg = C.load({"MIN_TASK_MINUTES": 5})
    tiny = Interval(datetime(2026, 11, 9, 18, 0), datetime(2026, 11, 9, 18, 3))
    tasks = [Task(1, STUDY, 30)]
    slices, _ = pack(tasks, [tiny, slot(19, 20)], cfg)
    assert len(slices) == 1 and slices[0].start.hour == 19


def test_generate_rejects_when_everything_mastered(plan_env):
    """目标（含先修）全部已自评掌握 → 没有任务可排，直接拒绝。"""
    conn = plan_env.connect()
    conn.execute("UPDATE plan_constraint SET mastered_concept_ids_json='[1,2]'"
                 " WHERE plan_id=1")
    conn.commit()
    conn.close()
    with pytest.raises(StateError) as e:
        PlannerService(plan_env, CFG).generate(1, 1, BASE)
    assert "全部掌握" in e.value.message
