"""M2 · 认证单元与接口测试（对齐 D06 表 3.9 的 11 条用例）。"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.errors import Forbidden, NotFound, Unauthorized
from app.core.security import (Claims, hash_password, issue_token, parse_token,
                               verify_password)
from app.main import create_app
from app.services.auth import AuthService

NOW = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def cfg():
    from app.core import config as C
    return C.load({"DB_PATH": ":memory:", "SECRET_KEY": "test-secret"})


@pytest.fixture()
def svc(seeded, cfg):
    conn = seeded.connect()
    conn.execute("UPDATE app_user SET password_hash = ? WHERE username='alice'",
                 (hash_password("Passw0rd!"),))
    conn.execute("UPDATE app_user SET password_hash = ? WHERE username='admin'",
                 (hash_password("Admin123!"),))
    conn.commit()
    conn.close()
    return AuthService(seeded, cfg)


@pytest.fixture()
def client(tmp_path):
    from app.core.security import hash_password as hp
    app = create_app({"DB_PATH": str(tmp_path / "t.db"), "LOG_LEVEL": "ERROR",
                      "SECRET_KEY": "test-secret"})
    conn = app.state.db.connect()
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('alice',?,'student','2026-01-01T00:00:00Z')", (hp("Passw0rd!"),))
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('admin',?,'admin','2026-01-01T00:00:00Z')", (hp("Admin123!"),))
    conn.commit()
    conn.close()
    return TestClient(app, raise_server_exceptions=False)


# ---------------- 口令散列
def test_password_hash_roundtrip():
    h = hash_password("Passw0rd!")
    assert h.startswith("pbkdf2_sha256$")
    assert verify_password("Passw0rd!", h) is True
    assert verify_password("wrong", h) is False


def test_password_hash_uses_random_salt():
    assert hash_password("x") != hash_password("x")


def test_verify_password_tolerates_garbage():
    assert verify_password("x", "not-a-hash") is False
    assert verify_password("x", "") is False


# ---------------- 令牌
def test_token_roundtrip(cfg):
    token, exp = issue_token(7, "student", NOW, cfg)
    claims = parse_token(token, NOW, cfg)
    assert claims.sub == 7 and claims.role == "student"
    assert claims.exp == int(exp.timestamp())


def test_token_expired(cfg):
    token, _ = issue_token(7, "student", NOW, cfg)
    later = NOW + timedelta(hours=cfg.TOKEN_TTL_HOURS + 1)
    with pytest.raises(Unauthorized):
        parse_token(token, later, cfg)


def test_token_tampered_payload(cfg):
    token, _ = issue_token(7, "student", NOW, cfg)
    body, sig = token.rsplit(".", 1)
    tampered = body[:-1] + ("A" if body[-1] != "A" else "B") + "." + sig
    with pytest.raises(Unauthorized):
        parse_token(tampered, NOW, cfg)


def test_token_wrong_secret(cfg):
    token, _ = issue_token(7, "student", NOW, cfg)
    cfg2 = type(cfg)(**{**cfg.__dict__, "SECRET_KEY": "other"})
    with pytest.raises(Unauthorized):
        parse_token(token, NOW, cfg2)


def test_token_requires_two_parts(cfg):
    with pytest.raises(Unauthorized):
        parse_token("justonestring", NOW, cfg)


# ---------------- 登录（T-01-01..T-01-06）
def test_login_success(svc, seeded):
    r = svc.login("alice", "Passw0rd!", NOW)
    assert r.role == "student"
    assert r.expires_at > NOW
    row = seeded.query("SELECT failed_attempts, last_login_at FROM app_user"
                       " WHERE username='alice'")[0]
    assert row["failed_attempts"] == 0
    assert row["last_login_at"] is not None


def test_login_unknown_user_same_message(svc):
    with pytest.raises(Unauthorized) as e:
        svc.login("nobody", "x", NOW)
    assert e.value.code == "E4001" and e.value.message == "账号或口令不正确"


def test_login_wrong_password_increments(svc, seeded):
    with pytest.raises(Unauthorized) as e:
        svc.login("alice", "bad", NOW)
    assert e.value.message == "账号或口令不正确"
    n = seeded.scalar("SELECT failed_attempts FROM app_user WHERE username='alice'")
    assert n == 1


def test_login_locks_after_five_failures(svc, seeded, cfg):
    for _ in range(cfg.LOCK_FAIL_LIMIT):
        with pytest.raises(Unauthorized):
            svc.login("alice", "bad", NOW)
    row = seeded.query("SELECT failed_attempts, locked_until FROM app_user"
                       " WHERE username='alice'")[0]
    assert row["failed_attempts"] == cfg.LOCK_FAIL_LIMIT
    assert row["locked_until"] is not None


def test_locked_account_rejects_correct_password(svc):
    for _ in range(5):
        with pytest.raises(Unauthorized):
            svc.login("alice", "bad", NOW)
    with pytest.raises(Unauthorized) as e:
        svc.login("alice", "Passw0rd!", NOW + timedelta(minutes=1))
    assert e.value.detail["lock_remaining_seconds"] > 0


def test_lock_expires_allows_login(svc):
    for _ in range(5):
        with pytest.raises(Unauthorized):
            svc.login("alice", "bad", NOW)
    later = NOW + timedelta(minutes=6)
    r = svc.login("alice", "Passw0rd!", later)
    assert r.token


# ---------------- 授权（T-01-09、T-01-10）
def test_require_role_blocks_student(svc):
    claims = Claims(sub=1, role="student", exp=9999999999)
    with pytest.raises(Forbidden):
        svc.require_role(claims, "admin")
    svc.require_role(claims, "student")   # 不抛


def test_require_owner_hides_existence(svc):
    claims = Claims(sub=1, role="student", exp=9999999999)
    svc.require_owner(1, claims)
    with pytest.raises(NotFound) as e:
        svc.require_owner(2, claims)
    assert e.value.code == "E1002"
    with pytest.raises(NotFound):
        svc.require_owner(None, claims)


# ---------------- HTTP 层
def test_http_login_and_me(client):
    r = client.post("/api/auth/login", json={"username": "alice", "password": "Passw0rd!"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["role"] == "student" and data["token"]
    token = data["token"]

    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + token})
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "alice"


def test_http_login_wrong_password_401(client):
    r = client.post("/api/auth/login", json={"username": "alice", "password": "bad"})
    assert r.status_code == 401
    assert r.json()["code"] == "E4001"


def test_http_login_missing_field_400(client):
    r = client.post("/api/auth/login", json={"username": "alice"})
    assert r.status_code == 400
    assert r.json()["field"] == "password"


def test_http_me_without_token_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["code"] == "E4001"


def test_http_me_with_bad_token_401(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer abc.def"})
    assert r.status_code == 401


def test_verify_password_rejects_other_algorithm():
    from app.core.security import verify_password
    assert verify_password("x", "bcrypt$12$abc$def") is False


def test_token_missing_parts(cfg):
    with pytest.raises(Unauthorized):
        parse_token("", NOW, cfg)


def test_parse_iso_accepts_both_formats():
    from app.services.auth import parse_iso
    assert parse_iso("2026-11-08T12:00:00Z") is not None
    assert parse_iso("2026-11-08T12:00:00.000000Z") is not None
    assert parse_iso(None) is None
    assert parse_iso("bad") is None
