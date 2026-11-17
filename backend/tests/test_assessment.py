"""测评服务测试：出题校验、判分重算、偏差转人工、报告阈值。"""
from __future__ import annotations

import json

import pytest

from app.services import assessment as svc

ITEMS = [
    {"no": 1, "type": "single", "stem": "聚合与组合的区别？",
     "options": ["A 一样", "B 生命周期是否一致", "C 都表示继承", "D 无关"],
     "answer": "B", "rubric": ["聚合可独立存在", "组合生命周期一致"], "points": 25},
    {"no": 2, "type": "short", "stem": "说明多重性 0..* 的含义",
     "rubric": ["零个或多个", "用在与集合的关联上"], "points": 25},
]


class FakeProvider:
    name = "real"

    def __init__(self, replies):
        self.replies = list(replies)

    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        return self.replies.pop(0)


def test_grade_single_is_deterministic():
    detail = svc._grade_single(ITEMS[0], "b")
    assert detail["got"] == 25 and detail["review_flag"] == 0
    wrong = svc._grade_single(ITEMS[0], "C")
    assert wrong["got"] == 0 and wrong["misses"]


def test_grade_short_takes_model_score():
    reply = json.dumps({"score": 18, "reason": "说清了零个或多个，但没提集合",
                        "quotes": ["零个或多个"], "confidence": 0.9})
    detail = svc._grade_short(FakeProvider([reply]), ITEMS[1], "零个或多个")
    assert detail["got"] == 18
    assert detail["reason"].startswith("说清了")
    assert detail["review_flag"] == 0


def test_grade_short_clamps_out_of_range():
    reply = json.dumps({"score": 40, "reason": "超范围", "quotes": []})
    detail = svc._grade_short(FakeProvider([reply]), ITEMS[1], "作答")
    assert detail["got"] == 25          # 夹到满分
    assert detail["review_flag"] == 1   # 原始分越界 → 待复核


def test_grade_short_without_provider_goes_manual():
    detail = svc._grade_short(None, ITEMS[1], "作答")
    assert detail["review_flag"] == 1 and detail["got"] == 0


def test_grade_short_bad_output_goes_manual():
    # _complete_json 会重试一次，所以准备两条非法回复
    detail = svc._grade_short(FakeProvider(["不是 JSON", "仍然不是 JSON"]), ITEMS[1], "作答")
    assert detail["review_flag"] == 1 and detail["got"] == 0


def test_grade_status_and_total():
    provider = FakeProvider([json.dumps({"score": 25, "reason": "答得好", "quotes": []})])
    score, max_score, details, status = svc.grade(
        provider, ITEMS, {"1": "B", "2": "零个或多个，通常用在集合"})
    assert (score, max_score, status) == (50, 50, "graded")
    assert len(details) == 2


def test_report_thresholds():
    full = [{"no": 1, "points": 25, "got": 25, "misses": [], "review_flag": 0}]
    assert svc.build_report("x", 25, 25, full)["action"] == "mark_mastered"
    weak = [{"no": 1, "points": 25, "got": 5, "misses": ["要点"], "review_flag": 0}]
    report = svc.build_report("x", 5, 25, weak)
    assert report["action"] == "add_practice" and report["weak_points"] == ["要点"]
    mid = [{"no": 1, "points": 25, "got": 15, "misses": ["要点"], "review_flag": 0}]
    assert svc.build_report("x", 15, 25, mid)["action"] == "keep"


def test_normalize_rejects_bad_items():
    assert svc._normalize_items({"items": []}) == []
    assert svc._normalize_items({"items": [{"type": "single", "stem": "x",
                                            "options": ["A"], "answer": "A",
                                            "rubric": ["r"], "points": 10}]}) == []
    # 采分点自 v1.5 起可选（判分改为直接打分），只剩题干与分值也是合法题目
    assert len(svc._normalize_items({"items": [{"type": "short", "stem": "x",
                                                "points": 10}]})) == 1


def test_public_items_hides_answer_and_rubric():
    public = svc.public_items(json.dumps(ITEMS, ensure_ascii=False))
    assert "answer" not in public[0] and "rubric" not in public[0]
    assert public[0]["options"][1].startswith("B")
    assert public[1]["type"] == "short"


def test_generate_items_from_provider():
    payload = {"title": "类图小测", "items": [
        {"no": 1, "type": "single", "stem": "s1", "options": ["A", "B", "C", "D"],
         "answer": "A", "rubric": ["r1"], "points": 50},
        {"no": 2, "type": "short", "stem": "s2", "rubric": ["r2"], "points": 50},
    ]}
    concept = {"name": "UML 类图", "chapter": "第3章", "difficulty": 4,
               "reference_minutes": 120, "outline": "关联/聚合/组合"}
    title, items, mode, reason = svc.generate_items(
        FakeProvider([json.dumps(payload, ensure_ascii=False)]), concept, [])
    assert title == "类图小测" and len(items) == 2 and mode == "llm"
    assert reason is None


def test_generate_items_degrades_without_real_provider():
    concept = {"name": "x", "chapter": "第1章", "difficulty": 2,
               "reference_minutes": 60, "outline": "要点"}

    class Mockish:
        name = "mock"

    title, items, mode, reason = svc.generate_items(Mockish(), concept, [])
    assert items == [] and mode == "local" and reason == "UNAVAILABLE"
