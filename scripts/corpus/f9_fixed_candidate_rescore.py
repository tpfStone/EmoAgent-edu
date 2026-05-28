import argparse
import asyncio
import csv
import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.schemas.critic import CandidateInput, CandidateScore, CriticEvaluateRequest
from app.schemas.safety import ConversationMessage
from app.services.critic_service import CriticService
from app.services.llm_client import DeepSeekLLMClient, MockLLMClient


USER_TEXT_COLUMNS = ("用户倾诉", "user_message", "user_text")
CANDIDATE_TEXT_COLUMNS = ("候选文本", "candidate_text")

RUN_COLUMNS = [
    "sample_no",
    "scenario",
    "candidate_id",
    "orientation",
    "original_F4_ER",
    "original_F4_IP",
    "original_F4_EX",
    "repeat_no",
    "rescore_F4_ER",
    "rescore_F4_IP",
    "rescore_F4_EX",
    "rescore_boundary_flag",
    "rescore_boundary_reason",
    "rescore_weighted_total",
    "changed_ER",
    "changed_IP",
    "changed_EX",
    "er_12_flip",
    "ip_12_flip",
    "ex_12_flip",
    "rationale",
    "user_text",
    "candidate_text",
]

SUMMARY_COLUMNS = [
    "sample_no",
    "scenario",
    "candidate_id",
    "orientation",
    "original_F4_ER",
    "original_F4_IP",
    "original_F4_EX",
    "rescore_ER_values",
    "rescore_IP_values",
    "rescore_EX_values",
    "changed_ER_count",
    "changed_IP_count",
    "changed_EX_count",
    "er_unstable",
    "ip_unstable",
    "ex_unstable",
    "er_12_flip",
    "ip_12_flip",
    "ex_12_flip",
    "user_text",
    "candidate_text",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _first_value(row: dict[str, str], columns: tuple[str, ...]) -> str:
    for column in columns:
        value = row.get(column, "")
        if value:
            return value
    return ""


def _bool_text(value: bool) -> str:
    return str(bool(value)).lower()


def _is_12_flip(first: str, second: str) -> bool:
    return {str(first).strip(), str(second).strip()} == {"1", "2"}


def _has_12_flip(values: list[str]) -> bool:
    stripped = {str(value).strip() for value in values}
    return "1" in stripped and "2" in stripped


def select_source_rows(
    source_rows: list[dict[str, str]], bucket: str | None = None
) -> list[dict[str, str]]:
    if not bucket:
        return source_rows
    return [
        row
        for row in source_rows
        if str(row.get("review_bucket", "")).strip() == bucket
    ]


def build_run_row(
    source_row: dict[str, str],
    *,
    repeat_no: int,
    score: CandidateScore,
) -> dict[str, str]:
    original_er = str(source_row.get("F4_ER", "")).strip()
    original_ip = str(source_row.get("F4_IP", "")).strip()
    original_ex = str(source_row.get("F4_EX", "")).strip()
    rescore_er = str(score.epitome.ER)
    rescore_ip = str(score.epitome.IP)
    rescore_ex = str(score.epitome.EX)
    return {
        "sample_no": str(source_row.get("sample_no", "")).strip(),
        "scenario": source_row.get("scenario", ""),
        "candidate_id": source_row.get("candidate_id", score.candidate_id),
        "orientation": source_row.get("orientation", ""),
        "original_F4_ER": original_er,
        "original_F4_IP": original_ip,
        "original_F4_EX": original_ex,
        "repeat_no": str(repeat_no),
        "rescore_F4_ER": rescore_er,
        "rescore_F4_IP": rescore_ip,
        "rescore_F4_EX": rescore_ex,
        "rescore_boundary_flag": _bool_text(score.boundary_flag),
        "rescore_boundary_reason": score.boundary_reason,
        "rescore_weighted_total": f"{score.weighted_total:.3f}",
        "changed_ER": _bool_text(original_er != rescore_er),
        "changed_IP": _bool_text(original_ip != rescore_ip),
        "changed_EX": _bool_text(original_ex != rescore_ex),
        "er_12_flip": _bool_text(_is_12_flip(original_er, rescore_er)),
        "ip_12_flip": _bool_text(_is_12_flip(original_ip, rescore_ip)),
        "ex_12_flip": _bool_text(_is_12_flip(original_ex, rescore_ex)),
        "rationale": score.rationale,
        "user_text": _first_value(source_row, USER_TEXT_COLUMNS),
        "candidate_text": _first_value(source_row, CANDIDATE_TEXT_COLUMNS),
    }


def summarize_rescore_rows(run_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: OrderedDict[tuple[str, str], list[dict[str, str]]] = OrderedDict()
    for row in run_rows:
        key = (row["sample_no"], row["candidate_id"])
        grouped.setdefault(key, []).append(row)

    summary_rows: list[dict[str, str]] = []
    for rows in grouped.values():
        first = rows[0]
        er_values = [row["rescore_F4_ER"] for row in rows]
        ip_values = [row["rescore_F4_IP"] for row in rows]
        ex_values = [row["rescore_F4_EX"] for row in rows]
        er_all = [first["original_F4_ER"], *er_values]
        ip_all = [first["original_F4_IP"], *ip_values]
        ex_all = [first["original_F4_EX"], *ex_values]
        summary_rows.append(
            {
                "sample_no": first["sample_no"],
                "scenario": first["scenario"],
                "candidate_id": first["candidate_id"],
                "orientation": first["orientation"],
                "original_F4_ER": first["original_F4_ER"],
                "original_F4_IP": first["original_F4_IP"],
                "original_F4_EX": first["original_F4_EX"],
                "rescore_ER_values": ";".join(er_values),
                "rescore_IP_values": ";".join(ip_values),
                "rescore_EX_values": ";".join(ex_values),
                "changed_ER_count": str(
                    sum(1 for row in rows if row["changed_ER"] == "true")
                ),
                "changed_IP_count": str(
                    sum(1 for row in rows if row["changed_IP"] == "true")
                ),
                "changed_EX_count": str(
                    sum(1 for row in rows if row["changed_EX"] == "true")
                ),
                "er_unstable": _bool_text(len(set(er_values)) > 1),
                "ip_unstable": _bool_text(len(set(ip_values)) > 1),
                "ex_unstable": _bool_text(len(set(ex_values)) > 1),
                "er_12_flip": _bool_text(_has_12_flip(er_all)),
                "ip_12_flip": _bool_text(_has_12_flip(ip_all)),
                "ex_12_flip": _bool_text(_has_12_flip(ex_all)),
                "user_text": first["user_text"],
                "candidate_text": first["candidate_text"],
            }
        )
    return summary_rows


def write_rescore_outputs(
    output_dir: Path,
    run_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
) -> tuple[Path, Path]:
    run_path = output_dir / "f9_fixed_candidate_rescore_runs.csv"
    summary_path = output_dir / "f9_fixed_candidate_rescore_summary.csv"
    _write_csv(run_path, RUN_COLUMNS, run_rows)
    _write_csv(summary_path, SUMMARY_COLUMNS, summary_rows)
    return run_path, summary_path


def _load_history_by_sample(blind_path: Path) -> dict[str, list[ConversationMessage]]:
    if not blind_path.exists():
        return {}
    history_by_sample: dict[str, list[ConversationMessage]] = {}
    for row in _read_csv(blind_path):
        raw_history = (row.get("对话历史") or "").strip()
        if not raw_history:
            history_by_sample[str(row.get("sample_no", "")).strip()] = []
            continue
        data = json.loads(raw_history)
        history_by_sample[str(row.get("sample_no", "")).strip()] = [
            ConversationMessage(**item) for item in data
        ]
    return history_by_sample


def _make_llm_client(settings: Settings):
    if settings.LLM_PROVIDER.lower() == "deepseek":
        return DeepSeekLLMClient(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.CRITIC_DEEPSEEK_MODEL or settings.DEEPSEEK_MODEL,
            thinking_type=settings.CRITIC_DEEPSEEK_THINKING,
        )
    return MockLLMClient()


async def _score_fixed_candidate(
    critic: CriticService,
    source_row: dict[str, str],
    history_by_sample: dict[str, list[ConversationMessage]],
    repeat_no: int,
) -> CandidateScore:
    sample_no = str(source_row.get("sample_no", "")).strip()
    candidate = CandidateInput(
        candidate_id=source_row.get("candidate_id", "fixed"),
        orientation=source_row.get("orientation", "fixed"),
        text=_first_value(source_row, CANDIDATE_TEXT_COLUMNS),
    )
    response = await critic.evaluate(
        CriticEvaluateRequest(
            session_id=f"f9-fixed-rescore-{sample_no}-r{repeat_no}",
            user_message=_first_value(source_row, USER_TEXT_COLUMNS),
            history=history_by_sample.get(sample_no, []),
            activated_casel=[],
            candidates=[candidate],
        )
    )
    return response.scores[0]


async def run_fixed_rescore(
    input_scores_path: Path,
    output_dir: Path,
    settings: Settings,
    repeats: int,
    blind_path: Path,
    bucket: str | None = None,
) -> tuple[Path, Path]:
    all_source_rows = _read_csv(input_scores_path)
    source_rows = select_source_rows(all_source_rows, bucket=bucket)
    history_by_sample = _load_history_by_sample(blind_path)
    critic = CriticService(_make_llm_client(settings), None, settings)

    run_rows: list[dict[str, str]] = []
    for repeat_no in range(1, repeats + 1):
        for source_row in source_rows:
            score = await _score_fixed_candidate(
                critic, source_row, history_by_sample, repeat_no
            )
            run_rows.append(
                build_run_row(source_row, repeat_no=repeat_no, score=score)
            )

    summary_rows = summarize_rescore_rows(run_rows)
    run_path, summary_path = write_rescore_outputs(output_dir, run_rows, summary_rows)
    (output_dir / "f9_fixed_candidate_rescore_manifest.json").write_text(
        json.dumps(
            {
                "input_scores_path": str(input_scores_path),
                "blind_path": str(blind_path),
                "bucket": bucket or "",
                "llm_provider": settings.LLM_PROVIDER,
                "deepseek_model": settings.CRITIC_DEEPSEEK_MODEL
                or settings.DEEPSEEK_MODEL,
                "critic_sample_count": settings.CRITIC_SAMPLE_COUNT,
                "repeats": repeats,
                "input_rows": len(all_source_rows),
                "scored_rows": len(source_rows),
                "run_rows": len(run_rows),
                "summary_rows": len(summary_rows),
                "run_path": str(run_path),
                "summary_path": str(summary_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescore a fixed F9 candidate package to isolate F4 judge variance."
    )
    parser.add_argument("--input-scores", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--critic-sample-count", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--bucket",
        default=None,
        help="Optional review_bucket value to rescore, for example priority.",
    )
    parser.add_argument(
        "--deepseek-model",
        default=None,
        help="Override the DeepSeek model for this rescore run without editing .env.",
    )
    parser.add_argument(
        "--blind-path",
        type=Path,
        default=Path("docs/corpus/f9/baseline/f9_blind_annotation.csv"),
    )
    args = parser.parse_args()

    settings_kwargs = {"CRITIC_SAMPLE_COUNT": args.critic_sample_count}
    if args.deepseek_model:
        settings_kwargs["CRITIC_DEEPSEEK_MODEL"] = args.deepseek_model
    settings = Settings(**settings_kwargs)
    run_path, summary_path = asyncio.run(
        run_fixed_rescore(
            input_scores_path=args.input_scores,
            output_dir=args.output_dir,
            settings=settings,
            repeats=args.repeats,
            blind_path=args.blind_path,
            bucket=args.bucket,
        )
    )
    print(f"run_path={run_path}")
    print(f"summary_path={summary_path}")


if __name__ == "__main__":
    main()
