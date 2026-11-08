"""工作单元与事务边界（对应 D06 第 13 章 M-11 §13.6.1）。

规则：一次业务用例一个事务；连接随事务释放，不跨层传递。
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

from ..core.errors import Busy, StateError, ValidationError


class Database:
    def __init__(self, path: Path, timeout: float = 3.0, busy_timeout_ms: int = 3000):
        self.path = path
        self.timeout = timeout
        self.busy_timeout_ms = busy_timeout_ms
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=self.timeout, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = %d" % self.busy_timeout_ms)
        return conn

    def init_schema(self, schema_sql: str) -> None:
        conn = self.connect()
        try:
            conn.executescript(schema_sql)
        finally:
            conn.close()

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        conn = self.connect()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        rows = self.query(sql, params)
        return rows[0][0] if rows else None


class UnitOfWork:
    """事务上下文：BEGIN IMMEDIATE 立刻取写锁，避免读后升级死锁。"""

    def __init__(self, db: Database):
        self.db = db
        self.conn: Optional[sqlite3.Connection] = None
        self._depth = 0

    def __enter__(self) -> "UnitOfWork":
        if self._depth == 0:
            self.conn = self.db.connect()
            self._begin()
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._depth -= 1
        if self._depth > 0:
            return False
        try:
            if exc_type is None:
                self.conn.execute("COMMIT")
            else:
                self.conn.execute("ROLLBACK")
        except sqlite3.Error:
            self.conn.execute("ROLLBACK")
            raise
        finally:
            self.conn.close()
            self.conn = None
        return False

    def _begin(self) -> None:
        try:
            self.conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as e:
            if "locked" in str(e) or "busy" in str(e):
                raise Busy("E1005", "数据库忙，请稍后重试")
            raise

    # --- 便捷操作
    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        try:
            return self.conn.execute(sql, params)
        except sqlite3.IntegrityError as e:
            raise translate_sqlite_error(e)
        except sqlite3.OperationalError as e:
            raise translate_sqlite_error(e)

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
        rows = self.conn.execute(sql, params).fetchall()
        return rows[0] if rows else None


def translate_sqlite_error(e: Exception) -> Exception:
    """把 SQLite 报错映射为业务错误码（D06 §13.6.3）。"""
    msg = str(e)
    if "FOREIGN KEY" in msg:
        return ValidationError("E1001", "关联对象不存在或跨课程引用")
    if "不可修改" in msg or "不可删除" in msg:
        return StateError("E1003", msg)
    if "UNIQUE" in msg:
        return StateError("E1003", msg)
    if "locked" in msg or "busy" in msg:
        return Busy("E1005", "数据库忙，请稍后重试")
    return StateError("E1003", msg)


@contextmanager
def transaction(db: Database) -> Iterator[UnitOfWork]:
    uow = UnitOfWork(db)
    with uow:
        yield uow
