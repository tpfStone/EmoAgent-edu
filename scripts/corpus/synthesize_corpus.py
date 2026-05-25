from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings
from app.services.llm_client import DeepSeekLLMClient, LLMClientProtocol, MockLLMClient
from scripts.corpus.models import (
    Cell,
    PersonaConfig,
    RawUtterance,
    ScenarioConfig,
    load_generation_config,
    read_jsonl,
    select_cells,
    write_jsonl,
)


DEFAULT_CONFIG_PATH = Path("docs/corpus/generation_config.json")
DEFAULT_OUTPUT_ROOT = Path("docs/corpus/runs")


@dataclass(frozen=True)
class SynthesisResult:
    run_dir: Path
    raw_path: Path
    prompts_path: Path
    summary_path: Path
    generated_count: int


def build_generation_prompt(
    persona: PersonaConfig,
    scenario: ScenarioConfig,
    subscenario: str,
    variant_tags: list[str],
) -> str:
    tags = "、".join(variant_tags) if variant_tags else "自然口语"
    return f"""你要扮演一名中国初中生（12-15岁），向一个倾诉对象讲述自己的困扰。

【性格与情绪调节方式】
{persona.description}
调节策略依据：{persona.persona_basis}
语言特征：{persona.language_features}

【困扰情境】
{scenario.name}：{scenario.description}
本条子情境：{subscenario}
表达变化要求：{tags}

【要求】
1. 用初中生真实、口语化的中文表达，符合上述性格。
2. 只输出学生的倾诉内容，1-5句、20-180字，不要写对方的回应。
3. 不要刻意煽情或夸张，贴近真实初中生的语气。
4. 不涉及自伤、自杀等危机内容；不要出现"活着没意思""不想存在""消失算了"等隐式危机表达。
5. 不要输出解释、标题、编号、括号里的写作说明或任何系统提示痕迹。

直接输出这段倾诉：
"""


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _cell_key(cell: Cell) -> str:
    return f"{cell.persona.name}:{cell.scenario.name}"


def _sample_id(run_id: str, index: int) -> str:
    compact_run = "".join(ch for ch in run_id if ch.isalnum())[-8:] or "run"
    return f"syn_{compact_run}_{index:05d}"


