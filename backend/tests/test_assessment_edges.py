"""补齐测评的异常分支，保持全项目 100% 覆盖率口径。"""
from __future__ import annotations

import json

import pytest

from app.api import assessment as api_mod
from app.core.errors import NotFound
from app.services import assessment as svc
from app.services.provider import ProviderError

from .test_assessment_api import FakeReal, VALID, auth, client, patched  # noqa: F401


def test_generate_with_concept_missing(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    response = client.post("/api/concepts/999/assessments/generate",
                           headers=auth(client), json={})
    assert response.status_code == 404


def test_generate_rejects_too_long_outline(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    client.patch("/api/concepts/1", headers=admin, json={"outline": "字" * 1001})
    too_long = client.patch("/api/concepts/1", headers=admin,
                            json={"outline": "字" * 1001})
    assert too_long.status_code == 400
    assert too_long.json()["field"] == "outline"


def test_patch_concept_missing(client):
    admin = auth(client)
    assert client.patch("/api/concepts/999", headers=admin,
                        json={"outline": "x"}).status_code == 404


def test_patch_paper_rejects_bad_items(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    bad = client.patch("/api/papers/%d" % paper_id, headers=admin,
                       json={"items": [{"type": "single", "stem": "x", "points": 10}]})
    assert bad.status_code == 400
    assert bad.json()["field"] == "items"


def test_patch_paper_missing(client):
    admin = auth(client)
    assert client.patch("/api/papers/999", headers=admin,
                        json={"title": "x"}).status_code == 404


def test_publish_missing_paper(client):
    admin = auth(client)
    assert client.post("/api/papers/999/publish", headers=admin).status_code == 404


def test_get_missing_attempt(client):
    student = auth(client, "alice")
    assert client.get("/api/attempts/999", headers=student).status_code == 404


def test_apply_unknown_action(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    client.post("/api/papers/%d/publish" % paper_id, headers=admin)
    student = auth(client, "alice")
    client.post("/api/plans", headers=student, json={"course_id": 1})
    patched(FakeReal([json.dumps({"score": 10, "reason": "弱", "quotes": []})]))
    attempt = client.post("/api/papers/%d/attempts" % paper_id, headers=student,
                          json={"answers": {"1": "A"}}).json()["data"]
    response = client.post("/api/attempts/%d/apply" % attempt["attempt_id"],
                           headers=student, json={"action": "unknown"})
    assert response.status_code == 400
    assert response.json()["field"] == "action"


def test_generate_handles_timeout(client, monkeypatch):
    from app.services.provider import ProviderTimeout

    class TimeoutProvider:
        name = "real"

        def complete(self, prompt, max_tokens=0):
            raise ProviderTimeout("t")

    monkeypatch.setattr(api_mod, "_provider", lambda request: TimeoutProvider())
    response = client.post("/api/concepts/1/assessments/generate",
                           headers=auth(client), json={})
    assert response.status_code == 503
    assert "TIMEOUT" in response.json()["message"]


def test_service_generate_timeout_branch():
    class TimeoutProvider:
        name = "real"

        def complete(self, prompt, max_tokens=0):
            from app.services.provider import ProviderTimeout
            raise ProviderTimeout("t")

    concept = {"name": "x", "chapter": "第1章", "difficulty": 2,
               "reference_minutes": 60, "outline": "要点"}
    title, items, mode, reason = svc.generate_items(TimeoutProvider(), concept, [])
    assert (title, items, mode, reason) == (None, [], "local", "TIMEOUT")


def test_service_generate_invalid_json_twice():
    class BadProvider:
        name = "real"

        def complete(self, prompt, max_tokens=0):
            return "不是 JSON"

    concept = {"name": "x", "chapter": "第1章", "difficulty": 2,
               "reference_minutes": 60, "outline": "要点"}
    title, items, mode, reason = svc.generate_items(BadProvider(), concept, [])
    assert items == [] and reason == "INVALID_OUTPUT"


def test_service_rejects_bad_item_shapes():
    bad_payloads = [
        {"items": "not-a-list"},
        {"items": [{"type": "unknown", "stem": "x", "points": 10}]},
        {"items": [{"type": "single", "stem": "", "points": 10}]},
        {"items": [{"type": "single", "stem": "x", "points": 0}]},
    ]
    for payload in bad_payloads:
        assert svc._normalize_items(payload) == []


def test_context_without_outline_or_resources():
    concept = {"name": "x", "chapter": "第1章", "difficulty": 2,
               "reference_minutes": 60, "outline": ""}
    text = svc._context(concept, [])
    assert "x" in text and "要点" not in text


def test_publish_requires_owner(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    # 直接改库模拟"别人创建的试卷"
    from app.db.uow import UnitOfWork
    with UnitOfWork(client.app.state.db) as uow:
        uow.execute("UPDATE assessment_paper SET created_by = 2 WHERE paper_id = ?",
                    (paper_id,))
    with pytest.raises(NotFound):
        svc.publish_paper(client.app.state.db, paper_id, 1)
