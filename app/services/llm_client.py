import asyncio
from typing import Any, AsyncIterator, Protocol

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

    async def stream_generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> AsyncIterator[dict[str, Any]]: ...


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
            return json_dumps(
                {
                    "winner": winner,
                    "reason": "mock pairwise",
                    "epitome_comparison": {"ER": winner, "IP": "tie", "EX": winner},
                    "casel_comparisons": casel_comparisons,
                    "boundary_concern": False,
                    "boundary_reason": "",
                }
            )
        if "EPITOME" in prompt:
            return (
                '{"ER": 1, "IP": 1, "EX": 1, "casel": {}, "boundary_flag": false, '
                '"boundary_reason": "", "rationale": "mock score"}'
            )
        if "secondary_safety" in prompt and "候选情境" in prompt:
            return json_dumps(
                {
                    "secondary_safety": {
                        "risk_level": "green",
                        "matched_signals": [],
                        "rationale": "mock f2 safety pass",
                    },
                    "scenario": "其他",
                    "scenario_confidence": 0.5,
                    "rationale": "mock scenario",
                }
            )
        if "情感教育陪伴者" in prompt:
            return "我听见你现在有些不容易，我会认真听你慢慢说。"
        return '{"risk_level": "green", "matched_signals": [], "rationale": "mock safety pass"}'

    async def stream_generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        text = await self.generate(prompt, timeout, temperature, max_tokens, response_format)
        yield {"type": "start", "provider": "mock", "model": "mock"}
        for index in range(0, len(text), 2):
            await asyncio.sleep(0)
            yield {"type": "delta", "text": text[index : index + 2]}
        yield {"type": "done", "provider": "mock", "model": "mock"}


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        thinking_type: str | None = None,
        extra_body_style: str = "deepseek",
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.thinking_type = thinking_type
        self.extra_body_style = extra_body_style

    async def generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        request_kwargs = self._request_kwargs(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            stream=False,
        )
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(**request_kwargs),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"LLM API call timed out ({timeout}s)")
        except Exception as exc:
            raise RuntimeError(f"LLM API call failed: {exc}") from exc
        return response.choices[0].message.content or ""

    async def stream_generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        request_kwargs = self._request_kwargs(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            stream=True,
        )
        yield {"type": "start", "provider": self.extra_body_style, "model": self.model}
        try:
            async with asyncio.timeout(timeout):
                stream = await self.client.chat.completions.create(**request_kwargs)
                reasoning_content = ""
                usage = None
                async for chunk in stream:
                    if not getattr(chunk, "choices", None):
                        raw_usage = getattr(chunk, "usage", None)
                        if raw_usage is not None:
                            usage = (
                                raw_usage.model_dump()
                                if hasattr(raw_usage, "model_dump")
                                else raw_usage
                            )
                        continue

                    delta = chunk.choices[0].delta
                    reasoning_delta = getattr(delta, "reasoning_content", None)
                    if reasoning_delta is not None:
                        reasoning_content += reasoning_delta

                    content_delta = getattr(delta, "content", None)
                    if content_delta:
                        yield {"type": "delta", "text": content_delta}

                yield {
                    "type": "done",
                    "provider": self.extra_body_style,
                    "model": self.model,
                    "reasoning_content": reasoning_content,
                    "usage": usage,
                }
        except TimeoutError:
            raise TimeoutError(f"LLM API stream timed out ({timeout}s)")
        except Exception as exc:
            raise RuntimeError(f"LLM API stream failed: {exc}") from exc

    def _request_kwargs(
        self,
        *,
        prompt: str,
        temperature: float,
        max_tokens: int | None,
        response_format: dict | None,
        stream: bool,
    ) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            request_kwargs["response_format"] = response_format
        if stream:
            request_kwargs["stream"] = True
            request_kwargs["stream_options"] = {"include_usage": True}

        extra_body = self._extra_body()
        if extra_body:
            request_kwargs["extra_body"] = extra_body
        return request_kwargs

    def _extra_body(self) -> dict[str, Any] | None:
        thinking = (self.thinking_type or "").strip().lower()
        if thinking in {"", "disabled", "none", "off", "false", "0"}:
            if self.extra_body_style == "dashscope-deepseek":
                return {"enable_thinking": False}
            return None
        if self.extra_body_style == "dashscope-deepseek":
            return {"enable_thinking": True}
        if self.extra_body_style == "dashscope-qwen":
            return {"enable_thinking": True}
        return {"thinking": {"type": self.thinking_type}}


class DeepSeekLLMClient(OpenAICompatibleLLMClient):
    pass


def json_dumps(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
