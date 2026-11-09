"""模型适配器（对应 D06 §14.6.5）。

Provider 抽象：mock / real / auto。真实实现走 OpenAI 兼容的 chat/completions，
只用标准库 urllib，避免为一次调用引入 HTTP 依赖。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

DEFAULT_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


class ProviderError(Exception):
    """调用失败（网络、鉴权、超时等）。"""


class ProviderTimeout(ProviderError):
    pass


class BaseProvider:
    name = "base"

    def complete(self, prompt: str) -> str:
        raise NotImplementedError

    def probe(self) -> bool:
        return True


@dataclass
class MockProvider(BaseProvider):
    """确定性替身：fail_mode 用于覆盖超时/不可用/乱答等降级路径。"""

    name = "mock"
    fail_mode: Optional[str] = None       # timeout / unavailable / garbage / bad_id / unsupported_id
    candidates: List[dict] = field(default_factory=list)
    supported_ids: Optional[set] = None

    def complete(self, prompt: str) -> str:
        if self.fail_mode == "timeout":
            raise ProviderTimeout("mock timeout")
        if self.fail_mode == "unavailable":
            raise ProviderError("mock unavailable")
        if self.fail_mode == "garbage":
            return "抱歉，我不太确定。"
        if self.fail_mode == "bad_id":
            return json.dumps({"concept_id": 999999})
        if self.candidates:
            return json.dumps({"concept_id": int(self.candidates[0]["concept_id"])})
        return json.dumps({"concept_id": None})

    def probe(self) -> bool:
        return self.fail_mode != "unavailable"


class RealProvider(BaseProvider):
    """真实模型适配器：POST {base}/chat/completions，要求模型只回 JSON。

    超时与错误统一映射成 ProviderTimeout / ProviderError，交给上层降级。
    """

    name = "real"

    def __init__(self, key: str = "", timeout: int = 10,
                 base: str = DEFAULT_BASE, model: str = DEFAULT_MODEL):
        self.key = key
        self.timeout = timeout
        self.base = (base or DEFAULT_BASE).rstrip("/")
        self.model = model or DEFAULT_MODEL

    # ---------------------------------------------------------------- HTTP
    def _request(self, path: str, payload: Optional[dict], method: str = "POST") -> dict:
        if not self.key:
            raise ProviderError("未配置密钥")
        url = self.base + path
        headers = {
            "Authorization": "Bearer " + self.key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except Exception:  # pragma: no cover - 读错误体失败时忽略
                detail = ""
            if exc.code in (401, 403):
                raise ProviderError("鉴权失败(%d) %s" % (exc.code, detail))
            if exc.code == 429:
                raise ProviderError("限流(429) %s" % detail)
            raise ProviderError("HTTP %d %s" % (exc.code, detail))
        except TimeoutError:
            raise ProviderTimeout("模型超时(%ss)" % self.timeout)
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise ProviderTimeout("模型超时(%ss)" % self.timeout)
            raise ProviderError("连接失败: %s" % getattr(exc, "reason", exc))
        except OSError as exc:
            raise ProviderError("网络错误: %s" % exc)

        try:
            parsed = json.loads(body)
        except ValueError:
            raise ProviderError("响应不是合法 JSON")
        if not isinstance(parsed, dict):
            raise ProviderError("响应不是对象")
        return parsed

    # ---------------------------------------------------------------- 接口
    def complete(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system",
                 "content": "你是课程学习规划系统的抽取器。只输出 JSON，不要解释、不要代码块。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 200,
            "stream": False,
        }
        data = self._request("/chat/completions", payload)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("响应缺少 choices")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("模型返回空内容")
        return content.strip()

    def probe(self) -> bool:
        """用 GET /models 做一次轻量可达性检查（auto 模式启动时调用）。"""
        if not self.key:
            return False
        try:
            self._request("/models", None, method="GET")
            return True
        except ProviderError:
            return False


def build_provider(mode: str, key: str = "", timeout: int = 10,
                   mock: Optional[MockProvider] = None,
                   base: str = DEFAULT_BASE,
                   model: str = DEFAULT_MODEL) -> BaseProvider:
    """mock / real / auto；auto 探测失败即降级为 mock（D06 §14.6.5）。"""
    if mode == "mock":
        return mock or MockProvider()
    if mode == "real":
        return RealProvider(key, timeout, base, model)
    provider = RealProvider(key, timeout, base, model)
    try:
        if provider.probe():
            return provider
    except ProviderError:
        pass
    return mock or MockProvider()
