"""M5 · 补齐分支：校验拒绝、基线冲突、差异四类、归属。"""
import json
from datetime import datetime, timezone

import pytest

from app.core.errors import NotFound, StateError, VersionConflict
from app.services.capacity import Interval
from app.services.planner import PlannerService, Task
from app.services.validation import check_deadline, check_tight
from app.services.version import VersionService

BASE = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)


def login(client, user="alice", pwd="Passw0rd!"):
    d = client.post("/api/auth/login", json={"username": user, "password": pwd}).json()["data"]
    return {"Authorization": "Bearer " + d["token"]}, d["user_id"]


def setup_draft(client):
    h, uid = login(client)
    pid = client.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    client.put("/api/plans/%d/constraint" % pid, headers=h, json={
        "target_concept_id": 2, "deadline": "2026-11-20",
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
        "base_time": "2026-11-09T09:00:00Z"})
    draft = PlannerService(client.app.state.db,
                           client.app.state.config).generate(pid, uid, BASE)
    return h, uid, pid, draft.revision


def vsvc(client):
    return VersionService(client.app.state.db, client.app.state.config)


# ---------------- validation 空输入分支
def test_check_deadline_with_no_slices():
    from datetime import date
    assert check_deadline([], date(2026, 11, 20)) == []


def test_check_tight_with_zero_capacity():
    assert check_tight([Task(1, "study", 60)], 0, 0.8) == []


# ---------------- 确认前重算校验
def test_confirm_rejects_invalid_payload(client):
    """绕过引擎直接改草案：片落在可用时段外 → 确认被拒。"""
    h, uid, pid, rev = setup_draft(client)
    db = client.app.state.db
    row = db.query("SELECT draft_id, payload_json FROM plan_draft"
                   " WHERE plan_id=? AND revision=?", (pid, rev))[0]
    payload = json.loads(row["payload_json"])
    payload["slices"][0]["start"] = "2026-11-09T03:00"
    payload["slices"][0]["end"] = "2026-11-09T04:00"
    conn = db.connect()
    conn.execute("UPDATE plan_draft SET payload_json=? WHERE draft_id=?",
                 (json.dumps(payload), row["draft_id"]))
    conn.commit()
    conn.close()

    with pytest.raises(StateError) as e:
        vsvc(client).confirm(pid, rev, "k1", uid, BASE)
    assert e.value.code == "E1003"
    assert e.value.detail["issues"]


# ---------------- 基线：current_version 冲突
def test_current_version_conflict(client):
    h, uid, pid, rev1 = setup_draft(client)
    vsvc(client).confirm(pid, rev1, "k1", uid, BASE)          # v1 生效
    draft2 = PlannerService(client.app.state.db,
                            client.app.state.config).generate(pid, uid, BASE)
    # v1 之后又冒出一个 v2（模拟别处已确认）→ 草案 2 的 base_version 落后
    db = client.app.state.db
    conn = db.connect()
    conn.execute(
        "INSERT INTO plan_version(plan_id,version_no,change_reason,change_note,"
        "snapshot_json,input_hash,engine_version,operator_id,created_at)"
        " VALUES(?,2,'manual','并发确认','{}',?,'0.1.0',?, '2026-11-09T10:00:00Z')",
        (pid, "a" * 64, uid))
    conn.execute("UPDATE study_plan SET current_version=2 WHERE plan_id=?", (pid,))
    conn.commit()
    conn.close()

    with pytest.raises(VersionConflict) as e:
        vsvc(client).confirm(pid, draft2.revision, "k2", uid, BASE)
    assert "current_version" in e.value.detail["conflicts"]


# ---------------- 差异四类
def test_diff_reports_moved(client):
    """基准时刻推后一天 → 所有片顺移，差异应报 moved。"""
    h, uid, pid, rev1 = setup_draft(client)
    vsvc(client).confirm(pid, rev1, "k1", uid, BASE)

    later = datetime(2026, 11, 10, 9, tzinfo=timezone.utc)
    draft2 = PlannerService(client.app.state.db,
                            client.app.state.config).generate(pid, uid, later)
    r = vsvc(client).confirm(pid, draft2.revision, "k2", uid, BASE)
    assert r.diff["moved"], "整体顺移应被识别为 moved"
    assert r.diff["added"] == [] and r.diff["removed"] == []


def test_diff_reports_resized(client):
    """任务时长减少 5 分钟且同步缩短对应末片 → 差异应报 resized。"""
    h, uid, pid, rev1 = setup_draft(client)
    vsvc(client).confirm(pid, rev1, "k1", uid, BASE)
    draft2 = PlannerService(client.app.state.db,
                            client.app.state.config).generate(pid, uid, BASE)
    db = client.app.state.db
    row = db.query("SELECT draft_id, payload_json FROM plan_draft"
                   " WHERE plan_id=? AND revision=?", (pid, draft2.revision))[0]
    payload = json.loads(row["payload_json"])

    target = payload["tasks"][0]
    key = (target["concept_id"], target["kind"])
    target["minutes"] = max(1, target["minutes"] - 5)
    # 把该任务的末片缩短 5 分钟，保持"片总时长 = 任务时长"
    mine = [s for s in payload["slices"]
            if (s["concept_id"], s["kind"]) == key]
    last = mine[-1]
    end_dt = datetime.strptime(last["end"], "%Y-%m-%dT%H:%M")
    last["end"] = (end_dt.replace(second=0)).__sub__(
        __import__("datetime").timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")

    conn = db.connect()
    conn.execute("UPDATE plan_draft SET payload_json=? WHERE draft_id=?",
                 (json.dumps(payload), row["draft_id"]))
    conn.commit()
    conn.close()

    r = vsvc(client).confirm(pid, draft2.revision, "k2", uid, BASE)
    assert r.diff["resized"], "时长变化应被识别为 resized"


def test_diff_added_when_target_grows(client):
    h, uid, pid, rev1 = setup_draft(client)
    vsvc(client).confirm(pid, rev1, "k1", uid, BASE)
    # 增加附加目标 → 草案多出任务 → added
    client.put("/api/plans/%d/constraint" % pid, headers=h, json={
        "target_concept_id": 2, "extra_concept_ids": [3], "deadline": "2026-11-20",
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
        "base_time": "2026-11-09T09:00:00Z"})
    draft2 = PlannerService(client.app.state.db,
                            client.app.state.config).generate(pid, uid, BASE)
    r = vsvc(client).confirm(pid, draft2.revision, "k2", uid, BASE)
    assert r.diff["added"] or r.diff["moved"]


# ---------------- 归属
def test_list_versions_unknown_plan_404(client):
    h, uid = login(client)
    with pytest.raises(NotFound):
        vsvc(client).list_versions(999, uid)


def test_diff_unknown_plan_404(client):
    h, uid = login(client)
    with pytest.raises(NotFound):
        vsvc(client).diff(999, uid, 1, 2)


def test_list_versions_of_other_student_404(client):
    h, uid, pid, rev = setup_draft(client)
    vsvc(client).confirm(pid, rev, "k1", uid, BASE)
    _, admin_id = login(client, "admin", "Admin123!")
    with pytest.raises(NotFound):
        vsvc(client).list_versions(pid, admin_id)
