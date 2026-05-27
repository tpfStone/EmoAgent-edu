import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.schemas.critic import CandidateInput, CriticEvaluateRequest
from app.schemas.generator import GeneratorGenerateRequest
from app.services.critic_service import CriticService
from app.services.generator_service import (
    GENERATOR_FALLBACK_TEXT,
    GeneratorService,
    f3_prompt_bundle_hash,
)
from app.services.llm_client import DeepSeekLLMClient, MockLLMClient
from scripts.corpus.f9_pairwise_package import (
    build_annotation_rows,
    build_pair_rows,
    validate_pair_provenance,
    write_annotation_template,
    write_pair_package,
)
from scripts.corpus.f9_validation import _read_csv, load_cases


RERUN_CANDIDATE_COLUMNS = [
    "sample_no",
    "source",
    "candidate_id",
    "scenario",
    "orientation",
    "user_text",
    "history_json",
    "candidate_text",
    "boundary_flag",
    "boundary_reason",
    "F4_ER",
    "F4_IP",
    "F4_EX",
    "weighted_total",
    "rationale",
    "generator_run_id",
    "generated_at",
    "generator_model",
    "generator_thinking",
    "f3_prompt_bundle_hash",
]

DEFAULT_OUTPUT_ROOT = Path("docs/corpus/f9/pairwise-selection-pilot")
DEFAULT_ANALYSIS_PATH = Path("docs/corpus/f9/error-analysis/f9_error_analysis_draft.csv")
DEFAULT_BLIND_PATH = Path("docs/corpus/f9/baseline/f9_blind_annotation.csv")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _make_generator_service(settings: Settings) -> GeneratorService:
    if settings.LLM_PROVIDER.lower() == "deepseek":
        llm_client = DeepSeekLLMClient(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            thinking_type=settings.DEEPSEEK_THINKING,
        )
    else:
        llm_client = MockLLMClient()
    return GeneratorService(llm_client, settings)


def _make_critic_service(settings: Settings) -> CriticService:
    if settings.LLM_PROVIDER.lower() == "deepseek":
        llm_client = DeepSeekLLMClient(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.CRITIC_DEEPSEEK_MODEL or settings.DEEPSEEK_MODEL,
            thinking_type=settings.CRITIC_DEEPSEEK_THINKING,
        )
    else:
        llm_client = MockLLMClient()
    return CriticService(llm_client, None, settings)


def _score_row_by_candidate_id(response) -> dict[str, object]:
    return {score.candidate_id: score for score in response.scores}


async def _candidate_rows_for_case(case, generator, critic, provenance) -> list[dict[str, str]]:
    generated = await generator.generate(
        GeneratorGenerateRequest(
            session_id=f"f9-pairwise-rerun-{case.sample_no}",
            user_message=case.user_message,
            history=case.history,
            scenario=case.scenario,
            rag_examples=[],
        )
    )
    candidates = [
        CandidateInput(
            candidate_id=candidate.candidate_id,
            orientation=candidate.orientation,
            text=candidate.text,
        )
        for candidate in generated.candidates
    ]
    scored = await critic.evaluate(
        CriticEvaluateRequest(
            session_id=f"f9-pairwise-rerun-{case.sample_no}",
            user_message=case.user_message,
            history=case.history,
            activated_casel=[],
            candidates=candidates,
        )
    )
    scores_by_id = _score_row_by_candidate_id(scored)
    rows: list[dict[str, str]] = []
    for candidate in generated.candidates:
        score = scores_by_id[candidate.candidate_id]
        rows.append(
            {
                "sample_no": str(case.sample_no),
                "source": "phase-a-rerun",
                "candidate_id": candidate.candidate_id,
                "scenario": case.scenario,
                "orientation": candidate.orientation,
                "user_text": case.user_message,
                "history_json": case.history_json,
                "candidate_text": candidate.text,
                "boundary_flag": _bool_text(score.boundary_flag),
                "boundary_reason": score.boundary_reason,
                "F4_ER": str(score.epitome.ER),
                "F4_IP": str(score.epitome.IP),
                "F4_EX": str(score.epitome.EX),
                "weighted_total": f"{score.weighted_total:.3f}",
                "rationale": score.rationale,
                **provenance,
            }
        )
    return rows


def _is_true(value: str) -> bool:
    return str(value).strip().lower() == "true"


def _nonzero_counts(counts: dict[str, int]) -> dict[str, int]:
    return {key: value for key, value in counts.items() if value}


def _balanced_subset(pair_rows: list[dict[str, str]], target_pair_count: int) -> list[dict[str, str]]:
    if len(pair_rows) <= target_pair_count:
        return pair_rows
    by_scenario: dict[str, list[dict[str, str]]] = {}
    scenario_order: list[str] = []
    for row in pair_rows:
        scenario = row.get("scenario", "")
        if scenario not in by_scenario:
            by_scenario[scenario] = []
            scenario_order.append(scenario)
        by_scenario[scenario].append(row)

    selected: list[dict[str, str]] = []
    while len(selected) < target_pair_count:
        progressed = False
        for scenario in scenario_order:
            if by_scenario[scenario] and len(selected) < target_pair_count:
                selected.append(by_scenario[scenario].pop(0))
                progressed = True
        if not progressed:
            break
    return selected


