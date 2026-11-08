"""M6 · 补齐分支：空输入、降级、更正链错误、无生效版本、适配器抽象。"""
from datetime import datetime, timezone

import pytest

from app.core.errors import ValidationError
from app.services.agent import extract, map_target, parse_relative_date
from app.services.progress import ProgressService
from app.services.provider import (BaseProvider, MockProvider, ProviderError,
                                   RealProvider, build_provider)

BASE = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)
CONCEPTS = [{"concept_id": 1, "name": "循环结构", "aliases": []},
            {"concept_id": 2, "name": "数组", "aliases": []}]


def login(client, user="alice", pwd="Passw0rd!"):
    d = client.post("/api/auth/login", json={"username": user, "password": pwd}).json()["data"]
    return {"Authorization": "Bearer " + d["token"]}, d["user_id"]


def confirmed_plan(client):
    from app.services.planner import PlannerService
    from app.services.version import VersionService
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
        "SELECT task_id FROM version_task WHERE version_id=1 ORDER BY task_id")]
    return h, uid, pid, tasks


def svc(client):
    return ProgressService(client.app.state.db, client.app.state.config)


# ---------------- agent 空输入与降级
def test_parse_empty_date_text():
    from datetime import date
    assert parse_relative_date("", date(2026, 11, 9)) is None


def test_map_empty_text():
    assert map_target("", CONCEPTS) == (None, [], "local", None)


def test_extract_marks_degraded_reason():
    """模型超时 → extract 把降级原因带回给界面。"""
    r = extract("那个循环的东西", {}, CONCEPTS, MockProvider(fail_mode="timeout"),
                BASE.date())
    assert r.degraded_reason == "TIMEOUT"
    assert r.candidates


# ---------------- 更正链错误分支
def test_note_cannot_correct(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    done = s.submit(pid, uid, tasks[0], "done", "k1", BASE, actual_minutes=30)
    with pytest.raises(ValidationError) as e:
        s.submit(pid, uid, tasks[0], "note", "k2", BASE,
                 corrects_event_id=done.event_id)
    assert e.value.field == "corrects_event_id"


def test_correction_requires_target(client):
    h, uid, pid, tasks = confirmed_plan(client)
    s = svc(client)
    s.submit(pid, uid, tasks[0], "done", "k1", BASE)
    with pytest.raises(ValidationError) as e:
        s.submit(pid, uid, tasks[0], "correction", "k2", BASE, actual_minutes=10)
    assert e.value.field == "corrects_event_id"


def test_correction_target_missing(client):
    h, uid, pid, tasks = confirmed_plan(client)
    with pytest.raises(ValidationError):
        svc(client).submit(pid, uid, tasks[0], "correction", "k1", BASE,
                           actual_minutes=10, corrects_event_id=9999)


# ---------------- 没有生效版本时的派生量
def test_metrics_when_plan_not_confirmed(client):
    h, uid = login(client)
    pid = client.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    s = svc(client)
    assert s.completion_rate(pid) == 0.0
    assert s.effective_minutes(pid, 1) is None
    p = s.progress(pid, uid, BASE)
    assert p.total_tasks == 0 and p.completion_rate == 0.0


def test_is_overdue_without_version(client):
    h, uid = login(client)
    pid = client.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    plan = client.app.state.db.query("SELECT * FROM study_plan WHERE plan_id=?", (pid,))[0]
    assert svc(client)._is_overdue(plan, BASE) is False


def test_completion_rate_zero_when_version_has_no_tasks(client):
    """空版本（无在范围内的任务）时完成率按 0 处理，不除零。"""
    h, uid, pid, tasks = confirmed_plan(client)
    db = client.app.state.db
    conn = db.connect()
    conn.execute(
        "INSERT INTO plan_version(plan_id,version_no,change_reason,change_note,"
        "snapshot_json,input_hash,engine_version,operator_id,created_at)"
        " VALUES(?,2,'manual','空版本','{}',?,'0.1.0',?, '2026-11-09T10:00:00Z')",
        (pid, "b" * 64, uid))
    conn.execute("UPDATE study_plan SET current_version = 2 WHERE plan_id = ?", (pid,))
    conn.commit()
    conn.close()
    assert svc(client).completion_rate(pid) == 0.0


# ---------------- 适配器抽象与降级
def test_base_provider_is_abstract():
    b = BaseProvider()
    assert b.probe() is True
    with pytest.raises(NotImplementedError):
        b.complete("x")


def test_mock_provider_unavailable_raises():
    with pytest.raises(ProviderError):
        MockProvider(fail_mode="unavailable").complete("x")


def test_build_provider_auto_when_probe_raises(monkeypatch):
    """探测抛异常也要降级到 mock，而不是把异常抛给调用方。"""
    def boom(self):
        raise ProviderError("probe failed")
    monkeypatch.setattr(RealProvider, "probe", boom)
    assert build_provider("auto", key="k").name == "mock"
