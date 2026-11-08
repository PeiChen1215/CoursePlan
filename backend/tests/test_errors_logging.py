"""M1 · errors 与 logging 模块单元测试（对应 D06 §12.6.2 / §14.6.3）。"""
import json
import logging

import pytest

from app.core import errors as E
from app.core.errors import envelope
from app.core.logging import REDACT, JsonFormatter, sanitize


# ---------------- 错误码映射
@pytest.mark.parametrize("cls,code,status", [
    (E.ValidationError, "E1001", 400),
    (E.NotFound, "E1002", 404),
    (E.StateError, "E1003", 400),
    (E.Busy, "E1005", 503),
    (E.PrereqCycle, "E2001", 422),
    (E.VersionConflict, "E2004", 409),
    (E.Unauthorized, "E4001", 401),
    (E.Forbidden, "E4003", 403),
])
def test_error_class_codes(cls, code, status):
    err = cls(message="x")
    assert err.code == code
    assert err.http_status == status


def test_error_keeps_message_field_detail():
    err = E.ValidationError("E1001", "字段非法", field="deadline", detail={"min": 2})
    assert (err.code, err.message, err.field) == ("E1001", "字段非法", "deadline")
    assert err.detail == {"min": 2}


def test_base_error_default_code_is_internal():
    assert E.AppError().code == "E9000"


def test_404_message_does_not_leak_existence():
    """越权与不存在必须返回同一错误码（D06 §3.6.4）。"""
    a = E.NotFound("E1002", "计划不存在")
    b = E.NotFound("E1002", "计划不存在")
    assert (a.code, a.http_status, a.message) == (b.code, b.http_status, b.message)


def test_envelope_shape_and_defaults():
    body = envelope()
    assert list(body) == ["code", "message", "data", "field", "detail", "request_id"]
    assert body["code"] == "OK"


# ---------------- 脱敏
def test_redact_covers_password_token_utterance():
    assert {"password", "token", "utterance"} <= REDACT


def test_sanitize_redacts_top_level():
    out = sanitize({"password": "p", "token": "t", "utterance": "我想学循环",
                    "deadline": "2026-12-01", "ok": 1})
    assert out["password"] == out["token"] == out["utterance"] == out["deadline"] == "***"
    assert out["ok"] == 1


def test_sanitize_is_case_insensitive_and_nested():
    out = sanitize({"Password": "p", "user": {"Token": "t", "name": "alice"}})
    assert out["Password"] == "***"
    assert out["user"]["Token"] == "***"
    assert out["user"]["name"] == "alice"


def test_sanitize_keeps_non_sensitive():
    assert sanitize({"STUDY_RATIO": 0.7, "level": "INFO"}) == {
        "STUDY_RATIO": 0.7, "level": "INFO"}


def test_json_formatter_emits_structured_line():
    rec = logging.LogRecord("studypath", logging.INFO, __file__, 1, "event_x", None, None)
    rec.extra_fields = {"request_id": "r1", "password": "secret"}
    out = json.loads(JsonFormatter().format(rec))
    assert out["event"] == "event_x"
    assert out["request_id"] == "r1"
    assert out["password"] == "***"
    assert out["level"] == "INFO" and "ts" in out
