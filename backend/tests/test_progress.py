"""M6 · 进度与事件测试（对齐 D06 表 10.6 的用例）。"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import NotFound, StateError, ValidationError
from app.services.progress import ProgressService
from app.services.version import VersionService

BASE = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)


def login(client, user="alice", pwd="Passw0rd!"):
    d = client.post("/api/auth/login", json={"username": user, "password": pwd}).json()["data"]
    return {"Authorization": "Bearer " + d["token"]}, d["user_id"]


def confirmed_plan(client):
    """建计划 → 约束 → 生成 → 确认，返回 (headers, uid, pid, 第一批 task_id)。"""
    from app.services.planner import PlannerService
    h, uid = login(client)
    pid = client.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    client.put("/api/plans/%d/constraint" % pid, headers=h, json={
        "target_concept_id": 2, "deadline": "2026-11-20",
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
        "base_time": "2026-11-09T09:00:00Z"})
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    VersionService(client.app.state.db,
                   client.app.state.config).confirm(pid, draft.revision, "k1", uid, BASE)
    tasks = [int(r["task_id"]) for r in client.app.state.db.query(
        "SELECT task_id FROM version_task WHERE version_id = 1 ORDER BY task_id")]
    return h, uid, pid, tasks


def svc(client):
    return ProgressService(client.app.state.db, client.app.state.config)


# ---------------- 打卡（T-10-01..T-10-03）
def test_submit_done_once(client):
    h, uid, pid, tasks = confirmed_plan(client)
    r = svc(client).submit(pid, uid, tasks[0], "done", "k1", BASE, actual_minutes=50)
    assert r.replayed is False and r.event_id > 0
    assert client.app.state.db.scalar(
        "SELECT progress_revision FROM study_plan WHERE plan_id=?", (pid,)) == 1


def test_duplicate_done_rejected(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    s.submit(pid, uid, tasks[0], "done", "k1", BASE)
    with pytest.raises(StateError) as e:
        s.submit(pid, uid, tasks[0], "done", "k2", BASE)
    assert e.value.code == "E1003"


def test_same_request_key_replays(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    a = s.submit(pid, uid, tasks[0], "done", "same", BASE)
    b = s.submit(pid, uid, tasks[0], "done", "same", BASE)
    assert b.replayed is True and b.event_id == a.event_id
    assert client.app.state.db.scalar("SELECT COUNT(*) FROM learning_event") == 1


# ---------------- 更正（T-10-04..T-10-07）
def test_correction_updates_effective_minutes(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    first = s.submit(pid, uid, tasks[0], "done", "k1", BASE, actual_minutes=50)
    s.submit(pid, uid, tasks[0], "correction", "k2", BASE, actual_minutes=35,
             corrects_event_id=first.event_id)
    assert s.effective_minutes(pid, tasks[0]) == 35


def test_correction_cross_task_rejected(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    first = s.submit(pid, uid, tasks[0], "done", "k1", BASE, actual_minutes=50)
    with pytest.raises(ValidationError) as e:
        s.submit(pid, uid, tasks[1], "correction", "k2", BASE,
                 actual_minutes=30, corrects_event_id=first.event_id)
    assert e.value.field == "corrects_event_id"


def test_correction_must_point_to_latest(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    first = s.submit(pid, uid, tasks[0], "done", "k1", BASE, actual_minutes=50)
    second = s.submit(pid, uid, tasks[0], "correction", "k2", BASE,
                      actual_minutes=40, corrects_event_id=first.event_id)
    with pytest.raises(StateError):
        s.submit(pid, uid, tasks[0], "correction", "k3", BASE,
                 actual_minutes=20, corrects_event_id=first.event_id)


def test_correction_of_note_rejected(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    note = s.submit(pid, uid, tasks[0], "note", "k1", BASE, note="今天状态不好")
    with pytest.raises(ValidationError):
        s.submit(pid, uid, tasks[0], "correction", "k2", BASE,
                 actual_minutes=10, corrects_event_id=note.event_id)


def test_note_does_not_change_minutes(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    s.submit(pid, uid, tasks[0], "done", "k1", BASE, actual_minutes=50)
    s.submit(pid, uid, tasks[0], "note", "k2", BASE, note="还行")
    assert s.effective_minutes(pid, tasks[0]) == 50


# ---------------- 有效用时与完成率（T-10-09..T-10-11）
def test_effective_minutes_falls_back_to_planned(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    s.submit(pid, uid, tasks[0], "done", "k1", BASE)      # 不填实际用时
    planned = client.app.state.db.scalar(
        "SELECT estimated_minutes FROM version_task WHERE version_id=1 AND task_id=?",
        (tasks[0],))
    assert s.effective_minutes(pid, tasks[0]) == int(planned)


def test_completion_rate_zero_and_full(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    assert s.completion_rate(pid) == 0.0
    for i, tid in enumerate(tasks):
        s.submit(pid, uid, tid, "done", "k%d" % i, BASE)
    assert s.completion_rate(pid) == 1.0


def test_completion_rate_ignores_out_of_scope(client):
    """分母只含 in_scope=1（口径由 version_task 决定）。"""
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    s.submit(pid, uid, tasks[0], "done", "k1", BASE)
    expected = round(1 / len(tasks), 3)
    assert s.completion_rate(pid) == expected


# ---------------- 逾期（T-10-12）
def test_overdue_is_derived_not_state_change(client):
    h, uid, pid, tasks = confirmed_plan(client)
    later = BASE + timedelta(days=30)
    p = svc(client).progress(pid, uid, later)
    assert p.overdue_tasks and len(p.overdue_tasks) == p.total_tasks
    row = client.app.state.db.query("SELECT status FROM study_plan WHERE plan_id=?",
                                    (pid,))[0]
    assert row["status"] == "active"          # 逾期不改计划状态


def test_finished_task_not_overdue(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    s.submit(pid, uid, tasks[0], "done", "k1", BASE)
    p = s.progress(pid, uid, BASE + timedelta(days=30))
    assert tasks[0] not in p.overdue_tasks


# ---------------- 参数与归属
def test_event_requires_confirmed_plan(client):
    h, uid = login(client)
    pid = client.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    with pytest.raises(StateError) as e:
        svc(client).submit(pid, uid, 1, "done", "k1", BASE)
    assert "尚未确认" in e.value.message


def test_unknown_task_404(client):
    h, uid, pid, tasks = confirmed_plan(client)
    with pytest.raises(NotFound):
        svc(client).submit(pid, uid, 9999, "done", "k1", BASE)


def test_bad_event_type(client):
    h, uid, pid, tasks = confirmed_plan(client)
    with pytest.raises(ValidationError):
        svc(client).submit(pid, uid, tasks[0], "skip", "k1", BASE)


def test_missing_request_key(client):
    h, uid, pid, tasks = confirmed_plan(client)
    with pytest.raises(ValidationError) as e:
        svc(client).submit(pid, uid, tasks[0], "done", "", BASE)
    assert e.value.field == "request_key"


def test_negative_minutes_rejected(client):
    h, uid, pid, tasks = confirmed_plan(client)
    with pytest.raises(ValidationError):
        svc(client).submit(pid, uid, tasks[0], "done", "k1", BASE, actual_minutes=-5)


def test_other_students_plan_404(client):
    h, uid, pid, tasks = confirmed_plan(client)
    _, admin_id = login(client, "admin", "Admin123!")
    with pytest.raises(NotFound):
        svc(client).submit(pid, admin_id, tasks[0], "done", "k1", BASE)


# ---------------- HTTP
def test_http_event_and_progress(client):
    h, uid, pid, tasks = confirmed_plan(client)
    r = client.post("/api/plans/%d/events" % pid, headers={**h, "Idempotency-Key": "e1"},
                    json={"task_id": tasks[0], "event_type": "done",
                          "actual_minutes": 45})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["completion_rate"] > 0

    p = client.get("/api/plans/%d/progress" % pid, headers=h).json()["data"]
    assert p["done_tasks"] == 1 and p["total_tasks"] == len(tasks)


def test_http_agent_extract(client):
    h, uid = login(client)
    r = client.post("/api/agent/extract", headers=h, json={
        "utterance": "我想学指针，10 天后，每天两小时",
        "base_date": "2026-11-09"})
    d = r.json()["data"]
    assert d["fields"]["target_concept_id"] == 3
    assert d["fields"]["deadline"] == "2026-11-19"
    assert d["mode"] in ("local", "mock")

# ---------------- 事件时间线（D06 §10.7）
def test_timeline_lists_events_with_names(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    s.submit(pid, uid, tasks[0], "done", "k1", BASE, actual_minutes=40)
    from app.services.timeline import TimelineService
    items = TimelineService(client.app.state.db, client.app.state.config).events(pid, uid)
    assert len(items) == 1
    row = items[0]
    assert row["event_type"] == "done" and row["label"] == "完成"
    assert row["concept_name"] and row["actual_minutes"] == 40
    assert row["is_current_version"] is True

def test_timeline_marks_correction_chain(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    first = s.submit(pid, uid, tasks[0], "done", "k1", BASE, actual_minutes=40)
    s.submit(pid, uid, tasks[0], "correction", "k2", BASE, actual_minutes=30,
             corrects_event_id=first.event_id)
    from app.services.timeline import TimelineService
    items = TimelineService(client.app.state.db, client.app.state.config).events(pid, uid)
    correction = [i for i in items if i["event_type"] == "correction"][0]
    assert correction["corrects_event_id"] == first.event_id

def test_timeline_other_student_404(client):
    from app.core.errors import NotFound
    from app.services.timeline import TimelineService
    h, uid, pid, tasks = confirmed_plan(client)
    _, admin_id = login(client, "admin", "Admin123!")
    with pytest.raises(NotFound):
        TimelineService(client.app.state.db, client.app.state.config).events(pid, admin_id)

def test_explain_maps_codes_to_plain_language(client):
    from app.services.timeline import TimelineService
    svc2 = TimelineService(client.app.state.db, client.app.state.config)
    out = svc2.explain(["CAP_EXCEEDED", "UNKNOWN_CODE"])
    assert out[0]["title"] and out[0]["action"]
    assert out[1]["code"] == "UNKNOWN_CODE" and out[1]["action"] == "暂无建议"

def test_http_events_and_explain(client):
    h, uid, pid, tasks = confirmed_plan(client)
    client.post("/api/plans/%d/events" % pid, headers={**h, "Idempotency-Key": "e1"},
                json={"task_id": tasks[0], "event_type": "done", "actual_minutes": 30})
    items = client.get("/api/plans/%d/events" % pid, headers=h).json()["data"]["items"]
    assert items and items[0]["label"] == "完成"
    exp = client.post("/api/plans/%d/explain" % pid, headers=h,
                      json={"codes": ["CAP_TIGHT"]}).json()["data"]["items"]
    assert exp[0]["code"] == "CAP_TIGHT" and "缓冲" in exp[0]["title"]

def test_confirm_records_change_reason(client):
    h, uid, pid, tasks = confirmed_plan(client)
    from app.services.planner import PlannerService
    from app.services.version import VersionService
    draft = PlannerService(client.app.state.db, client.app.state.config).generate(pid, uid, BASE)
    VersionService(client.app.state.db, client.app.state.config).confirm(
        pid, draft.revision, "adj-1", uid, BASE,
        change_reason="delay", change_note="截止日期延后到 12-20")
    row = client.app.state.db.query(
        "SELECT change_reason, change_note FROM plan_version WHERE plan_id=? ORDER BY version_no DESC",
        (pid,))[0]
    assert row["change_reason"] == "delay"
    assert row["change_note"] == "截止日期延后到 12-20"

def test_confirm_ignores_unknown_reason(client):
    h, uid, pid, tasks = confirmed_plan(client)
    from app.services.planner import PlannerService
    from app.services.version import VersionService
    draft = PlannerService(client.app.state.db, client.app.state.config).generate(pid, uid, BASE)
    VersionService(client.app.state.db, client.app.state.config).confirm(
        pid, draft.revision, "adj-2", uid, BASE, change_reason="whatever")
    row = client.app.state.db.query(
        "SELECT change_reason FROM plan_version WHERE plan_id=? ORDER BY version_no DESC",
        (pid,))[0]
    assert row["change_reason"] == "manual"


def test_http_event_without_key_is_accepted(client):
    """D06：未带 Idempotency-Key 时服务端生成新键，而不是 400。"""
    h, uid, pid, tasks = confirmed_plan(client)
    r = client.post("/api/plans/%d/events" % pid, headers=h,
                    json={"task_id": tasks[0], "event_type": "done", "actual_minutes": 30})
    assert r.status_code == 200
    assert r.json()["data"]["replayed"] is False


def test_duplicate_done_race_returns_clean_error(client, monkeypatch):
    """并发窗口里预检查可能漏掉：唯一约束触发时要翻译成业务错误，不能抛 SQL。"""
    from app.core.errors import StateError
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    s.submit(pid, uid, tasks[0], "done", "race-1", BASE, actual_minutes=30)
    monkeypatch.setattr(type(s), "_has_done", lambda self, v, t: False)
    with pytest.raises(StateError) as err:
        s.submit(pid, uid, tasks[0], "done", "race-2", BASE, actual_minutes=30)
    assert err.value.code == "E1003"
    assert "打过卡" in err.value.message


def test_submit_reraises_unexpected_db_error(client, monkeypatch):
    """非唯一约束的异常要原样抛出，不能被当成重复打卡吞掉。"""
    import app.services.progress as P
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    real_execute = P.UnitOfWork.execute

    def fake_execute(self, sql, params=()):
        if "INSERT INTO learning_event" in sql:
            raise ValueError("磁盘写满了")
        return real_execute(self, sql, params)

    monkeypatch.setattr(P.UnitOfWork, "execute", fake_execute)
    with pytest.raises(ValueError, match="磁盘写满了"):
        s.submit(pid, uid, tasks[0], "note", "boom-1", BASE, note="记一笔")
