from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


HUMAN_SCORE_COLUMNS = ["A_ER", "A_IP", "A_EX", "B_ER", "B_IP", "B_EX"]
F4_SCORE_COLUMNS = ["F4_ER", "F4_IP", "F4_EX"]
DIMENSIONS = ["ER", "IP", "EX"]
LABELS = [0, 1, 2]

MERGED_COLUMNS = [
    "sample_no",
    "scenario",
    "orientation",
    "用户倾诉",
    "对话历史",
    "候选文本",
    "A_ER",
    "A_IP",
    "A_EX",
    "B_ER",
    "B_IP",
    "B_EX",
    "consensus_ER",
    "consensus_IP",
    "consensus_EX",
    "F4_ER",
    "F4_IP",
    "F4_EX",
]

RELIABILITY_COLUMNS = [
    "dimension",
    "n",
    "human_human_weighted_kappa",
    "human_f4_weighted_kappa",
    "pass_threshold",
    "passes_threshold",
    "A_distribution",
    "B_distribution",
    "consensus_distribution",
    "F4_distribution",
]


@dataclass(frozen=True)
class F9ReliabilityResult:
    output_dir: Path
    merged_annotations_path: Path
    reliability_summary_path: Path
    report_path: Path
    sample_count: int


def _read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        return [
            {
                key: value
                for key, value in row.items()
                if key is not None and key.strip() != ""
            }
            for row in reader
        ]


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _parse_score(row: dict[str, str], column: str) -> int:
    sample_no = row.get("sample_no", "")
    value = str(row.get(column, "")).strip()
    if value == "":
        raise ValueError(f"{column} is blank for sample_no {sample_no}")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(
            f"{column} must be one of 0, 1, 2 for sample_no {sample_no}: {value}"
        ) from exc
    if parsed not in LABELS:
        raise ValueError(
            f"{column} must be one of 0, 1, 2 for sample_no {sample_no}: {value}"
        )
    return parsed


def _validate_unique_sample_numbers(rows: Iterable[dict[str, str]], source: str) -> None:
    seen: set[str] = set()
    for row in rows:
        sample_no = str(row.get("sample_no", "")).strip()
        if sample_no == "":
            raise ValueError(f"{source} contains a blank sample_no")
        if sample_no in seen:
            raise ValueError(f"{source} contains duplicate sample_no {sample_no}")
        seen.add(sample_no)


def consensus_score(a_score: int, b_score: int) -> int:
    return int(math.floor(((a_score + b_score) / 2) + 0.5))


def quadratic_weighted_kappa(y1: list[int], y2: list[int]) -> float | None:
    if len(y1) != len(y2):
        raise ValueError("kappa inputs must have the same length")
    if not y1:
        raise ValueError("kappa inputs must not be empty")

    label_index = {label: index for index, label in enumerate(LABELS)}
    observed = [[0.0 for _ in LABELS] for _ in LABELS]
    hist1 = [0.0 for _ in LABELS]
    hist2 = [0.0 for _ in LABELS]
    for left, right in zip(y1, y2, strict=True):
        if left not in label_index or right not in label_index:
            raise ValueError("kappa scores must be 0, 1, or 2")
        i = label_index[left]
        j = label_index[right]
        observed[i][j] += 1.0
        hist1[i] += 1.0
        hist2[j] += 1.0

    max_distance = len(LABELS) - 1
    observed_disagreement = 0.0
    expected_disagreement = 0.0
    sample_count = float(len(y1))
    for i in range(len(LABELS)):
        for j in range(len(LABELS)):
            weight = ((i - j) / max_distance) ** 2
            observed_disagreement += weight * observed[i][j] / sample_count
            expected_disagreement += (
                weight * (hist1[i] * hist2[j] / sample_count) / sample_count
            )

    if expected_disagreement == 0:
        return None
    return 1.0 - (observed_disagreement / expected_disagreement)


def _format_kappa(value: float | None) -> str:
    return "not_applicable" if value is None else f"{value:.3f}"


def _distribution(values: list[int]) -> str:
    counts = Counter(values)
    return json.dumps(
        {str(label): counts.get(label, 0) for label in LABELS},
        ensure_ascii=False,
        sort_keys=True,
    )


def _passes_threshold(dimension: str, human_f4_kappa: float | None) -> str:
    if human_f4_kappa is None:
        return "no"
    threshold = 0.6 if dimension == "EX" else 0.4
    return "yes" if human_f4_kappa >= threshold else "no"


def _threshold_label(dimension: str) -> str:
    return "0.600" if dimension == "EX" else "0.400"


