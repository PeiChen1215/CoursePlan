"""补齐最后 4 处未覆盖分支（要点更新成功路径、迁移、截断异常）。"""
from __future__ import annotations

import json
import sqlite3

import pytest

from app.services.provider import ProviderTruncated, RealProvider

from .test_assessment_api import FakeReal, VALID, auth, client, patched  # noqa: F401


def test_patch_concept_success(client):
    admin = auth(client)
    response = client.patch("/api/concepts/1", headers=admin,
                            json={"outline": "聚合可独立存在\n组合生命周期一致"})
    assert response.status_code == 200
    assert "聚合" in response.json()["data"]["outline"]
    concepts = client.get("/api/courses/1/concepts", headers=admin).json()["data"]["items"]
    assert any(item.get("outline") for item in concepts)


def test_migration_adds_reason_column(tmp_path):
    from app.db.uow import Database

    db = Database(tmp_path / "old.db")
    conn = db.connect()
    conn.executescript(
        "CREATE TABLE concept (concept_id INTEGER PRIMARY KEY, course_id INTEGER,"
        " name TEXT, chapter TEXT, difficulty INTEGER, reference_minutes INTEGER,"
        " status TEXT);"
        "CREATE TABLE assessment_item (item_id INTEGER PRIMARY KEY, attempt_id INTEGER,"
        " no INTEGER, type TEXT, points INTEGER, got INTEGER, hits_json TEXT,"
        " misses_json TEXT, quotes_json TEXT, confidence REAL, review_flag INTEGER);"
    )
    conn.commit()
    conn.close()

    db._migrate(db.connect())
    columns = [row[1] for row in db.connect().execute("PRAGMA table_info(assessment_item)")]
    assert "reason" in columns


def test_content_update_outline_success(seeded):
    from app.services.content import ContentService

    service = ContentService(seeded)
    concept_id = seeded.query("SELECT concept_id FROM concept LIMIT 1")[0]["concept_id"]
    row = service.update_concept_outline(concept_id, "  要点一\n要点二  ")
    assert row["outline"] == "要点一\n要点二"


def test_provider_raises_truncated_on_length(monkeypatch):
    provider = RealProvider(key="k", timeout=5)

    def fake_request(path, payload, method="POST"):
        return {"choices": [{"message": {"content": "{\"items\": ["},
                             "finish_reason": "length"}]}

    monkeypatch.setattr(provider, "_request", fake_request)
    with pytest.raises(ProviderTruncated) as error:
        provider.complete("prompt", max_tokens=120)
    assert "截断" in str(error.value)


def test_update_outline_rejects_too_long(seeded):
    from app.core.errors import ValidationError
    from app.services.content import ContentService

    service = ContentService(seeded)
    concept_id = seeded.query("SELECT concept_id FROM concept LIMIT 1")[0]["concept_id"]
    with pytest.raises(ValidationError) as error:
        service.update_concept_outline(concept_id, "字" * 1001)
    assert error.value.field == "outline"
