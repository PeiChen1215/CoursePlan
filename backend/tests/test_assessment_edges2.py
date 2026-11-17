"""再补最后一层分支：列表权限分支、patch 空字段、判分异常等。"""
from __future__ import annotations

import json

from app.services import assessment as svc

from .test_assessment_api import FakeReal, VALID, auth, client, patched  # noqa: F401


def test_student_list_without_plan(client, patched):
    """学生没有计划时，课程测评列表为空。"""
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    client.post("/api/papers/%d/publish" % paper_id, headers=admin)
    student = auth(client, "alice")
    listed = client.get("/api/courses/1/assessments", headers=student).json()["data"]["items"]
    assert listed == []


def test_patch_paper_only_title_or_empty(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    noop = client.patch("/api/papers/%d" % paper_id, headers=admin, json={})
    assert noop.status_code == 200
    assert noop.json()["data"]["title"]


def test_apply_twice_is_idempotent(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    client.post("/api/papers/%d/publish" % paper_id, headers=admin)
    student = auth(client, "alice")
    client.post("/api/plans", headers=student,
                json={"course_id": 1}).json()["data"]["plan_id"]
    pid = client.get("/api/plans", headers=student).json()["data"]["items"][0]["plan_id"]
    client.put("/api/plans/%d/constraint" % pid, headers=student, json={
        "target_concept_id": 1, "deadline": "2027-01-10",
        "availability": {"mon": [["19:00", "21:00"]]},
        "excluded_dates": [], "mastered_concept_ids": [],
        "base_time": "2026-11-09T09:00:00Z"})
    patched(FakeReal([json.dumps({"score": 24, "reason": "好", "quotes": []})]))
    attempt = client.post("/api/papers/%d/attempts" % paper_id, headers=student,
                          json={"answers": {"1": "B"}}).json()["data"]
    first = client.post("/api/attempts/%d/apply" % attempt["attempt_id"],
                        headers=student, json={"action": "mark_mastered"}).json()["data"]
    second = client.post("/api/attempts/%d/apply" % attempt["attempt_id"],
                         headers=student, json={"action": "mark_mastered"}).json()["data"]
    assert first["mastered_concept_ids"] == second["mastered_concept_ids"] == [1]


def test_grade_short_key_error_goes_manual():
    class Weird:
        name = "real"

        def complete(self, prompt, max_tokens=0):
            return json.dumps({"score": "很高", "reason": "x"})

    detail = svc._grade_short(Weird(), {"no": 1, "type": "short", "stem": "s",
                                        "points": 25, "rubric": []}, "答")
    assert detail["got"] == 0 and detail["review_flag"] == 1


def test_grade_short_provider_error_goes_manual():
    from app.services.provider import ProviderError

    class Down:
        name = "real"

        def complete(self, prompt, max_tokens=0):
            raise ProviderError("down")

    detail = svc._grade_short(Down(), {"no": 1, "type": "short", "stem": "s",
                                       "points": 25, "rubric": []}, "答")
    assert detail["got"] == 0 and detail["review_flag"] == 1


def test_admin_list_and_missing_endpoints(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    listed = client.get("/api/courses/1/assessments", headers=admin).json()["data"]["items"]
    assert [row["paper_id"] for row in listed] == [paper_id]
    assert client.get("/api/papers/999/items", headers=admin).status_code == 404
    assert client.post("/api/attempts/999/apply", headers=admin,
                       json={"action": "mark_mastered"}).status_code == 404


def test_get_attempt_success(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    client.post("/api/papers/%d/publish" % paper_id, headers=admin)
    student = auth(client, "alice")
    patched(FakeReal([json.dumps({"score": 20, "reason": "不错", "quotes": []})]))
    attempt = client.post("/api/papers/%d/attempts" % paper_id, headers=student,
                          json={"answers": {"1": "B"}}).json()["data"]
    got = client.get("/api/attempts/%d" % attempt["attempt_id"], headers=student)
    assert got.status_code == 200
    assert got.json()["data"]["score"] == attempt["score"]
    assert got.json()["data"]["report"]["items"]


def test_context_includes_resource_summaries():
    concept = {"name": "x", "chapter": "第1章", "difficulty": 2,
               "reference_minutes": 60, "outline": "要点"}
    text = svc._context(concept, [{"summary": "资料 A"}, {"summary": ""}])
    assert "资料摘要" in text and "资料 A" in text


def test_normalize_rejects_non_dict_item():
    assert svc._normalize_items({"items": ["不是对象"]}) == []


def test_truncated_twice_raises():
    from app.services.provider import ProviderTruncated

    class AlwaysTruncated:
        name = "real"
        calls = 0

        def complete(self, prompt, max_tokens=0):
            AlwaysTruncated.calls += 1
            raise ProviderTruncated("截断")

    concept = {"name": "x", "chapter": "第1章", "difficulty": 2,
               "reference_minutes": 60, "outline": "要点"}
    title, items, mode, reason = svc.generate_items(AlwaysTruncated(), concept, [])
    assert items == [] and mode == "local" and reason == "UNAVAILABLE"
    assert AlwaysTruncated.calls == 2   # 首次 + 翻倍重试一次


def test_provider_factory_builds_real():
    from types import SimpleNamespace

    from app.api import assessment as mod

    cfg = SimpleNamespace(PROVIDER_MODE="mock", PROVIDER_KEY="", MODEL_TIMEOUT_SECONDS=5,
                          PROVIDER_BASE="https://example.com", PROVIDER_MODEL="m",
                          PROVIDER_THINKING="disabled", MAX_TOKENS_AUTHOR=3000)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config=cfg)))
    provider = mod._provider(request)
    assert provider.name in ("real", "mock")
