"""计划问答（advisor）：事实由程序算，模型只负责组织语言。"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.services import advisor
from app.services.board import BoardService
from app.services.planner import PlannerService
from app.services.provider import MockProvider, ProviderError, ProviderTimeout
from app.services.version import VersionService

BASE = datetime(2026, 11, 9, 9, 0)


def _confirmed(client):
    h = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": "alice", "password": "Passw0rd!"}
    ).json()["data"]["token"]}
    pid = client.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    from datetime import date as _date, timedelta as _td
    client.put("/api/plans/%d/constraint" % pid, headers=h, json={
        "target_concept_id": 2,
        "deadline": (_date.today() + _td(days=14)).isoformat(),
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
        "base_time": "2026-11-09T09:00:00Z"})
    uid = 2
    draft = PlannerService(client.app.state.db, client.app.state.config).generate(pid, uid, BASE)
    VersionService(client.app.state.db, client.app.state.config).confirm(
        pid, draft.revision, "k1", uid, BASE)
    return h, pid, uid


def test_facts_contain_computed_numbers(client):
    h, pid, uid = _confirmed(client)
    facts = advisor.build_facts(client.app.state.db, pid, uid, BASE,
                                client.app.state.config)
    for key in ("计划总时长T", "可排上限C_prime", "覆盖知识点", "课程知识点总数",
                "任务数", "已完成", "每周可用分钟"):
        assert key in facts
    assert facts["计划总时长T"] > 0
    assert facts["可排上限C_prime"] > 0
    assert facts["课程知识点总数"] >= facts["覆盖知识点"] >= 1
    assert facts["每周可用分钟"] == 240


def test_template_answer_uses_facts():
    facts = {"缺口D": 154, "完成率": 0.0, "逾期任务数": 3,
             "覆盖知识点": 3, "课程知识点总数": 12, "任务数": 22, "已完成": 0,
             "计划总时长T": 1180, "可排上限C_prime": 1026}
    text = advisor.template_answer(facts, "怎么办")
    assert "154" in text and "1026" in text
    assert "排不下" in text


def test_mock_provider_falls_back_to_template(client):
    h, pid, uid = _confirmed(client)
    facts = advisor.build_facts(client.app.state.db, pid, uid, BASE,
                                client.app.state.config)
    answer, mode, reason = advisor.advise(MockProvider(), facts, "我落后了怎么办")
    assert mode == "mock" and reason is None
    assert "分钟" in answer


@pytest.mark.parametrize("provider", [
    MockProvider(fail_mode="timeout"),
    MockProvider(fail_mode="unavailable"),
])
def test_provider_failure_degrades(provider, client):
    h, pid, uid = _confirmed(client)
    facts = advisor.build_facts(client.app.state.db, pid, uid, BASE,
                                client.app.state.config)
    answer, mode, reason = advisor.advise(provider, facts, "排得下吗")
    assert mode == "local"
    assert reason in ("TIMEOUT", "UNAVAILABLE")
    assert answer == advisor.template_answer(facts, "排得下吗")


def test_http_advise_returns_answer_and_facts(client):
    h, pid, uid = _confirmed(client)
    response = client.post("/api/plans/%d/advise" % pid, headers=h,
                           json={"question": "这份计划排得下吗？"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answer"]
    assert data["mode"] in ("llm", "local", "mock")
    assert data["facts"]["可排上限C_prime"] > 0


# ---------------- 真实模型分支（用假 provider 覆盖，不联网）


class _FakeReal:
    name = "real"

    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error

    def complete(self, prompt: str) -> str:
        if self.error is not None:
            raise self.error
        return self.reply


def _facts():
    return advisor.build_facts  # 占位，真正的 facts 由 fixture 构造


def test_real_provider_answer_is_used(client):
    h, pid, uid = _confirmed(client)
    facts = advisor.build_facts(client.app.state.db, pid, uid, BASE,
                                client.app.state.config)
    answer, mode, reason = advisor.advise(
        _FakeReal("这份计划时间够用，先按今天的任务推进；落后超过两天再调整。"),
        facts, "排得下吗")
    assert mode == "llm" and reason is None
    assert answer.startswith("这份计划时间够用")


def test_real_provider_timeout_degrades(client):
    h, pid, uid = _confirmed(client)
    facts = advisor.build_facts(client.app.state.db, pid, uid, BASE,
                                client.app.state.config)
    answer, mode, reason = advisor.advise(_FakeReal(error=ProviderTimeout("t")), facts, "q")
    assert (mode, reason) == ("local", "TIMEOUT")
    assert answer == advisor.template_answer(facts, "q")


def test_real_provider_unavailable_degrades(client):
    h, pid, uid = _confirmed(client)
    facts = advisor.build_facts(client.app.state.db, pid, uid, BASE,
                                client.app.state.config)
    answer, mode, reason = advisor.advise(_FakeReal(error=ProviderError("x")), facts, "q")
    assert (mode, reason) == ("local", "UNAVAILABLE")


@pytest.mark.parametrize("reply", ["", "   ", '{"concept_id": 1}', "```json\n{}\n```"])
def test_real_provider_invalid_output_degrades(reply, client):
    h, pid, uid = _confirmed(client)
    facts = advisor.build_facts(client.app.state.db, pid, uid, BASE,
                                client.app.state.config)
    answer, mode, reason = advisor.advise(_FakeReal(reply), facts, "q")
    assert (mode, reason) == ("local", "INVALID_OUTPUT")
    assert answer == advisor.template_answer(facts, "q")


def test_mock_garbage_mode_degrades():
    facts = {"缺口D": 0, "完成率": 0.0, "逾期任务数": 1, "覆盖知识点": 1,
             "课程知识点总数": 2, "任务数": 3, "已完成": 0,
             "计划总时长T": 100, "可排上限C_prime": 200}
    answer, mode, reason = advisor.advise(MockProvider(fail_mode="garbage"), facts, "q")
    assert (mode, reason) == ("local", "INVALID_OUTPUT")


def test_no_provider_returns_local():
    facts = {"缺口D": 0, "完成率": 0.5, "逾期任务数": 0, "覆盖知识点": 2,
             "课程知识点总数": 2, "任务数": 4, "已完成": 2,
             "计划总时长T": 120, "可排上限C_prime": 300}
    answer, mode, reason = advisor.advise(None, facts, "q")
    assert (mode, reason) == ("local", "UNAVAILABLE")
    assert "余量" in answer


def test_template_without_gap_or_overdue():
    facts = {"缺口D": 0, "完成率": 0.5, "逾期任务数": 0, "覆盖知识点": 2,
             "课程知识点总数": 2, "任务数": 4, "已完成": 2,
             "计划总时长T": 120, "可排上限C_prime": 300}
    text = advisor.template_answer(facts, "q")
    assert "120" in text and "300" in text and "180" in text
    assert "已完成 2/4" in text


def test_minutes_accepts_strings():
    assert advisor._minutes("09:00", "10:30") == 90
    from datetime import time
    assert advisor._minutes(time(9, 0), time(10, 30)) == 90
    assert advisor._minutes("10:00", "09:00") == 0
