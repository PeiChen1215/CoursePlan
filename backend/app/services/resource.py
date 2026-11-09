"""课程资源维护与关联（对应 D02 F-05、AT-09、AT-10）。

规则：
- 资源必须属于同一门课；标题 1–200，类型四选一；
- url 必须是 http(s)，link 类型必须有 url；
- url 与 summary 至少给一个（schema 已约束，这里给出可定位的错误）；
- 知识点关联是多对多，重复关联幂等；
- 资源被知识点引用时只能停用，历史任务仍可打开。
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from ..core.errors import NotFound, ValidationError
from ..db.uow import Database, UnitOfWork

RESOURCE_TYPES = {"document", "video", "exercise", "link"}

TYPE_LABEL = {"document": "文档", "video": "视频", "exercise": "练习", "link": "链接"}


@dataclass(frozen=True)
class ResourceInput:
    title: str
    type: str
    url: Optional[str] = None
    summary: Optional[str] = None
    read_minutes: int = 0


class ResourceService:
    def __init__(self, db: Database):
        self.db = db

    # ---------------------------------------------------------------- 校验
    def _validate(self, data: ResourceInput) -> None:
        if not (1 <= len(data.title.strip()) <= 200):
            raise ValidationError("E1001", "资料标题长度需在 1–200 之间", field="title")
        if data.type not in RESOURCE_TYPES:
            raise ValidationError("E1001", "资料类型只能是 document / video / exercise / link",
                                  field="type")
        url = (data.url or "").strip()
        summary = (data.summary or "").strip()
        if not url and not summary:
            raise ValidationError("E1001", "网址与摘要至少要填一个", field="url")
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise ValidationError("E1001", "网址必须以 http:// 或 https:// 开头", field="url")
        if url and len(url) > 2048:
            raise ValidationError("E1001", "网址过长（最多 2048 字符）", field="url")
        if data.type == "link" and not url:
            raise ValidationError("E1001", "链接类资料必须填网址", field="url")
        if not (0 <= data.read_minutes <= 240):
            raise ValidationError("E1001", "预计阅读时长需在 0–240 分钟", field="read_minutes")

    # ---------------------------------------------------------------- 资源
    def list_resources(self, course_id: int, include_disabled: bool = True) -> List[dict]:
        sql = ("SELECT resource_id, title, type, url, summary, read_minutes, status"
               " FROM resource WHERE course_id = ?")
        if not include_disabled:
            sql += " AND status = 'enabled'"
        rows = self.db.query(sql + " ORDER BY resource_id", (course_id,))
        return [{
            "resource_id": int(r["resource_id"]),
            "title": r["title"],
            "type": r["type"],
            "type_label": TYPE_LABEL.get(r["type"], r["type"]),
            "url": r["url"],
            "summary": r["summary"],
            "read_minutes": int(r["read_minutes"]),
            "status": r["status"],
        } for r in rows]

    def create_resource(self, course_id: int, data: ResourceInput) -> int:
        self._validate(data)
        course = self.db.query("SELECT course_id FROM course WHERE course_id = ?",
                               (course_id,))
        if not course:
            raise NotFound("E1002", "课程不存在")
        with UnitOfWork(self.db) as uow:
            cur = uow.execute(
                "INSERT INTO resource(course_id,title,type,url,summary,read_minutes,status)"
                " VALUES(?,?,?,?,?,?,'enabled')",
                (course_id, data.title.strip(), data.type,
                 (data.url or "").strip() or None,
                 (data.summary or "").strip() or None, data.read_minutes))
            return int(cur.lastrowid)

    def disable_resource(self, resource_id: int) -> Dict[str, int]:
        rows = self.db.query("SELECT course_id FROM resource WHERE resource_id = ?",
                             (resource_id,))
        if not rows:
            raise NotFound("E1002", "资料不存在")
        with UnitOfWork(self.db) as uow:
            uow.execute("UPDATE resource SET status = 'disabled' WHERE resource_id = ?",
                        (resource_id,))
        return {"linked_concepts": self._link_count(resource_id)}

    def _link_count(self, resource_id: int) -> int:
        return int(self.db.scalar(
            "SELECT COUNT(*) FROM concept_resource WHERE resource_id = ?",
            (resource_id,)) or 0)

    # ---------------------------------------------------------------- 关联
    def concept_resources(self, concept_id: int) -> List[dict]:
        rows = self.db.query(
            "SELECT r.resource_id, r.title, r.type, r.url, r.summary, r.read_minutes,"
            " r.status FROM concept_resource cr JOIN resource r"
            " ON r.resource_id = cr.resource_id"
            " WHERE cr.concept_id = ? ORDER BY r.resource_id", (concept_id,))
        return [{
            "resource_id": int(r["resource_id"]), "title": r["title"],
            "type": r["type"], "type_label": TYPE_LABEL.get(r["type"], r["type"]),
            "url": r["url"], "summary": r["summary"],
            "read_minutes": int(r["read_minutes"]), "status": r["status"],
        } for r in rows]

    def set_concept_resources(self, concept_id: int,
                             resource_ids: Sequence[int]) -> Dict[str, int]:
        """整体替换某个知识点的资料关联（先删后插，幂等）。"""
        concept = self.db.query("SELECT course_id FROM concept WHERE concept_id = ?",
                                (concept_id,))
        if not concept:
            raise NotFound("E1002", "知识点不存在")
        course_id = int(concept[0]["course_id"])

        valid = {int(r["resource_id"]) for r in self.db.query(
            "SELECT resource_id FROM resource WHERE course_id = ?", (course_id,))}
        for rid in resource_ids:
            if int(rid) not in valid:
                raise ValidationError("E1001", "资料不属于本课程", field="resource_ids")

        with UnitOfWork(self.db) as uow:
            uow.execute("DELETE FROM concept_resource WHERE concept_id = ?", (concept_id,))
            for rid in sorted({int(r) for r in resource_ids}):
                uow.execute("INSERT INTO concept_resource(concept_id,resource_id,course_id)"
                            " VALUES(?,?,?)", (concept_id, rid, course_id))
        return {"linked": len(set(int(r) for r in resource_ids))}

    def resources_for_tasks(self, task_concept_ids: Sequence[int]) -> Dict[int, List[dict]]:
        """给看板用：一次取回多个知识点的可用资料。"""
        if not task_concept_ids:
            return {}
        placeholders = ",".join("?" for _ in task_concept_ids)
        rows = self.db.query(
            "SELECT cr.concept_id, r.resource_id, r.title, r.type, r.url, r.summary,"
            " r.read_minutes FROM concept_resource cr JOIN resource r"
            " ON r.resource_id = cr.resource_id"
            " WHERE r.status = 'enabled' AND cr.concept_id IN (%s)"
            " ORDER BY cr.concept_id, r.resource_id" % placeholders,
            tuple(int(c) for c in task_concept_ids))
        out: Dict[int, List[dict]] = {}
        for r in rows:
            cid = int(r["concept_id"])
            rid = int(r["resource_id"])
            out.setdefault(cid, []).append({
                "resource_id": rid, "title": r["title"],
                "type": r["type"], "type_label": TYPE_LABEL.get(r["type"], r["type"]),
                "url": r["url"], "summary": r["summary"],
                "read_minutes": int(r["read_minutes"]),
            })
        return out
