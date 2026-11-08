"""M5 · 确认与版本测试（对齐 D06 表 9.10 的用例）。"""
from datetime import datetime, timezone

import pytest

from app.core.errors import NotFound, StateError, VersionConflict
from app.services.planner import PlannerService
from app.services.version import VersionService

BASE = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)


def login(client, user="alice", pwd="Passw0rd!"):
    d = client.post("/api/auth/login", json={"username": user, "password": pwd}).json()["data"]
    return {"Authorization": "Bearer " + d["token"]}, d["user_id"]


def setup_draft(client):
    """登录 → 建计划 → 存约束 → 生成草案，返回 (headers, uid, pid, revision)。"""
    h, uid = login(client)
    pid = client.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    client.put("/api/plans/%d/constraint" % pid, headers=h, json={
        "target_concept_id": 2, "deadline": "2026-11-20",
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
        "base_time": "2026-11-09T09:00:00Z"})
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    return h, uid, pid, draft.revision


def svc(client):
    return VersionService(client.app.state.db, client.app.state.config)


# ---------------- 首次确认（T-09-01）
def test_first_confirm_creates_version(client):
    h, uid, pid, rev = setup_draft(client)
    r = svc(client).confirm(pid, rev, "key-1", uid, BASE)
    assert r.version_no == 1 and r.replayed is False
    row = client.app.state.db.query(
        "SELECT status, current_version FROM study_plan WHERE plan_id=?", (pid,))[0]
    assert row["status"] == "active" and row["current_version"] == 1


def test_confirm_writes_tasks_slices_and_report(client):
    h, uid, pid, rev = setup_draft(client)
    r = svc(client).confirm(pid, rev, "key-1", uid, BASE)
    db = client.app.state.db
    assert db.scalar("SELECT COUNT(*) FROM version_task WHERE version_id=?", (r.version_id,)) > 0
    assert db.scalar("SELECT COUNT(*) FROM task_slice WHERE version_id=?", (r.version_id,)) > 0
    assert db.scalar("SELECT COUNT(*) FROM plan_validation WHERE version_id=?",
                     (r.version_id,)) == 1


def test_task_identity_is_stable_across_versions(client):
    h, uid, pid, rev1 = setup_draft(client)
    svc(client).confirm(pid, rev1, "k1", uid, BASE)
    ids1 = {int(r["task_id"]) for r in client.app.state.db.query(
        "SELECT task_id FROM version_task WHERE version_id=1")}
    draft2 = PlannerService(client.app.state.db,
                            client.app.state.config).generate(pid, uid, BASE)
    r2 = svc(client).confirm(pid, draft2.revision, "k2", uid, BASE)
    ids2 = {int(r["task_id"]) for r in client.app.state.db.query(
        "SELECT task_id FROM version_task WHERE version_id=?", (r2.version_id,))}
    assert ids1 == ids2          # 稳定任务 ID 不因版本变化而重编


# ---------------- 幂等（T-09-02）
def test_repeat_with_same_key_replays(client):
    h, uid, pid, rev = setup_draft(client)
    a = svc(client).confirm(pid, rev, "same-key", uid, BASE)
    b = svc(client).confirm(pid, rev, "same-key", uid, BASE)
    assert b.replayed is True and b.version_no == a.version_no
    assert client.app.state.db.scalar(
        "SELECT COUNT(*) FROM plan_version WHERE plan_id=?", (pid,)) == 1


def test_repeat_with_new_key_rejected(client):
    h, uid, pid, rev = setup_draft(client)
    svc(client).confirm(pid, rev, "k1", uid, BASE)
    with pytest.raises(StateError) as e:
        svc(client).confirm(pid, rev, "k2", uid, BASE)
    assert e.value.code == "E1003"


# ---------------- 基线冲突（T-09-04..T-09-06）
def test_progress_revision_conflict(client):
    h, uid, pid, rev = setup_draft(client)
    db = client.app.state.db
    db.connect().execute("UPDATE study_plan SET progress_revision = 1 WHERE plan_id=?", (pid,)).connection.commit()
    with pytest.raises(VersionConflict) as e:
        svc(client).confirm(pid, rev, "k1", uid, BASE)
    assert e.value.code == "E2004"
    assert "progress_revision" in e.value.detail["conflicts"]


def test_content_revision_conflict(client):
    h, uid, pid, rev = setup_draft(client)
    h_admin, _ = login(client, "admin", "Admin123!")
    client.post("/api/courses/1/concepts", headers=h_admin,
                json={"name": "新点", "chapter": "第9章", "difficulty": 2,
                      "reference_minutes": 30})
    with pytest.raises(VersionConflict) as e:
        svc(client).confirm(pid, rev, "k1", uid, BASE)
    assert "content_revision" in e.value.detail["conflicts"]


