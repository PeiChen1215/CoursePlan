"""课程内容管理（对应 D06 第 4 章 M-02）。

要点：
- 先修关系必须在「原图 ∪ 本批」上做环检测，单条校验只能发现自环；
- 批量提交要么全成、要么全退；
- 被版本引用的知识点只能停用，不能删除；
- 任何写操作都要递增 content_revision。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ..core.errors import NotFound, PrereqCycle, StateError, ValidationError
from ..db.uow import Database, UnitOfWork

MAX_BATCH = 40


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- 环检测
def detect_cycle(edges: Iterable[Tuple[int, int]], nodes: Iterable[int]) -> Optional[List[int]]:
    """DFS 三色标记；返回环路节点序列（首尾相同），无环返回 None。"""
    adj: Dict[int, List[int]] = {}
    for u, v in edges:
        adj.setdefault(u, []).append(v)
    color: Dict[int, int] = {n: 0 for n in nodes}       # 0 白 / 1 灰 / 2 黑
    path: List[int] = []

    def dfs(u: int) -> Optional[List[int]]:
        color[u] = 1
        path.append(u)
        for v in adj.get(u, []):
            if color.get(v, 0) == 1:
                return path[path.index(v):] + [v]
            if color.get(v, 0) == 0:
                found = dfs(v)
                if found:
                    return found
        path.pop()
        color[u] = 2
        return None

    for n in sorted(nodes):
        if color.get(n, 0) == 0:
            found = dfs(n)
            if found:
                return found
    return None


@dataclass(frozen=True)
class ConceptInput:
    name: str
    chapter: str
    difficulty: int
    reference_minutes: int
    objectives: Sequence[str] = ()
    pitfalls: Sequence[str] = ()


class ContentService:
    def __init__(self, db: Database):
        self.db = db

    # ---------------- 课程
    def list_courses(self) -> List[sqlite3.Row]:
        return self.db.query(
            "SELECT course_id, name, semester, total_hours, status, content_revision"
            " FROM course ORDER BY course_id")

    def get_course(self, course_id: int) -> sqlite3.Row:
        rows = self.db.query("SELECT * FROM course WHERE course_id = ?", (course_id,))
        if not rows:
            raise NotFound("E1002", "课程不存在")
        return rows[0]

    def create_course(self, maintainer_id: int, name: str, semester: str,
                      total_hours: int, now: datetime) -> int:
        if not name or len(name) > 100:
            raise ValidationError("E1001", "课程名长度需在 1–100 之间", field="name")
        if total_hours <= 0:
            raise ValidationError("E1001", "总学时需大于 0", field="total_hours")
        if self.db.scalar("SELECT COUNT(*) FROM course"):
            raise StateError("E1003", "系统只支持一门课程，请先归档现有课程")
        with UnitOfWork(self.db) as uow:
            cur = uow.execute(
                "INSERT INTO course(maintainer_id,name,semester,total_hours,status)"
                " VALUES(?,?,?,?,'enabled')", (maintainer_id, name, semester, total_hours))
            return int(cur.lastrowid)

    # ---------------- 知识点
    def list_concepts(self, course_id: int, include_disabled: bool = False):
        sql = ("SELECT concept_id, name, chapter, difficulty, reference_minutes, status"
               " FROM concept WHERE course_id = ?")
        if not include_disabled:
            sql += " AND status = 'enabled'"
        return self.db.query(sql + " ORDER BY concept_id", (course_id,))

    def save_concept(self, course_id: int, data: ConceptInput) -> int:
        self._validate_concept(data)
        self.get_course(course_id)
        rows = self.db.query("SELECT concept_id FROM concept WHERE course_id=? AND name=?",
                             (course_id, data.name))
        if rows:
            raise ValidationError("E1001", "同课程下知识点名称重复", field="name")
        with UnitOfWork(self.db) as uow:
            cur = uow.execute(
                "INSERT INTO concept(course_id,name,chapter,difficulty,reference_minutes,"
                "objectives_json,pitfalls_json,status) VALUES(?,?,?,?,?,?,?,'enabled')",
                (course_id, data.name, data.chapter, data.difficulty,
                 data.reference_minutes, _json_list(data.objectives),
                 _json_list(data.pitfalls)))
            uow.execute("UPDATE course SET content_revision = content_revision + 1"
                        " WHERE course_id = ?", (course_id,))
            return int(cur.lastrowid)

    def _validate_concept(self, d: ConceptInput) -> None:
        if not d.name or len(d.name) > 100:
            raise ValidationError("E1001", "名称长度需在 1–100 之间", field="name")
        if not d.chapter:
            raise ValidationError("E1001", "章节不能为空", field="chapter")
        if not 1 <= d.difficulty <= 5:
            raise ValidationError("E1001", "难度需在 1–5 之间", field="difficulty")
        if not 5 <= d.reference_minutes <= 600:
            raise ValidationError("E1001", "参考时长需在 5–600 分钟", field="reference_minutes")

    # ---------------- 先修关系
    def list_prereqs(self, course_id: int):
        return self.db.query(
            "SELECT from_concept_id, to_concept_id FROM prerequisite WHERE course_id = ?"
            " ORDER BY from_concept_id, to_concept_id", (course_id,))

    def submit_prereqs(self, course_id: int, batch: Sequence[Tuple[int, int]],
                       now: datetime) -> int:
        if not batch:
            raise ValidationError("E1001", "本批为空", field="batch")
        if len(batch) > MAX_BATCH:
            raise ValidationError("E1001", "单批最多 %d 条" % MAX_BATCH, field="batch")
        self.get_course(course_id)

        concept_ids = {int(r["concept_id"]) for r in self.list_concepts(course_id, True)}
        for idx, (u, v) in enumerate(batch, start=1):
            if int(u) == int(v):
                raise ValidationError("E1001", "第 %d 行为自环" % idx, field="batch")
            if int(u) not in concept_ids or int(v) not in concept_ids:
                raise ValidationError("E1001", "第 %d 行两端不属于本课程" % idx,
                                      field="batch")

        cleaned = sorted({(int(u), int(v)) for u, v in batch})
        existing = {(int(r["from_concept_id"]), int(r["to_concept_id"]))
                    for r in self.list_prereqs(course_id)}
        graph = set(existing) | set(cleaned)
        cycle = detect_cycle(graph, concept_ids)
        if cycle:
            raise PrereqCycle("E2001", "先修关系成环", detail={"cycle": cycle})

        with UnitOfWork(self.db) as uow:
            for u, v in cleaned:
                if (u, v) in existing:
                    continue
                uow.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                            " VALUES(?,?,?)", (course_id, u, v))
            uow.execute("UPDATE course SET content_revision = content_revision + 1"
                        " WHERE course_id = ?", (course_id,))
        return len(cleaned)

    # ---------------- 停用与影响
    def impact_of(self, concept_id: int) -> Dict[str, int]:
        refs = self.db.scalar(
            "SELECT COUNT(*) FROM version_task WHERE task_id IN"
            " (SELECT task_id FROM plan_task WHERE concept_id = ?)", (concept_id,)) or 0
        return {"version_task_refs": int(refs)}

    def disable_concept(self, concept_id: int) -> Dict[str, int]:
        rows = self.db.query("SELECT course_id FROM concept WHERE concept_id = ?",
                             (concept_id,))
        if not rows:
            raise NotFound("E1002", "知识点不存在")
        course_id = int(rows[0]["course_id"])
        with UnitOfWork(self.db) as uow:
            uow.execute("UPDATE concept SET status='disabled' WHERE concept_id = ?",
                        (concept_id,))
            uow.execute("UPDATE course SET content_revision = content_revision + 1"
                        " WHERE course_id = ?", (course_id,))
        return self.impact_of(concept_id)


def _json_list(items: Sequence[str]) -> str:
    import json
    return json.dumps(list(items), ensure_ascii=False)
