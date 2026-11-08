"""M7 · 看板与草案接口测试（对应 D06 第 11 章）。"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import NotFound
from app.services.board import BoardService
from app.services.planner import PlannerService
from app.services.version import VersionService

BASE = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)


def login(client, user="alice", pwd="Passw0rd!"):
    d = client.post("/api/auth/login", json={"username": user, "password": pwd}).json()["data"]
    return {"Authorization": "Bearer " + d["token"]}, d["user_id"]


def make_plan(client, headers):
    return client.post("/api/plans", headers=headers,
                       json={"course_id": 1}).json()["data"]["plan_id"]


def set_constraint(client, headers, pid, **kw):
    body = {"target_concept_id": 2, "deadline": "2026-11-20",
            "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
            "base_time": "2026-11-09T09:00:00Z"}
    body.update(kw)
    return client.put("/api/plans/%d/constraint" % pid, headers=headers, json=body)


def confirmed(client):
    h, uid = login(client)
    pid = make_plan(client, h)
    set_constraint(client, h, pid)
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    VersionService(client.app.state.db,
                   client.app.state.config).confirm(pid, draft.revision, "k1", uid, BASE)
    return h, uid, pid


def svc(client):
    return BoardService(client.app.state.db, client.app.state.config)


# ---------------- 无版本
def test_board_without_version(client):
    h, uid = login(client)
    pid = make_plan(client, h)
    data = svc(client).build(pid, uid, BASE)
    assert data["version_no"] is None and data["tasks"] == []
    assert data["progress"]["total_tasks"] == 0


# ---------------- 正常看板
def test_board_lists_tasks_with_names(client):
    h, uid, pid = confirmed(client)
    data = svc(client).build(pid, uid, BASE)
    assert data["version_no"] == 1 and data["readonly"] is False
    assert data["tasks"] and all(t["concept_name"] for t in data["tasks"])
    assert all(t["start"] < t["end"] for t in data["tasks"])


def test_board_progress_numbers(client):
    h, uid, pid = confirmed(client)
    data = svc(client).build(pid, uid, BASE)
    p = data["progress"]
    assert p["total_tasks"] == len({t["task_id"] for t in data["tasks"]})
    assert p["completion_rate"] == 0.0
    assert p["planned_minutes"] == sum(t["minutes"] for t in data["tasks"])


def test_board_marks_done_after_checkin(client):
    h, uid, pid = confirmed(client)
    first = svc(client).build(pid, uid, BASE)["tasks"][0]
    client.post("/api/plans/%d/events" % pid, headers={**h, "Idempotency-Key": "e1"},
                json={"task_id": first["task_id"], "event_type": "done",
                      "actual_minutes": 30})
    data = svc(client).build(pid, uid, BASE)
    done = [t for t in data["tasks"] if t["task_id"] == first["task_id"]]
    assert done and all(t["done"] for t in done)
    assert data["progress"]["done_tasks"] == 1
    assert data["progress"]["completion_rate"] > 0


def test_board_marks_overdue_after_time_passes(client):
    h, uid, pid = confirmed(client)
    later = BASE + timedelta(days=60)
    data = svc(client).build(pid, uid, later)
    assert data["progress"]["overdue_tasks"]
    assert any(t["overdue"] for t in data["tasks"])


def test_board_readonly_for_old_version(client):
    h, uid, pid = confirmed(client)
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    VersionService(client.app.state.db,
                   client.app.state.config).confirm(pid, draft.revision, "k2", uid, BASE)

    current = svc(client).build(pid, uid, BASE)
    old = svc(client).build(pid, uid, BASE, version_no=1)
    assert current["version_no"] == 2 and current["readonly"] is False
    assert old["readonly"] is True
    # 历史版本不标逾期
    assert all(not t["overdue"] for t in old["tasks"])


def test_board_issue_codes_attached(client):
    """确认时保存的 INFO（孤点）会挂到对应知识点的片上。"""
    h, uid = login(client)
    pid = make_plan(client, h)
    set_constraint(client, h, pid, extra_concept_ids=[3])
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    VersionService(client.app.state.db, client.app.state.config).confirm(
        pid, draft.revision, "k1", uid, BASE)
    data = svc(client).build(pid, uid, BASE)
    assert any(i["code"] == "ISOLATED_CONCEPT" for i in data["issues"])
    c3 = [t for t in data["tasks"] if t["concept_id"] == 3]
    assert c3 and "ISOLATED_CONCEPT" in c3[0]["issue_codes"]


# ---------------- 未排入
def test_board_lists_unscheduled(client):
    """版本里存在未排入任务时，看板单列出来（读路径，含历史数据）。"""
    h, uid, pid = confirmed(client)
    db = client.app.state.db
    conn = db.connect()
    conn.execute(
        "INSERT INTO plan_version(plan_id,version_no,change_reason,change_note,"
        "snapshot_json,input_hash,engine_version,operator_id,created_at)"
        " VALUES(?,2,'manual','含未排入','{}',?,'0.1.0',?,'2026-11-09T11:00:00Z')",
        (pid, "c" * 64, uid))
    vid = conn.execute("SELECT version_id FROM plan_version WHERE plan_id=? AND version_no=2",
                       (pid,)).fetchone()[0]
    tid = conn.execute("SELECT task_id FROM plan_task WHERE plan_id=? LIMIT 1",
                       (pid,)).fetchone()[0]
    conn.execute("INSERT INTO version_task(version_id,task_id,plan_id,in_scope,frozen,"
                 "original_minutes,estimated_minutes,schedule_state)"
                 " VALUES(?,?,?,1,0,60,60,'unscheduled')", (vid, tid, pid))
    conn.execute("UPDATE study_plan SET current_version=2 WHERE plan_id=?", (pid,))
    conn.commit()
    conn.close()

    data = svc(client).build(pid, uid, BASE)
    assert data["unscheduled"] and data["unscheduled"][0]["reason"] == "CAPACITY"


# ---------------- 归属与版本
def test_board_other_student_404(client):
    h, uid, pid = confirmed(client)
    _, admin_id = login(client, "admin", "Admin123!")
    with pytest.raises(NotFound):
        svc(client).build(pid, admin_id, BASE)


def test_board_unknown_version_404(client):
    h, uid, pid = confirmed(client)
    with pytest.raises(NotFound):
        svc(client).build(pid, uid, BASE, version_no=99)


# ---------------- HTTP 路由
def test_http_board(client):
    h, uid, pid = confirmed(client)
    r = client.get("/api/plans/%d/board" % pid, headers=h)
    assert r.status_code == 200
    assert r.json()["data"]["version_no"] == 1


def test_http_board_with_version_param(client):
    h, uid, pid = confirmed(client)
    r = client.get("/api/plans/%d/board?version=1" % pid, headers=h)
    assert r.status_code == 200 and r.json()["data"]["readonly"] is False


def test_http_generate_draft(client):
    h, uid = login(client)
    pid = make_plan(client, h)
    set_constraint(client, h, pid)
    r = client.post("/api/plans/%d/drafts" % pid, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["revision"] == 1 and d["tasks"] and "report" in d
    assert d["metrics"]["total_minutes"] > 0


def test_http_generate_requires_constraint(client):
    h, uid = login(client)
    pid = make_plan(client, h)
    r = client.post("/api/plans/%d/drafts" % pid, headers=h)
    assert r.status_code == 400
    assert r.json()["code"] == "E1003"


def test_http_get_draft(client):
    h, uid = login(client)
    pid = make_plan(client, h)
    set_constraint(client, h, pid)
    client.post("/api/plans/%d/drafts" % pid, headers=h)
    r = client.get("/api/plans/%d/drafts/1" % pid, headers=h)
    assert r.status_code == 200
    assert r.json()["data"]["tasks"]


def test_http_get_missing_draft_404(client):
    h, uid = login(client)
    pid = make_plan(client, h)
    assert client.get("/api/plans/%d/drafts/9" % pid, headers=h).status_code == 404


def test_http_get_draft_of_other_student_404(client):
    h, uid = login(client)
    pid = make_plan(client, h)
    set_constraint(client, h, pid)
    client.post("/api/plans/%d/drafts" % pid, headers=h)
    h_admin, _ = login(client, "admin", "Admin123!")
    assert client.get("/api/plans/%d/drafts/1" % pid,
                      headers=h_admin).status_code == 404

def test_http_list_plans(client):
    h, uid = login(client)
    pid = make_plan(client, h)
    items = client.get("/api/plans", headers=h).json()["data"]["items"]
    assert items and items[0]["plan_id"] == pid
    assert items[0]["status"] == "draft"

def test_http_list_plans_only_mine(client):
    h, uid = login(client)
    make_plan(client, h)
    h_admin, _ = login(client, "admin", "Admin123!")
    assert client.get("/api/plans", headers=h_admin).json()["data"]["items"] == []


def test_board_exposes_slice_position(client):
    """同一任务被切成多片时，前端要知道这是第几片（含总片数）。"""
    h, uid, pid = confirmed(client)
    db = client.app.state.db
    conn = db.connect()
    conn.execute(
        "INSERT INTO plan_version(plan_id,version_no,change_reason,change_note,"
        "snapshot_json,input_hash,engine_version,operator_id,created_at)"
        " VALUES(?,2,'manual','多片版本','{}',?,'0.1.0',?,'2026-11-09T12:00:00Z')",
        (pid, "d" * 64, uid))
    vid = conn.execute("SELECT version_id FROM plan_version WHERE plan_id=? AND version_no=2",
                       (pid,)).fetchone()[0]
    tid = conn.execute("SELECT task_id FROM plan_task WHERE plan_id=? LIMIT 1",
                       (pid,)).fetchone()[0]
    conn.execute("INSERT INTO version_task(version_id,task_id,plan_id,in_scope,frozen,"
                 "original_minutes,estimated_minutes,schedule_state)"
                 " VALUES(?,?,?,1,0,180,180,'scheduled')", (vid, tid, pid))
    start_epoch = 1794250800          # 2026-11-09 19:00 本地时间附近的整分钟
    for index, minutes in [(1, 120), (2, 60)]:
        conn.execute("INSERT INTO task_slice(version_id,task_id,slice_no,start_epoch,end_epoch)"
                     " VALUES(?,?,?,?,?)",
                     (vid, tid, index, start_epoch + (index - 1) * 7200,
                      start_epoch + (index - 1) * 7200 + minutes * 60))
    conn.execute("UPDATE study_plan SET current_version=2 WHERE plan_id=?", (pid,))
    conn.commit()
    conn.close()

    data = svc(client).build(pid, uid, BASE)
    rows = [t for t in data["tasks"] if t["task_id"] == tid]
    assert [r["slice_no"] for r in rows] == [1, 2]
    assert all(r["slice_total"] == 2 for r in rows)


def test_http_draft_tasks_carry_concept_names(client):
    """草案里的任务要带知识点名称，界面不能只显示 ID。"""
    h, uid = login(client)
    pid = make_plan(client, h)
    set_constraint(client, h, pid)
    data = client.post("/api/plans/%d/drafts" % pid, headers=h).json()["data"]
    assert data["tasks"] and all(task["name"] for task in data["tasks"])
    assert all(slice_["name"] for slice_ in data["slices"])
