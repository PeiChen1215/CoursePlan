"""认证与授权（对应 D06 第 3 章 M-01）。

要点：
- 账号不存在与口令错误返回同一响应，不泄露账号是否存在；
- 锁定判定在口令比对之前，锁定期内口令正确也不放行；
- 失败计数只在“账号存在且口令错”时累加；
- 越权访问按 404 处理，与“不存在”不可区分。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from ..core.errors import NotFound, StateError, Unauthorized
from ..core.security import Claims, issue_token, parse_token, verify_password
from ..db.uow import Database, UnitOfWork


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class LoginResult:
    token: str
    role: str
    expires_at: datetime
    user_id: int


class AuthService:
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config

    # ---------------- 登录
    def login(self, username: str, password: str, now: datetime) -> LoginResult:
        row = self._find_user(username)
        if row is None:
            raise Unauthorized("E4001", "账号或口令不正确")

        locked_until = parse_iso(row["locked_until"])
        if locked_until and locked_until > now:
            remain = int((locked_until - now).total_seconds())
            raise Unauthorized("E4001", "账号已锁定，请稍后再试",
                               detail={"lock_remaining_seconds": remain})

        if not verify_password(password, row["password_hash"]):
            self._on_failed(row, now)
            raise Unauthorized("E4001", "账号或口令不正确")

        token, exp = issue_token(row["user_id"], row["role"], now, self.config)
        self._on_success(row["user_id"], now)
        return LoginResult(token=token, role=row["role"], expires_at=exp,
                           user_id=row["user_id"])

    def _find_user(self, username: str) -> Optional[sqlite3.Row]:
        rows = self.db.query(
            "SELECT user_id, username, password_hash, role, status, failed_attempts,"
            " locked_until FROM app_user WHERE username = ?", (username,))
        return rows[0] if rows else None

    def _on_failed(self, row: sqlite3.Row, now: datetime) -> None:
        attempts = int(row["failed_attempts"]) + 1
        locked = None
        if attempts >= self.config.LOCK_FAIL_LIMIT:
            locked = to_iso(now + timedelta(minutes=self.config.LOCK_MINUTES))
        with UnitOfWork(self.db) as uow:
            uow.execute("UPDATE app_user SET failed_attempts = ?, locked_until = ?"
                        " WHERE user_id = ?", (attempts, locked, row["user_id"]))

    def _on_success(self, user_id: int, now: datetime) -> None:
        with UnitOfWork(self.db) as uow:
            uow.execute("UPDATE app_user SET failed_attempts = 0, locked_until = NULL,"
                        " last_login_at = ? WHERE user_id = ?", (to_iso(now), user_id))

    # ---------------- 令牌与授权
    def authenticate(self, token: Optional[str], now: datetime) -> Claims:
        return parse_token(token or "", now, self.config)

    def require_role(self, claims: Claims, role: str) -> None:
        if claims.role != role:
            from ..core.errors import Forbidden
            raise Forbidden("E4003", "当前角色无权访问该资源")

    def require_owner(self, owner_id: Optional[int], claims: Claims) -> None:
        """对象不存在或不属于本人，一律 NotFound（D06 §3.6.4）。"""
        if owner_id is None or int(owner_id) != int(claims.sub):
            raise NotFound("E1002", "对象不存在")

    def load_user(self, user_id: int) -> Optional[sqlite3.Row]:
        rows = self.db.query(
            "SELECT user_id, username, role, status FROM app_user WHERE user_id = ?",
            (user_id,))
        return rows[0] if rows else None

    def ensure_enabled(self, user_id: int) -> sqlite3.Row:
        row = self.load_user(user_id)
        if row is None or row["status"] != "enabled":
            raise StateError("E1003", "账号不可用")
        return row
