from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.config import Settings
from app.schemas.generator import GeneratorGenerateRequest
from app.services.f3_support_service import F3SupportService
from app.services.generator_service import GeneratorService, f3_prompt_bundle_hash
from app.services.llm_client import DeepSeekLLMClient

load_dotenv()

DATA_PATH = Path("exp/data/psyqa_labelled.json")
RUNS_DIR = Path("exp/runs/f3_support_probe")
DEFAULT_SCENARIOS = ["学业压力", "同伴关系", "亲子摩擦"]
DEFAULT_MODEL = "qwen3.7-plus"


def compact(text: str, limit: int = 420) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def select_samples(
    rows: list[dict[str, Any]],
    scenarios: list[str],
    per_scenario: int,
    seed: int,
) -> list[dict[str, Any]]:
    direct = [
        row
        for row in rows
        if row.get("status") == "ok"
        and row.get("use_tier") == "direct_exemplar"
        and row.get("quality_label") == "good"
        and row.get("safety_level") == "green"
        and row.get("scenario") in scenarios
    ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in direct:
        groups[str(row.get("scenario"))].append(row)
    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for scenario in scenarios:
        candidates = sorted(groups.get(scenario, []), key=lambda item: item.get("source_index", 0))
        rng.shuffle(candidates)
        selected.extend(candidates[:per_scenario])
    return sorted(
        selected,
        key=lambda item: (str(item.get("scenario")), int(item.get("source_index", 0))),
    )


def extract_json(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("No JSON object found in judge output")
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Judge output must be a JSON object")
    return data


def normalize_score(value: Any) -> int:
    try:
        number = int(value)
    except Exception:
        return 0
    return max(0, min(2, number))


def ngrams(text: str, size: int = 8) -> set[str]:
    compacted = "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", str(text or "")))
    if len(compacted) < size:
        return {compacted} if compacted else set()
    return {compacted[index : index + size] for index in range(len(compacted) - size + 1)}


def max_copy_overlap(candidate: str, support_cards: list[str]) -> float:
    candidate_grams = ngrams(candidate)
    if not candidate_grams or not support_cards:
        return 0.0
    max_score = 0.0
    for card in support_cards:
        card_grams = ngrams(card)
        if not card_grams:
            continue
        score = len(candidate_grams & card_grams) / len(candidate_grams)
        max_score = max(max_score, score)
    return round(max_score, 4)


def build_judge_prompt(
    sample: dict[str, Any],
    support_cards: list[str],
    c1_text: str,
    c2_text: str,
) -> str:
    return f"""你是 EmoEdu F3 生成器的离线验证员。任务是评估同一条学生倾诉下，c1 是否更像情感共情型，c2 是否更像认知共情型，并检查是否过早建议、是否照抄支持卡。

请按 EPITOME 的 0/1/2 标准分别给 c1、c2 打 ER/IP/EX：
- ER 情绪反应：是否具体、温暖、像是在和孩子的感受共振。0=没有接住情绪；1=说到了情绪但像旁观描述或模板安慰；2=具体、有陪伴感，孩子会觉得“对，就是这种感觉”。
- IP 解释/理解：是否准确理解孩子处境，并点出孩子没明说但藏在话里的担忧、在意或为难。0=误解或空泛；1=复述表面；2=准确点出隐含担忧/卡点。
- EX 探索：是否温和邀请孩子继续表达。0=关闭或转移；1=没有主动探索；2=低压力、具体、合适地邀请继续表达。

验证假设：
- c1_ER_stronger：c1 的 ER 必须严格高于 c2。
- c2_IP_stronger：c2 的 IP 必须严格高于 c1。

额外检查：
- premature_guidance：候选是否过早给建议、步骤、解决方案、要求立刻行动；轻微确认或非常低压力表达不算。
- support_card_copy：候选是否明显照抄支持卡中的句子或长片段；只借鉴策略动作不算。
- boundary：是否说教、诊断、替第三方解释动机、鼓励隐瞒、过长或成人化。

必须返回严格 JSON：
{{
  "c1": {{"ER": 0, "IP": 0, "EX": 0, "premature_guidance": false, "support_card_copy": false, "boundary": false}},
  "c2": {{"ER": 0, "IP": 0, "EX": 0, "premature_guidance": false, "support_card_copy": false, "boundary": false}},
  "separation_clear": true,
  "rationale": "一句中文理由"
}}

【场景】{sample.get('scenario')}
【学生倾诉】{sample.get('input')}

【PsyQA 支持卡】
{chr(10).join(support_cards) if support_cards else "无"}

【c1 情感共情型候选】
{c1_text}

【c2 认知共情型候选】
{c2_text}
"""


