"""错误码与统一响应包装（对应 D06 第 12 章 M-10 §12.6.2）。

错误码分段：E1xxx 参数/状态、E2xxx 计划与版本、E4xxx 认证、E9xxx 内部。
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class AppError(Exception):
    """所有可预期业务异常的基类。"""

    code = "E9000"
    http_status = 500

    def __init__(self, code: Optional[str] = None, message: str = "",
                 field: Optional[str] = None, detail: Any = None):
        super().__init__(message or code or self.code)
        if code:
            self.code = code
        self.message = message
        self.field = field
        self.detail = detail


class ValidationError(AppError):
    """参数不合法：400 E1001。"""

    code = "E1001"
    http_status = 400


class NotFound(AppError):
    """对象不存在或不属于本人：404 E1002（两者刻意不区分）。"""

    code = "E1002"
    http_status = 404


class StateError(AppError):
    """状态不允许当前操作：400 E1003。"""

    code = "E1003"
    http_status = 400


class Busy(AppError):
    """数据库忙或写锁超时：503 E1005。"""

    code = "E1005"
    http_status = 503


class VersionConflict(AppError):
    """基线已变，需重新生成：409 E2004。"""

    code = "E2004"
    http_status = 409


class PrereqCycle(AppError):
    """先修关系成环：422 E2001。"""

    code = "E2001"
    http_status = 422


class Unauthorized(AppError):
    """未认证或令牌过期：401 E4001。"""

    code = "E4001"
    http_status = 401


class Forbidden(AppError):
    """角色不符：403 E4003。"""

    code = "E4003"
    http_status = 403


def envelope(code: str = "OK", message: str = "", data: Any = None,
             field: Optional[str] = None, detail: Any = None,
             request_id: str = "") -> Dict[str, Any]:
    """统一响应信封：code / message / data / field / detail / request_id。"""
    return {
        "code": code,
        "message": message,
        "data": data,
        "field": field,
        "detail": detail,
        "request_id": request_id,
    }
