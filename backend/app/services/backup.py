"""一致性备份与恢复（对应 D02 AT-31、D06 §13.6.5）。

备份用 SQLite 官方 backup API（WAL 下直接复制主库文件会得到不一致快照），
备份后跑 integrity_check 与 foreign_key_check，只保留最近若干份。
恢复是显式动作：先把现有库改名留底，再用备份覆盖，最后做完整性校验。
"""
from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..core.errors import AppError, NotFound, ValidationError

KEEP = 7


class BackupError(AppError):
    code = "E1006"
    http_status = 500


@dataclass(frozen=True)
class BackupResult:
    path: str
    size_bytes: int
    integrity: str
    foreign_key_violations: int
    pruned: int


class BackupService:
    def __init__(self, db_path: Path, backup_dir: Path, keep: int = KEEP):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.keep = keep

    # ---------------------------------------------------------------- 备份
    def backup(self, now: Optional[datetime] = None) -> BackupResult:
        if not self.db_path.exists():
            raise BackupError("E1006", "数据库文件不存在，无法备份")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
        target = self.backup_dir / ("studypath-%s.db" % stamp)
        suffix = 1
        while target.exists():
            target = self.backup_dir / ("studypath-%s-%d.db" % (stamp, suffix))
            suffix += 1

        src = sqlite3.connect(self.db_path)
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        integrity = self._integrity(target)
        violations = self._foreign_key_violations(target)
        pruned = self._prune()
        return BackupResult(str(target), target.stat().st_size, integrity,
                            violations, pruned)

    def _integrity(self, path: Path) -> str:
        """损坏的文件不抛 500，而是返回 corrupt，由调用方给出可读的 400。"""
        conn = sqlite3.connect(path)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            return str(row[0]) if row else "unknown"
        except sqlite3.DatabaseError:
            return "corrupt"
        finally:
            conn.close()

    def _foreign_key_violations(self, path: Path) -> int:
        conn = sqlite3.connect(path)
        try:
            return len(conn.execute("PRAGMA foreign_key_check").fetchall())
        except sqlite3.DatabaseError:
            return 1
        finally:
            conn.close()

    def _prune(self) -> int:
        files = sorted(self.backup_dir.glob("studypath-*.db"),
                       key=lambda p: p.stat().st_mtime)
        removed = 0
        while len(files) > self.keep:
            files.pop(0).unlink()
            removed += 1
        return removed

    # ---------------------------------------------------------------- 查询
    def list_backups(self) -> List[dict]:
        if not self.backup_dir.exists():
            return []
        files = sorted(self.backup_dir.glob("studypath-*.db"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        return [{
            "name": p.name,
            "size_bytes": p.stat().st_size,
            "created_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
        } for p in files]

    def latest(self) -> Optional[Path]:
        files = sorted(self.backup_dir.glob("studypath-*.db"),
                       key=lambda p: p.stat().st_mtime)
        return files[-1] if files else None

    # ---------------------------------------------------------------- 恢复
    def restore(self, backup_name: str, now: Optional[datetime] = None) -> dict:
        source = self.backup_dir / backup_name
        if not source.exists():
            raise NotFound("E1002", "备份文件不存在")
        if self._integrity(source) != "ok":
            raise ValidationError("E1001", "备份文件未通过完整性检查，拒绝恢复")
        if self._foreign_key_violations(source):
            raise ValidationError("E1001", "备份文件存在外键不一致，拒绝恢复")

        stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
        safeguard = self.db_path.with_name(self.db_path.name + ".before-restore-%s" % stamp)
        if self.db_path.exists():
            shutil.copy2(self.db_path, safeguard)
        for suffix in ("-wal", "-shm"):
            side = Path(str(self.db_path) + suffix)
            if side.exists():
                side.unlink()
        shutil.copy2(source, self.db_path)

        conn = sqlite3.connect(self.db_path)
        try:
            counts = {
                table: conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
                for table in ("app_user", "course", "concept", "plan_version",
                              "version_task", "learning_event")
            }
        finally:
            conn.close()
        return {"restored_from": backup_name, "safeguard": str(safeguard),
                "counts": counts, "integrity": self._integrity(self.db_path)}
