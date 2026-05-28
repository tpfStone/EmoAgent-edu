import argparse
import csv
import json
from pathlib import Path


EVAL_COLUMNS = [
    "pair_id",
    "sample_no",
    "human_preference",
    "pairwise_winner",
    "pairwise_match",
    "pointwise_winner",
    "pointwise_match",
    "pointwise_sample_count",
    "main_exclusion_reason",
    "selection_method",
    "pairwise_confidence",
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


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _is_true(value: str) -> bool:
    return str(value).strip().lower() == "true"


def _valid_choice(value: str) -> bool:
    return value in {"c1", "c2"}


def _is_formal_pointwise(pointwise_row: dict[str, str]) -> bool:
    return str(pointwise_row.get("pointwise_sample_count", "")).strip() == "3"


def build_eval_rows(
    pairwise_rows: list[dict[str, str]],
    human_rows: list[dict[str, str]],
    pointwise_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    pairwise_by_id = {row["pair_id"]: row for row in pairwise_rows}
    pointwise_by_id = {
        row["pair_id"]: row for row in (pointwise_rows or []) if row.get("pair_id")
    }
    eval_rows: list[dict[str, str]] = []

    for human in human_rows:
        pair_id = human["pair_id"]
        pairwise = pairwise_by_id.get(pair_id, {})
        pointwise = pointwise_by_id.get(pair_id, {})
        human_preference = human.get("human_preference", "")
        human_valid = (
            _valid_choice(human_preference)
            and not _is_true(human.get("human_tie", ""))
            and not _is_true(human.get("human_invalid", ""))
        )
        pairwise_winner = pairwise.get("winner_id", "")
        critic_valid = (
            human_valid
            and _valid_choice(pairwise_winner)
            and _is_true(pairwise.get("pairwise_stable", ""))
            and str(pairwise.get("selection_method", "")) == "pairwise_stable"
            and str(pairwise.get("invalid_count", "0")) == "0"
        )
        pointwise_winner = pointwise.get("pointwise_winner", "")
        pointwise_sample_count = str(pointwise.get("pointwise_sample_count", ""))
        pointwise_valid = (
            human_valid
            and _valid_choice(pointwise_winner)
            and _is_formal_pointwise(pointwise)
        )

        if not human_valid:
            exclusion = "human_tie_or_invalid"
        elif not critic_valid:
            exclusion = "critic_invalid_or_unstable"
        elif not pointwise_valid:
            exclusion = "pointwise_invalid_or_nonformal"
        else:
            exclusion = ""

        eval_rows.append(
            {
                "pair_id": pair_id,
                "sample_no": human.get("sample_no") or pairwise.get("sample_no", ""),
                "human_preference": human_preference,
                "pairwise_winner": pairwise_winner,
                "pairwise_match": (
                    _bool_text(pairwise_winner == human_preference)
                    if critic_valid
                    else ""
                ),
                "pointwise_winner": pointwise_winner,
                "pointwise_match": (
                    _bool_text(pointwise_winner == human_preference)
                    if pointwise_valid
                    else ""
                ),
                "pointwise_sample_count": pointwise_sample_count,
                "main_exclusion_reason": exclusion,
                "selection_method": pairwise.get("selection_method", ""),
                "pairwise_confidence": pairwise.get("pairwise_confidence", ""),
            }
        )
    return eval_rows


def _ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.000"
    return f"{numerator / denominator:.3f}"


def summarize_eval_rows(eval_rows: list[dict[str, str]]) -> dict[str, int | str]:
    total_pairs = len(eval_rows)
    human_valid_rows = [
        row for row in eval_rows if row["human_preference"] in {"c1", "c2"}
    ]
    pairwise_valid_rows_all = [
        row for row in human_valid_rows if row["pairwise_match"] in {"true", "false"}
    ]
    pointwise_valid_rows_all = [
        row for row in human_valid_rows if _valid_choice(row.get("pointwise_winner", ""))
    ]
    comparison_rows = [
        row
        for row in pairwise_valid_rows_all
        if row["pointwise_match"] in {"true", "false"}
    ]
    pairwise_matches = sum(1 for row in comparison_rows if row["pairwise_match"] == "true")
    pointwise_matches = sum(
        1 for row in comparison_rows if row["pointwise_match"] == "true"
    )
    critic_agreement = (
        pairwise_matches / len(comparison_rows) if comparison_rows else 0.0
    )
    pointwise_agreement = (
        pointwise_matches / len(comparison_rows) if comparison_rows else 0.0
    )
    human_ties = sum(1 for row in eval_rows if row["human_preference"] == "tie")
    attrition_pairwise = sum(
        1 for row in human_valid_rows if row["pairwise_match"] not in {"true", "false"}
    )
    attrition_pointwise = sum(
        1
        for row in pairwise_valid_rows_all
        if row["pointwise_match"] not in {"true", "false"}
    )

    return {
        "total_pairs": total_pairs,
        "human_valid_pairs": len(human_valid_rows),
        "critic_valid_pairs": len(comparison_rows),
        "pairwise_matches": pairwise_matches,
        "critic_human_agreement": _ratio(pairwise_matches, len(comparison_rows)),
        "pointwise_valid_pairs": len(comparison_rows),
        "pointwise_matches": pointwise_matches,
        "pointwise_human_agreement": _ratio(
            pointwise_matches, len(comparison_rows)
        ),
        "agreement_delta_vs_pointwise": (
            f"{critic_agreement - pointwise_agreement:.3f}"
            if comparison_rows
            else "unavailable"
        ),
        "comparison_intersection_pairs": len(comparison_rows),
        "pairwise_valid_pairs_all": len(pairwise_valid_rows_all),
        "pointwise_valid_pairs_all": len(pointwise_valid_rows_all),
        "attrition_human_tie_or_invalid": total_pairs - len(human_valid_rows),
        "attrition_pairwise_unstable_or_invalid": attrition_pairwise,
        "attrition_pointwise_invalid_or_nonformal": attrition_pointwise,
        "human_tie_rate": _ratio(human_ties, total_pairs),
    }


def build_markdown_report(summary: dict[str, int | str]) -> str:
    lines = ["# F9 Pairwise Pilot Evaluation", ""]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## 样本流失分解",
            "",
            f"- total_pairs: {summary.get('total_pairs', 0)}",
            f"- human_valid_pairs: {summary.get('human_valid_pairs', 0)}",
            f"- pairwise_valid_pairs_all: {summary.get('pairwise_valid_pairs_all', 0)}",
            f"- comparison_intersection_pairs: {summary.get('comparison_intersection_pairs', 0)}",
            f"- attrition_human_tie_or_invalid: {summary.get('attrition_human_tie_or_invalid', 0)}",
            f"- attrition_pairwise_unstable_or_invalid: {summary.get('attrition_pairwise_unstable_or_invalid', 0)}",
            f"- attrition_pointwise_invalid_or_nonformal: {summary.get('attrition_pointwise_invalid_or_nonformal', 0)}",
            "",
            "本轮 agreement 数字只在三方交集上解释；当 pointwise baseline 不是 3-sample formal 口径时，delta 记为 unavailable。",
        ]
    )
    lines.append("")
    return "\n".join(lines)


def write_eval_outputs(
    output_dir: Path,
    eval_rows: list[dict[str, str]],
    summary: dict[str, int | str],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    eval_path = output_dir / "f9_pairwise_eval.csv"
    summary_path = output_dir / "f9_pairwise_eval_summary.json"
    report_path = output_dir / "f9_pairwise_eval_report.md"
    _write_csv(eval_path, EVAL_COLUMNS, eval_rows)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(build_markdown_report(summary), encoding="utf-8")
    return {"eval": eval_path, "summary": summary_path, "report": report_path}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate F9 pairwise judge output against human A/B annotations."
    )
    parser.add_argument("--pairwise-summary", type=Path, required=True)
    parser.add_argument("--human-annotations", type=Path, required=True)
    parser.add_argument("--pointwise-baseline", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    eval_rows = build_eval_rows(
        pairwise_rows=_read_csv(args.pairwise_summary),
        human_rows=_read_csv(args.human_annotations),
        pointwise_rows=(
            _read_csv(args.pointwise_baseline) if args.pointwise_baseline else []
        ),
    )
    summary = summarize_eval_rows(eval_rows)
    write_eval_outputs(args.output_dir, eval_rows, summary)


if __name__ == "__main__":
    main()
