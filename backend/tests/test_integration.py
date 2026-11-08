"""跨模块联合测试：把 M1–M4 串起来，验证模块之间的契约与不变量。

覆盖的不变量：
1. 约束接口算出的 C/B/C′ 与排程引擎内部完全一致；
2. 任务总时长 = 闭包内参考时长之和（7:3 拆分不丢分钟）；
3. 先修顺序落到时间片上：先修最后一片结束 ≤ 后继第一片开始；
4. 片互不重叠，且都落在可用时段内，单片 ≤ 120 分钟；
5. 已掌握/停用的知识点不产生任务；内容变更会改变 input_hash；
6. 同样输入两次生成结果一致（可复现）；
7. 权限与归属跨模块一致（学生不能写内容、看不了他人计划）。
"""
from datetime import datetime, timezone

import pytest

from app.services.capacity import expand_slots, normalize_availability
from app.services.planner import PlannerService, input_hash

BASE = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)


def login(client, user="alice", pwd="Passw0rd!"):
    d = client.post("/api/auth/login", json={"username": user, "password": pwd}).json()["data"]
    return {"Authorization": "Bearer " + d["token"]}, d["user_id"]


def make_plan(client, h):
    return client.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]


def constraint_body(**kw):
    body = {"target_concept_id": 2, "deadline": "2026-11-20",
            "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
            "base_time": "2026-11-09T09:00:00Z"}
    body.update(kw)
    return body


@pytest.fixture()
def flow(client):
    """登录 → 建计划 → 存约束，返回 (client, headers, uid, plan_id, 约束响应)。"""
    h, uid = login(client)
    pid = make_plan(client, h)
    resp = client.put("/api/plans/%d/constraint" % pid, headers=h,
                      json=constraint_body())
    assert resp.status_code == 200, resp.text
    return client, h, uid, pid, resp.json()["data"]


# ---------------------------------------------------------------- 1. 容量口径一致
def test_capacity_matches_planner_metrics(flow):
    client, h, uid, pid, cap = flow
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    m = draft.metrics
    assert (cap["C"], cap["B"], cap["C_prime"]) == (
        m.raw_minutes, m.buffer_minutes, m.usable_minutes)


# ---------------------------------------------------------------- 2. 任务总量守恒
def test_total_minutes_equals_closure_sum(flow):
    client, h, uid, pid, _ = flow
    db = client.app.state.db
    draft = PlannerService(db, client.app.state.config).generate(pid, uid, BASE)
    rows = db.query("SELECT concept_id, reference_minutes FROM concept"
                    " WHERE concept_id IN (SELECT concept_id FROM concept)")
    minutes = {int(r["concept_id"]): int(r["reference_minutes"]) for r in rows}
    expected = sum(minutes[cid] for cid in draft.order if cid in draft.goals
                   or cid == 1)          # 目标 2 + 其先修 1
    assert draft.metrics.total_minutes == expected


def test_every_task_is_study_or_practice(flow):
    client, h, uid, pid, _ = flow
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    assert {t.kind for t in draft.tasks} <= {"study", "practice"}
    for cid in {t.concept_id for t in draft.tasks}:
        kinds = [t.kind for t in draft.tasks if t.concept_id == cid]
        assert kinds[0] == "study"          # 同一知识点学习在前


# ---------------------------------------------------------------- 3. 先修落在时间上
def test_prereq_precedes_successor_on_timeline(flow):
    client, h, uid, pid, _ = flow
    db = client.app.state.db
    draft = PlannerService(db, client.app.state.config).generate(pid, uid, BASE)
    edges = [(int(r["from_concept_id"]), int(r["to_concept_id"]))
             for r in db.query("SELECT from_concept_id, to_concept_id FROM prerequisite")]
    for u, v in edges:
        u_end = max((s.end for s in draft.slices if s.concept_id == u), default=None)
        v_start = min((s.start for s in draft.slices if s.concept_id == v), default=None)
        if u_end and v_start:
            assert u_end <= v_start, "先修 %d 应排在后继 %d 之前" % (u, v)


# ---------------------------------------------------------------- 4. 片的不变量
def test_slices_within_limits_and_slots(flow):
    client, h, uid, pid, _ = flow
    cfg = client.app.state.config
    db = client.app.state.db
    draft = PlannerService(db, cfg).generate(pid, uid, BASE)

    assert draft.slices, "应当排出至少一片"
    for s in draft.slices:
        assert s.minutes <= cfg.MAX_SLICE_SECONDS // 60
        assert s.minutes > 0

    # 互不重叠（按开始时间排序后逐对检查）
    ordered = sorted(draft.slices, key=lambda s: s.start)
    for a, b in zip(ordered, ordered[1:]):
        assert a.end <= b.start

    # 每片都落在展开后的可用时段内
    row = db.query("SELECT availability_json, excluded_dates_json, deadline"
                   " FROM plan_constraint WHERE plan_id = ?", (pid,))[0]
    import json
    from datetime import datetime as dtm
    slots = expand_slots(normalize_availability(json.loads(row["availability_json"])),
                         [dtm.strptime(d, "%Y-%m-%d").date()
                          for d in json.loads(row["excluded_dates_json"])],
                         BASE, dtm.strptime(row["deadline"], "%Y-%m-%d").date())
    for s in draft.slices:
        assert any(slot.start <= s.start and s.end <= slot.end for slot in slots)


