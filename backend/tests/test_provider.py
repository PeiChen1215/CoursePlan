"""RealProvider：真实模型适配器的 HTTP 行为（不联网，全部用假传输）。"""
import io
import json
import urllib.error

import pytest

from app.services.provider import (
    ProviderError,
    ProviderTimeout,
    RealProvider,
    build_provider,
)


class FakeResponse:
    def __init__(self, body: str, status: int = 200):
        self.body = body.encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def patch_urlopen(monkeypatch, result):
    """result 可以是 FakeResponse 或要抛出的异常。"""
    calls = []

    def fake(request, timeout=None):
        calls.append({"url": request.full_url, "timeout": timeout,
                      "headers": dict(request.headers), "data": request.data})
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr("app.services.provider.urllib.request.urlopen", fake)
    return calls


def chat_body(content: str) -> str:
    return json.dumps({"choices": [{"message": {"content": content}}]})


# ---------------------------------------------------------------- 正常路径
def test_complete_returns_content(monkeypatch):
    calls = patch_urlopen(monkeypatch, FakeResponse(chat_body('{"concept_id": 3}')))
    provider = RealProvider("k-1", timeout=7)
    assert provider.complete("选一个") == '{"concept_id": 3}'

    assert calls[0]["url"] == "https://api.deepseek.com/chat/completions"
    assert calls[0]["timeout"] == 7
    assert calls[0]["headers"]["Authorization"] == "Bearer k-1"
    payload = json.loads(calls[0]["data"].decode("utf-8"))
    assert payload["model"] == "deepseek-flash"
    assert payload["temperature"] == 0
    assert payload["stream"] is False


def test_custom_base_and_model(monkeypatch):
    calls = patch_urlopen(monkeypatch, FakeResponse(chat_body("{}")))
    provider = RealProvider("k", base="https://example.test/v1/", model="m-2")
    provider.complete("x")
    assert calls[0]["url"] == "https://example.test/v1/chat/completions"
    assert json.loads(calls[0]["data"].decode("utf-8"))["model"] == "m-2"


# ---------------------------------------------------------------- 错误映射
def test_missing_key_raises():
    with pytest.raises(ProviderError, match="未配置密钥"):
        RealProvider("").complete("x")


def test_http_401_becomes_auth_error(monkeypatch):
    error = urllib.error.HTTPError(
        "https://api.deepseek.com/chat/completions", 401, "Unauthorized", {},
        io.BytesIO(b'{"error":"invalid key"}'))
    patch_urlopen(monkeypatch, error)
    with pytest.raises(ProviderError, match="鉴权失败"):
        RealProvider("bad").complete("x")


def test_http_429_becomes_rate_limit(monkeypatch):
    error = urllib.error.HTTPError(
        "https://api.deepseek.com/chat/completions", 429, "Too Many", {},
        io.BytesIO(b"slow down"))
    patch_urlopen(monkeypatch, error)
    with pytest.raises(ProviderError, match="限流"):
        RealProvider("k").complete("x")


def test_http_500_becomes_generic_error(monkeypatch):
    error = urllib.error.HTTPError(
        "https://api.deepseek.com/chat/completions", 500, "Boom", {}, io.BytesIO(b"oops"))
    patch_urlopen(monkeypatch, error)
    with pytest.raises(ProviderError, match="HTTP 500"):
        RealProvider("k").complete("x")


def test_timeout_becomes_provider_timeout(monkeypatch):
    patch_urlopen(monkeypatch, urllib.error.URLError(TimeoutError("timed out")))
    with pytest.raises(ProviderTimeout):
        RealProvider("k", timeout=3).complete("x")


def test_connection_error(monkeypatch):
    patch_urlopen(monkeypatch, urllib.error.URLError("dns fail"))
    with pytest.raises(ProviderError, match="连接失败"):
        RealProvider("k").complete("x")


def test_bad_json(monkeypatch):
    patch_urlopen(monkeypatch, FakeResponse("not json"))
    with pytest.raises(ProviderError, match="合法 JSON"):
        RealProvider("k").complete("x")


def test_json_not_object(monkeypatch):
    patch_urlopen(monkeypatch, FakeResponse("[1,2,3]"))
    with pytest.raises(ProviderError, match="不是对象"):
        RealProvider("k").complete("x")


def test_missing_choices(monkeypatch):
    patch_urlopen(monkeypatch, FakeResponse(json.dumps({"error": "x"})))
    with pytest.raises(ProviderError, match="缺少 choices"):
        RealProvider("k").complete("x")


def test_empty_content(monkeypatch):
    patch_urlopen(monkeypatch, FakeResponse(chat_body("   ")))
    with pytest.raises(ProviderError, match="空内容"):
        RealProvider("k").complete("x")


# ---------------------------------------------------------------- probe
def test_probe_without_key():
    assert RealProvider("").probe() is False


def test_probe_success(monkeypatch):
    calls = patch_urlopen(monkeypatch, FakeResponse('{"data":[]}'))
    assert RealProvider("k").probe() is True
    assert calls[0]["url"].endswith("/models")
    assert calls[0]["data"] is None


def test_probe_failure(monkeypatch):
    error = urllib.error.HTTPError(
        "https://api.deepseek.com/models", 401, "Unauthorized", {}, io.BytesIO(b""))
    patch_urlopen(monkeypatch, error)
    assert RealProvider("k").probe() is False


# ---------------------------------------------------------------- 工厂
def test_build_real_mode(monkeypatch):
    provider = build_provider("real", "k", 5, base="https://x.test", model="m")
    assert provider.name == "real"
    assert provider.timeout == 5
    assert provider.base == "https://x.test"
    assert provider.model == "m"


def test_build_auto_uses_real_when_probe_passes(monkeypatch):
    monkeypatch.setattr(RealProvider, "probe", lambda self: True)
    assert build_provider("auto", "k").name == "real"


def test_build_auto_falls_back_when_probe_fails(monkeypatch):
    monkeypatch.setattr(RealProvider, "probe", lambda self: False)
    assert build_provider("auto", "k").name == "mock"


def test_build_auto_falls_back_when_probe_raises(monkeypatch):
    def boom(self):
        raise ProviderError("probe broke")

    monkeypatch.setattr(RealProvider, "probe", boom)
    assert build_provider("auto", "k").name == "mock"


def test_socket_timeout_direct(monkeypatch):
    """读超时时 urlopen 可能直接抛 TimeoutError，而不是包在 URLError 里。"""
    patch_urlopen(monkeypatch, TimeoutError("read timed out"))
    with pytest.raises(ProviderTimeout, match="模型超时"):
        RealProvider("k", timeout=2).complete("x")


def test_os_error_maps_to_provider_error(monkeypatch):
    patch_urlopen(monkeypatch, OSError("socket reset"))
    with pytest.raises(ProviderError, match="网络错误"):
        RealProvider("k").complete("x")