def test_conflict_leaves_no_partial_version(client):
    h, uid, pid, rev = setup_draft(client)
    db = client.app.state.db
    db.connect().execute("UPDATE study_plan SET progress_revision = 5 WHERE plan_id=?", (pid,)).connection.commit()
    with pytest.raises(VersionConflict):
        svc(client).confirm(pid, rev, "k1", uid, BASE)
    assert db.scalar("SELECT COUNT(*) FROM plan_version WHERE plan_id=?", (pid,)) == 0
    assert db.scalar("SELECT COUNT(*) FROM plan_task WHERE plan_id=?", (pid,)) == 0


def test_only_one_of_two_confirm_attempts_wins(client):
    """模拟两个窗口同时确认：第二个用不同幂等键必然失败。"""
    h, uid, pid, rev = setup_draft(client)
    first = svc(client).confirm(pid, rev, "win-a", uid, BASE)
    with pytest.raises(StateError):
        svc(client).confirm(pid, rev, "win-b", uid, BASE)
    assert client.app.state.db.scalar(
        "SELECT COUNT(*) FROM plan_version WHERE plan_id=?", (pid,)) == 1


# ---------------- 归属与参数（T-09-03）
def test_missing_draft_is_404(client):
    h, uid, pid, rev = setup_draft(client)
    with pytest.raises(NotFound):
        svc(client).confirm(pid, 99, "k1", uid, BASE)


def test_other_students_draft_is_404(client):
    h, uid, pid, rev = setup_draft(client)
    h_admin, admin_id = login(client, "admin", "Admin123!")
    with pytest.raises(NotFound):
        svc(client).confirm(pid, rev, "k1", admin_id, BASE)


def test_empty_key_rejected(client):
    from app.core.errors import ValidationError
    h, uid, pid, rev = setup_draft(client)
    with pytest.raises(ValidationError):
        svc(client).confirm(pid, rev, "", uid, BASE)


# ---------------- HTTP 层
def test_http_confirm_and_list_versions(client):
    h, uid, pid, rev = setup_draft(client)
    r = client.post("/api/plans/%d/drafts/%d/confirm" % (pid, rev), headers=h,
                    json={"revision": rev})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["version_no"] == 1

    items = client.get("/api/plans/%d/versions" % pid, headers=h).json()["data"]["items"]
    assert len(items) == 1 and items[0]["tasks"] > 0


def test_http_confirm_without_key_generates_one(client):
    """未带 Idempotency-Key 时服务端生成：第一次成功，第二次因草案已消费而拒绝。"""
    h, uid, pid, rev = setup_draft(client)
    url = "/api/plans/%d/drafts/%d/confirm" % (pid, rev)
    first = client.post(url, headers=h, json={"revision": rev})
    assert first.status_code == 200, first.text
    second = client.post(url, headers=h, json={"revision": rev})
    assert second.status_code == 400
    assert second.json()["code"] == "E1003"


def test_http_idempotent_replay(client):
    h, uid, pid, rev = setup_draft(client)
    url = "/api/plans/%d/drafts/%d/confirm" % (pid, rev)
    a = client.post(url, headers={**h, "Idempotency-Key": "abc"}, json={"revision": rev})
    b = client.post(url, headers={**h, "Idempotency-Key": "abc"}, json={"revision": rev})
    assert a.json()["data"]["replayed"] is False
    assert b.json()["data"]["replayed"] is True


def test_http_diff_between_versions(client):
    h, uid, pid, rev1 = setup_draft(client)
    client.post("/api/plans/%d/drafts/%d/confirm" % (pid, rev1), headers={
        **h, "Idempotency-Key": "k1"}, json={"revision": rev1})
    draft2 = PlannerService(client.app.state.db,
                            client.app.state.config).generate(pid, uid, BASE)
    client.post("/api/plans/%d/drafts/%d/confirm" % (pid, draft2.revision), headers={
        **h, "Idempotency-Key": "k2"}, json={"revision": draft2.revision})
    d = client.get("/api/plans/%d/versions/1/diff?against=2" % pid, headers=h).json()["data"]
    assert set(d) == {"added", "removed", "moved", "resized"}


def test_http_diff_missing_version_404(client):
    h, uid, pid, rev = setup_draft(client)
    client.post("/api/plans/%d/drafts/%d/confirm" % (pid, rev), headers={
        **h, "Idempotency-Key": "k1"}, json={"revision": rev})
    assert client.get("/api/plans/%d/versions/1/diff?against=9" % pid,
                      headers=h).status_code == 404
