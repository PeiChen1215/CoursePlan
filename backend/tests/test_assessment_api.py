"""测评 HTTP 全链路：出题（含截断重试）→ 发布 → 作答 → 判分 → 采纳建议。"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.api import assessment as api_mod
from app.main import create_app
from app.services.provider import ProviderError, ProviderTruncated

VALID = {
    "title": "类图小测",
    "items": [
        {"no": 1, "type": "single", "stem": "聚合与组合的区别？",
         "options": ["A 一样", "B 生命周期是否一致", "C 都表示继承", "D 无关"],
         "answer": "B", "rubric": ["聚合可独立存在"], "points": 50},
        {"no": 2, "type": "short", "stem": "说明 0..* 的含义",
         "rubric": ["零个或多个", "用在与集合的关联上"], "points": 50},
    ],
}


class FakeReal:
    name = "real"

    def __init__(self, replies, errors=None):
        self.replies = list(replies)
        self.errors = list(errors or [])
        self.calls = 0

    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.replies.pop(0)


@pytest.fixture()
def client(tmp_path):
    app = create_app({"DB_PATH": str(tmp_path / "t.db"), "PROVIDER_MODE": "mock"})
    from app.db.uow import UnitOfWork
    from app.core.security import hash_password

    db = app.state.db
    with UnitOfWork(db) as uow:
        uow.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                    " VALUES('admin',?,'admin','2026-01-01T00:00:00Z')",
                    (hash_password("A1!aaaaa"),))
        uow.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                    " VALUES('alice',?,'student','2026-01-01T00:00:00Z')",
                    (hash_password("A1!aaaaa"),))
        uow.execute("INSERT INTO course(maintainer_id,name,semester,total_hours,status)"
                    " VALUES(1,'软件工程','2026秋',48,'enabled')")
        uow.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                    "reference_minutes,outline,status) VALUES(1,'UML 类图','第3章',4,120,"
                    "'关联/聚合/组合','enabled')")
    return TestClient(app, raise_server_exceptions=False)


def auth(client, user="admin"):
    token = client.post("/api/auth/login",
                        json={"username": user, "password": "A1!aaaaa"}).json()["data"]["token"]
    return {"Authorization": "Bearer " + token}


@pytest.fixture()
def patched(monkeypatch):
    def _use(provider):
        monkeypatch.setattr(api_mod, "_provider", lambda request: provider)
        return provider
    return _use


def _make_plan(client, headers):
    pid = client.post("/api/plans", headers=headers,
                      json={"course_id": 1}).json()["data"]["plan_id"]
    client.put("/api/plans/%d/constraint" % pid, headers=headers, json={
        "target_concept_id": 1, "deadline": "2027-01-10",
        "availability": {"mon": [["19:00", "21:00"]]},
        "excluded_dates": [], "mastered_concept_ids": [],
        "base_time": "2026-11-09T09:00:00Z"})
    return pid


def test_admin_generate_publish_and_student_flow(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    generated = client.post("/api/concepts/1/assessments/generate", headers=admin, json={})
    assert generated.status_code == 200, generated.text
    paper = generated.json()["data"]
    assert paper["mode"] == "llm" and len(paper["items"]) == 2

    assert client.post("/api/papers/%d/publish" % paper["paper_id"],
                       headers=admin).json()["data"]["status"] == "published"

    student = auth(client, "alice")
    pid = _make_plan(client, student)
    listed = client.get("/api/courses/1/assessments", headers=student).json()["data"]["items"]
    assert [row["paper_id"] for row in listed] == [paper["paper_id"]]

    items = client.get("/api/papers/%d/items" % paper["paper_id"],
                       headers=student).json()["data"]["items"]
    assert "answer" not in items[0] and "rubric" not in items[0]

    patched(FakeReal([json.dumps({"score": 50, "reason": "答得好", "quotes": ["零个或多个"]})]))
    submitted = client.post("/api/papers/%d/attempts" % paper["paper_id"],
                            headers=student,
                            json={"answers": {"1": "B", "2": "零个或多个，用在集合上"}})
    assert submitted.status_code == 200, submitted.text
    data = submitted.json()["data"]
    assert data["score"] == 100 and data["status"] == "graded"
    assert data["report"]["action"] == "mark_mastered"

    applied = client.post("/api/attempts/%d/apply" % data["attempt_id"],
                          headers=student, json={"action": "mark_mastered"})
    assert applied.status_code == 200
    assert applied.json()["data"]["mastered_concept_ids"] == [1]


def test_generate_requires_outline(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    client.post("/api/courses/1/concepts", headers=admin,
                json={"name": "没有要点", "chapter": "第1章", "difficulty": 2,
                      "reference_minutes": 30})
    response = client.post("/api/concepts/2/assessments/generate", headers=admin, json={})
    assert response.status_code == 400
    assert "要点" in response.json()["message"]


def test_generate_degrades_when_provider_fails(client, patched):
    patched(FakeReal([], errors=[ProviderError("down")]))
    response = client.post("/api/concepts/1/assessments/generate",
                           headers=auth(client), json={})
    assert response.status_code == 503
    assert "出题失败" in response.json()["message"]


def test_truncated_output_retries_with_bigger_budget(client, patched):
    provider = patched(FakeReal([json.dumps(VALID, ensure_ascii=False)],
                                errors=[ProviderTruncated("截断")]))
    generated = client.post("/api/concepts/1/assessments/generate",
                            headers=auth(client), json={})
    assert generated.status_code == 200
    assert provider.calls == 2


def test_only_author_can_publish_and_students_cannot_generate(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    student = auth(client, "alice")
    assert client.post("/api/papers/%d/publish" % paper_id,
                       headers=student).status_code == 403
    assert client.post("/api/concepts/1/assessments/generate",
                       headers=student, json={}).status_code == 403


def test_unpublished_paper_is_invisible_to_students(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    student = auth(client, "alice")
    assert client.get("/api/papers/%d/items" % paper_id,
                      headers=student).status_code == 404
    assert client.post("/api/papers/%d/attempts" % paper_id, headers=student,
                       json={"answers": {}}).status_code == 404


def test_patch_paper_updates_items(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    edited = dict(VALID)
    edited["title"] = "改过的标题"
    response = client.patch("/api/papers/%d" % paper_id, headers=admin,
                            json={"title": "改过的标题", "items": VALID["items"]})
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "改过的标题"


def test_apply_requires_plan(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    client.post("/api/papers/%d/publish" % paper_id, headers=admin)
    student = auth(client, "alice")
    patched(FakeReal([json.dumps({"score": 25, "reason": "部分正确", "quotes": []})]))
    attempt = client.post("/api/papers/%d/attempts" % paper_id, headers=student,
                          json={"answers": {"1": "A", "2": "不知道"}}).json()["data"]
    response = client.post("/api/attempts/%d/apply" % attempt["attempt_id"],
                           headers=student, json={"action": "mark_mastered"})
    assert response.status_code == 400
    assert "计划" in response.json()["message"]
