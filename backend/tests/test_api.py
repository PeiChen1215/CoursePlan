"""M1 · HTTP 层测试：健康检查、错误信封、request_id（对应 D06 §12.6.2 / §12.6.3）。"""
import pytest
from fastapi.testclient import TestClient

from app.core.errors import Busy, Forbidden, NotFound
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app({"DB_PATH": str(tmp_path / "t.db"), "LOG_LEVEL": "ERROR"})
    return TestClient(app, raise_server_exceptions=False)


# ---------------- 健康检查
def test_health_four_items(client):
    body = client.get("/api/health").json()
    assert body["code"] == "OK"
    d = body["data"]
    assert d["service"] == "ok" and d["database"] == "ok"
    assert d["provider"] in ("mock", "real")
    assert d["backup"] in ("ok", "warn")


def test_health_reports_database_error(client, monkeypatch):
    from app.db.uow import Database

    def boom(self, sql, params=()):
        raise RuntimeError("down")

    monkeypatch.setattr(Database, "scalar", boom)
    d = client.get("/api/health").json()["data"]
    assert d["database"] == "error"
    assert d["service"] == "ok"


# ---------------- 统一信封与 request_id
def test_response_carries_request_id(client):
    r = client.get("/api/health")
    assert r.headers["X-Request-ID"]
    assert r.json()["request_id"] == r.headers["X-Request-ID"]


def test_client_request_id_is_echoed(client):
    r = client.get("/api/health", headers={"X-Request-ID": "trace-001"})
    assert r.headers["X-Request-ID"] == "trace-001"
    assert r.json()["request_id"] == "trace-001"


def test_meta_returns_config_without_secrets(client):
    cfg = client.get("/api/meta").json()["data"]["config"]
    assert cfg["STUDY_RATIO"] == 0.7
    assert "SECRET_KEY" not in cfg


# ---------------- 错误映射
def test_business_error_maps_to_status(client):
    client.app.router.routes  # 保持引用

    @client.app.get("/api/_notfound")
    def _nf():
        raise NotFound("E1002", "计划不存在")

    r = client.get("/api/_notfound")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "E1002" and body["message"] == "计划不存在"


def test_forbidden_maps_403(client):
    @client.app.get("/api/_forbidden")
    def _fb():
        raise Forbidden("E4003", "角色不符")

    assert client.get("/api/_forbidden").status_code == 403


def test_busy_maps_503(client):
    @client.app.get("/api/_busy")
    def _busy():
        raise Busy("E1005", "数据库忙")

    assert client.get("/api/_busy").status_code == 503


def test_validation_error_locates_field(client):
    @client.app.get("/api/_need")
    def _need(limit: int):
        return {"ok": limit}

    r = client.get("/api/_need?limit=abc")
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "E1001"
    assert body["field"] == "limit"


def test_unexpected_error_hides_details(client):
    @client.app.get("/api/_boom")
    def _boom():
        raise RuntimeError("secret stack info")

    r = client.get("/api/_boom")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "E9000"
    assert "secret stack info" not in str(body)


def test_unknown_route_returns_json_not_html(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