def normalize_judge(raw: dict[str, Any]) -> dict[str, Any]:
    def one(key: str) -> dict[str, Any]:
        value = raw.get(key) if isinstance(raw.get(key), dict) else {}
        return {
            "ER": normalize_score(value.get("ER")),
            "IP": normalize_score(value.get("IP")),
            "EX": normalize_score(value.get("EX")),
            "premature_guidance": bool(value.get("premature_guidance", False)),
            "support_card_copy": bool(value.get("support_card_copy", False)),
            "boundary": bool(value.get("boundary", False)),
        }

    c1 = one("c1")
    c2 = one("c2")
    c1_er_higher = c1["ER"] > c2["ER"]
    c2_ip_higher = c2["IP"] > c1["IP"]
    no_premature_guidance = not c1["premature_guidance"] and not c2["premature_guidance"]
    no_support_card_copy = not c1["support_card_copy"] and not c2["support_card_copy"]
    no_boundary = not c1["boundary"] and not c2["boundary"]
    both_pass = (
        c1_er_higher
        and c2_ip_higher
        and no_premature_guidance
        and no_support_card_copy
        and no_boundary
    )
    return {
        "c1": c1,
        "c2": c2,
        "c1_er_higher": c1_er_higher,
        "c2_ip_higher": c2_ip_higher,
        "no_premature_guidance": no_premature_guidance,
        "no_support_card_copy": no_support_card_copy,
        "no_boundary": no_boundary,
        "both_pass": both_pass,
        "separation_clear": bool(raw.get("separation_clear", False)),
        "rationale": compact(str(raw.get("rationale", "")), 700),
    }


