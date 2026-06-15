import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.schemas.safety import ConversationMessage
from app.services.critic_pairwise import (
    CriticPairwiseService,
    PairwiseCandidate,
    PairwiseContext,
    aggregate_pairwise_samples,
)
from app.services.llm_client import DeepSeekLLMClient, MockLLMClient


RUN_COLUMNS = [
    "pair_id",
    "sample_no",
    "repeat_no",
    "judgment_1_winner_id",
    "judgment_2_winner_id",
    "stable",
    "stable_winner_id",
    "invalid",
    "reason",
]

SUMMARY_COLUMNS = [
    "pair_id",
    "sample_no",
    "scenario",
    "c1_orientation",
    "c2_orientation",
    "pairwise_sample_count",
    "stable_votes_c1",
    "stable_votes_c2",
    "unstable_count",
    "invalid_count",
    "winner_id",
    "pairwise_stable",
    "pairwise_confidence",
    "selection_method",
    "c1_text",
    "c2_text",
]


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _history_from_json(raw_history: str) -> list[ConversationMessage]:
    if not raw_history:
        return []
    try:
        items = json.loads(raw_history)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    history = []
    for item in items:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = item.get("text")
        if role in {"student", "assistant"} and isinstance(text, str):
            history.append(ConversationMessage(role=role, text=text))
    return history


def _context_from_pair_row(row: dict[str, str]) -> PairwiseContext:
    return PairwiseContext(
        pair_id=row["pair_id"],
        session_id=f"pairwise-{row['pair_id']}",
        user_message=row["user_text"],
        history=_history_from_json(row.get("history_json", "")),
    )


def _candidate_from_pair_row(
    row: dict[str, str], candidate_id: str
) -> PairwiseCandidate:
    return PairwiseCandidate(
        candidate_id=candidate_id,
        orientation=row[f"{candidate_id}_orientation"],
        text=row[f"{candidate_id}_text"],
    )


def _run_row(pair_row: dict[str, str], sample) -> dict[str, str]:
    return {
        "pair_id": pair_row["pair_id"],
        "sample_no": pair_row["sample_no"],
        "repeat_no": str(sample.sample_no),
        "judgment_1_winner_id": sample.judgment_1_winner_id or "",
        "judgment_2_winner_id": sample.judgment_2_winner_id or "",
        "stable": _bool_text(sample.stable),
        "stable_winner_id": sample.stable_winner_id or "",
        "invalid": _bool_text(sample.invalid),
        "reason": sample.reason,
    }


def _summary_row(pair_row: dict[str, str], aggregate) -> dict[str, str]:
    return {
        "pair_id": pair_row["pair_id"],
        "sample_no": pair_row["sample_no"],
        "scenario": pair_row.get("scenario", ""),
        "c1_orientation": pair_row.get("c1_orientation", ""),
        "c2_orientation": pair_row.get("c2_orientation", ""),
        "pairwise_sample_count": str(aggregate.pairwise_sample_count),
        "stable_votes_c1": str(aggregate.stable_votes.get("c1", 0)),
        "stable_votes_c2": str(aggregate.stable_votes.get("c2", 0)),
        "unstable_count": str(aggregate.unstable_count),
        "invalid_count": str(aggregate.invalid_count),
        "winner_id": aggregate.winner_id or "",
        "pairwise_stable": _bool_text(aggregate.pairwise_stable),
        "pairwise_confidence": aggregate.pairwise_confidence,
        "selection_method": aggregate.selection_method,
        "c1_text": pair_row.get("c1_text", ""),
        "c2_text": pair_row.get("c2_text", ""),
    }


def _make_pairwise_service(settings: Settings) -> CriticPairwiseService:
    if settings.LLM_PROVIDER == "deepseek":
        llm_client = DeepSeekLLMClient(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.CRITIC_DEEPSEEK_MODEL or settings.DEEPSEEK_MODEL,
            thinking_type=settings.CRITIC_DEEPSEEK_THINKING,
        )
    else:
        llm_client = MockLLMClient()
    return CriticPairwiseService(llm_client, settings)


def _unique_values(rows: list[dict[str, str]], column: str) -> list[str]:
    return sorted({str(row.get(column, "")).strip() for row in rows if row.get(column)})


async def run_pairwise_judge(
    pair_package_path: Path,
    output_dir: Path,
    service=None,
    pairwise_sample_count: int = 3,
    settings: Settings | None = None,
) -> dict[str, Path]:
    settings = settings or Settings()
    service = service or _make_pairwise_service(settings)
    pair_rows = _read_csv(pair_package_path)
    run_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []

    for pair_row in pair_rows:
        context = _context_from_pair_row(pair_row)
        c1 = _candidate_from_pair_row(pair_row, "c1")
        c2 = _candidate_from_pair_row(pair_row, "c2")
        samples = []
        for repeat_no in range(1, pairwise_sample_count + 1):
            sample = await service.judge_sample(context, c1, c2, repeat_no)
            samples.append(sample)
            run_rows.append(_run_row(pair_row, sample))
        aggregate = aggregate_pairwise_samples(
            pair_row["pair_id"], samples, candidate_ids=["c1", "c2"]
        )
        summary_rows.append(_summary_row(pair_row, aggregate))

    output_dir.mkdir(parents=True, exist_ok=True)
    run_path = output_dir / "f9_pairwise_judge_runs.csv"
    summary_path = output_dir / "f9_pairwise_judge_summary.csv"
    manifest_path = output_dir / "f9_pairwise_judge_manifest.json"
    _write_csv(run_path, RUN_COLUMNS, run_rows)
    _write_csv(summary_path, SUMMARY_COLUMNS, summary_rows)
    manifest = {
        "pair_package_path": str(pair_package_path),
        "input_pairs": len(pair_rows),
        "judged_pairs": len(summary_rows),
        "pairwise_sample_count": pairwise_sample_count,
        "llm_provider": settings.LLM_PROVIDER,
        "critic_model": settings.CRITIC_DEEPSEEK_MODEL or settings.DEEPSEEK_MODEL,
        "critic_thinking": settings.CRITIC_DEEPSEEK_THINKING,
        "llm_timeout": settings.LLM_TIMEOUT,
        "critic_temperature": settings.CRITIC_LLM_TEMPERATURE,
        "generator_run_ids": _unique_values(pair_rows, "generator_run_id"),
        "generated_at_values": _unique_values(pair_rows, "generated_at"),
        "generator_models": _unique_values(pair_rows, "generator_model"),
        "generator_thinking_values": _unique_values(pair_rows, "generator_thinking"),
        "f3_prompt_bundle_hashes": _unique_values(pair_rows, "f3_prompt_bundle_hash"),
        "runs_path": str(run_path),
        "summary_path": str(summary_path),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"runs": run_path, "summary": summary_path, "manifest": manifest_path}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run offline F9 pairwise judge over a frozen pair package."
    )
    parser.add_argument("--pair-package", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pairwise-sample-count", type=int, default=3)
    args = parser.parse_args()

    asyncio.run(
        run_pairwise_judge(
            pair_package_path=args.pair_package,
            output_dir=args.output_dir,
            pairwise_sample_count=args.pairwise_sample_count,
        )
    )


if __name__ == "__main__":
    main()
