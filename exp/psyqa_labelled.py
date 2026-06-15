from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()


DEFAULT_INPUT_PATH = Path("LLM/data/PsyQA/PsyQA_alpaca_labelled.json")
DEFAULT_OUTPUT_PATH = Path("LLM/data/processed/psyqa_labelled/psyqa_labelled_annotations.jsonl")

STRATEGIES = [
    "Restatement",
    "Interpretation",
    "Approval and Reassurance",
    "Direct Guidance",
    "Information",
    "Self-disclosure",
    "Others",
]

STRATEGY_PATTERN = re.compile(
    r"<(" + "|".join(re.escape(strategy) for strategy in STRATEGIES) + r")>"
)

ALLOWED_USE_TIERS = {"direct_exemplar", "strategy_reference", "negative_example", "reject"}
ALLOWED_SCENARIOS = {"学业压力", "同伴关系", "亲子摩擦", "其他"}
ALLOWED_AGE_STAGES = {"初中", "高中", "大学", "成人", "不明"}
ALLOWED_SAFETY_LEVELS = {"green", "yellow", "red", "reject"}
ALLOWED_QUALITY_LABELS = {"good", "rewrite", "reject"}

SYSTEM_PROMPT = """你是 EmoEdu 项目的中文数据标注员。
项目目标是面向中国初中生（12-15岁）的情感教育对话系统，不是成人心理咨询，也不是临床治疗。

你要根据用户倾诉 input 和 PsyQA 回答 output，判断这个样本以后应该如何使用。
请严格输出 JSON，不要输出解释性文本。
"""


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    enable_thinking: bool = False


class NonRetryableLLMError(RuntimeError):
    """余额、鉴权这类错误不会因为重试而恢复，应该立刻停止批处理。"""


def is_non_retryable_api_error(exc: Exception) -> bool:
    message = str(exc).lower()
    signals = [
        "insufficient balance",
        "billing",
        "invalid_api_key",
        "invalid api key",
        "unauthorized",
        "authentication",
        "401",
        "402",
    ]
    return any(signal in message for signal in signals)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_llm_config(provider: str) -> LLMConfig:
    normalized = provider.lower()
    if normalized in {"dashscope-deepseek", "deepseek-v4-pro"}:
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required when --provider dashscope-deepseek.")
        return LLMConfig(
            provider="dashscope-deepseek",
            api_key=api_key,
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            model=os.getenv("DASHSCOPE_DEEPSEEK_MODEL", "qwen3.6-max-preview"),
            enable_thinking=env_flag("DASHSCOPE_ENABLE_THINKING", default=False),
        )

    if normalized == "dashscope":
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required when --provider dashscope.")
        return LLMConfig(
            provider="dashscope",
            api_key=api_key,
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            model=os.getenv("DASHSCOPE_MODEL") or os.getenv("DASHSCOPE_DEEPSEEK_MODEL", "qwen-plus"),
            enable_thinking=env_flag("DASHSCOPE_ENABLE_THINKING", default=False),
        )

    if normalized != "deepseek":
        raise ValueError("--provider must be deepseek, dashscope, or dashscope-deepseek.")

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required when --provider deepseek.")
    return LLMConfig(
        provider="deepseek",
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        enable_thinking=False,
    )


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array.")
    return data


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def compact_text(text: str, limit: int = 3000) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def parse_strategy_sequence(output: str) -> list[str]:
    return [match.group(1) for match in STRATEGY_PATTERN.finditer(output or "")]


def parse_strategy_segments(output: str) -> list[dict[str, str]]:
    matches = list(STRATEGY_PATTERN.finditer(output or ""))
    segments: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(output)
        text = compact_text(output[start:end], limit=1200)
        if text:
            segments.append({"strategy": match.group(1), "text": text})
    return segments