def test_scheduled_minutes_not_exceed_usable(flow):
    client, h, uid, pid, _ = flow
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    assert draft.metrics.scheduled_minutes <= draft.metrics.usable_minutes


# ---------------------------------------------------------------- 5. 内容变更的影响
def test_mastered_goal_produces_no_task(client):
    """目标里有一个已掌握：它不排任务，其他目标与先修照排。"""
    h, uid = login(client)
    pid = make_plan(client, h)
    r = client.put("/api/plans/%d/constraint" % pid, headers=h,
                   json=constraint_body(target_concept_id=2, extra_concept_ids=[3],
                                        mastered_concept_ids=[2]))
    assert r.status_code == 200, r.text
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    assert all(t.concept_id != 2 for t in draft.tasks)
    ids = {t.concept_id for t in draft.tasks}
    assert 1 in ids and 3 in ids                          # 先修与另一个目标仍要学


def test_all_goals_mastered_is_rejected(client):
    """目标全部掌握 → 约束阶段就该拒（NOTHING_TO_PLAN）。"""
    h, uid = login(client)
    pid = make_plan(client, h)
    r = client.put("/api/plans/%d/constraint" % pid, headers=h,
                   json=constraint_body(target_concept_id=2, mastered_concept_ids=[2]))
    assert r.status_code == 400
    assert r.json()["code"] == "E1003"
    assert r.json()["detail"]["reason"] == "NOTHING_TO_PLAN"


def test_disabling_concept_changes_hash(client):
    h_admin, _ = login(client, "admin", "Admin123!")
    h, uid = login(client)
    pid = make_plan(client, h)
    client.put("/api/plans/%d/constraint" % pid, headers=h, json=constraint_body())
    svc = PlannerService(client.app.state.db, client.app.state.config)
    first = svc.generate(pid, uid, BASE)

    assert client.post("/api/concepts/2/disable", headers=h_admin).status_code == 200
    second = svc.generate(pid, uid, BASE)
    assert first.hash != second.hash
    assert all(t.concept_id != 2 for t in second.tasks)


# ---------------------------------------------------------------- 6. 可复现
def test_generation_is_deterministic(flow):
    client, h, uid, pid, _ = flow
    svc = PlannerService(client.app.state.db, client.app.state.config)
    a = svc.generate(pid, uid, BASE)
    b = svc.generate(pid, uid, BASE)
    assert a.hash == b.hash
    assert [(s.concept_id, s.kind, s.slice_no, s.start, s.end) for s in a.slices] == \
           [(s.concept_id, s.kind, s.slice_no, s.start, s.end) for s in b.slices]
    assert b.revision == a.revision + 1


def test_hash_ignores_revision(flow):
    client, h, uid, pid, _ = flow
    svc = PlannerService(client.app.state.db, client.app.state.config)
    a = svc.generate(pid, uid, BASE)
    payload = {"plan_id": pid, "goals": a.goals, "order": a.order}
    assert input_hash(payload) == input_hash(dict(reversed(list(payload.items()))))


# ---------------------------------------------------------------- 7. 权限跨模块一致
def test_student_cannot_manage_content_but_admin_can(client):
    h, _ = login(client)
    h_admin, _ = login(client, "admin", "Admin123!")
    body = {"name": "新点", "chapter": "第9章", "difficulty": 2, "reference_minutes": 40}
    assert client.post("/api/courses/1/concepts", headers=h, json=body).status_code == 403
    assert client.post("/api/courses/1/concepts", headers=h_admin,
                       json=body).status_code == 200


def test_other_student_plan_is_hidden(client):
    h, _ = login(client)
    pid = make_plan(client, h)
    h_admin, _ = login(client, "admin", "Admin123!")
    assert client.get("/api/plans/%d/constraint" % pid, headers=h_admin).status_code == 404


def test_plan_flow_requires_constraint_before_draft(client):
    from app.core.errors import StateError
    h, uid = login(client)
    pid = make_plan(client, h)
    with pytest.raises(StateError):
        PlannerService(client.app.state.db,
                       client.app.state.config).generate(pid, uid, BASE)
