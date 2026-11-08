"""M3 · 约束保存与容量接口测试（HTTP 全链路）。"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import create_app

BASE = "2026-11-09T09:00:00Z"


def login(client, user="alice", pwd="Passw0rd!"):
    r = client.post("/api/auth/login", json={"username": user, "password": pwd})
    return {"Authorization": "Bearer " + r.json()["data"]["token"]}


def make_plan(client, headers):
    r = client.post("/api/plans", headers=headers, json={"course_id": 1})
    return r.json()["data"]["plan_id"]


def body(**kw):
    d = {"target_concept_id": 2, "deadline": "2026-11-20",
         "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
         "base_time": BASE}
    d.update(kw)
    return d


def test_plan_and_constraint_roundtrip(client):
    h = login(client)
    pid = make_plan(client, h)
    r = client.put("/api/plans/%d/constraint" % pid, headers=h, json=body())
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["C"] > 0 and data["C_prime"] == data["C"] - data["B"]
    # 目标 2 的闭包含 1、2 → 路径时长 = 90 + 120
    assert data["path_minutes"] == 210

    got = client.get("/api/plans/%d/constraint" % pid, headers=h).json()["data"]
    assert got["target_concept_id"] == 2
    assert got["availability"] == {"mon": [["19:00", "21:00"]],
                                  "wed": [["19:00", "21:00"]]}


def test_constraint_is_upserted(client):
    h = login(client)
    pid = make_plan(client, h)
    client.put("/api/plans/%d/constraint" % pid, headers=h, json=body())
    client.put("/api/plans/%d/constraint" % pid, headers=h,
               json=body(target_concept_id=3))
    got = client.get("/api/plans/%d/constraint" % pid, headers=h).json()["data"]
    assert got["target_concept_id"] == 3


def test_preview_does_not_persist(client):
    h = login(client)
    pid = make_plan(client, h)
    r = client.post("/api/plans/%d/capacity/preview" % pid, headers=h, json=body())
    assert r.status_code == 200
    assert client.get("/api/plans/%d/constraint" % pid, headers=h).json()["data"] is None


def test_preview_reports_empty_availability(client):
    h = login(client)
    pid = make_plan(client, h)
    r = client.post("/api/plans/%d/capacity/preview" % pid, headers=h,
                    json=body(availability={}))
    assert r.json()["data"]["reject_reason"] == "EMPTY_AVAILABILITY"


def test_zero_capacity_rejected_on_save(client):
    h = login(client)
    pid = make_plan(client, h)
    r = client.put("/api/plans/%d/constraint" % pid, headers=h,
                   json=body(availability={}))
    assert r.status_code == 400
    assert r.json()["code"] == "E1003"
    assert r.json()["detail"]["reason"] == "EMPTY_AVAILABILITY"


def test_other_students_plan_is_404(client):
    h_admin = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": "admin", "password": "Admin123!"}
    ).json()["data"]["token"]}
    h = login(client)
    pid = make_plan(client, h)
    r = client.get("/api/plans/%d/constraint" % pid, headers=h_admin)
    assert r.status_code == 404
    assert r.json()["code"] == "E1002"


def test_goal_must_belong_to_course(client):
    h = login(client)
    pid = make_plan(client, h)
    r = client.put("/api/plans/%d/constraint" % pid, headers=h,
                   json=body(target_concept_id=999))
    assert r.status_code == 400
    assert r.json()["field"] == "target_concept_id"


def test_mastered_allows_prereq_concept(client):
    """已掌握可以是先修（跳过已会的内容），不计入目标路径时长。"""
    h = login(client)
    pid = make_plan(client, h)
    full = client.put("/api/plans/%d/constraint" % pid, headers=h,
                      json=body()).json()["data"]
    skipped = client.put("/api/plans/%d/constraint" % pid, headers=h,
                         json=body(mastered_concept_ids=[1])).json()["data"]
    assert skipped["path_minutes"] < full["path_minutes"]


def test_mastered_rejects_foreign_concept(client):
    h = login(client)
    pid = make_plan(client, h)
    r = client.put("/api/plans/%d/constraint" % pid, headers=h,
                   json=body(mastered_concept_ids=[999]))
    assert r.status_code == 400
    assert r.json()["field"] == "mastered_concept_ids"


def test_bad_base_time_format(client):
    h = login(client)
    pid = make_plan(client, h)
    r = client.post("/api/plans/%d/capacity/preview" % pid, headers=h,
                    json=body(base_time="2026-11-09 09:00"))
    assert r.status_code == 400
    assert r.json()["field"] == "base_time"


def test_plan_for_missing_course(client):
    h = login(client)
    r = client.post("/api/plans", headers=h, json={"course_id": 99})
    assert r.status_code == 400


def test_plan_requires_auth(client):
    assert client.post("/api/plans", json={"course_id": 1}).status_code == 401


def test_capacity_matches_hand_calc(client):
    """2026-11-09 起至 11-20，每周一、三各 2 小时 → 手算比对。"""
    h = login(client)
    pid = make_plan(client, h)
    r = client.put("/api/plans/%d/constraint" % pid, headers=h, json=body())
    d = r.json()["data"]
    # 11-09(一) 11(三) 16(一) 18(三) = 4 天 × 120 = 480
    assert d["C"] == 480
    assert d["B"] == 48
    assert d["C_prime"] == 432
    assert d["slots"] == 4
