import asyncio
from typing import Protocol

from openai import AsyncOpenAI


class LLMClientProtocol(Protocol):
    async def generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str: ...


class MockLLMClient:
    async def generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        await asyncio.sleep(0)
        if "EPITOME" in prompt:
            return (
                '{"ER": 1, "IP": 1, "EX": 1, "casel": {}, "boundary_flag": false, '
                '"boundary_reason": "", "rationale": "mock score"}'
            )
        if "情境分类模块" in prompt:
            return (
                '{"scenario": "其他", "scenario_confidence": 0.5, '
                '"rationale": "mock scenario"}'
            )
        if "情感教育陪伴者" in prompt:
            return "我听见你现在有些不容易，我愿意继续听你慢慢说。"
        return (
            '{"risk_level": "green", "matched_signals": [], '
            '"rationale": "mock safety pass"}'
        )


class DeepSeekLLMClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"DeepSeek API call timed out ({timeout}s)")
        except Exception as exc:
            raise RuntimeError(f"DeepSeek API call failed: {exc}") from exc
        return response.choices[0].message.content or ""
