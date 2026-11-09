"""M2 · 课程内容管理测试（对齐 D06 表 4.6 的 12 条用例）。"""
import pytest

from app.core.errors import NotFound, PrereqCycle, StateError, ValidationError
from app.services.content import ConceptInput, ContentService, detect_cycle

NOW = __import__("datetime").datetime(2026, 11, 8, 12, tzinfo=__import__("datetime").timezone.utc)


@pytest.fixture()
def svc(seeded):
    return ContentService(seeded)


def make(name, **kw):
    d = dict(name=name, chapter="第1章", difficulty=3, reference_minutes=60)
    d.update(kw)
    return ConceptInput(**d)


# ---------------- 环检测（纯函数）
def test_detect_cycle_none():
    assert detect_cycle([(1, 2), (2, 3)], [1, 2, 3]) is None


def test_detect_cycle_found():
    cyc = detect_cycle([(1, 2), (2, 3), (3, 1)], [1, 2, 3])
    assert cyc is not None
    assert cyc[0] == cyc[-1]


def test_detect_cycle_self_loop():
    assert detect_cycle([(1, 1)], [1]) == [1, 1]


def test_detect_cycle_ignores_disconnected():
    assert detect_cycle([(1, 2)], [1, 2, 3, 4]) is None


# ---------------- 知识点（T-02-01..T-02-03）
def test_save_concept_ok(svc):
    cid = svc.save_concept(1, make("栈"))
    assert cid > 0
    assert any(r["name"] == "栈" for r in svc.list_concepts(1))


def test_duplicate_name_rejected(svc):
    svc.save_concept(1, make("栈"))
    with pytest.raises(ValidationError) as e:
        svc.save_concept(1, make("栈"))
    assert e.value.field == "name"


def test_minutes_out_of_range(svc):
    with pytest.raises(ValidationError) as e:
        svc.save_concept(1, make("队列", reference_minutes=601))
    assert e.value.field == "reference_minutes"


def test_difficulty_out_of_range(svc):
    with pytest.raises(ValidationError):
        svc.save_concept(1, make("图", difficulty=6))


def test_content_revision_increments(svc, seeded):
    before = seeded.scalar("SELECT content_revision FROM course WHERE course_id=1")
    svc.save_concept(1, make("栈"))
    after = seeded.scalar("SELECT content_revision FROM course WHERE course_id=1")
    assert after == before + 1


# ---------------- 先修（T-02-04..T-02-08）
def test_self_loop_rejected(svc):
    with pytest.raises(ValidationError) as e:
        svc.submit_prereqs(1, [(1, 1)])
    assert "自环" in e.value.message


def test_concept_not_in_course_rejected(svc):
    """两端必须属于本课程；schema 用 ux_single_course 保证只有一门课程。"""
    with pytest.raises(ValidationError) as e:
        svc.submit_prereqs(1, [(1, 999)])
    assert "不属于本课程" in e.value.message


def test_duplicate_edges_deduped(svc):
    n = svc.submit_prereqs(1, [(1, 2), (1, 2)])
    assert n == 1
    assert len(svc.list_prereqs(1)) == 1


def test_cycle_in_batch_rejected(svc):
    svc.submit_prereqs(1, [(1, 2), (2, 3)])
    with pytest.raises(PrereqCycle) as e:
        svc.submit_prereqs(1, [(3, 1)])
    assert e.value.code == "E2001"
    assert e.value.detail["cycle"][0] == e.value.detail["cycle"][-1]


def test_batch_atomic_on_cycle(svc):
    svc.submit_prereqs(1, [(1, 2)])
    with pytest.raises(PrereqCycle):
        svc.submit_prereqs(1, [(2, 3), (3, 1)])
    names = {(r["from_concept_id"], r["to_concept_id"]) for r in svc.list_prereqs(1)}
    assert names == {(1, 2)}          # 整批回滚，未残留


def test_batch_size_limit(svc):
    with pytest.raises(ValidationError):
        svc.submit_prereqs(1, [(1, 2)] * 41)


# ---------------- 停用与影响（T-02-09、T-02-10）
def test_disable_keeps_row(svc, seeded):
    svc.disable_concept(2)
    status = seeded.scalar("SELECT status FROM concept WHERE concept_id=2")
    assert status == "disabled"
    assert all(r["concept_id"] != 2 for r in svc.list_concepts(1))
    assert any(r["concept_id"] == 2 for r in svc.list_concepts(1, True))


def test_impact_unknown_concept_is_zero(svc):
    assert svc.impact_of(999)["version_task_refs"] == 0


def test_disable_missing_concept_404(svc):
    with pytest.raises(NotFound):
        svc.disable_concept(999)


