"""配置加载与校验（对应 D06 第 14 章 M-12）。

优先级：默认值 < 环境变量（DSH_ 前缀）< 显式传参。
越界即抛 ConfigError，进程拒绝启动（D06 §14.6.2）。
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# D06 表 2.2 全局配置常量
DEFAULTS: Dict[str, Any] = {
    "STUDY_RATIO": 0.70,
    "BUFFER_RATIO": 0.10,
    "MAX_SLICE_SECONDS": 7200,
    "MAX_SLICES_PER_TASK": 100,
    "CAP_TIGHT_THRESHOLD": 0.80,
    "DELAY_THRESHOLD_HOURS": 48,
    "BACKUP_KEEP": 7,
    "BACKUP_DIR": "backups",
    "MODEL_TIMEOUT_SECONDS": 10,
    "MIN_TASK_MINUTES": 1,
    "MAX_DEADLINE_DAYS": 180,
    "LOCK_FAIL_LIMIT": 5,
    "LOCK_MINUTES": 5,
    "TOKEN_TTL_HOURS": 24,
    # 运行环境
    "DB_PATH": "data/studypath.db",
    "LOG_LEVEL": "INFO",
    "PROVIDER_MODE": "mock",          # mock / real / auto
    "PROVIDER_KEY": "",
    "PROVIDER_BASE": "https://api.deepseek.com",
    "PROVIDER_MODEL": "deepseek-flash",
    "PROVIDER_THINKING": "disabled",
    "SECRET_KEY": "studypath-dev-secret",
}

# 数值型配置的允许范围（D06 §14.6.2）
SPECS = {
    "STUDY_RATIO": (0.1, 0.9),
    "BUFFER_RATIO": (0.0, 0.5),
    "MAX_SLICE_SECONDS": (600, 14400),
    "MAX_SLICES_PER_TASK": (1, 500),
    "CAP_TIGHT_THRESHOLD": (0.5, 0.99),
    "DELAY_THRESHOLD_HOURS": (1, 720),
    "MODEL_TIMEOUT_SECONDS": (1, 60),
    "MIN_TASK_MINUTES": (1, 60),
    "MAX_DEADLINE_DAYS": (7, 365),
    "LOCK_FAIL_LIMIT": (1, 20),
    "LOCK_MINUTES": (1, 120),
    "TOKEN_TTL_HOURS": (1, 72),
}

CHOICES = {
    "LOG_LEVEL": {"DEBUG", "INFO", "WARNING", "ERROR"},
    "PROVIDER_MODE": {"mock", "real", "auto"},
}


class ConfigError(Exception):
    """配置非法，启动必须中止。"""


@dataclass(frozen=True)
class EngineConfig:
    STUDY_RATIO: float
    BUFFER_RATIO: float
    MAX_SLICE_SECONDS: int
    MAX_SLICES_PER_TASK: int
    CAP_TIGHT_THRESHOLD: float
    DELAY_THRESHOLD_HOURS: int
    MODEL_TIMEOUT_SECONDS: int
    MIN_TASK_MINUTES: int
    MAX_DEADLINE_DAYS: int
    LOCK_FAIL_LIMIT: int
    LOCK_MINUTES: int
    TOKEN_TTL_HOURS: int
    DB_PATH: str
    LOG_LEVEL: str
    PROVIDER_MODE: str
    PROVIDER_KEY: str
    SECRET_KEY: str
    PROVIDER_BASE: str = "https://api.deepseek.com"
    PROVIDER_MODEL: str = "deepseek-flash"
    PROVIDER_THINKING: str = "disabled"
    BACKUP_KEEP: int = 7
    BACKUP_DIR: str = "backups"

    @property
    def db_file(self) -> Path:
        p = Path(self.DB_PATH)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def backup_dir(self) -> Path:
        """默认放在数据库文件同级的 backups/ 下。"""
        p = Path(self.BACKUP_DIR or "backups")
        if p.is_absolute():
            return p
        return self.db_file.parent / p

    def as_dict(self) -> Dict[str, Any]:
        return {
            "STUDY_RATIO": self.STUDY_RATIO,
            "BUFFER_RATIO": self.BUFFER_RATIO,
            "MAX_SLICE_SECONDS": self.MAX_SLICE_SECONDS,
            "MAX_SLICES_PER_TASK": self.MAX_SLICES_PER_TASK,
            "CAP_TIGHT_THRESHOLD": self.CAP_TIGHT_THRESHOLD,
            "DELAY_THRESHOLD_HOURS": self.DELAY_THRESHOLD_HOURS,
            "MODEL_TIMEOUT_SECONDS": self.MODEL_TIMEOUT_SECONDS,
            "MIN_TASK_MINUTES": self.MIN_TASK_MINUTES,
            "MAX_DEADLINE_DAYS": self.MAX_DEADLINE_DAYS,
            "LOCK_FAIL_LIMIT": self.LOCK_FAIL_LIMIT,
            "LOCK_MINUTES": self.LOCK_MINUTES,
            "TOKEN_TTL_HOURS": self.TOKEN_TTL_HOURS,
            "DB_PATH": str(self.db_file),
            "LOG_LEVEL": self.LOG_LEVEL,
            "PROVIDER_MODE": self.PROVIDER_MODE,
            "PROVIDER_BASE": self.PROVIDER_BASE,
            "PROVIDER_MODEL": self.PROVIDER_MODEL,
            "PROVIDER_THINKING": self.PROVIDER_THINKING,
            "BACKUP_KEEP": self.BACKUP_KEEP,
            "BACKUP_DIR": str(self.backup_dir),
        }


# ---------------------------------------------------------------- .env
ENV_FILE_NAMES = (".env", "backend/.env")


def load_dotenv(root: Optional[Path] = None) -> List[str]:
    """读 .env 到 os.environ，只填空缺项，不覆盖已有环境变量。

    支持两种写法：
        PROVIDER_MODE=real            # 自动补 DSH_ 前缀
        DSH_PROVIDER_MODE=real        # 原样使用
    返回实际生效的键，便于启动日志说明来源。
    """
    root = Path(root) if root else PROJECT_ROOT
    applied: List[str] = []
    seen = set()
    for name in ENV_FILE_NAMES:
        path = root / name
        if not path.exists() or path in seen:
            continue
        seen.add(path)
        for raw_line in io.open(path, encoding="utf-8"):
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue
            env_key = key if key.startswith("DSH_") else "DSH_" + key
            if env_key in os.environ:
                continue
            os.environ[env_key] = value
            applied.append(env_key)
    return applied


def load(overrides: Optional[Dict[str, Any]] = None) -> EngineConfig:
    overrides = overrides or {}
    raw: Dict[str, Any] = {}
    for key, default in DEFAULTS.items():
        raw[key] = overrides.get(key, os.getenv("DSH_" + key, default))

    for key, (low, high) in SPECS.items():
        try:
            v = int(raw[key]) if isinstance(DEFAULTS[key], int) else float(raw[key])
        except (TypeError, ValueError):
            raise ConfigError("%s=%r 不是数字（允许 %s）" % (key, raw[key], SPECS[key]))
        if not low <= v <= high:
            raise ConfigError("%s=%s 越界（允许 %s–%s）" % (key, v, low, high))
        raw[key] = v

    for key, choices in CHOICES.items():
        v = str(raw[key]).upper() if key == "LOG_LEVEL" else str(raw[key]).lower()
        if v not in choices:
            raise ConfigError("%s=%s 不在允许取值 %s 内" % (key, raw[key], sorted(choices)))
        raw[key] = v

    return EngineConfig(**raw)


load_dotenv()
