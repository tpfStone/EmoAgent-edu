import asyncio
import json
from typing import Protocol

from openai import AsyncOpenAI


class LLMClientProtocol(Protocol):
    async def generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str: ...


class MockLLMClient:
    def __init__(self):
        self._pairwise_call_count = 0

    async def generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        await asyncio.sleep(0)
        if "回应A" in prompt and "回应B" in prompt:
            self._pairwise_call_count += 1
            winner = "A" if self._pairwise_call_count % 2 == 1 else "B"
            casel_comparisons = {
                dimension: winner
                for dimension in (
                    "自我觉察引导",
                    "自我管理引导",
                    "社会觉察培养",
                    "关系技能培养",
                    "负责任决策引导",
                )
                if dimension in prompt
            }
            return json.dumps(
                {
                    "winner": winner,
                    "reason": "mock pairwise",
                    "epitome_comparison": {"ER": winner, "IP": "tie", "EX": winner},
                    "casel_comparisons": casel_comparisons,
                    "boundary_concern": False,
                    "boundary_reason": "",
                },
                ensure_ascii=False,
            )
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
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        thinking_type: str | None = None,
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.thinking_type = thinking_type

    async def generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        request_kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            request_kwargs["response_format"] = response_format
        if self.thinking_type:
            request_kwargs["extra_body"] = {"thinking": {"type": self.thinking_type}}
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(**request_kwargs),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"DeepSeek API call timed out ({timeout}s)")
        except Exception as exc:
            raise RuntimeError(f"DeepSeek API call failed: {exc}") from exc
        return response.choices[0].message.content or ""
