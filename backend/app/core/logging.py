"""日志与脱敏（对应 D06 第 14 章 M-12 §14.6.3）。

黑名单字段一律替换为 ***：口令、令牌、学生原话、精确日程。
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# D06 §14.6.3 脱敏黑名单
REDACT = {
    "password", "password_hash", "token", "authorization", "utterance",
    "deadline", "availability", "excluded_dates",
}

_LOGGER = logging.getLogger("studypath")


def sanitize(record: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in record.items():
        if k.lower() in REDACT:
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = sanitize(v)
        else:
            out[k] = v
    return out


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(sanitize(extra))
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> logging.Logger:
    _LOGGER.setLevel(level.upper())
    _LOGGER.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    _LOGGER.addHandler(handler)
    _LOGGER.propagate = False
    return _LOGGER


def log_event(event: str, level: str = "INFO", **fields: Any) -> None:
    _LOGGER.log(getattr(logging, level.upper(), logging.INFO), event,
                extra={"extra_fields": fields})
