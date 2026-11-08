"""M1 · 事务单元与仓储基座测试（对应 D06 第 13 章 M-11）。"""
import sqlite3

import pytest

from app.core.errors import Busy, StateError, ValidationError
from app.db.uow import Database, UnitOfWork, translate_sqlite_error


def count(db, table):
    return db.scalar("SELECT COUNT(*) FROM %s" % table)


# ---------------- 事务语义
def test_commit_persists(seeded):
    with UnitOfWork(seeded) as uow:
        uow.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                    "reference_minutes,status) VALUES(1,'图','第6章',2,30,'enabled')")
    assert count(seeded, "concept") == 4


def test_rollback_leaves_no_residue(seeded):
    before = count(seeded, "concept")
    with pytest.raises(RuntimeError):
        with UnitOfWork(seeded) as uow:
            uow.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                        "reference_minutes,status) VALUES(1,'栈','第7章',3,45,'enabled')")
            inner = uow.fetch_all("SELECT COUNT(*) AS n FROM concept")[0]["n"]
            assert inner == before + 1        # 事务内可见
            raise RuntimeError("boom")
    assert count(seeded, "concept") == before


def test_same_unit_can_be_reentered(seeded):
    """同一 UnitOfWork 可重入（服务层组合），不新开事务、不重复取锁。"""
    before = count(seeded, "concept")
    uow = UnitOfWork(seeded)
    with uow:
        uow.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                    "reference_minutes,status) VALUES(1,'队列','第8章',3,40,'enabled')")
        with uow:                      # 重入：把已有连接让给内层
            uow.fetch_all("SELECT 1")
        assert count(seeded, "concept") == before   # 尚未提交，另一连接看不到
    assert count(seeded, "concept") == before + 1


def test_two_units_at_once_is_busy(seeded):
    """两实例各开事务 = 写锁冲突，后到者收到 E1005（单写者设计）。"""
    from app.core.errors import Busy
    with UnitOfWork(seeded) as outer:
        outer.fetch_all("SELECT 1")
        with pytest.raises(Busy):
            with UnitOfWork(seeded) as inner:
                inner.fetch_all("SELECT 1")


def test_fetch_helpers(seeded):
    with UnitOfWork(seeded) as uow:
        rows = uow.fetch_all("SELECT name FROM concept ORDER BY concept_id")
        one = uow.fetch_one("SELECT name FROM concept WHERE concept_id=1")
        none = uow.fetch_one("SELECT name FROM concept WHERE concept_id=999")
    assert [r["name"] for r in rows] == ["循环结构", "数组", "指针"]
    assert one["name"] == "循环结构"
    assert none is None


def test_connection_released_after_unit(seeded):
    uow = UnitOfWork(seeded)
    with uow:
        uow.fetch_all("SELECT 1")
    assert uow.conn is None


# ---------------- 约束与触发器错误映射
def test_foreign_key_becomes_e1001(seeded):
    with pytest.raises(ValidationError) as e:
        with UnitOfWork(seeded) as uow:
            uow.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                        " VALUES(1,1,999)")
    assert e.value.code == "E1001"


def test_duplicate_prereq_becomes_e1003(seeded):
    with UnitOfWork(seeded) as uow:
        uow.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                    " VALUES(1,1,2)")
    with pytest.raises(StateError) as e:
        with UnitOfWork(seeded) as uow:
            uow.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                        " VALUES(1,1,2)")
    assert e.value.code == "E1003"


def test_self_loop_rejected_by_check(seeded):
    with pytest.raises(StateError):
        with UnitOfWork(seeded) as uow:
            uow.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                        " VALUES(1,1,1)")


def test_immutable_trigger_maps_to_e1003(seeded):
    """计划版本写入后不可修改（D06 §13.6.3）。"""
    conn = seeded.connect()
    conn.execute("INSERT INTO study_plan(student_id,course_id,status,created_at,updated_at)"
                 " VALUES(1,1,'draft','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO plan_version(plan_id,version_no,change_reason,change_note,snapshot_json,"
        "input_hash,engine_version,operator_id,created_at) VALUES"
        "(1,1,'initial','首版','{}',?, '1.0',1,'2026-01-01T00:00:00Z')", ("a" * 64,))
    conn.commit()
    conn.close()

    with pytest.raises(StateError) as e:
        with UnitOfWork(seeded) as uow:
            uow.execute("UPDATE plan_version SET change_note='改' WHERE version_id=1")
    assert "不可修改" in str(e.value) or e.value.code == "E1003"


def test_busy_lock_becomes_e1005(db):
    holder = db.connect()
    holder.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(Busy) as e:
            with UnitOfWork(db) as uow:
                uow.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                            " VALUES('bob','x','student','2026-01-01T00:00:00Z')")
        assert e.value.code == "E1005"
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def test_translate_sqlite_error_passthroughs():
    assert translate_sqlite_error(sqlite3.IntegrityError(
        "FOREIGN KEY constraint failed")).code == "E1001"
    assert translate_sqlite_error(sqlite3.IntegrityError(
        "UNIQUE constraint failed: x")).code == "E1003"
    err = translate_sqlite_error(sqlite3.OperationalError("database is locked"))
    assert err.code == "E1005"


# ---------------- 建库
def test_init_schema_is_idempotent(tmp_path):
    from pathlib import Path
    schema = (Path(__file__).resolve().parents[2] / "scripts" / "schema.sql").read_text(
        encoding="utf-8")
    d = Database(tmp_path / "i.db")
    d.init_schema(schema)
    d.init_schema(schema)
    assert d.scalar("SELECT COUNT(*) FROM sqlite_master WHERE type='table'") >= 16


def test_foreign_keys_enforced_on_connection(db):
    conn = db.connect()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()