def _select_variant(config, cell: Cell, index: int) -> tuple[str, list[str]]:
    subscenario = cell.scenario.subscenarios[index % len(cell.scenario.subscenarios)]
    tag_count = len(config.variant_tags)
    tags = [
        config.variant_tags[index % tag_count],
        config.variant_tags[(index // max(1, len(cell.scenario.subscenarios))) % tag_count],
    ]
    return subscenario, list(dict.fromkeys(tags))


def _dry_run_text(cell: Cell, subscenario: str, variant_tags: list[str]) -> str:
    if "反刍" in cell.persona.name:
        return f"{subscenario}这件事我一直在想。我总怀疑是不是自己哪里做错了。"
    if "外放" in cell.persona.name:
        return f"{subscenario}真的让我很火大。我明明已经很努力了，为什么还要这样对我！"
    if "适应" in cell.persona.name:
        return f"{subscenario}让我有点难受。我想冷静想想怎么处理，也想听听你的看法。"
    return f"{subscenario}这事我不太想多说。反正先这样吧，过几天也许就好了。"


def _load_quota_file(path: str | Path | None) -> dict[str, int]:
    if path is None:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(key): int(value) for key, value in data.items()}


def _target_for_cell(config, cell: Cell, mode: str, per_cell: int | None) -> int:
    if per_cell is None:
        return config.targets.probe_per_cell if mode == "probe" else 0
    if mode != "production":
        return per_cell
    multiplier = config.production_quota_multipliers.get(cell.persona.name, 1.0)
    return int(math.ceil(per_cell * multiplier))


def _build_llm_from_settings() -> LLMClientProtocol:
    settings = Settings()
    if settings.LLM_PROVIDER.lower() == "deepseek":
        return DeepSeekLLMClient(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
        )
    return MockLLMClient()


async def generate_corpus(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    run_id: str = "probe",
    mode: str = "probe",
    cells: list[str] | None = None,
    quota_file: str | Path | None = None,
    per_cell: int | None = None,
    dry_run: bool = False,
    resume: bool = False,
    max_concurrency: int = 3,
    llm_client: LLMClientProtocol | None = None,
) -> SynthesisResult:
    config = load_generation_config(config_path)
    selected_cells = select_cells(config, mode=mode, cells=cells)
    quotas = _load_quota_file(quota_file)
    run_dir = Path(output_root) / run_id
    raw_path = run_dir / "raw.jsonl"
    prompts_path = run_dir / "prompts.jsonl"
    summary_path = run_dir / "summary_generation.md"
    run_dir.mkdir(parents=True, exist_ok=True)

    existing_rows = read_jsonl(raw_path) if resume else []
    existing_by_cell: dict[str, int] = {}
    for row in existing_rows:
        key = f"{row.get('persona')}:{row.get('scenario')}"
        existing_by_cell[key] = existing_by_cell.get(key, 0) + 1
    if not resume:
        raw_path.write_text("", encoding="utf-8")
        prompts_path.write_text("", encoding="utf-8")

    llm = llm_client or _build_llm_from_settings()
    semaphore = asyncio.Semaphore(max(1, max_concurrency))
    rows_to_write: list[dict[str, Any]] = []
    prompts_to_write: list[dict[str, Any]] = []
    next_index = len(existing_rows) + 1

    async def generate_one(cell: Cell, cell_index: int, sample_index: int):
        subscenario, tags = _select_variant(config, cell, cell_index)
        prompt = build_generation_prompt(cell.persona, cell.scenario, subscenario, tags)
        sample_id = _sample_id(run_id, sample_index)
        if dry_run:
            text = _dry_run_text(cell, subscenario, tags)
        else:
            async with semaphore:
                text = await llm.generate(
                    prompt=prompt,
                    timeout=Settings().LLM_TIMEOUT,
                    temperature=0.9,
                    max_tokens=Settings().LLM_MAX_TOKENS,
                )
        row = RawUtterance(
            id=sample_id,
            persona=cell.persona.name,
            persona_basis=cell.persona.persona_basis,
            scenario=cell.scenario.name,
            text=text.strip(),
            human_checked=False,
            run_id=run_id,
            subscenario=subscenario,
            variant_tags=tags,
            gen_model=config.gen_model,
            gen_prompt_version=config.prompt_version,
            prompt_hash=_prompt_hash(prompt),
            intended_use=config.intended_use,
        ).to_dict()
        prompt_row = {
            "id": sample_id,
            "run_id": run_id,
            "persona": cell.persona.name,
            "scenario": cell.scenario.name,
            "subscenario": subscenario,
            "variant_tags": tags,
            "prompt_hash": row["prompt_hash"],
            "prompt": prompt,
        }
        return row, prompt_row

    tasks = []
    for cell in selected_cells:
        key = _cell_key(cell)
        target = quotas.get(key)
        if target is None:
            target = _target_for_cell(config, cell, mode, per_cell)
        already = existing_by_cell.get(key, 0)
        for cell_index in range(already, target):
            tasks.append(generate_one(cell, cell_index, next_index))
            next_index += 1

    for row, prompt_row in await asyncio.gather(*tasks):
        rows_to_write.append(row)
        prompts_to_write.append(prompt_row)

    write_jsonl(raw_path, rows_to_write, append=True)
    write_jsonl(prompts_path, prompts_to_write, append=True)
    total_rows = len(existing_rows) + len(rows_to_write)
    summary_path.write_text(
        "\n".join(
            [
                "# Corpus Synthesis Summary",
                "",
                f"- run_id: `{run_id}`",
                f"- mode: `{mode}`",
                f"- dry_run: `{dry_run}`",
                f"- generated_this_run: {len(rows_to_write)}",
                f"- total_raw_rows: {total_rows}",
                f"- selected_cells: {len(selected_cells)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return SynthesisResult(
        run_dir=run_dir,
        raw_path=raw_path,
        prompts_path=prompts_path,
        summary_path=summary_path,
        generated_count=len(rows_to_write),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate EmoEdu synthetic corpus.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=["probe", "production"], default="probe")
    parser.add_argument("--cells", nargs="*", default=None)
    parser.add_argument("--quota-file", default=None)
    parser.add_argument("--per-cell", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-concurrency", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    asyncio.run(
        generate_corpus(
            config_path=args.config,
            output_root=args.output_root,
            run_id=args.run_id,
            mode=args.mode,
            cells=args.cells,
            quota_file=args.quota_file,
            per_cell=args.per_cell,
            dry_run=args.dry_run,
            resume=args.resume,
            max_concurrency=args.max_concurrency,
        )
    )


if __name__ == "__main__":
    main()
