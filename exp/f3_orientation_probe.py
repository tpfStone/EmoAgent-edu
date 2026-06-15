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

from app.services.generator_service import (
    COMMON_PROMPT,
    F9_RELIABILITY_GUARDRAILS,
    ORIENTATION_PROMPTS,
    clean_generator_output,
    f3_prompt_bundle_hash,
)

load_dotenv()

DATA_PATH = Path("exp/data/psyqa_labelled.json")
RUNS_DIR = Path("exp/runs/f3_orientation_probe")
DEFAULT_MODELS = [
    "qwen3.7-max-2026-05-20",
    "qwen3.7-max-preview",
    "qwen3.6-max-preview",
    "qwen3.5-plus-2026-04-20",
]
DEFAULT_SCENARIOS = ["学业压力", "同伴关系", "亲子摩擦"]
ORIENTATION_BY_ID = {
    "c1": "共情型",
    "c2": "引导反思型",
}


class ExperimentError(RuntimeError):
    pass


def compact(text: str, limit: int = 420) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def parse_models(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def select_samples(
    rows: list[dict[str, Any]],
    scenarios: list[str],
    per_scenario: int,
    limit: int | None,
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

    if limit is not None and len(selected) > limit:
        rng.shuffle(selected)
        selected = selected[:limit]

    return sorted(selected, key=lambda item: (str(item.get("scenario")), int(item.get("source_index", 0))))


def build_f3_prompt(sample: dict[str, Any], orientation: str) -> str:
    scenario = sample.get("scenario", "其他")
    user_message = sample.get("input", "")
    return f"""{COMMON_PROMPT}
{F9_RELIABILITY_GUARDRAILS}
{ORIENTATION_PROMPTS[orientation]}

【情境】{scenario}
【对话历史】无
【参考（可选，仅供风格参考，不要照抄）】无
【孩子刚说的话】{user_message}

请按你的取向，生成一条回应：
"""


def build_judge_prompt(sample: dict[str, Any], c1_text: str, c2_text: str) -> str:
    return f"""你是 EmoEdu F3 生成器的离线验证员。任务是判断同一条学生倾诉下，c1 是否更像共情型，c2 是否更像引导反思型。

请按 EPITOME 的 0/1/2 标准分别给 c1、c2 打 ER/IP/EX：
- ER 情绪反应：是否具体、温暖、像是在和孩子的感受共振。0=没有接住情绪；1=说到了情绪但像旁观描述或模板安慰；2=具体、有陪伴感，孩子会觉得“对，就是这种感觉”。
- IP 解释/理解：是否准确理解孩子处境，并点出孩子没明说但藏在话里的担忧、在意或为难。0=误解或空泛；1=复述表面；2=准确点出隐含担忧/卡点。
- EX 探索：是否温和邀请孩子继续表达。0=关闭或转移；1=没有主动探索；2=低压力、具体、合适地邀请继续表达。

本次验证关注两个假设：
- c1_ER_higher：c1 的 ER 必须严格高于 c2。
- c2_IP_higher：c2 的 IP 必须严格高于 c1。

注意：
- 只根据候选文本判断，不脑补。
- c1 不应给建议、分析成因或推进下一步。
- c2 不应给建议或新视角，而应把孩子自己的视角和没说出口的担忧说准。
- 如果两条都很像、都模板化、都越界，separation_clear=false。

必须返回严格 JSON，不要解释性散文：
{{
  "c1": {{"ER": 0, "IP": 0, "EX": 0, "boundary": false}},
  "c2": {{"ER": 0, "IP": 0, "EX": 0, "boundary": false}},
  "separation_clear": true,
  "better_orientation_fit": "both_fit|c1_only|c2_only|neither|unclear",
  "rationale": "一句中文理由"
}}

【场景】{sample.get('scenario')}
【学生倾诉】{sample.get('input')}

【c1 共情型候选】
{c1_text}

【c2 引导反思型候选】
{c2_text}
"""


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


def normalize_judge(raw: dict[str, Any]) -> dict[str, Any]:
    c1_raw = raw.get("c1") if isinstance(raw.get("c1"), dict) else {}
    c2_raw = raw.get("c2") if isinstance(raw.get("c2"), dict) else {}
    c1 = {
        "ER": normalize_score(c1_raw.get("ER")),
        "IP": normalize_score(c1_raw.get("IP")),
        "EX": normalize_score(c1_raw.get("EX")),
        "boundary": bool(c1_raw.get("boundary", False)),
    }
    c2 = {
        "ER": normalize_score(c2_raw.get("ER")),
        "IP": normalize_score(c2_raw.get("IP")),
        "EX": normalize_score(c2_raw.get("EX")),
        "boundary": bool(c2_raw.get("boundary", False)),
    }
    c1_er_higher = c1["ER"] > c2["ER"]
    c2_ip_higher = c2["IP"] > c1["IP"]
    both_pass = c1_er_higher and c2_ip_higher and not c1["boundary"] and not c2["boundary"]
    return {
        "c1": c1,
        "c2": c2,
        "c1_er_higher": c1_er_higher,
        "c2_ip_higher": c2_ip_higher,
        "both_pass": both_pass,
        "separation_clear": bool(raw.get("separation_clear", False)),
        "better_orientation_fit": str(raw.get("better_orientation_fit", "unclear")),
        "rationale": compact(str(raw.get("rationale", "")), limit=600),
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
            response = await asyncio.wait_for(client.chat.completions.create(**kwargs), timeout=timeout)
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries:
                await asyncio.sleep(1.5 * (attempt + 1))
    raise ExperimentError(last_error)


async def run_case(
    client: AsyncOpenAI,
    sample: dict[str, Any],
    model: str,
    judge_model: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    started = time.perf_counter()
    base = {
        "source_index": sample.get("source_index"),
        "scenario": sample.get("scenario"),
        "model": model,
        "judge_model": judge_model,
        "input": sample.get("input", ""),
        "reference_output": sample.get("output", ""),
        "psyqa_strategy_sequence": sample.get("psyqa_strategy_sequence", []),
    }
    try:
        c1_prompt = build_f3_prompt(sample, ORIENTATION_BY_ID["c1"])
        c2_prompt = build_f3_prompt(sample, ORIENTATION_BY_ID["c2"])
        c1_raw, c2_raw = await asyncio.gather(
            chat_once(client, model, c1_prompt, args.timeout, args.generator_temperature, args.generator_max_tokens, retries=args.retries),
            chat_once(client, model, c2_prompt, args.timeout, args.generator_temperature, args.generator_max_tokens, retries=args.retries),
        )
        c1_text = clean_generator_output(c1_raw)
        c2_text = clean_generator_output(c2_raw)
        judge_prompt = build_judge_prompt(sample, c1_text, c2_text)
        judge_raw = await chat_once(
            client,
            judge_model,
            judge_prompt,
            args.timeout,
            0.0,
            args.judge_max_tokens,
            response_format={"type": "json_object"},
            retries=args.retries,
        )
        judge = normalize_judge(extract_json(judge_raw))
        return {
            **base,
            "status": "ok",
            "candidates": [
                {"candidate_id": "c1", "orientation": ORIENTATION_BY_ID["c1"], "text": c1_text},
                {"candidate_id": "c2", "orientation": ORIENTATION_BY_ID["c2"], "text": c2_text},
            ],
            "judge": judge,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": "",
        }
    except Exception as exc:
        return {
            **base,
            "status": "failed",
            "candidates": [],
            "judge": {},
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": str(exc),
        }


def load_done_keys(path: Path) -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    if not path.exists():
        return done
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "ok" and isinstance(row.get("source_index"), int):
                done.add((str(row.get("model")), int(row["source_index"])))
    return done


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_model[str(row.get("model"))].append(row)

    model_summary: dict[str, Any] = {}
    for model, model_rows in sorted(by_model.items()):
        ok_rows = [row for row in model_rows if row.get("status") == "ok"]
        failed_rows = [row for row in model_rows if row.get("status") != "ok"]
        def rate(predicate) -> float:
            return round(sum(1 for row in ok_rows if predicate(row)) / len(ok_rows), 4) if ok_rows else 0.0
        er_diffs = [row["judge"]["c1"]["ER"] - row["judge"]["c2"]["ER"] for row in ok_rows]
        ip_diffs = [row["judge"]["c2"]["IP"] - row["judge"]["c1"]["IP"] for row in ok_rows]
        by_scenario: dict[str, Counter] = defaultdict(Counter)
        for row in ok_rows:
            scenario = str(row.get("scenario"))
            by_scenario[scenario]["total"] += 1
            if row["judge"].get("both_pass"):
                by_scenario[scenario]["both_pass"] += 1
            if row["judge"].get("c1_er_higher"):
                by_scenario[scenario]["c1_er_higher"] += 1
            if row["judge"].get("c2_ip_higher"):
                by_scenario[scenario]["c2_ip_higher"] += 1
        model_summary[model] = {
            "total": len(model_rows),
            "ok": len(ok_rows),
            "failed": len(failed_rows),
            "c1_er_higher_rate": rate(lambda row: row["judge"].get("c1_er_higher")),
            "c2_ip_higher_rate": rate(lambda row: row["judge"].get("c2_ip_higher")),
            "both_pass_rate": rate(lambda row: row["judge"].get("both_pass")),
            "separation_clear_rate": rate(lambda row: row["judge"].get("separation_clear")),
            "avg_c1_minus_c2_ER": round(mean(er_diffs), 4) if er_diffs else 0.0,
            "avg_c2_minus_c1_IP": round(mean(ip_diffs), 4) if ip_diffs else 0.0,
            "by_scenario": {scenario: dict(counter) for scenario, counter in sorted(by_scenario.items())},
            "errors": Counter(row.get("error", "")[:160] for row in failed_rows).most_common(5),
        }
    return model_summary


def write_report(run_dir: Path, metadata: dict[str, Any], summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# F3 Orientation Probe Report",
        "",
        f"- run_id: `{metadata['run_id']}`",
        f"- data_path: `{metadata['data_path']}`",
        f"- sample_count: `{metadata['sample_count']}`",
        f"- models: `{', '.join(metadata['models'])}`",
        f"- judge_model: `{metadata['judge_model']}`",
        f"- prompt_hash: `{metadata['prompt_hash']}`",
        "",
        "## Summary",
        "",
        "| model | ok/total | c1 ER higher | c2 IP higher | both pass | separation clear | avg ER diff | avg IP diff |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model, item in summary.items():
        lines.append(
            f"| {model} | {item['ok']}/{item['total']} | {item['c1_er_higher_rate']:.2%} | "
            f"{item['c2_ip_higher_rate']:.2%} | {item['both_pass_rate']:.2%} | "
            f"{item['separation_clear_rate']:.2%} | {item['avg_c1_minus_c2_ER']:.2f} | "
            f"{item['avg_c2_minus_c1_IP']:.2f} |"
        )
    lines.extend(["", "## Failed Cases", ""])
    for model, item in summary.items():
        if item["errors"]:
            lines.append(f"- {model}: {item['errors']}")
    if all(not item["errors"] for item in summary.values()):
        lines.append("- None")

    lines.extend(["", "## Case Preview", ""])
    for row in [item for item in rows if item.get("status") == "ok"][:8]:
        judge = row["judge"]
        lines.extend([
            f"### {row['model']} / source_index={row['source_index']} / {row['scenario']}",
            "",
            f"Input: {compact(row.get('input', ''), 180)}",
            "",
            f"c1 ER/IP/EX = {judge['c1']['ER']}/{judge['c1']['IP']}/{judge['c1']['EX']}",
            f"c2 ER/IP/EX = {judge['c2']['ER']}/{judge['c2']['IP']}/{judge['c2']['EX']}",
            f"both_pass = `{judge['both_pass']}`, separation_clear = `{judge['separation_clear']}`",
            f"Rationale: {judge.get('rationale', '')}",
            "",
        ])
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


async def main_async(args: argparse.Namespace) -> None:
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key and not args.dry_run:
        raise RuntimeError("DASHSCOPE_API_KEY is required")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    models = parse_models(args.models)
    scenarios = parse_models(args.scenarios)
    rows = load_rows(Path(args.data_path))
    samples = select_samples(rows, scenarios, args.per_scenario, args.limit, args.seed)
    if not samples:
        raise RuntimeError("No direct_exemplar samples selected")

    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    samples_path = run_dir / "samples.json"
    summary_path = run_dir / "summary.json"
    metadata_path = run_dir / "metadata.json"

    metadata = {
        "run_id": run_id,
        "data_path": args.data_path,
        "base_url": base_url,
        "models": models,
        "judge_model": args.judge_model,
        "sample_count": len(samples),
        "sample_source_indices": [sample.get("source_index") for sample in samples],
        "scenarios": scenarios,
        "per_scenario": args.per_scenario,
        "seed": args.seed,
        "prompt_hash": f3_prompt_bundle_hash(),
        "generator_temperature": args.generator_temperature,
    }
    samples_path.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Run directory: {run_dir}")
    print(f"Selected {len(samples)} samples: {[sample.get('source_index') for sample in samples]}")
    print(f"Models: {models}")
    print(f"Judge model: {args.judge_model}")

    if args.dry_run:
        print("Dry run only. No API calls were made.")
        return

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    done = load_done_keys(results_path) if args.resume else set()
    all_rows: list[dict[str, Any]] = []
    if results_path.exists():
        with results_path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    all_rows.append(json.loads(line))

    semaphore = asyncio.Semaphore(args.concurrency)

    async def guarded_run(model: str, sample: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await run_case(client, sample, model, args.judge_model, args)

    pending: list[tuple[str, dict[str, Any]]] = []
    for model in models:
        for sample in samples:
            key = (model, int(sample.get("source_index")))
            if key not in done:
                pending.append((model, sample))

    started_at = time.perf_counter()
    tasks = [asyncio.create_task(guarded_run(model, sample)) for model, sample in pending]
    for index, task in enumerate(asyncio.as_completed(tasks), 1):
        row = await task
        append_jsonl(results_path, row)
        all_rows.append(row)
        status = row.get("status")
        print(
            f"[{index}/{len(pending)}] {row.get('model')} source={row.get('source_index')} "
            f"scenario={row.get('scenario')} status={status} elapsed={time.perf_counter() - started_at:.1f}s"
        )

    summary = summarize(all_rows)
    summary_payload = {"metadata": metadata, "summary": summary}
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(run_dir, metadata, summary, all_rows)
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))
    print(f"Report: {run_dir / 'report.md'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe F3 c1/c2 orientation separation on PsyQA direct_exemplar samples.")
    parser.add_argument("--data-path", default=str(DATA_PATH))
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--judge-model", default="qwen3.7-max-2026-05-20")
    parser.add_argument("--scenarios", default=",".join(DEFAULT_SCENARIOS))
    parser.add_argument("--per-scenario", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--generator-temperature", type=float, default=0.8)
    parser.add_argument("--generator-max-tokens", type=int, default=420)
    parser.add_argument("--judge-max-tokens", type=int, default=900)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main_async(parse_args()))



