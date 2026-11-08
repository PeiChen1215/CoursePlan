"""追问与抽取（对应 D06 第 6 章 M-04）。

规则优先、模型兜底、输出必校验：
- 日期、时长这类有明确写法的信息用本地规则解析，不调模型；
- 目标映射四层降级：精确 → 别名 → 模型（限候选内）→ 给候选列表；
- 缺字段一次最多追问 2 项；模型超时/不可用/乱答一律降级，不清空已填字段。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence

from .provider import ProviderError, ProviderTimeout, MockProvider

WEEKDAY_CN = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

# 追问优先级：不填就无法排程的排前面（D06 §6.6.3）
FIELD_PRIORITY = ["target_concept_id", "deadline", "availability", "daily_limit"]
REQUIRED_FIELDS = FIELD_PRIORITY

QUESTIONS = {
    "target_concept_id": "这次想重点掌握哪个知识点？",
    "deadline": "希望什么时候之前学完？",
    "availability": "每周哪些时间段方便学习？",
    "daily_limit": "每天最多学多久？",
}

MODE_LOCAL = "local"
MODE_MOCK = "mock"
MODE_LLM = "llm"


@dataclass(frozen=True)
class Extraction:
    fields: Dict[str, object]
    questions: List[str]
    candidates: List[dict]
    mode: str
    degraded_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------- 日期归一化
def parse_relative_date(text: str, base: date) -> Optional[date]:
    """纯本地规则：不调模型（D06 §6.6.2）。"""
    if not text:
        return None
    if "今天" in text:
        return base
    if "明天" in text:
        return base + timedelta(days=1)
    if "后天" in text:
        return base + timedelta(days=2)

    m = re.search(r"下(?:个)?(?:周|星期)([一二三四五六日天])", text)
    if m:
        return _weekday(base, WEEKDAY_CN[m.group(1)], next_week=True)

    m = re.search(r"(?:这|本)(?:周|星期)([一二三四五六日天])", text)
    if m:
        return _weekday(base, WEEKDAY_CN[m.group(1)], next_week=False)

    m = re.search(r"(\d+)\s*周(?:后|内|以后)?", text)
    if m:
        return base + timedelta(weeks=int(m.group(1)))
    if "两周内" in text or "半个月" in text:
        return base + timedelta(days=14)

    m = re.search(r"(\d+)\s*天(?:后|内|以后)?", text)
    if m:
        return base + timedelta(days=int(m.group(1)))
    return None


def _weekday(base: date, weekday: int, next_week: bool) -> date:
    monday = base - timedelta(days=base.weekday())
    if next_week:
        monday += timedelta(days=7)
    day = monday + timedelta(days=weekday)
    if not next_week and day < base:
        # 本周已过 → 顺延到下一周，避免生成过去的日期
        day += timedelta(days=7)
    return day


# ---------------------------------------------------------------- 时长
def parse_minutes(text: str) -> Optional[int]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(小时|h|H)", text)
    if m:
        return int(float(m.group(1)) * 60)
    m = re.search(r"([一二两三四五六七八九十])\s*(?:个)?小时", text)
    if m:
        return {"一": 60, "二": 120, "两": 120, "三": 180, "四": 240,
                "五": 300, "六": 360, "七": 420, "八": 480,
                "九": 540, "十": 600}[m.group(1)]
    m = re.search(r"(\d+)\s*分钟", text)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------- 目标映射
def map_target(text: str, concepts: Sequence[dict], provider=None,
               mode: str = MODE_LOCAL) -> tuple:
    """返回 (映射结果, candidates, 实际使用的模式, 降级原因)。"""
    if not text:
        return None, [], mode, None

    said = text.strip()
    exact = [c for c in concepts if c["name"] == said]
    if exact:
        return exact[0], [], MODE_LOCAL, None

    # 名称出现在整句里也算命中：取最长匹配，避免“数组指针”误判成“数组”
    contained = [c for c in concepts if c["name"] and c["name"] in said]
    if contained:
        best = max(contained, key=lambda c: (len(c["name"]), -c["concept_id"]))
        return best, [], MODE_LOCAL, None

    alias = [c for c in concepts if said in (c.get("aliases") or [])]
    if not alias:
        alias = [c for c in concepts
                 if any(a and a in said for a in (c.get("aliases") or []))]
    if alias:
        best = max(alias, key=lambda c: max((len(a) for a in c["aliases"] if a in said),
                                            default=0))
        return best, [], MODE_LOCAL, None

    if provider is not None:
        try:
            raw = provider.complete("从候选里选一个知识点：" + text)
            data = json.loads(raw)
            cid = data.get("concept_id")
            match = [c for c in concepts if c["concept_id"] == cid]
            if match:
                used = getattr(provider, "name", MODE_LLM)
                return match[0], [], used, None
            return None, _candidates(text, concepts), mode, "INVALID_OUTPUT"
        except ProviderTimeout:
            return None, _candidates(text, concepts), MODE_LOCAL, "TIMEOUT"
        except (ProviderError, ValueError, AttributeError):
            return None, _candidates(text, concepts), MODE_LOCAL, "UNAVAILABLE"

    return None, _candidates(text, concepts), mode, None


def _candidates(text: str, concepts: Sequence[dict], limit: int = 5) -> List[dict]:
    scored = []
    for c in concepts:
        score = sum(1 for ch in text if ch in c["name"])
        if score:
            scored.append((score, c))
    scored.sort(key=lambda x: (-x[0], x[1]["concept_id"]))
    return [{"concept_id": c["concept_id"], "name": c["name"]} for _, c in scored[:limit]]


# ---------------------------------------------------------------- 追问
def pick_questions(missing: Sequence[str], limit: int = 2) -> List[str]:
    ordered = [f for f in FIELD_PRIORITY if f in missing]
    return [QUESTIONS[f] for f in ordered[:limit]]


# ---------------------------------------------------------------- 主流程
def extract(utterance: str, filled: Dict[str, object], concepts: Sequence[dict],
            provider=None, base: Optional[date] = None,
            daily_limit_default: int = 480) -> Extraction:
    base = base or date.today()
    fields: Dict[str, object] = dict(filled)
    warnings: List[str] = []
    mode = MODE_LOCAL
    degraded = None
    candidates: List[dict] = []

    due = parse_relative_date(utterance, base)
    if due:
        fields["deadline"] = due.isoformat()

    limit = parse_minutes(utterance)
    if limit:
        fields["daily_limit"] = limit

    target, candidates, used_mode, why = map_target(utterance, concepts, provider, mode)
    if target:
        fields["target_concept_id"] = target["concept_id"]
    if used_mode:
        mode = used_mode
    if why:
        degraded = why

    if "daily_limit" not in fields:
        fields["daily_limit"] = daily_limit_default
        warnings.append("每日上限取默认值 %d 分钟" % daily_limit_default)

    missing = [f for f in REQUIRED_FIELDS if f not in fields
               or fields.get(f) in (None, "", [])]
    questions = pick_questions(missing) if (missing or candidates) else []

    return Extraction(fields=fields, questions=questions, candidates=candidates,
                      mode=mode, degraded_reason=degraded, warnings=warnings)
