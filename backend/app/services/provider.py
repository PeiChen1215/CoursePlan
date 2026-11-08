"""模型适配器（对应 D06 §14.6.5）。

Provider 抽象：mock / real / auto。真实实现缺省不可用，因此系统始终可离线运行。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


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
    """真实模型适配器占位：未配置密钥时不可用，供 auto 降级。"""

    name = "real"

    def __init__(self, key: str = "", timeout: int = 10):
        self.key = key
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        raise ProviderError("真实模型未配置")

    def probe(self) -> bool:
        return bool(self.key)


def build_provider(mode: str, key: str = "", timeout: int = 10,
                   mock: Optional[MockProvider] = None) -> BaseProvider:
    """mock / real / auto；auto 探测失败即降级为 mock（D06 §14.6.5）。"""
    if mode == "mock":
        return mock or MockProvider()
    if mode == "real":
        return RealProvider(key, timeout)
    provider = RealProvider(key, timeout)
    try:
        if provider.probe():
            return provider
    except ProviderError:
        pass
    return mock or MockProvider()
