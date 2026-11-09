"""M6 · 追问抽取单元测试（对齐 D06 表 6.6 的 10 条用例）。"""
from datetime import date, timedelta

import pytest

from app.services.agent import (MODE_LOCAL, MODE_MOCK, extract, map_target,
                                parse_minutes, parse_relative_date, pick_questions)
from app.services.provider import MockProvider, ProviderError, ProviderTimeout, build_provider

BASE = date(2026, 11, 9)          # 周一
CONCEPTS = [
    {"concept_id": 1, "name": "循环结构", "aliases": ["for 循环", "while"]},
    {"concept_id": 2, "name": "数组", "aliases": []},
    {"concept_id": 3, "name": "指针", "aliases": ["指针操作"]},
]


# ---------------- 相对日期（T-06-04、T-06-05）
def test_parse_today_tomorrow():
    assert parse_relative_date("今天", BASE) == BASE
    assert parse_relative_date("明天", BASE) == BASE + timedelta(days=1)
    assert parse_relative_date("后天", BASE) == BASE + timedelta(days=2)


def test_parse_next_week_wednesday():
    """下周三 = 下一周的周三，不是最近的周三。"""
    assert parse_relative_date("下周三之前", BASE) == date(2026, 11, 18)


def test_parse_this_week_already_passed_rolls_forward():
    """周六说“本周五”：已是过去，顺延到下周。"""
    saturday = date(2026, 11, 14)
    assert parse_relative_date("本周五", saturday) == date(2026, 11, 20)


def test_parse_days_and_weeks():
    assert parse_relative_date("10 天后", BASE) == BASE + timedelta(days=10)
    assert parse_relative_date("3周后", BASE) == BASE + timedelta(weeks=3)
    assert parse_relative_date("两周内", BASE) == BASE + timedelta(days=14)
    assert parse_relative_date("半个月", BASE) == BASE + timedelta(days=14)


def test_parse_no_date_returns_none():
    assert parse_relative_date("我想好好学", BASE) is None


# ---------------- 时长
def test_parse_minutes_forms():
    assert parse_minutes("每天两小时") == 120
    assert parse_minutes("1.5 小时") == 90
    assert parse_minutes("90 分钟") == 90
    assert parse_minutes("没有时长") is None


# ---------------- 目标映射四层（T-06-01、T-06-02、T-06-03）
def test_map_exact_name():
    hit, cands, mode, why = map_target("指针", CONCEPTS)
    assert hit["concept_id"] == 3 and cands == [] and mode == MODE_LOCAL and why is None


def test_map_name_inside_sentence():
    """整句里出现名称也算精确命中。"""
    hit, _, mode, _ = map_target("我想学指针，10 天后", CONCEPTS)
    assert hit["concept_id"] == 3 and mode == MODE_LOCAL


def test_map_longest_name_wins():
    concepts = [{"concept_id": 1, "name": "数组", "aliases": []},
                {"concept_id": 2, "name": "数组指针", "aliases": []}]
    hit, _, _, _ = map_target("想学数组指针", concepts)
    assert hit["concept_id"] == 2


def test_map_alias_inside_sentence():
    hit, _, mode, _ = map_target("帮我看看指针操作这块", CONCEPTS)
    assert hit["concept_id"] == 3 and mode == MODE_LOCAL


def test_map_via_alias():
    hit, _, mode, _ = map_target("for 循环", CONCEPTS)
    assert hit["concept_id"] == 1 and mode == MODE_LOCAL


def test_map_via_model_returns_first_candidate():
    """整句里没有完整知识点名时，才交给模型挑。"""
    provider = MockProvider(candidates=[{"concept_id": 2}])
    hit, _, mode, why = map_target("那个循环的东西", CONCEPTS, provider)
    assert hit["concept_id"] == 2 and mode == MODE_MOCK and why is None


def test_map_falls_back_to_candidates():
    """模型明确回答"都不匹配"时，如实记为模型作答并给候选。"""
    hit, cands, mode, why = map_target("那个循环的东西", CONCEPTS, MockProvider())
    assert hit is None and len(cands) <= 5
    assert mode == "mock" and why is None


def test_map_discards_model_invented_id():
    """模型返回不存在的 ID 必须丢弃。"""
    provider = MockProvider(fail_mode="bad_id")
    hit, cands, mode, why = map_target("循环", CONCEPTS, provider)
    assert hit is None and why == "INVALID_OUTPUT"


