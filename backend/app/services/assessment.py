"""测评：出题 → 作答 → 判分 → 可解释报告（对应 D02 F-16）。

设计原则（与抽取、问答一致）：
- 出题与判分都要模型输出**结构化 JSON**，非法输出直接降级；
- 选择题由程序比对答案键，简答题按"采分点"判并**由程序重算分数**；
- 模型自报分数与重算分数偏差超过 5 分 → 转人工复核，不计入总分；
- 报告的数字全部来自程序计算，模型只负责写解释文字。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.errors import NotFound, StateError, ValidationError
from ..db.uow import Database, UnitOfWork
from .agent import _parse_json_object
from .provider import (BaseProvider, ProviderError, ProviderTimeout,
                       ProviderTruncated)

ITEMS_PER_PAPER = 4
DEFAULT_AUTHOR_TOKENS = 3000
DEFAULT_GRADE_TOKENS = 1024
SINGLE_COUNT = 2
MASTERED_RATIO = 0.8
WEAK_RATIO = 0.5
DEVIATION_LIMIT = 5

MODE_LLM = "llm"
MODE_LOCAL = "local"

AUTHOR_PROMPT = """你是课程测评出题助手。依据给定知识点信息，出一份 4 题的小测：2 道单选、2 道简答。
只输出 JSON，结构如下（不要任何解释文字）：
{"title":"...","items":[
 {"no":1,"type":"single","stem":"...","options":["A...","B...","C...","D..."],"answer":"B","rubric":["知识点要点1"],"points":25},
 {"no":2,"type":"single",...},
 {"no":3,"type":"short","stem":"...","rubric":["要点1","要点2","要点3"],"points":25},
 {"no":4,"type":"short",...}]}