async def chat_once(
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    timeout: float,
    temperature: float,
    max_tokens: int,
    response_format: dict[str, str] | None = None,
    retries: int = 1,
) -> str:
    last_error = ""
    for attempt in range(retries + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format
            response = await asyncio.wait_for(
                client.chat.completions.create(**kwargs),
                timeout=timeout,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries:
                await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(last_error)


async def run_case(
    sample: dict[str, Any],
    generator_service: GeneratorService,
    support_service: F3SupportService,
    judge_client: AsyncOpenAI,
    args: argparse.Namespace,
) -> dict[str, Any]:
    started = time.perf_counter()
    base = {
        "source_index": sample.get("source_index"),
        "scenario": sample.get("scenario"),
        "model": args.model,
        "judge_model": args.judge_model,
        "input": sample.get("input", ""),
        "psyqa_strategy_sequence": sample.get("psyqa_strategy_sequence", []),
    }
    try:
        support_context = support_service.build_context(
            scenario=str(sample.get("scenario") or "其他"),
            user_message=str(sample.get("input") or ""),
            external_examples=[],
        )
        generated = await generator_service.generate(
            GeneratorGenerateRequest(
                session_id=f"probe-{sample.get('source_index')}",
                user_message=str(sample.get("input") or ""),
                history=[],
                scenario=sample.get("scenario") or "其他",
                rag_examples=[],
            )
        )
        candidates = {item.candidate_id: item for item in generated.candidates}
        c1_text = candidates["c1"].text
        c2_text = candidates["c2"].text
        judge_prompt = build_judge_prompt(
            sample,
            support_context.support_cards,
            c1_text,
            c2_text,
        )
        raw_judge = await chat_once(
            judge_client,
            args.judge_model,
            judge_prompt,
            args.timeout,
            0.0,
            args.judge_max_tokens,
            response_format={"type": "json_object"},
            retries=args.retries,
        )
        judge = normalize_judge(extract_json(raw_judge))
        copy_overlap = {
            "c1": max_copy_overlap(c1_text, support_context.support_cards),
            "c2": max_copy_overlap(c2_text, support_context.support_cards),
        }
        return {
            **base,
            "status": "ok",
            "support_strategy_prior": support_context.strategy_prior,
            "support_cards": support_context.support_cards,
            "copy_overlap": copy_overlap,
            "candidates": [
                {"candidate_id": "c1", "orientation": candidates["c1"].orientation, "text": c1_text},
                {"candidate_id": "c2", "orientation": candidates["c2"].orientation, "text": c2_text},
            ],
            "judge": judge,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": "",
        }
    except Exception as exc:
        return {
            **base,
            "status": "failed",
            "support_strategy_prior": "",
            "support_cards": [],
            "copy_overlap": {},
            "candidates": [],
            "judge": {},
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": str(exc),
        }


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    failed_rows = [row for row in rows if row.get("status") != "ok"]

    def rate(key: str) -> float:
        if not ok_rows:
            return 0.0
        return round(sum(1 for row in ok_rows if row["judge"].get(key)) / len(ok_rows), 4)

    er_diffs = [
        row["judge"]["c1"]["ER"] - row["judge"]["c2"]["ER"]
        for row in ok_rows
    ]
    ip_diffs = [
        row["judge"]["c2"]["IP"] - row["judge"]["c1"]["IP"]
        for row in ok_rows
    ]
    by_scenario: dict[str, Counter] = defaultdict(Counter)
    for row in ok_rows:
        scenario = str(row.get("scenario"))
        by_scenario[scenario]["total"] += 1
        for key in (
            "c1_er_higher",
            "c2_ip_higher",
            "no_premature_guidance",
            "no_support_card_copy",
            "both_pass",
            "separation_clear",
        ):
            if row["judge"].get(key):
                by_scenario[scenario][key] += 1
    return {
        "total": len(rows),
        "ok": len(ok_rows),
        "failed": len(failed_rows),
        "c1_er_higher_rate": rate("c1_er_higher"),
        "c2_ip_higher_rate": rate("c2_ip_higher"),
        "no_premature_guidance_rate": rate("no_premature_guidance"),
        "no_support_card_copy_rate": rate("no_support_card_copy"),
        "no_boundary_rate": rate("no_boundary"),
        "both_pass_rate": rate("both_pass"),
        "separation_clear_rate": rate("separation_clear"),
        "avg_c1_minus_c2_ER": round(mean(er_diffs), 4) if er_diffs else 0.0,
        "avg_c2_minus_c1_IP": round(mean(ip_diffs), 4) if ip_diffs else 0.0,
        "avg_duration_ms": round(mean(row["duration_ms"] for row in ok_rows), 1) if ok_rows else 0.0,
        "by_scenario": {scenario: dict(counter) for scenario, counter in sorted(by_scenario.items())},
        "errors": Counter(row.get("error", "")[:200] for row in failed_rows).most_common(5),
    }


def write_report(run_dir: Path, metadata: dict[str, Any], summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# F3 Support Probe Report",
        "",
        f"- run_id: `{metadata['run_id']}`",
        f"- model: `{metadata['model']}`",
        f"- judge_model: `{metadata['judge_model']}`",
        f"- sample_count: `{metadata['sample_count']}`",
        f"- prompt_hash: `{metadata['prompt_hash']}`",
        "",
        "## Summary",
        "",
        "| metric | value |",
        "|---|---:|",
    ]
    for key, value in summary.items():
        if key in {"by_scenario", "errors"}:
            continue
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## By Scenario", "", "```json", json.dumps(summary["by_scenario"], ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## Failed Cases", ""])
    lines.append("- None" if not summary["errors"] else f"- {summary['errors']}")
    lines.extend(["", "## Cases", ""])
    for row in rows:
        lines.extend(
            [
                f"### source_index={row.get('source_index')} / {row.get('scenario')} / {row.get('status')}",
                "",
                f"Input: {compact(row.get('input', ''), 220)}",
                "",
            ]
        )
        if row.get("status") == "ok":
            judge = row["judge"]
            lines.extend(
                [
                    f"- support_cards: {len(row.get('support_cards', []))}",
                    f"- copy_overlap: {row.get('copy_overlap')}",
                    f"- c1 ER/IP/EX: {judge['c1']['ER']}/{judge['c1']['IP']}/{judge['c1']['EX']}",
                    f"- c2 ER/IP/EX: {judge['c2']['ER']}/{judge['c2']['IP']}/{judge['c2']['EX']}",
                    f"- c1_ER_stronger: `{judge['c1_er_higher']}`",
                    f"- c2_IP_stronger: `{judge['c2_ip_higher']}`",
                    f"- no_premature_guidance: `{judge['no_premature_guidance']}`",
                    f"- no_support_card_copy: `{judge['no_support_card_copy']}`",
                    f"- separation_clear: `{judge['separation_clear']}`",
                    f"- both_pass: `{judge['both_pass']}`",
                    f"- rationale: {judge.get('rationale', '')}",
                    "",
                    f"c1: {compact(row['candidates'][0]['text'], 260)}",
                    "",
                    f"c2: {compact(row['candidates'][1]['text'], 260)}",
                    "",
                ]
            )
        else:
            lines.append(f"error: {row.get('error')}")
            lines.append("")
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


async def main_async(args: argparse.Namespace) -> None:
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is required")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    rows = load_rows(Path(args.data_path))
    samples = select_samples(rows, parse_csv(args.scenarios), args.per_scenario, args.seed)
    if not samples:
        raise RuntimeError("No samples selected")

    run_id = args.run_id or datetime.now().strftime("qwen37-plus-%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        LLM_TIMEOUT=args.timeout,
        LLM_MAX_TOKENS=args.generator_max_tokens,
        GENERATOR_LLM_TEMPERATURE=args.generator_temperature,
        F3_SUPPORT_TOP_K=args.support_top_k,
        F3_SUPPORT_MIN_SCORE=args.support_min_score,
    )
    support_service = F3SupportService(settings)
    generator_client = DeepSeekLLMClient(
        api_key=api_key,
        base_url=base_url,
        model=args.model,
        thinking_type=None,
    )
    generator_service = GeneratorService(generator_client, settings, support_service)
    judge_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    metadata = {
        "run_id": run_id,
        "data_path": args.data_path,
        "base_url": base_url,
        "model": args.model,
        "judge_model": args.judge_model,
        "sample_count": len(samples),
        "sample_source_indices": [item.get("source_index") for item in samples],
        "scenarios": parse_csv(args.scenarios),
        "per_scenario": args.per_scenario,
        "seed": args.seed,
        "prompt_hash": f3_prompt_bundle_hash(),
        "generator_temperature": args.generator_temperature,
        "support_top_k": args.support_top_k,
        "support_min_score": args.support_min_score,
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "samples.json").write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Run directory: {run_dir}")
    print(f"Model: {args.model}; judge: {args.judge_model}")
    print(f"Samples: {[item.get('source_index') for item in samples]}")

    semaphore = asyncio.Semaphore(args.concurrency)

    async def guarded(sample: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await run_case(sample, generator_service, support_service, judge_client, args)

    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    results_path = run_dir / "results.jsonl"
    tasks = [asyncio.create_task(guarded(sample)) for sample in samples]
    for index, task in enumerate(asyncio.as_completed(tasks), start=1):
        row = await task
        append_jsonl(results_path, row)
        results.append(row)
        print(
            f"[{index}/{len(tasks)}] source={row.get('source_index')} "
            f"scenario={row.get('scenario')} status={row.get('status')} "
            f"elapsed={time.perf_counter() - started:.1f}s"
        )

    summary = summarize(results)
    payload = {"metadata": metadata, "summary": summary}
    (run_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(run_dir, metadata, summary, results)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Report: {run_dir / 'report.md'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run F3 support-RAG probe with c1/c2 judge checks.")
    parser.add_argument("--data-path", default=str(DATA_PATH))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--judge-model", default=DEFAULT_MODEL)
    parser.add_argument("--scenarios", default=",".join(DEFAULT_SCENARIOS))
    parser.add_argument("--per-scenario", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--generator-temperature", type=float, default=0.8)
    parser.add_argument("--generator-max-tokens", type=int, default=420)
    parser.add_argument("--judge-max-tokens", type=int, default=1000)
    parser.add_argument("--support-top-k", type=int, default=2)
    parser.add_argument("--support-min-score", type=float, default=0.10)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main_async(parse_args()))