def test_map_model_garbage_output():
    """模型回了非 JSON：退回规则，原因记为 INVALID_OUTPUT。"""
    provider = MockProvider(fail_mode="garbage")
    hit, _, mode, why = map_target("循环", CONCEPTS, provider)
    assert hit is None and mode == MODE_LOCAL and why == "INVALID_OUTPUT"


def test_map_accepts_fenced_json():
    """真实模型常把 JSON 包在 ``` 围栏里，必须能剥掉。"""
    class Fenced(MockProvider):
        def complete(self, prompt):
            return "```json\n{\"concept_id\": 1}\n```"

    hit, cands, mode, why = map_target("循环", CONCEPTS, Fenced())
    assert hit is not None and hit["concept_id"] == 1
    assert cands == [] and mode == "mock" and why is None


def test_map_accepts_json_with_prefix_text():
    class Chatty(MockProvider):
        def complete(self, prompt):
            return '我认为是第一个：{"concept_id": 1} 希望有帮助'

    hit, _, _, why = map_target("循环", CONCEPTS, Chatty())
    assert hit is not None and hit["concept_id"] == 1 and why is None


def test_map_model_unknown_id_keeps_mode():
    """模型给了候选外的 id：结果丢弃，但模式仍是模型。"""
    hit, cands, mode, why = map_target("循环", CONCEPTS, MockProvider(fail_mode="bad_id"))
    assert hit is None and cands and mode == "mock" and why == "INVALID_OUTPUT"


def test_map_model_timeout_degrades():
    provider = MockProvider(fail_mode="timeout")
    hit, cands, mode, why = map_target("循环", CONCEPTS, provider)
    assert hit is None and why == "TIMEOUT" and mode == MODE_LOCAL


def test_candidates_are_limited_and_ranked():
    concepts = [{"concept_id": i, "name": "循环%d" % i, "aliases": []} for i in range(1, 9)]
    _, cands, _, _ = map_target("循环", concepts)
    assert len(cands) == 5


# ---------------- 追问（T-06-07）
def test_pick_questions_at_most_two_in_priority_order():
    qs = pick_questions(["availability", "deadline", "target_concept_id"])
    assert len(qs) == 2
    assert qs[0].startswith("这次想重点掌握")     # 目标优先
    assert qs[1].startswith("希望什么时候")


def test_extract_fills_all_fields():
    r = extract("我想学指针，10 天后，每天两小时", {}, CONCEPTS, None, BASE)
    assert r.fields["target_concept_id"] == 3
    assert r.fields["deadline"] == (BASE + timedelta(days=10)).isoformat()
    assert r.fields["daily_limit"] == 120
    # 没说可用时间 → 只追问这一项
    assert len(r.questions) == 1 and "时间段" in r.questions[0]


def test_extract_defaults_daily_limit():
    r = extract("我想学数组", {}, CONCEPTS, None, BASE)
    assert r.fields["daily_limit"] == 480
    assert any("默认值" in w for w in r.warnings)


def test_extract_keeps_filled_fields():
    r = extract("每天两小时", {"deadline": "2026-11-20", "target_concept_id": 2},
                CONCEPTS, None, BASE)
    assert r.fields["deadline"] == "2026-11-20"
    assert r.fields["target_concept_id"] == 2


# ---------------- Provider 适配
def test_build_provider_mock():
    assert build_provider("mock").name == "mock"


def test_build_provider_real_without_key_is_unusable():
    p = build_provider("real")
    with pytest.raises(ProviderError):
        p.complete("x")


def test_build_provider_auto_falls_back_to_mock(monkeypatch):
    """auto 现在真的探测 /models：没 key 或探测失败都回落 mock。"""
    assert build_provider("auto").name == "mock"
    monkeypatch.setattr("app.services.provider.RealProvider.probe", lambda self: False)
    assert build_provider("auto", key="k").name == "mock"


def test_mock_probe_unavailable():
    assert MockProvider(fail_mode="unavailable").probe() is False


def test_map_provider_error_degrades_to_local():
    """模型不可用（如鉴权失败）时退回规则，原因 UNAVAILABLE。"""
    provider = MockProvider(fail_mode="unavailable")
    hit, cands, mode, why = map_target("循环", CONCEPTS, provider)
    assert hit is None and mode == MODE_LOCAL and why == "UNAVAILABLE"