def build_source_row(
    index: int,
    item: dict[str, Any],
    strategy_sequence: list[str],
    strategy_segments: list[dict[str, str]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    # 标注主文件默认保留原始回答，后续可用命令行参数导出更轻的训练/RAG 版本。
    row: dict[str, Any] = {
        "source_index": index,
        "input": item.get("input", ""),
        "psyqa_strategy_sequence": strategy_sequence,
    }
    if not args.omit_output:
        row["output"] = item.get("output", "")
    if not args.omit_strategy_segments:
        row["psyqa_strategy_segments"] = strategy_segments
    return row


def read_done_indices(output_path: Path, skip_failed: bool = False) -> set[int]:
    done: set[int] = set()
    if not output_path.exists():
        return done
    with output_path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            index = row.get("source_index")
            if isinstance(index, int) and (skip_failed or row.get("status") == "ok"):
                done.add(index)
    return done


def build_user_prompt(
    item: dict[str, Any],
    strategy_sequence: list[str],
    strategy_segments: list[dict[str, str]],
) -> str:
    payload = {
        "input": compact_text(str(item.get("input", "")), limit=2600),
        "output": compact_text(str(item.get("output", "")), limit=3600),
        "parsed_strategy_sequence": strategy_sequence,
        "parsed_strategy_segments_sample": strategy_segments[:8],
    }
    return f"""请为下面这条 PsyQA labelled 样本做 EmoEdu 数据标注。

标注目标：判断它是否能用于“面向中国初中生（12-15岁）的中文情感教育对话系统”。

必须输出这些字段：
- use_tier: direct_exemplar | strategy_reference | negative_example | reject
- scenario: 学业压力 | 同伴关系 | 亲子摩擦 | 其他
- age_stage: 初中 | 高中 | 大学 | 成人 | 不明
- minor_suitability: true | false
- safety_level: green | yellow | red | reject
- quality_label: good | rewrite | reject
- reject_reasons: string array
- rationale: 一句简短中文理由

use_tier 判定：
- direct_exemplar: 可以进入 EmoEdu 样例库；必须适合初中生，场景明确，安全，回答质量较高，不能太成人化。
- strategy_reference: 不直接给模型检索，但可用于分析 PsyQA 策略组合；例如高中/大学/考研/保研样本，或较成人但策略仍有参考价值。
- negative_example: 可用于 critic 负例和测试；例如过度说教、过度自我暴露、太长、成人化、泛泛而谈、事实补全明显。
- reject: 不用；明显不安全、严重不适合、临床/药物/诊断/私聊/成人性内容/危机内容等。

教育相关强信号：
初中、初一、初二、初三、中考、学校、老师、同学、朋友、作业、考试、成绩、排名、补课、班级、宿舍、家长、父母、青春期。

scenario 分类：
- 学业压力：考试、成绩、作业、排名、偏科、补课、学习、老师、升学。
- 同伴关系：同学、朋友、被孤立、群聊、冷落、误会、背后议论、组队。
- 亲子摩擦：父母、妈妈、爸爸、家长、管控、手机、隐私、比较、不被理解。
- 其他：以上都不明显，或主问题不是初中教育情境。

不适合初中生的常见 reject_reasons：
考研、保研、大学导师、职场、婚姻、成人恋爱、性、严重创伤、药物、诊断、治疗承诺、私聊联系方式、明显危机内容、过度说教、过度自我暴露、太长、成人化、编造事实。

注意：
- 高中/大学样本不要默认丢弃；通常可进 strategy_reference，但不能进 direct_exemplar。
- 已解析出的策略序列不需要你重算，但你可以据此判断质量。
- minor_suitability 只表示是否适合直接面向初中生作为参考样例；高中/大学/成人样本通常为 false。
- safety_level: green 表示普通情绪困扰；yellow 表示有被动自伤/不想存在等风险；red 表示有意图、计划、方法或准备；reject 表示内容本身不适合纳入本项目。
- 如果 output 中含有“私聊我”“加我”“药物建议”“诊断为”“保证治好”等，通常 reject 或 negative_example。
- 如果 output 很长但策略有参考价值，use_tier 通常是 strategy_reference 或 negative_example，而不是 direct_exemplar。

返回严格 JSON，格式如下：
{{
  "use_tier": "direct_exemplar",
  "scenario": "学业压力",
  "age_stage": "初中",
  "minor_suitability": true,
  "safety_level": "green",
  "quality_label": "good",
  "reject_reasons": [],
  "rationale": "样本聚焦初中学习压力，回答安全且有清晰支持策略。"
}}

样本 JSON：
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""


def extract_json_object(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("No JSON object found in LLM output.")
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("LLM output JSON must be an object.")
    return data


def normalize_annotation(data: dict[str, Any]) -> dict[str, Any]:
    use_tier = str(data.get("use_tier", "")).strip()
    scenario = str(data.get("scenario", "")).strip()
    age_stage = str(data.get("age_stage", "")).strip()
    safety_level = str(data.get("safety_level", "")).strip()
    quality_label = str(data.get("quality_label", "")).strip()

    if use_tier not in ALLOWED_USE_TIERS:
        use_tier = "reject"
    if scenario not in ALLOWED_SCENARIOS:
        scenario = "其他"
    if age_stage not in ALLOWED_AGE_STAGES:
        age_stage = "不明"
    if safety_level not in ALLOWED_SAFETY_LEVELS:
        safety_level = "reject"
    if quality_label not in ALLOWED_QUALITY_LABELS:
        quality_label = "reject"

    reject_reasons = data.get("reject_reasons", [])
    if not isinstance(reject_reasons, list):
        reject_reasons = [str(reject_reasons)]
    reject_reasons = [str(reason).strip() for reason in reject_reasons if str(reason).strip()]

    minor_suitability = data.get("minor_suitability", False)
    if isinstance(minor_suitability, str):
        minor_suitability = minor_suitability.strip().lower() in {"true", "yes", "1", "是"}
    else:
        minor_suitability = bool(minor_suitability)

    if use_tier == "direct_exemplar" and (
        not minor_suitability
        or age_stage != "初中"
        or safety_level != "green"
        or quality_label != "good"
    ):
        use_tier = "strategy_reference"
        if "direct_exemplar条件不足" not in reject_reasons:
            reject_reasons.append("direct_exemplar条件不足")

    if safety_level in {"red", "reject"} or quality_label == "reject":
        if use_tier == "direct_exemplar":
            use_tier = "reject"

    return {
        "use_tier": use_tier,
        "scenario": scenario,
        "age_stage": age_stage,
        "minor_suitability": minor_suitability,
        "safety_level": safety_level,
        "quality_label": quality_label,
        "reject_reasons": reject_reasons,
        "rationale": compact_text(str(data.get("rationale", "")).strip(), limit=400),
    }


async def annotate_with_llm(
    client: Any,
    config: LLMConfig,
    prompt: str,
    timeout: float,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> dict[str, Any]:
    request_kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        request_kwargs["response_format"] = {"type": "json_object"}
    if config.provider == "dashscope-deepseek":
        request_kwargs["extra_body"] = {"enable_thinking": config.enable_thinking}
    elif config.provider == "dashscope" and config.enable_thinking:
        request_kwargs["extra_body"] = {"enable_thinking": config.enable_thinking}

    response = await asyncio.wait_for(
        client.chat.completions.create(**request_kwargs),
        timeout=timeout,
    )
    content = response.choices[0].message.content or ""
    return normalize_annotation(extract_json_object(content))


async def annotate_one(
    semaphore: asyncio.Semaphore,
    client: Any,
    config: LLMConfig,
    index: int,
    item: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    strategy_sequence = parse_strategy_sequence(str(item.get("output", "")))
    strategy_segments = parse_strategy_segments(str(item.get("output", "")))
    prompt = build_user_prompt(item, strategy_sequence, strategy_segments)

    last_error = ""
    for attempt in range(1, args.retries + 2):
        try:
            async with semaphore:
                annotation = await annotate_with_llm(
                    client=client,
                    config=config,
                    prompt=prompt,
                    timeout=args.timeout,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    json_mode=not args.no_json_mode,
                )
                if args.sleep > 0:
                    await asyncio.sleep(args.sleep)
            return {
                **build_source_row(index, item, strategy_sequence, strategy_segments, args),
                **annotation,
                "llm_provider": config.provider,
                "llm_model": config.model,
                "status": "ok",
                "error": "",
            }
        except Exception as exc:
            last_error = str(exc)
            if is_non_retryable_api_error(exc):
                raise NonRetryableLLMError(last_error) from exc
            if attempt <= args.retries:
                await asyncio.sleep(min(2 ** attempt, 20))

    return {
        **build_source_row(index, item, strategy_sequence, strategy_segments, args),
        "use_tier": "reject",
        "scenario": "其他",
        "age_stage": "不明",
        "minor_suitability": False,
        "safety_level": "reject",
        "quality_label": "reject",
        "reject_reasons": ["llm_annotation_failed"],
        "rationale": "LLM 标注失败，保守标记为 reject。",
        "llm_provider": config.provider,
        "llm_model": config.model,
        "status": "failed",
        "error": last_error,
    }


async def run(args: argparse.Namespace) -> None:
    from openai import AsyncOpenAI

    input_path = Path(args.input)
    output_path = Path(args.output)
    items = load_json(input_path)
    config = build_llm_config(args.provider)
    if args.model:
        config = replace(config, model=args.model)
    if args.base_url:
        config = replace(config, base_url=args.base_url)
    client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
    done_indices = read_done_indices(output_path, skip_failed=args.skip_failed) if args.resume else set()

    selected: list[tuple[int, dict[str, Any]]] = []
    start = max(args.start, 0)
    end = len(items) if args.limit is None else min(len(items), start + args.limit)
    for index in range(start, end):
        if index in done_indices:
            continue
        selected.append((index, items[index]))

    print(f"Loaded {len(items)} rows from {input_path}")
    print(f"Output path: {output_path}")
    print(f"Provider/model: {config.provider}/{config.model}")
    print(f"Base URL: {config.base_url}")
    print(f"Rows to process: {len(selected)} (range {start}..{end - 1}, skipped {len(done_indices)} rows by resume policy)")

    processed = 0
    ok_count = 0
    failed_count = 0
    started_at = time.perf_counter()
    semaphore = asyncio.Semaphore(args.concurrency)

    for batch_start in range(0, len(selected), args.batch_size):
        batch = selected[batch_start : batch_start + args.batch_size]
        tasks = [
            annotate_one(semaphore, client, config, index, item, args)
            for index, item in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        stop_reason = ""
        for result in results:
            if isinstance(result, NonRetryableLLMError):
                stop_reason = str(result)
                break
            if isinstance(result, Exception):
                raise result

            row = result
            append_jsonl(output_path, row)
            processed += 1
            if row["status"] == "ok":
                ok_count += 1
            else:
                failed_count += 1
            if processed % args.print_every == 0 or processed == len(selected):
                elapsed = time.perf_counter() - started_at
                print(
                    f"Processed {processed}/{len(selected)} rows "
                    f"(ok={ok_count}, failed={failed_count}, elapsed={elapsed:.1f}s)"
                )
        if stop_reason:
            print("Stopped because the API returned a non-retryable error.")
            print(f"Error: {stop_reason}")
            print("Fix the API key/account issue, then rerun with --resume.")
            break

    print(
        f"Done. Processed {processed} rows. ok={ok_count}, failed={failed_count}. "
        f"Output: {output_path}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Annotate PsyQA_alpaca_labelled.json for EmoEdu with an OpenAI-compatible LLM API."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument(
        "--provider",
        choices=["deepseek", "dashscope", "dashscope-deepseek"],
        default="dashscope-deepseek",
    )
    parser.add_argument("--model", default="", help="Override provider default model, for example deepseek-v4-pro or qwen-plus.")
    parser.add_argument("--base-url", default="", help="Override provider default OpenAI-compatible base URL.")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--print-every", type=int, default=20)
    parser.add_argument("--resume", action="store_true", help="Skip rows already annotated successfully in output JSONL.")
    parser.add_argument("--skip-failed", action="store_true", help="With --resume, also skip rows whose previous status is failed.")
    parser.add_argument("--omit-output", action="store_true", help="Do not write the raw PsyQA output field.")
    parser.add_argument("--omit-strategy-segments", action="store_true", help="Do not write psyqa_strategy_segments text spans.")
    parser.add_argument("--no-json-mode", action="store_true", help="Disable OpenAI-compatible JSON mode.")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
