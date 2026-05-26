import argparse
import csv
from pathlib import Path


COMPARISON_COLUMNS = [
    "sample_no",
    "candidate_id",
    "priority_rank",
    "human_er_should_be_2",
    "human_ip_should_be_2",
    "human_issue_type",
    "human_notes",
    "baseline_model",
    "baseline_valid",
    "baseline_failure_reason",
    "baseline_ER",
    "baseline_IP",
    "baseline_er_match",
    "baseline_ip_match",
    "baseline_total_matches",
    "candidate_model",
    "candidate_valid",
    "candidate_failure_reason",
    "candidate_ER",
    "candidate_IP",
    "candidate_er_match",
    "candidate_ip_match",
    "candidate_total_matches",
    "preferred_model",
    "user_text",
    "candidate_text",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARISON_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _key(row: dict[str, str]) -> tuple[str, str]:
    return (
        str(row.get("sample_no", "")).strip(),
        str(row.get("candidate_id", "")).strip(),
    )


def _score_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {_key(row): row for row in rows if any(_key(row))}


def _failure_index(rows: list[dict[str, str]] | None) -> dict[tuple[str, str], str]:
    failures: dict[tuple[str, str], str] = {}
    for row in rows or []:
        reason = str(row.get("rescore_boundary_reason", "")).strip()
        if reason.startswith("llm_"):
            failures.setdefault(_key(row), reason)
    return failures


def _median_score(raw_values: str) -> str:
    values: list[int] = []
    for value in str(raw_values).split(";"):
        value = value.strip()
        if not value:
            continue
        try:
            values.append(int(value))
        except ValueError:
            continue
    if not values:
        return ""
    values.sort()
    return str(values[len(values) // 2])


def _match_score(score: str, human_should_be_2: str) -> bool:
    normalized = str(human_should_be_2).strip().lower()
    if normalized == "yes":
        return score == "2"
    if normalized == "no":
        return score in {"0", "1"}
    return False


def _bool_text(value: bool) -> str:
    return str(bool(value)).lower()


def _preferred_model(
    baseline_total: int, candidate_total: int, baseline_model: str, candidate_model: str
) -> str:
    if candidate_total > baseline_total:
        return "candidate"
    if baseline_total > candidate_total:
        return "baseline"
    return "tie"


def build_model_comparison(
    human_rows: list[dict[str, str]],
    *,
    baseline_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    baseline_run_rows: list[dict[str, str]] | None = None,
    candidate_run_rows: list[dict[str, str]] | None = None,
    baseline_model: str,
    candidate_model: str,
) -> tuple[list[dict[str, str]], dict[str, int | str]]:
    baseline_by_key = _score_index(baseline_rows)
    candidate_by_key = _score_index(candidate_rows)
    baseline_failures = _failure_index(baseline_run_rows)
    candidate_failures = _failure_index(candidate_run_rows)
    comparison_rows: list[dict[str, str]] = []
    summary = {
        "baseline_model": baseline_model,
        "candidate_model": candidate_model,
        "review_rows": 0,
        "baseline_total_matches": 0,
        "candidate_total_matches": 0,
        "baseline_invalid_rows": 0,
        "candidate_invalid_rows": 0,
        "baseline_better_rows": 0,
        "candidate_better_rows": 0,
        "tie_rows": 0,
    }

    for human_row in human_rows:
        if str(human_row.get("review_bucket", "")).strip() != "priority":
            continue
        key = _key(human_row)
        baseline_row = baseline_by_key.get(key, {})
        candidate_row = candidate_by_key.get(key, {})
        baseline_failure = baseline_failures.get(key, "")
        candidate_failure = candidate_failures.get(key, "")
        baseline_valid = not baseline_failure
        candidate_valid = not candidate_failure
        baseline_er = _median_score(baseline_row.get("rescore_ER_values", ""))
        baseline_ip = _median_score(baseline_row.get("rescore_IP_values", ""))
        candidate_er = _median_score(candidate_row.get("rescore_ER_values", ""))
        candidate_ip = _median_score(candidate_row.get("rescore_IP_values", ""))

        baseline_er_match = baseline_valid and _match_score(
            baseline_er, human_row.get("human_er_should_be_2", "")
        )
        baseline_ip_match = baseline_valid and _match_score(
            baseline_ip, human_row.get("human_ip_should_be_2", "")
        )
        candidate_er_match = candidate_valid and _match_score(
            candidate_er, human_row.get("human_er_should_be_2", "")
        )
        candidate_ip_match = candidate_valid and _match_score(
            candidate_ip, human_row.get("human_ip_should_be_2", "")
        )
        baseline_total = int(baseline_er_match) + int(baseline_ip_match)
        candidate_total = int(candidate_er_match) + int(candidate_ip_match)
        preferred = _preferred_model(
            baseline_total, candidate_total, baseline_model, candidate_model
        )

        summary["review_rows"] += 1
        summary["baseline_total_matches"] += baseline_total
        summary["candidate_total_matches"] += candidate_total
        if not baseline_valid:
            summary["baseline_invalid_rows"] += 1
        if not candidate_valid:
            summary["candidate_invalid_rows"] += 1
        if preferred == "candidate":
            summary["candidate_better_rows"] += 1
        elif preferred == "baseline":
            summary["baseline_better_rows"] += 1
        else:
            summary["tie_rows"] += 1

        comparison_rows.append(
            {
                "sample_no": key[0],
                "candidate_id": key[1],
                "priority_rank": human_row.get("priority_rank", ""),
                "human_er_should_be_2": human_row.get("human_er_should_be_2", ""),
                "human_ip_should_be_2": human_row.get("human_ip_should_be_2", ""),
                "human_issue_type": human_row.get("human_issue_type", ""),
                "human_notes": human_row.get("human_notes", ""),
                "baseline_model": baseline_model,
                "baseline_valid": _bool_text(baseline_valid),
                "baseline_failure_reason": baseline_failure,
                "baseline_ER": baseline_er,
                "baseline_IP": baseline_ip,
                "baseline_er_match": _bool_text(baseline_er_match),
                "baseline_ip_match": _bool_text(baseline_ip_match),
                "baseline_total_matches": str(baseline_total),
                "candidate_model": candidate_model,
                "candidate_valid": _bool_text(candidate_valid),
                "candidate_failure_reason": candidate_failure,
                "candidate_ER": candidate_er,
                "candidate_IP": candidate_ip,
                "candidate_er_match": _bool_text(candidate_er_match),
                "candidate_ip_match": _bool_text(candidate_ip_match),
                "candidate_total_matches": str(candidate_total),
                "preferred_model": preferred,
                "user_text": human_row.get("user_text", ""),
                "candidate_text": human_row.get("candidate_text", ""),
            }
        )
    return comparison_rows, summary


def _summary_markdown(summary: dict[str, int | str]) -> str:
    lines = [
        "# F9 Priority Model Comparison Summary",
        "",
        f"baseline_model: {summary['baseline_model']}",
        f"candidate_model: {summary['candidate_model']}",
        f"review_rows: {summary['review_rows']}",
        f"baseline_total_matches: {summary['baseline_total_matches']}",
        f"candidate_total_matches: {summary['candidate_total_matches']}",
        f"baseline_invalid_rows: {summary['baseline_invalid_rows']}",
        f"candidate_invalid_rows: {summary['candidate_invalid_rows']}",
        f"baseline_better_rows: {summary['baseline_better_rows']}",
        f"candidate_better_rows: {summary['candidate_better_rows']}",
        f"tie_rows: {summary['tie_rows']}",
        "",
    ]
    return "\n".join(lines)


def write_model_eval_outputs(
    output_dir: Path,
    comparison_rows: list[dict[str, str]],
    summary: dict[str, int | str],
) -> tuple[Path, Path]:
    csv_path = output_dir / "f9_priority_model_comparison.csv"
    summary_path = output_dir / "f9_priority_model_comparison_summary.md"
    _write_csv(csv_path, comparison_rows)
    summary_path.write_text(_summary_markdown(summary), encoding="utf-8")
    return csv_path, summary_path


def _sibling_runs_path(summary_path: Path) -> Path | None:
    run_path = summary_path.parent / "f9_fixed_candidate_rescore_runs.csv"
    if run_path.exists():
        return run_path
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two F4 model rescore outputs against human priority labels."
    )
    parser.add_argument("--human-queue", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline-model", default="deepseek-chat")
    parser.add_argument("--candidate-model", default="deepseek-v4-pro")
    parser.add_argument("--baseline-runs", type=Path, default=None)
    parser.add_argument("--candidate-runs", type=Path, default=None)
    args = parser.parse_args()

    baseline_runs_path = args.baseline_runs or _sibling_runs_path(args.baseline)
    candidate_runs_path = args.candidate_runs or _sibling_runs_path(args.candidate)

    comparison_rows, summary = build_model_comparison(
        _read_csv(args.human_queue),
        baseline_rows=_read_csv(args.baseline),
        candidate_rows=_read_csv(args.candidate),
        baseline_run_rows=_read_csv(baseline_runs_path) if baseline_runs_path else [],
        candidate_run_rows=_read_csv(candidate_runs_path) if candidate_runs_path else [],
        baseline_model=args.baseline_model,
        candidate_model=args.candidate_model,
    )
    csv_path, summary_path = write_model_eval_outputs(
        args.output_dir, comparison_rows, summary
    )
    print(f"comparison_path={csv_path}")
    print(f"summary_path={summary_path}")


if __name__ == "__main__":
    main()
