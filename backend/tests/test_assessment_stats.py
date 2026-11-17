"""学情统计测试：单卷统计与课程汇总。"""
from __future__ import annotations

import json

from app.services import assessment as svc

from .test_assessment_api import FakeReal, VALID, auth, client, patched  # noqa: F401


def _publish(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    client.post("/api/papers/%d/publish" % paper_id, headers=admin)
    return paper_id


def _attempt(client, patched, paper_id, student_name, answers, short_score):
    # 两道简答各一次调用
    patched(FakeReal([json.dumps({"score": short_score, "reason": "理由", "quotes": []}),
                      json.dumps({"score": short_score, "reason": "理由", "quotes": []})]))
    student = auth(client, student_name)
    client.post("/api/plans", headers=student, json={"course_id": 1})
    return client.post("/api/papers/%d/attempts" % paper_id, headers=student,
                       json={"answers": answers}).json()["data"]


def test_paper_stats_aggregates_attempts(client, patched):
    from app.db.uow import UnitOfWork

    from app.core.security import hash_password

    with UnitOfWork(client.app.state.db) as uow:
        uow.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                    " VALUES('bob',?,'student','2026-01-01T00:00:00Z')",
                    (hash_password("A1!aaaaa"),))

    paper_id = _publish(client, patched)
    first = _attempt(client, patched, paper_id, "alice", {"1": "B", "2": "答"}, 20)
    second = _attempt(client, patched, paper_id, "bob", {"1": "A", "2": "答"}, 10)

    admin = auth(client)
    stats = client.get("/api/papers/%d/stats" % paper_id, headers=admin).json()["data"]
    assert stats["attempts"] == 2
    assert stats["max_score"] == 100
    assert stats["pass_line"] == 60
    assert stats["average"] == round((first["score"] + second["score"]) / 2, 1)
    assert 0 <= stats["pass_rate"] <= 1
    assert sum(stats["distribution"].values()) == 2
    assert {item["no"] for item in stats["items"]} == {1, 2}
    assert stats["recent"][0]["username"]
    assert stats["highest"] >= stats["lowest"]


def test_course_stats_lists_papers(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    client.post("/api/papers/%d/publish" % paper_id, headers=admin)
    items = client.get("/api/courses/1/assessment-stats",
                       headers=admin).json()["data"]["items"]
    assert [row["paper_id"] for row in items] == [paper_id]
    assert items[0]["attempts"] == 0


def test_stats_forbidden_for_students(client, patched):
    patched(FakeReal([json.dumps(VALID, ensure_ascii=False)]))
    admin = auth(client)
    paper_id = client.post("/api/concepts/1/assessments/generate",
                           headers=admin, json={}).json()["data"]["paper_id"]
    student = auth(client, "alice")
    assert client.get("/api/papers/%d/stats" % paper_id,
                      headers=student).status_code == 403
    assert client.get("/api/courses/1/assessment-stats",
                      headers=student).status_code == 403


def test_stats_missing_paper(client):
    admin = auth(client)
    assert client.get("/api/papers/999/stats", headers=admin).status_code == 404


def test_distribution_covers_all_buckets(client, patched):
    """四个分数档都要有样本，覆盖分布统计的全部分支。"""
    from app.core.security import hash_password
    from app.db.uow import UnitOfWork

    names = ["s60", "s75", "s95"]
    with UnitOfWork(client.app.state.db) as uow:
        for name in names:
            uow.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                        " VALUES(?,?,'student','2026-01-01T00:00:00Z')",
                        (name, hash_password("A1!aaaaa")))

    paper_id = _publish(client, patched)
    # 满分 100：两条选择题 50 分 + 两道简答各 25
    # 试卷：1 道单选 50 分 + 1 道简答 50 分
    _attempt(client, patched, paper_id, "alice", {"1": "B"}, 40)   # 90 → >=85%
    _attempt(client, patched, paper_id, "s75", {"1": "B"}, 20)     # 70 → 70-85%
    _attempt(client, patched, paper_id, "s95", {"1": "B"}, 15)     # 65 → 50-70%
    _attempt(client, patched, paper_id, "s60", {"1": "A"}, 10)     # 10 → <50%

    admin = auth(client)
    stats = client.get("/api/papers/%d/stats" % paper_id, headers=admin).json()["data"]
    assert stats["distribution"]["<50%"] >= 1
    assert stats["distribution"]["50-70%"] >= 1
    assert stats["distribution"]["70-85%"] >= 1
    assert stats["distribution"][">=85%"] >= 1
