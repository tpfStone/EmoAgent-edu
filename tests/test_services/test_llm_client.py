from types import SimpleNamespace

import pytest

import app.services.llm_client as llm_client_module
from app.services.llm_client import DeepSeekLLMClient


class FakeCompletions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
        )


class FakeAsyncOpenAI:
    instances = []

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)
        FakeAsyncOpenAI.instances.append(self)


@pytest.mark.asyncio
async def test_deepseek_client_forwards_disabled_thinking_config(monkeypatch):
    FakeAsyncOpenAI.instances = []
    monkeypatch.setattr(llm_client_module, "AsyncOpenAI", FakeAsyncOpenAI)
    client = DeepSeekLLMClient(
        api_key="key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        thinking_type="disabled",
    )

    result = await client.generate("prompt")

    assert result == "ok"
    call = FakeAsyncOpenAI.instances[0].completions.calls[0]
    assert call["model"] == "deepseek-v4-flash"
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}


@pytest.mark.asyncio
async def test_deepseek_client_forwards_enabled_thinking_config(monkeypatch):
    FakeAsyncOpenAI.instances = []
    monkeypatch.setattr(llm_client_module, "AsyncOpenAI", FakeAsyncOpenAI)
    client = DeepSeekLLMClient(
        api_key="key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        thinking_type="enabled",
    )

    result = await client.generate("prompt")

    assert result == "ok"
    call = FakeAsyncOpenAI.instances[0].completions.calls[0]
    assert call["model"] == "deepseek-v4-flash"
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}


@pytest.mark.asyncio
async def test_deepseek_client_omits_thinking_config_when_unset(monkeypatch):
    FakeAsyncOpenAI.instances = []
    monkeypatch.setattr(llm_client_module, "AsyncOpenAI", FakeAsyncOpenAI)
    client = DeepSeekLLMClient(
        api_key="key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        thinking_type=None,
    )

    result = await client.generate("prompt")

    assert result == "ok"
    call = FakeAsyncOpenAI.instances[0].completions.calls[0]
    assert call["model"] == "deepseek-v4-flash"
    assert "extra_body" not in call