要求：
1. 每题 points 之和为 100；
2. 单选必须有 4 个选项，answer 是正确选项的字母；
3. 简答必须给 2–3 条可判定的采分点（rubric），不要含糊表述；
4. 只能基于给定信息出题，不要引入未给出的教材细节；
5. 题干用中文、面向学生。
知识点信息：{context}"""

GRADE_PROMPT = """你是阅卷助手。请按采分点判断学生简答题的作答，只输出 JSON：
{"hits":[命中采分点的序号，从0开始],"misses":[未命中的序号],"quotes":["学生原话片段"],"score":学生应得分数(整数),"confidence":0到1的小数,"reason":"一句话理由"}
要求：只依据采分点判断；引用学生原话作为依据；score 不得超过题目满分 {points}。
题目：{stem}
采分点：{rubric}
学生作答：{answer}"""


# ---------------------------------------------------------------- 出题
def _complete_json(provider: BaseProvider, prompt: str,
                   retries: int = 1,
                   max_tokens: int = 320) -> Optional[Dict[str, Any]]:
    """调用模型并解析 JSON；截断时提高预算重试，解析失败时用更严格提示重试。"""
    attempt_prompt = prompt
    budget = int(max_tokens)
    for attempt in range(retries + 1):
        try:
            raw = provider.complete(attempt_prompt, max_tokens=budget)
        except ProviderTruncated:
            # 思考模式会吃掉一部分预算：翻倍后重试一次
            budget = min(budget * 2, 8000)
            if attempt >= retries:
                raise
            continue
        except ProviderTimeout:
            raise
        except ProviderError:
            raise
        try:
            data = _parse_json_object(raw or "")
        except (ValueError, TypeError):
            data = None
        if isinstance(data, dict):
            return data
        attempt_prompt = prompt + "\n\n注意：上一次输出不是合法 JSON。请只输出一个 JSON 对象，" \
                                  "不要代码围栏、不要额外文字，字符串内的换行写成 \\n。"
    return None


def _context(concept: sqlite3.Row, resources: Sequence[sqlite3.Row]) -> str:
    parts = [
        "知识点：%s" % concept["name"],
        "章节：%s" % concept["chapter"],
        "难度（1–5）：%d" % int(concept["difficulty"]),
        "参考学习时长：%d 分钟" % int(concept["reference_minutes"]),
    ]
    outline = (concept["outline"] or "").strip()
    if outline:
        parts.append("管理员标注的要点：\n" + outline)
    summaries = [r["summary"].strip() for r in resources if (r["summary"] or "").strip()]
    if summaries:
        parts.append("已有资料摘要：\n" + "\n".join("- " + s for s in summaries[:3]))
    return "\n".join(parts)


def _normalize_items(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        return []
    items: List[Dict[str, Any]] = []
    for index, item in enumerate(raw["items"][:ITEMS_PER_PAPER], start=1):
        if not isinstance(item, dict):
            return []
        kind = item.get("type")
        stem = str(item.get("stem") or "").strip()
        if kind not in ("single", "short") or not stem:
            return []
        points = int(item.get("points") or 0)
        if points <= 0:
            return []
        entry: Dict[str, Any] = {
            "no": index, "type": kind, "stem": stem, "points": points,
            "rubric": [str(x) for x in (item.get("rubric") or [])][:3],
        }
        if kind == "single":
            options = [str(x).strip() for x in (item.get("options") or [])]
            answer = str(item.get("answer") or "").strip().upper()
            if len(options) != 4 or answer not in ("A", "B", "C", "D"):
                return []
            entry["options"] = options
            entry["answer"] = answer
        if not entry["rubric"]:
            return []
        items.append(entry)
    return items


def generate_items(provider: Optional[BaseProvider], concept: sqlite3.Row,
                   resources: Sequence[sqlite3.Row],
                   max_tokens: int = DEFAULT_AUTHOR_TOKENS
                   ) -> Tuple[Optional[str], List[Dict[str, Any]], str, Optional[str]]:
    """返回 (标题, 题目, 模式, 降级原因)；模型不可用时题目为空。"""
    if provider is None or getattr(provider, "name", "") != "real":
        return None, [], "local", "UNAVAILABLE"
    prompt = AUTHOR_PROMPT.replace("{context}", _context(concept, resources))
    try:
        data = _complete_json(provider, prompt, max_tokens=max_tokens)
    except ProviderTimeout:
        return None, [], "local", "TIMEOUT"
    except ProviderError:
        return None, [], "local", "UNAVAILABLE"
    items = _normalize_items(data)
    if not items:
        return None, [], "local", "INVALID_OUTPUT"
    title = str((data or {}).get("title") or "").strip() or ("%s 小测" % concept["name"])
    return title[:120], items, MODE_LLM, None


# ---------------------------------------------------------------- 判分
def _norm_text(value: str) -> str:
    return "".join(str(value).split()).lower()


def _grade_single(item: Dict[str, Any], answer: str) -> Dict[str, Any]:
    key = str(item.get("answer") or "").upper()
    picked = str(answer or "").strip().upper()[:1]
    correct = picked == key
    return {
        "no": item["no"], "type": "single", "points": item["points"],
        "got": item["points"] if correct else 0,
        "hits": item["rubric"][:1] if correct else [],
        "misses": [] if correct else item["rubric"][:1],
        "quotes": [] if correct else [picked or "（未作答）"],
        "confidence": 1.0, "review_flag": 0,
    }


def _grade_short(provider: Optional[BaseProvider], item: Dict[str, Any],
                 answer: str, max_tokens: int = DEFAULT_GRADE_TOKENS) -> Dict[str, Any]:
    rubric = item.get("rubric") or []
    base = {"no": item["no"], "type": "short", "points": item["points"]}
    if provider is None or getattr(provider, "name", "") != "real":
        return {**base, "got": 0, "hits": [], "misses": rubric,
                "quotes": [], "confidence": None, "review_flag": 1}
    prompt = (GRADE_PROMPT.replace("{points}", str(item["points"]))
              .replace("{stem}", item["stem"])
              .replace("{rubric}", json.dumps(rubric, ensure_ascii=False))
              .replace("{answer}", answer or "（未作答）"))
    try:
        data = _complete_json(provider, prompt, max_tokens=max_tokens)
    except (ProviderTimeout, ProviderError):
        data = None
    if not isinstance(data, dict) or not rubric:
        return {**base, "got": 0, "hits": [], "misses": rubric,
                "quotes": [], "confidence": None, "review_flag": 1}
    hits_idx = [int(i) for i in data.get("hits") or [] if isinstance(i, int) and 0 <= i < len(rubric)]
    hits = [rubric[i] for i in sorted(set(hits_idx))]
    misses = [r for i, r in enumerate(rubric) if i not in hits_idx]
    got = int(round(item["points"] * len(hits) / len(rubric)))
    review = 0
    # 模型自报分数与重算分数偏差过大 → 转人工复核
    reported = data.get("score")
    if isinstance(reported, (int, float)) and abs(int(reported) - got) > DEVIATION_LIMIT:
        review = 1
    return {**base, "got": got, "hits": hits, "misses": misses,
            "quotes": [str(q)[:120] for q in (data.get("quotes") or [])][:3],
            "confidence": float(data.get("confidence") or 0) or None,
            "review_flag": review}


def grade(provider: Optional[BaseProvider], items: Sequence[Dict[str, Any]],
          answers: Dict[str, str], max_tokens: int = DEFAULT_GRADE_TOKENS
          ) -> Tuple[int, int, List[Dict[str, Any]], str]:
    details: List[Dict[str, Any]] = []
    for item in items:
        answer = answers.get(str(item["no"]), "")
        if item["type"] == "single":
            details.append(_grade_single(item, answer))
        else:
            details.append(_grade_short(provider, item, answer, max_tokens))
    score = sum(d["got"] for d in details)
    max_score = sum(int(i["points"]) for i in items)
    status = "manual_review" if any(d["review_flag"] for d in details) else "graded"
    return score, max_score, details, status


# ---------------------------------------------------------------- 报告
def build_report(concept_name: str, score: int, max_score: int,
                 details: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ratio = round(score / max_score, 4) if max_score else 0
    if ratio >= MASTERED_RATIO:
        action, suggestion = "mark_mastered", "掌握良好，建议标记为已掌握，后续计划不再排这个知识点。"
    elif ratio < WEAK_RATIO:
        action, suggestion = "add_practice", "掌握不足，建议该知识点多加 1 片练习，再测一次。"
    else:
        action, suggestion = "keep", "基本掌握，保持原计划，过几天再测一次巩固。"
    wrong = [d for d in details if d["got"] < d["points"]]
    return {
        "concept": concept_name,
        "score": score,
        "max_score": max_score,
        "ratio": ratio,
        "status": "manual_review" if any(d["review_flag"] for d in details) else "graded",
        "suggestion": suggestion,
        "action": action,
        "weak_points": [m for d in wrong for m in d["misses"]][:5],
        "items": list(details),
    }


# ---------------------------------------------------------------- 存取
def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def save_paper(db: Database, concept: sqlite3.Row, title: str,
               items: Sequence[Dict[str, Any]], author_id: int,
               model: str) -> int:
    with UnitOfWork(db) as uow:
        cur = uow.execute(
            "INSERT INTO assessment_paper(course_id,concept_id,title,items_json,"
            "status,created_by,created_at,model) VALUES(?,?,?,?, 'draft',?,?,?)",
            (int(concept["course_id"]), int(concept["concept_id"]), title,
             json.dumps(list(items), ensure_ascii=False), author_id, _now(), model))
        return int(cur.lastrowid)


def publish_paper(db: Database, paper_id: int, author_id: int) -> sqlite3.Row:
    rows = db.query("SELECT * FROM assessment_paper WHERE paper_id = ?", (paper_id,))
    if not rows:
        raise NotFound("E1002", "试卷不存在")
    if int(rows[0]["created_by"]) != int(author_id):
        raise NotFound("E1002", "试卷不存在")
    with UnitOfWork(db) as uow:
        uow.execute("UPDATE assessment_paper SET status='published', published_at=?"
                    " WHERE paper_id = ?", (_now(), paper_id))
    return db.query("SELECT * FROM assessment_paper WHERE paper_id = ?", (paper_id,))[0]


def published_papers(db: Database, course_id: int) -> List[sqlite3.Row]:
    return db.query(
        "SELECT paper_id, concept_id, title, items_json, published_at"
        " FROM assessment_paper WHERE course_id = ? AND status = 'published'"
        " ORDER BY paper_id DESC", (course_id,))


def public_items(items_json: str) -> List[Dict[str, Any]]:
    """发给学生的题目：去掉答案键与采分点。"""
    items = json.loads(items_json or "[]")
    out = []
    for item in items:
        entry = {"no": item["no"], "type": item["type"], "stem": item["stem"],
                 "points": item["points"]}
        if item["type"] == "single":
            entry["options"] = item.get("options", [])
        out.append(entry)
    return out


def save_attempt(db: Database, paper: sqlite3.Row, student_id: int,
                 answers: Dict[str, str], score: int, max_score: int,
                 details: Sequence[Dict[str, Any]], status: str,
                 report: Dict[str, Any], model: str) -> int:
    with UnitOfWork(db) as uow:
        cur = uow.execute(
            "INSERT INTO assessment_attempt(paper_id,student_id,answers_json,"
            "score,max_score,status,report_json,created_at,graded_at,model)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (int(paper["paper_id"]), student_id,
             json.dumps(answers, ensure_ascii=False), score, max_score, status,
             json.dumps(report, ensure_ascii=False), _now(), _now(), model))
        attempt_id = int(cur.lastrowid)
        for detail in details:
            uow.execute(
                "INSERT INTO assessment_item(attempt_id,no,type,points,got,"
                "hits_json,misses_json,quotes_json,confidence,review_flag)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (attempt_id, detail["no"], detail["type"], detail["points"],
                 detail["got"], json.dumps(detail["hits"], ensure_ascii=False),
                 json.dumps(detail["misses"], ensure_ascii=False),
                 json.dumps(detail["quotes"], ensure_ascii=False),
                 detail["confidence"], detail["review_flag"]))
    return attempt_id
