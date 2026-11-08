"""M1 · 补充分支测试：异常路径、备份状态、日志异常、事务辅助函数。"""
import logging
import sqlite3
import time

import pytest

from app.core import config as C
from app.core.errors import Busy, StateError
from app.core.logging import JsonFormatter
from app.db.uow import Database, UnitOfWork, transaction


def test_load_without_arguments():
    assert C.load().STUDY_RATIO == 0.70


def test_begin_reraises_non_lock_operational_error(db):
    """BEGIN IMMEDIATE 非锁类错误应原样抛出，不被吞成 E1005。"""
    real_connect = db.connect

    class BadConn:
        def __init__(self, conn):
            self._c = conn

        def execute(self, sql, *a):
            if sql.startswith("BEGIN"):
                raise sqlite3.OperationalError("malformed database")
            return self._c.execute(sql, *a)

        def __getattr__(self, item):
            return getattr(self._c, item)

    db.connect = lambda: BadConn(real_connect())
    with pytest.raises(sqlite3.OperationalError):
        with UnitOfWork(db):
            pass


def test_execute_operational_error_translated(seeded):
    with pytest.raises(StateError):
        with UnitOfWork(seeded) as uow:
            uow.execute("SELECT * FROM no_such_table")


def test_transaction_helper_commits(seeded):
    before = seeded.scalar("SELECT COUNT(*) FROM concept")
    with transaction(seeded) as uow:
        uow.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                    "reference_minutes,status) VALUES(1,'树','第9章',4,90,'enabled')")
    assert seeded.scalar("SELECT COUNT(*) FROM concept") == before + 1


def test_transaction_helper_rolls_back(seeded):
    before = seeded.scalar("SELECT COUNT(*) FROM concept")
    with pytest.raises(ValueError):
        with transaction(seeded) as uow:
            uow.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                        "reference_minutes,status) VALUES(1,'堆','第10章',4,90,'enabled')")
            raise ValueError("nope")
    assert seeded.scalar("SELECT COUNT(*) FROM concept") == before


def test_formatter_includes_exception_text():
    try:
        raise ValueError("boom-detail")
    except ValueError:
        import sys
        rec = logging.LogRecord("studypath", logging.ERROR, __file__, 1, "fail", None,
                                sys.exc_info())
    out = JsonFormatter().format(rec)
    assert "boom-detail" in out and "ValueError" in out


def test_backup_status_without_backup_dir(tmp_path):
    from app.main import _backup_age_hours
    assert _backup_age_hours(tmp_path / "none") is None


def test_backup_status_with_recent_file(tmp_path):
    from app.main import _backup_age_hours
    root = tmp_path / "backups"
    root.mkdir()
    (root / "a.db").write_bytes(b"x")
    age = _backup_age_hours(root)
    assert age is not None and age < 1


def test_health_backup_warn_when_old(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app({"DB_PATH": str(tmp_path / "t.db"), "LOG_LEVEL": "ERROR"})
    c = TestClient(app, raise_server_exceptions=False)
    data = c.get("/api/health").json()["data"]
    assert data["backup"] in ("ok", "warn")


def test_database_creates_parent_dir(tmp_path):
    target = tmp_path / "deep" / "nested" / "x.db"
    d = Database(target)
    d.init_schema("CREATE TABLE t(a INTEGER);")
    assert target.exists()
    assert d.scalar("SELECT COUNT(*) FROM t") == 0


def test_commit_failure_triggers_rollback(db):
    """COMMIT 自身失败时仍要尝试回滚并抛错，不留悬挂事务。"""
    real = db.connect

    class Flaky:
        def __init__(self, conn):
            self._c = conn
            self.rolled = False

        def execute(self, sql, *a):
            if sql.startswith("COMMIT"):
                raise sqlite3.OperationalError("disk I/O error")
            if sql.startswith("ROLLBACK"):
                self.rolled = True
            return self._c.execute(sql, *a)

        def __getattr__(self, item):
            return getattr(self._c, item)

    holder = {}

    def fake_connect():
        holder["c"] = Flaky(real())
        return holder["c"]

    db.connect = fake_connect
    with pytest.raises(sqlite3.OperationalError):
        with UnitOfWork(db):
            pass
    assert holder["c"].rolled is True


def test_app_skips_schema_when_file_missing(tmp_path, monkeypatch):
    import app.main as M
    monkeypatch.setattr(M, "SCHEMA_FILE", tmp_path / "nope.sql")
    application = M.create_app({"DB_PATH": str(tmp_path / "x.db"), "LOG_LEVEL": "ERROR"})
    assert application.state.db.scalar(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'") == 0
