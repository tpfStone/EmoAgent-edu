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
from app.schemas.critic import CandidateInput, CriticEvaluateRequest
from app.services.critic_service import CriticService
from app.services.llm_client import DeepSeekLLMClient, MockLLMClient
from scripts.corpus.f9_pairwise_judge import _history_from_json


BASELINE_COLUMNS = [
    "pair_id",
    "sample_no",
    "c1_weighted_total",
    "c2_weighted_total",
    "c1_boundary_flag",
    "c2_boundary_flag",
    "pointwise_winner",
    "pointwise_tie",
    "pointwise_sample_count",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BASELINE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _make_critic_service(settings: Settings) -> CriticService:
    if settings.LLM_PROVIDER == "deepseek":
        llm_client = DeepSeekLLMClient(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.CRITIC_DEEPSEEK_MODEL or settings.DEEPSEEK_MODEL,
            thinking_type=settings.CRITIC_DEEPSEEK_THINKING,
        )
    else:
        llm_client = MockLLMClient()
    return CriticService(llm_client, None, settings)


def _winner_from_scores(scores_by_id) -> tuple[str, bool]:
    c1 = scores_by_id["c1"]
    c2 = scores_by_id["c2"]
    if c1.boundary_flag and c2.boundary_flag:
        return "", False
    if c1.boundary_flag:
        return "c2", False
    if c2.boundary_flag:
        return "c1", False
    if c1.weighted_total == c2.weighted_total:
        return "tie", True
    return ("c1", False) if c1.weighted_total > c2.weighted_total else ("c2", False)


async def run_pointwise_baseline(
    pair_package_path: Path,
    output_path: Path,
    critic_service=None,
    settings: Settings | None = None,
) -> dict[str, Path]:
    settings = settings or Settings()
    critic_service = critic_service or _make_critic_service(settings)
    pair_rows = _read_csv(pair_package_path)
    rows = []
    for pair_row in pair_rows:
        response = await critic_service.evaluate(
            CriticEvaluateRequest(
                session_id=f"pointwise-{pair_row['pair_id']}",
                user_message=pair_row["user_text"],
                history=_history_from_json(pair_row.get("history_json", "")),
                activated_casel=[],
                candidates=[
                    CandidateInput(
                        candidate_id="c1",
                        orientation=pair_row["c1_orientation"],
                        text=pair_row["c1_text"],
                    ),
                    CandidateInput(
                        candidate_id="c2",
                        orientation=pair_row["c2_orientation"],
                        text=pair_row["c2_text"],
                    ),
                ],
            )
        )
        scores_by_id = {score.candidate_id: score for score in response.scores}
        winner, tie = _winner_from_scores(scores_by_id)
        rows.append(
            {
                "pair_id": pair_row["pair_id"],
                "sample_no": pair_row["sample_no"],
                "c1_weighted_total": f"{scores_by_id['c1'].weighted_total:.3f}",
                "c2_weighted_total": f"{scores_by_id['c2'].weighted_total:.3f}",
                "c1_boundary_flag": _bool_text(scores_by_id["c1"].boundary_flag),
                "c2_boundary_flag": _bool_text(scores_by_id["c2"].boundary_flag),
                "pointwise_winner": winner,
                "pointwise_tie": _bool_text(tie),
                "pointwise_sample_count": str(settings.CRITIC_SAMPLE_COUNT),
            }
        )
    baseline_path = _write_csv(output_path, rows)
    manifest_path = output_path.with_name(f"{output_path.stem}_manifest.json")
    manifest = {
        "pair_package_path": str(pair_package_path),
        "baseline_path": str(baseline_path),
        "input_pairs": len(pair_rows),
        "pointwise_rows": len(rows),
        "llm_provider": settings.LLM_PROVIDER,
        "critic_model": settings.CRITIC_DEEPSEEK_MODEL or settings.DEEPSEEK_MODEL,
        "critic_thinking": settings.CRITIC_DEEPSEEK_THINKING,
        "llm_timeout": settings.LLM_TIMEOUT,
        "critic_temperature": settings.CRITIC_LLM_TEMPERATURE,
        "pointwise_sample_count": settings.CRITIC_SAMPLE_COUNT,
        "f3_prompt_bundle_hashes": sorted(
            {
                str(row.get("f3_prompt_bundle_hash", "")).strip()
                for row in pair_rows
                if row.get("f3_prompt_bundle_hash")
            }
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"baseline": baseline_path, "manifest": manifest_path}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build pointwise weighted-total baseline for F9 pairwise packages."
    )
    parser.add_argument("--pair-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(
        run_pointwise_baseline(
            pair_package_path=args.pair_package,
            output_path=args.output,
        )
    )


if __name__ == "__main__":
    main()
