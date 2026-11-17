"""计划问答（advisor）：用程序算出的确定性事实，让模型说人话。

职责边界（对应 D06 §6 与 D02 F-07 的延伸）：
- 事实（容量、覆盖、进度、问题码、未排入原因）全部由程序计算，随回答一起返回；
- 模型只负责把这些事实组织成 3–5 句中文，**不允许产生新数字**；
- 模型超时/不可用/输出异常时退回模板回答（mode=local），保证功能可用。
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .board import BoardService
from .capacity import expand_slots, normalize_availability, normalize_dates
from .provider import BaseProvider, ProviderError, ProviderTimeout

MODE_LLM = "llm"
MODE_LOCAL = "local"

SYSTEM_PROMPT = """你是「学径 StudyPath」的学习规划助手。
只用下面 JSON 里的事实回答，不要编造任何数字，也不要承诺计划会自动改变。
要求：中文；3–5 句；先给结论，再给一条今天就能做的下一步；不复述 JSON 字段名。"""


def build_facts(db, plan_id: int, student_id: int, now: datetime, config) -> Dict[str, Any]:
    """把看板、约束与容量汇总成一份可核对的事实清单。"""
    board = BoardService(db, config).build(plan_id, student_id, now)
    course = board.get("course") or {}

    rows = db.query(
        "SELECT target_concept_id, extra_concept_ids_json, deadline, availability_json,"
        " excluded_dates_json, mastered_concept_ids_json"
        " FROM plan_constraint WHERE plan_id = ?", (plan_id,))
    constraint = dict(rows[0]) if rows else {}

    weekly_minutes = 0
    capacity = {"C": 0, "B": 0, "C_prime": 0}
    deadline = ""
    if constraint:
        deadline = constraint["deadline"]
        availability = normalize_availability(json.loads(constraint["availability_json"]))
        excluded = normalize_dates(json.loads(constraint["excluded_dates_json"]))
        from datetime import datetime as _dt
        end = _dt.strptime(deadline, "%Y-%m-%d").date()
        slots = expand_slots(availability, excluded, now.replace(tzinfo=None), end)
        raw = sum(s.minutes for s in slots)
        buffer = math.ceil(config.BUFFER_RATIO * raw)
        capacity = {"C": raw, "B": buffer, "C_prime": raw - buffer}
        weekly_minutes = sum(
            _minutes(a, b) for day in availability.values() for a, b in day)

    concept_rows = db.query(
        "SELECT concept_id, reference_minutes FROM concept"
        " WHERE course_id = ? AND status = 'enabled'", (int(course.get("course_id", 1)),))
    course_minutes = sum(int(r["reference_minutes"]) for r in concept_rows)
    covered = sorted({int(t["concept_id"]) for t in board.get("tasks", [])})
    covered_minutes = sum(int(r["reference_minutes"]) for r in concept_rows
                          if int(r["concept_id"]) in set(covered))

    progress = board.get("progress") or {}
    planned = int(progress.get("planned_minutes") or 0)
    facts = {
        "课程": course.get("name", ""),
        "学期": course.get("semester", ""),
        "课程总学时": int(course.get("total_hours") or 0),
        "计划版本": board.get("version_no"),
        "截止日期": deadline,
        "每周可用分钟": weekly_minutes,
        "可排总量C": capacity["C"],
        "缓冲B": capacity["B"],
        "可排上限C_prime": capacity["C_prime"],
        "计划总时长T": planned,
        "缺口D": max(0, planned - capacity["C_prime"]),
        "利用率": round(planned / capacity["C_prime"], 4) if capacity["C_prime"] else 0,
        "覆盖知识点": len(covered),
        "课程知识点总数": len(concept_rows),
        "覆盖分钟": covered_minutes,
        "课程参考总量": course_minutes,
        "任务数": int(progress.get("total_tasks") or 0),
        "已完成": int(progress.get("done_tasks") or 0),
        "完成率": progress.get("completion_rate", 0),
        "逾期任务数": len(progress.get("overdue_tasks") or []),
        "校验问题": [i.get("code") for i in board.get("issues", [])],
        "未排入": [u.get("reason") for u in board.get("unscheduled", [])][:5],
        "范围": "整门课" if constraint.get("extra_concept_ids_json") not in
                (None, "[]") else "只学目标及其先修",
    }
    return facts


def _minutes(start, end) -> int:
    """时段长度（分钟）；兼容 HH:MM 字符串与 datetime.time。"""
    def parse(value) -> int:
        if hasattr(value, "hour"):
            return value.hour * 60 + value.minute
        hour, minute = str(value).split(":")
        return int(hour) * 60 + int(minute)
    return max(0, parse(end) - parse(start))


def template_answer(facts: Dict[str, Any], question: str) -> str:
    """模型不可用时的兜底：直接读事实讲结论。"""
    gap = facts["缺口D"]
    rate = facts["完成率"]
    overdue = facts["逾期任务数"]
    coverage = "%d/%d 个知识点" % (facts["覆盖知识点"], facts["课程知识点总数"])
    if gap > 0:
        return ("这份计划排不下：需要 %d 分钟，可排上限只有 %d 分钟，差 %d 分钟。"
                "建议先把截止日期往后挪，或把范围从「整门课」改回目标闭包（当前覆盖 %s）。"
                % (facts["计划总时长T"], facts["可排上限C_prime"], gap, coverage))
    if overdue > 0:
        return ("目前有 %d 个任务逾期，完成率 %.0f%%，计划共 %d 分钟、可用上限 %d 分钟，"
                "时间还够。建议先补最靠前的逾期任务，再决定是否调整计划（调整会生成新版本，"
                "旧打卡记录不会丢）。"
                % (overdue, rate * 100, facts["计划总时长T"], facts["可排上限C_prime"]))
    return ("当前计划覆盖 %s，共 %d 分钟，可用上限 %d 分钟，还剩 %d 分钟余量；"
            "已完成 %d/%d。建议按课表推进，落后超过 48 小时再考虑调整。"
            % (coverage, facts["计划总时长T"], facts["可排上限C_prime"],
               facts["可排上限C_prime"] - facts["计划总时长T"],
               facts["已完成"], facts["任务数"]))


def advise(provider: Optional[BaseProvider], facts: Dict[str, Any],
           question: str) -> Tuple[str, str, Optional[str]]:
    """返回 (回答, 模式, 降级原因)。"""
    fallback = template_answer(facts, question)
    if provider is None:
        return fallback, MODE_LOCAL, "UNAVAILABLE"
    name = getattr(provider, "name", "")
    # mock 替身只会做知识点映射，问答一律走模板，避免输出牛头不对马嘴；
    # 但替身被设为失败模式时，仍按真实降级路径返回原因，便于测试覆盖
    if name != "real":
        fail = getattr(provider, "fail_mode", None)
        if fail == "timeout":
            return fallback, MODE_LOCAL, "TIMEOUT"
        if fail == "unavailable":
            return fallback, MODE_LOCAL, "UNAVAILABLE"
        if fail == "garbage":
            return fallback, MODE_LOCAL, "INVALID_OUTPUT"
        return fallback, "mock", None
    prompt = ("%s\n\n事实：\n%s\n\n用户问题：%s\n\n请用中文回答。"
              % (SYSTEM_PROMPT, json.dumps(facts, ensure_ascii=False), question))
    try:
        raw = provider.complete(prompt)
    except ProviderTimeout:
        return fallback, MODE_LOCAL, "TIMEOUT"
    except ProviderError:
        return fallback, MODE_LOCAL, "UNAVAILABLE"
    text = (raw or "").strip()
    # 模型有时会退回 JSON 或空串：这类输出不能当作解释，直接降级
    if len(text) < 6 or text.startswith(("{", "```")):
        return fallback, MODE_LOCAL, "INVALID_OUTPUT"
    return text, MODE_LLM, None