# ---------------- HTTP 层
@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient
    from app.core.security import hash_password
    from app.main import create_app
    app = create_app({"DB_PATH": str(tmp_path / "t.db"), "LOG_LEVEL": "ERROR",
                      "SECRET_KEY": "s"})
    conn = app.state.db.connect()
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('admin',?,'admin','2026-01-01T00:00:00Z')", (hash_password("A1!aaaaa"),))
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('alice',?,'student','2026-01-01T00:00:00Z')", (hash_password("A1!aaaaa"),))
    conn.execute("INSERT INTO course(maintainer_id,name,semester,total_hours,status)"
                 " VALUES(1,'软件工程','2026秋',48,'enabled')")
    conn.commit()
    conn.close()
    return TestClient(app, raise_server_exceptions=False)


def token_of(client, user="admin"):
    r = client.post("/api/auth/login", json={"username": user, "password": "A1!aaaaa"})
    return r.json()["data"]["token"]


def auth(t):
    return {"Authorization": "Bearer " + t}


def test_http_only_admin_can_write(client):
    t_admin = token_of(client, "admin")
    t_student = token_of(client, "alice")
    body = {"name": "循环结构", "chapter": "第3章", "difficulty": 3, "reference_minutes": 60}
    assert client.post("/api/courses/1/concepts", json=body,
                       headers=auth(t_student)).status_code == 403
    r = client.post("/api/courses/1/concepts", json=body, headers=auth(t_admin))
    assert r.status_code == 200


def test_http_concept_validation_field(client):
    t = token_of(client)
    r = client.post("/api/courses/1/concepts", headers=auth(t),
                    json={"name": "x", "chapter": "c", "difficulty": 9,
                          "reference_minutes": 60})
    assert r.status_code == 400
    assert r.json()["field"] == "difficulty"


def test_http_prereq_cycle_returns_e2001(client):
    t = token_of(client)
    for name in ["A", "B", "C"]:
        client.post("/api/courses/1/concepts", headers=auth(t),
                    json={"name": name, "chapter": "第1章", "difficulty": 2,
                          "reference_minutes": 30})
    ids = [c["concept_id"] for c in
           client.get("/api/courses/1/concepts").json()["data"]["items"]]
    a, b, c = ids[:3]
    assert client.post("/api/courses/1/prerequisites/batch", headers=auth(t),
                       json={"edges": [[a, b], [b, c]]}).status_code == 200
    r = client.post("/api/courses/1/prerequisites/batch", headers=auth(t),
                    json={"edges": [[c, a]]})
    assert r.status_code == 422
    assert r.json()["code"] == "E2001"


def test_create_course_ok(db):
    conn = db.connect()
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('admin','x','admin','2026-01-01T00:00:00Z')")
    conn.commit()
    conn.close()
    svc = ContentService(db)
    cid = svc.create_course(1, "新课程", "2027春", 36)
    assert cid > 0
    assert [c["name"] for c in svc.list_courses()] == ["新课程"]


def test_second_course_rejected(seeded, svc):
    with pytest.raises(StateError) as e:
        svc.create_course(2, "另一门", "2027春", 36)
    assert "只支持一门课程" in e.value.message


def test_create_course_rejects_bad_hours(svc):
    with pytest.raises(ValidationError) as e:
        svc.create_course(2, "x", "2027春", 0)
    assert e.value.field == "total_hours"


def test_get_missing_course_404(svc):
    with pytest.raises(NotFound):
        svc.get_course(999)

# ---------------- 课程编辑与停用（D02 AT-04）
def test_update_course_fields(svc):
    row = svc.update_course(1, name="软件工程实训（改）", total_hours=64, description="新的简介")
    assert row["name"] == "软件工程实训（改）"
    assert row["total_hours"] == 64

def test_update_course_rejects_bad_hours(svc):
    with pytest.raises(ValidationError) as e:
        svc.update_course(1, total_hours=0)
    assert e.value.field == "total_hours"

def test_update_course_requires_a_field(svc):
    with pytest.raises(ValidationError):
        svc.update_course(1)

def test_disable_course_blocks_new_plans(client):
    h_admin = auth(token_of(client, "admin"))
    assert client.post("/api/courses/1/disable", headers=h_admin).status_code == 200
    h = auth(token_of(client, "alice"))
    r = client.post("/api/plans", headers=h, json={"course_id": 1})
    assert r.status_code == 400
    assert r.json()["field"] == "course_id"


def test_http_patch_course(client):
    h_admin = auth(token_of(client, "admin"))
    r = client.patch("/api/courses/1", headers=h_admin, json={"total_hours": 72})
    assert r.status_code == 200
    assert r.json()["data"]["total_hours"] == 72


def test_student_cannot_patch_course(client):
    h = auth(token_of(client, "alice"))
    assert client.patch("/api/courses/1", headers=h, json={"total_hours": 72}).status_code == 403

def test_update_course_rejects_long_name(svc):
    with pytest.raises(ValidationError) as e:
        svc.update_course(1, name="课" * 101)
    assert e.value.field == "name"

def test_update_course_rejects_long_description(svc):
    with pytest.raises(ValidationError) as e:
        svc.update_course(1, description="x" * 2001)
    assert e.value.field == "description"