def build_filtered_pair_rows(
    candidate_rows: list[dict[str, str]], target_pair_count: int
) -> tuple[list[dict[str, str]], dict[str, int]]:
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    order: list[str] = []
    for row in candidate_rows:
        sample_no = str(row.get("sample_no", "")).strip()
        candidate_id = str(row.get("candidate_id", "")).strip()
        if not sample_no or candidate_id not in {"c1", "c2"}:
            continue
        if sample_no not in grouped:
            grouped[sample_no] = {}
            order.append(sample_no)
        grouped[sample_no][candidate_id] = row

    excluded = {
        "incomplete_pair": 0,
        "generator_fallback": 0,
        "double_boundary": 0,
        "duplicate_user_text": 0,
    }
    seen_user_text: set[str] = set()
    eligible_candidate_rows: list[dict[str, str]] = []
    for sample_no in order:
        candidates = grouped[sample_no]
        if "c1" not in candidates or "c2" not in candidates:
            excluded["incomplete_pair"] += 1
            continue
        c1 = candidates["c1"]
        c2 = candidates["c2"]
        if GENERATOR_FALLBACK_TEXT in {
            c1.get("candidate_text", ""),
            c2.get("candidate_text", ""),
        }:
            excluded["generator_fallback"] += 1
            continue
        if _is_true(c1.get("boundary_flag", "")) and _is_true(
            c2.get("boundary_flag", "")
        ):
            excluded["double_boundary"] += 1
            continue
        user_text = c1.get("user_text") or c2.get("user_text", "")
        if user_text in seen_user_text:
            excluded["duplicate_user_text"] += 1
            continue
        seen_user_text.add(user_text)
        eligible_candidate_rows.extend([c1, c2])

    pair_rows = build_pair_rows(eligible_candidate_rows)
    validate_pair_provenance(pair_rows)
    return _balanced_subset(pair_rows, target_pair_count), _nonzero_counts(excluded)


async def run_pairwise_rerun_generation(
    analysis_path: Path,
    blind_path: Path,
    output_root: Path,
    settings: Settings,
    target_pair_count: int = 24,
    sample_nos: list[int] | None = None,
    generator_service=None,
    critic_service=None,
    run_id: str | None = None,
    generated_at: str | None = None,
    prompt_bundle_hash: str | None = None,
) -> dict[str, Path]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    run_id = run_id or f"phase-a-rerun-{generated_at}"
    prompt_bundle_hash = prompt_bundle_hash or f3_prompt_bundle_hash()
    provenance = {
        "generator_run_id": run_id,
        "generated_at": generated_at,
        "generator_model": settings.DEEPSEEK_MODEL,
        "generator_thinking": settings.DEEPSEEK_THINKING,
        "f3_prompt_bundle_hash": prompt_bundle_hash,
    }
    generator = generator_service or _make_generator_service(settings)
    critic = critic_service or _make_critic_service(settings)
    sample_nos = sample_nos or [int(row["sample_no"]) for row in _read_csv(analysis_path)]
    cases = load_cases(analysis_path, blind_path, sample_nos)

    candidate_rows: list[dict[str, str]] = []
    for case in cases:
        candidate_rows.extend(
            await _candidate_rows_for_case(case, generator, critic, provenance)
        )

    pair_rows, excluded_counts = build_filtered_pair_rows(
        candidate_rows, target_pair_count=target_pair_count
    )
    input_dir = output_root / "inputs" / "phase-a-rerun"
    annotation_dir = output_root / "annotations" / "phase-a-rerun"
    candidates_path = input_dir / "f9_pairwise_rerun_candidates.csv"
    pairs_path = input_dir / "f9_pairwise_rerun_pairs.csv"
    annotation_path = annotation_dir / "f9_pairwise_rerun_human_ab.csv"
    manifest_path = input_dir / "f9_pairwise_rerun_generation_manifest.json"

    _write_csv(candidates_path, RERUN_CANDIDATE_COLUMNS, candidate_rows)
    write_pair_package(pairs_path, pair_rows)
    write_annotation_template(annotation_path, build_annotation_rows(pair_rows))
    manifest = {
        "analysis_path": str(analysis_path),
        "blind_path": str(blind_path),
        "generated_candidate_rows": len(candidate_rows),
        "selected_pairs": len(pair_rows),
        "target_pair_count": target_pair_count,
        "source_sample_nos": sample_nos,
        "excluded_counts": excluded_counts,
        "llm_provider": settings.LLM_PROVIDER,
        "generator_model": settings.DEEPSEEK_MODEL,
        "generator_thinking": settings.DEEPSEEK_THINKING,
        "critic_model": settings.CRITIC_DEEPSEEK_MODEL or settings.DEEPSEEK_MODEL,
        "critic_thinking": settings.CRITIC_DEEPSEEK_THINKING,
        "critic_sample_count": settings.CRITIC_SAMPLE_COUNT,
        "llm_timeout": settings.LLM_TIMEOUT,
        "pair_package_path": str(pairs_path),
        "annotation_path": str(annotation_path),
        **provenance,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "candidates": candidates_path,
        "pairs": pairs_path,
        "annotations": annotation_path,
        "manifest": manifest_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Phase A rerun candidate pairs and blind annotation template."
    )
    parser.add_argument("--analysis-path", type=Path, default=DEFAULT_ANALYSIS_PATH)
    parser.add_argument("--blind-path", type=Path, default=DEFAULT_BLIND_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--target-pair-count", type=int, default=24)
    parser.add_argument(
        "--sample-nos",
        help="Comma-separated sample numbers to generate, e.g. 1,2,3. Defaults to all analysis rows.",
    )
    args = parser.parse_args()
    sample_nos = (
        [int(item.strip()) for item in args.sample_nos.split(",") if item.strip()]
        if args.sample_nos
        else None
    )

    paths = asyncio.run(
        run_pairwise_rerun_generation(
            analysis_path=args.analysis_path,
            blind_path=args.blind_path,
            output_root=args.output_root,
            settings=Settings(),
            target_pair_count=args.target_pair_count,
            sample_nos=sample_nos,
        )
    )
    for key, path in paths.items():
        print(f"{key}={path}")


if __name__ == "__main__":
    main()
