"""M1 冒烟测试：配置校验、脱敏、健康检查、错误信封。"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import config as config_mod  # noqa: E402
from app.core.errors import NotFound, envelope  # noqa: E402
from app.core.logging import sanitize  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    app = create_app({"DB_PATH": str(tmp_path / "t.db"), "LOG_LEVEL": "ERROR"})
    return TestClient(app)


def test_health_has_four_items(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "OK"
    assert set(["service", "database", "provider", "backup"]) <= set(body["data"])
    assert body["data"]["database"] == "ok"
    assert r.headers["X-Request-ID"]


def test_meta_exposes_config(client):
    r = client.get("/api/meta")
    cfg = r.json()["data"]["config"]
    assert cfg["STUDY_RATIO"] == 0.7
    assert cfg["BUFFER_RATIO"] == 0.1
    assert cfg["MAX_SLICES_PER_TASK"] == 100


def test_config_defaults_match_d06_table_2_2():
    cfg = config_mod.load({})
    assert cfg.STUDY_RATIO == 0.70
    assert cfg.BUFFER_RATIO == 0.10
    assert cfg.MAX_SLICE_SECONDS == 7200
    assert cfg.MAX_SLICES_PER_TASK == 100
    assert cfg.CAP_TIGHT_THRESHOLD == 0.80
    assert cfg.DELAY_THRESHOLD_HOURS == 48
    assert cfg.MODEL_TIMEOUT_SECONDS == 10
    assert cfg.MIN_TASK_MINUTES == 1


def test_config_out_of_range_rejected():
    with pytest.raises(config_mod.ConfigError) as e:
        config_mod.load({"BUFFER_RATIO": 0.9})
    assert "BUFFER_RATIO" in str(e.value)


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("DSH_STUDY_RATIO", "0.8")
    assert config_mod.load({}).STUDY_RATIO == 0.8


def test_config_explicit_beats_env(monkeypatch):
    monkeypatch.setenv("DSH_STUDY_RATIO", "0.8")
    assert config_mod.load({"STUDY_RATIO": 0.6}).STUDY_RATIO == 0.6


def test_sanitize_redacts_secrets():
    out = sanitize({"password": "x", "token": "y", "utterance": "我想学循环",
                    "STUDY_RATIO": 0.7})
    assert out["password"] == "***"
    assert out["token"] == "***"
    assert out["utterance"] == "***"
    assert out["STUDY_RATIO"] == 0.7


def test_error_envelope_shape():
    body = envelope("E1002", "不存在", None, "plan_id", None, "rid")
    assert set(body) == {"code", "message", "data", "field", "detail", "request_id"}


def test_app_error_returns_mapped_status(client):
    app = client.app

    @app.get("/api/_boom")
    def boom():
        raise NotFound("E1002", "计划不存在")

    r = client.get("/api/_boom")
    assert r.status_code == 404
    assert r.json()["code"] == "E1002"