def _build_merged_rows(
    blind_rows: list[dict[str, str]], holdout_rows: list[dict[str, str]]
) -> list[dict[str, object]]:
    _validate_unique_sample_numbers(blind_rows, "blind annotations")
    _validate_unique_sample_numbers(holdout_rows, "F4 holdout")
    holdout_by_sample = {
        str(row["sample_no"]).strip(): row for row in holdout_rows
    }
    missing_holdout = [
        str(row["sample_no"]).strip()
        for row in blind_rows
        if str(row["sample_no"]).strip() not in holdout_by_sample
    ]
    if missing_holdout:
        raise ValueError(
            "missing F4 holdout rows for sample_no "
            + ", ".join(sorted(missing_holdout, key=int))
        )

    merged_rows: list[dict[str, object]] = []
    for row in sorted(blind_rows, key=lambda item: int(item["sample_no"])):
        sample_no = str(row["sample_no"]).strip()
        holdout = holdout_by_sample[sample_no]
        parsed = {
            column: _parse_score(row, column) for column in HUMAN_SCORE_COLUMNS
        }
        parsed.update(
            {column: _parse_score(holdout, column) for column in F4_SCORE_COLUMNS}
        )
        consensus = {
            f"consensus_{dim}": consensus_score(parsed[f"A_{dim}"], parsed[f"B_{dim}"])
            for dim in DIMENSIONS
        }
        merged_rows.append(
            {
                "sample_no": int(sample_no),
                "scenario": row.get("scenario", ""),
                "orientation": row.get("orientation", ""),
                "用户倾诉": row.get("用户倾诉", ""),
                "对话历史": row.get("对话历史", ""),
                "候选文本": row.get("候选文本", ""),
                **parsed,
                **consensus,
            }
        )
    return merged_rows


def _build_summary_rows(
    merged_rows: list[dict[str, object]]
) -> list[dict[str, object]]:
    summary_rows: list[dict[str, object]] = []
    for dimension in DIMENSIONS:
        a_scores = [int(row[f"A_{dimension}"]) for row in merged_rows]
        b_scores = [int(row[f"B_{dimension}"]) for row in merged_rows]
        consensus_scores = [
            int(row[f"consensus_{dimension}"]) for row in merged_rows
        ]
        f4_scores = [int(row[f"F4_{dimension}"]) for row in merged_rows]
        human_human = quadratic_weighted_kappa(a_scores, b_scores)
        human_f4 = quadratic_weighted_kappa(consensus_scores, f4_scores)
        summary_rows.append(
            {
                "dimension": dimension,
                "n": len(merged_rows),
                "human_human_weighted_kappa": _format_kappa(human_human),
                "human_f4_weighted_kappa": _format_kappa(human_f4),
                "pass_threshold": _threshold_label(dimension),
                "passes_threshold": _passes_threshold(dimension, human_f4),
                "A_distribution": _distribution(a_scores),
                "B_distribution": _distribution(b_scores),
                "consensus_distribution": _distribution(consensus_scores),
                "F4_distribution": _distribution(f4_scores),
            }
        )
    return summary_rows


def _markdown_table(summary_rows: list[dict[str, object]]) -> list[str]:
    lines = [
        "| dimension | n | A vs B κ | consensus vs F4 κ | threshold | pass | F4 distribution |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for row in summary_rows:
        lines.append(
            "| {dimension} | {n} | {human_human_weighted_kappa} | "
            "{human_f4_weighted_kappa} | {pass_threshold} | "
            "{passes_threshold} | `{F4_distribution}` |".format(**row)
        )
    return lines


def _write_report(path: Path, summary_rows: list[dict[str, object]]) -> None:
    lines = [
        "# F9 Reliability Summary",
        "",
        "Metric: quadratically weighted Cohen's κ.",
        "",
        *_markdown_table(summary_rows),
        "",
        "Thresholds: EX >= 0.600; ER/IP >= 0.400.",
        "Human-vs-F4 uses half-up rounded A/B consensus scores.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def analyze_f9_annotations(
    blind_annotation_path: str | Path,
    f4_holdout_path: str | Path,
    output_dir: str | Path,
) -> F9ReliabilityResult:
    blind_rows = _read_csv_rows(blind_annotation_path)
    holdout_rows = _read_csv_rows(f4_holdout_path)
    merged_rows = _build_merged_rows(blind_rows, holdout_rows)
    summary_rows = _build_summary_rows(merged_rows)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    merged_annotations_path = output / "f9_annotations_merged.csv"
    reliability_summary_path = output / "f9_reliability_summary.csv"
    report_path = output / "f9_reliability_report.md"

    _write_csv(merged_annotations_path, MERGED_COLUMNS, merged_rows)
    _write_csv(reliability_summary_path, RELIABILITY_COLUMNS, summary_rows)
    _write_report(report_path, summary_rows)

    return F9ReliabilityResult(
        output_dir=output,
        merged_annotations_path=merged_annotations_path,
        reliability_summary_path=reliability_summary_path,
        report_path=report_path,
        sample_count=len(merged_rows),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge F9 annotations and compute κ.")
    parser.add_argument(
        "--blind-annotation-path",
        default="docs/corpus/f9/baseline/f9_blind_annotation.csv",
    )
    parser.add_argument(
        "--f4-holdout-path",
        default="docs/corpus/f9/baseline/f9_f4_scores_holdout.csv",
    )
    parser.add_argument("--output-dir", default="docs/corpus/f9/baseline")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = analyze_f9_annotations(
        blind_annotation_path=args.blind_annotation_path,
        f4_holdout_path=args.f4_holdout_path,
        output_dir=args.output_dir,
    )
    print(f"merged_annotations_path={result.merged_annotations_path}")
    print(f"reliability_summary_path={result.reliability_summary_path}")
    print(f"report_path={result.report_path}")
    print(f"sample_count={result.sample_count}")


if __name__ == "__main__":
    main()
