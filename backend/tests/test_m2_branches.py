"""M2 · 补齐分支测试：校验拒绝路径、排序、影响查询、停用路由。"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.errors import StateError, Unauthorized, ValidationError
from app.core.security import Claims, hash_password, issue_token, parse_token
from app.services.auth import AuthService, to_iso
from app.services.content import ConceptInput, ContentService

NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)


def make(name, **kw):
    d = dict(name=name, chapter="第1章", difficulty=3, reference_minutes=60)
    d.update(kw)
    return ConceptInput(**d)


# ---------------- content：校验拒绝路径
def test_create_course_rejects_blank_name(svc):
    with pytest.raises(ValidationError) as e:
        svc.create_course(2, "", "2027春", 36)
    assert e.value.field == "name"


def test_create_course_rejects_too_long_name(svc):
    with pytest.raises(ValidationError) as e:
        svc.create_course(2, "课" * 101, "2027春", 36)
    assert e.value.field == "name"


def test_concept_rejects_blank_name(svc):
    with pytest.raises(ValidationError) as e:
        svc.save_concept(1, make(""))
    assert e.value.field == "name"


def test_concept_rejects_blank_chapter(svc):
    with pytest.raises(ValidationError) as e:
        svc.save_concept(1, make("栈", chapter=""))
    assert e.value.field == "chapter"


def test_submit_empty_batch_rejected(svc):
    with pytest.raises(ValidationError) as e:
        svc.submit_prereqs(1, [])
    assert e.value.field == "batch"


def test_resubmit_same_edge_is_noop(svc):
    """已存在的边再提交一次：不重复插入，也不报错。"""
    assert svc.submit_prereqs(1, [(1, 2)]) == 1
    assert svc.submit_prereqs(1, [(1, 2)]) == 1     # 返回值是入参条数
    rows = svc.list_prereqs(1)
    assert len(rows) == 1


# ---------------- content：排序与影响
def test_list_prereqs_is_ordered(svc, seeded):
    """乱序提交后，查询必须按 (from, to) 升序返回。"""
    svc.submit_prereqs(1, [(2, 3), (1, 3), (1, 2)])
    rows = svc.list_prereqs(1)
    pairs = [(r["from_concept_id"], r["to_concept_id"]) for r in rows]
    assert pairs == sorted(pairs) == [(1, 2), (1, 3), (2, 3)]


def test_list_concepts_ordered_by_id(svc):
    svc.save_concept(1, make("栈"))
    ids = [r["concept_id"] for r in svc.list_concepts(1)]
    assert ids == sorted(ids)


def test_disable_returns_impact_dict(svc):
    svc.disable_concept(2)
    impact = svc.impact_of(2)
    assert set(impact) == {"version_task_refs"}


# ---------------- auth：可用性校验
def test_ensure_enabled_rejects_disabled(seeded, cfg):
    conn = seeded.connect()
    conn.execute("UPDATE app_user SET status='disabled' WHERE username='alice'")
    conn.commit()
    conn.close()
    svc = AuthService(seeded, cfg)
    uid = seeded.scalar("SELECT user_id FROM app_user WHERE username='alice'")
    with pytest.raises(StateError) as e:
        svc.ensure_enabled(uid)
    assert e.value.code == "E1003"


def test_ensure_enabled_missing_user(seeded, cfg):
    with pytest.raises(StateError):
        AuthService(seeded, cfg).ensure_enabled(999)


def test_to_iso_roundtrip():
    text = to_iso(NOW)
    assert text == "2026-11-08T12:00:00Z"


# ---------------- security：属性与坏载荷
def test_claims_expires_at(cfg):
    token, exp = issue_token(1, "student", NOW, cfg)
    claims = parse_token(token, NOW, cfg)
    assert claims.expires_at == exp


def test_token_payload_missing_fields(cfg):
    import base64, json
    body = base64.urlsafe_b64encode(json.dumps({"role": "student"}).encode()).decode().rstrip("=")
    from app.core.security import _sign
    token = body + "." + _sign(cfg.SECRET_KEY, body)
    with pytest.raises(Unauthorized):
        parse_token(token, NOW, cfg)


def test_token_payload_not_json(cfg):
    import base64
    from app.core.security import _sign
    body = base64.urlsafe_b64encode(b"not-json").decode().rstrip("=")
    token = body + "." + _sign(cfg.SECRET_KEY, body)
    with pytest.raises(Unauthorized):
        parse_token(token, NOW, cfg)


# ---------------- HTTP：列表、建课、先修、影响、停用
@pytest.fixture()
def client(tmp_path):
    from app.main import create_app
    app = create_app({"DB_PATH": str(tmp_path / "t.db"), "LOG_LEVEL": "ERROR",
                      "SECRET_KEY": "s"})
    conn = app.state.db.connect()
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('admin',?,'admin','2026-01-01T00:00:00Z')",
                 (hash_password("Admin123!"),))
    conn.commit()
    conn.close()
    return TestClient(app, raise_server_exceptions=False)


def auth_headers(client):
    t = client.post("/api/auth/login",
                    json={"username": "admin", "password": "Admin123!"}).json()["data"]["token"]
    return {"Authorization": "Bearer " + t}


def test_http_create_course_and_list(client):
    h = auth_headers(client)
    r = client.post("/api/courses", headers=h,
                    json={"name": "软件工程", "semester": "2026秋", "total_hours": 48})
    assert r.status_code == 200
    cid = r.json()["data"]["course_id"]
    items = client.get("/api/courses").json()["data"]["items"]
    assert [c["course_id"] for c in items] == [cid]


def test_http_create_second_course_409(client):
    h = auth_headers(client)
    client.post("/api/courses", headers=h,
                json={"name": "第一门", "semester": "2026秋", "total_hours": 48})
    r = client.post("/api/courses", headers=h,
                    json={"name": "第二门", "semester": "2026秋", "total_hours": 48})
    assert r.status_code == 400
    assert r.json()["code"] == "E1003"


def test_http_prereq_list_after_batch(client):
    h = auth_headers(client)
    cid = client.post("/api/courses", headers=h, json={
        "name": "课", "semester": "2026秋", "total_hours": 48}).json()["data"]["course_id"]
    ids = []
    for n in ["A", "B"]:
        ids.append(client.post("/api/courses/%d/concepts" % cid, headers=h, json={
            "name": n, "chapter": "c1", "difficulty": 2,
            "reference_minutes": 30}).json()["data"]["concept_id"])
    client.post("/api/courses/%d/prerequisites/batch" % cid, headers=h,
                json={"edges": [[ids[0], ids[1]]]})
    items = client.get("/api/courses/%d/prerequisites" % cid).json()["data"]["items"]
    assert items == [{"from_concept_id": ids[0], "to_concept_id": ids[1]}]


def test_http_impact_and_disable(client):
    h = auth_headers(client)
    cid = client.post("/api/courses", headers=h, json={
        "name": "课", "semester": "2026秋", "total_hours": 48}).json()["data"]["course_id"]
    kid = client.post("/api/courses/%d/concepts" % cid, headers=h, json={
        "name": "A", "chapter": "c1", "difficulty": 2,
        "reference_minutes": 30}).json()["data"]["concept_id"]

    impact = client.get("/api/concepts/%d/impact" % kid).json()["data"]
    assert impact == {"version_task_refs": 0}

    r = client.post("/api/concepts/%d/disable" % kid, headers=h)
    assert r.status_code == 200
    assert r.json()["data"] == {"version_task_refs": 0}
    listed = client.get("/api/courses/%d/concepts" % cid).json()["data"]["items"]
    assert listed == []
