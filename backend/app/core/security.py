"""口令散列与令牌签发（对应 D06 §3.6.1、§3.6.3）。

口令：PBKDF2-HMAC-SHA256，随机盐，格式 pbkdf2_sha256$迭代数$盐$散列。
令牌：base64url(payload).base64url(HMAC-SHA256(payload))，无状态、不查会话表。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Tuple

from .errors import Unauthorized

ITERATIONS = 200_000


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (iterations, _b64e(salt), _b64e(dk))


def verify_password(plain: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"),
                                 _b64d(salt_b64), int(iters))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(_b64e(dk), hash_b64)


@dataclass(frozen=True)
class Claims:
    sub: int
    role: str
    exp: int

    @property
    def expires_at(self) -> datetime:
        return datetime.fromtimestamp(self.exp, tz=timezone.utc)


def _sign(secret: str, body: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return _b64e(mac)


def issue_token(user_id: int, role: str, now: datetime, config) -> Tuple[str, datetime]:
    exp = now + timedelta(hours=config.TOKEN_TTL_HOURS)
    payload = {"sub": user_id, "role": role, "exp": int(exp.timestamp())}
    body = _b64e(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return "%s.%s" % (body, _sign(config.SECRET_KEY, body)), exp


def parse_token(token: str, now: datetime, config) -> Claims:
    if not token or "." not in token:
        raise Unauthorized("E4001", "令牌无效或已过期")
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(config.SECRET_KEY, body)):
        raise Unauthorized("E4001", "令牌无效或已过期")
    try:
        payload = json.loads(_b64d(body))
        claims = Claims(sub=int(payload["sub"]), role=str(payload["role"]),
                        exp=int(payload["exp"]))
    except (ValueError, KeyError, TypeError):
        raise Unauthorized("E4001", "令牌无效或已过期")
    if claims.exp <= int(now.timestamp()):
        raise Unauthorized("E4001", "令牌无效或已过期")
    return claims
