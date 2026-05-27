import argparse
import csv
from pathlib import Path


PAIR_PACKAGE_COLUMNS = [
    "pair_id",
    "sample_no",
    "scenario",
    "user_text",
    "history_json",
    "c1_orientation",
    "c1_text",
    "c2_orientation",
    "c2_text",
    "source_run",
    "notes",
]

HUMAN_ANNOTATION_COLUMNS = [
    "pair_id",
    "sample_no",
    "scenario",
    "user_text",
    "c1_text",
    "c2_text",
    "human_preference",
    "human_tie",
    "human_invalid",
    "human_boundary_winner",
    "human_issue_type",
    "human_notes",
    "annotator_id",
]

USER_TEXT_COLUMNS = ("user_text", "用户倾诉")
HISTORY_COLUMNS = ("history_json", "对话历史")
CANDIDATE_TEXT_COLUMNS = ("candidate_text", "候选文本")


def _first_value(row: dict[str, str], columns: tuple[str, ...]) -> str:
    for column in columns:
        value = row.get(column, "")
        if value:
            return value
    return ""


def build_pair_rows(source_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    order: list[str] = []
    for row in source_rows:
        sample_no = str(row.get("sample_no", "")).strip()
        candidate_id = str(row.get("candidate_id", "")).strip()
        if not sample_no or candidate_id not in {"c1", "c2"}:
            continue
        if sample_no not in grouped:
            grouped[sample_no] = {}
            order.append(sample_no)
        grouped[sample_no][candidate_id] = row

    pair_rows: list[dict[str, str]] = []
    for sample_no in order:
        candidates = grouped[sample_no]
        if "c1" not in candidates or "c2" not in candidates:
            continue
        c1 = candidates["c1"]
        c2 = candidates["c2"]
        pair_rows.append(
            {
                "pair_id": f"sample-{sample_no}",
                "sample_no": sample_no,
                "scenario": c1.get("scenario") or c2.get("scenario", ""),
                "user_text": _first_value(c1, USER_TEXT_COLUMNS)
                or _first_value(c2, USER_TEXT_COLUMNS),
                "history_json": _first_value(c1, HISTORY_COLUMNS)
                or _first_value(c2, HISTORY_COLUMNS),
                "c1_orientation": c1.get("orientation", ""),
                "c1_text": _first_value(c1, CANDIDATE_TEXT_COLUMNS),
                "c2_orientation": c2.get("orientation", ""),
                "c2_text": _first_value(c2, CANDIDATE_TEXT_COLUMNS),
                "source_run": c1.get("source")
                or c2.get("source")
                or c1.get("review_bucket")
                or c2.get("review_bucket", ""),
                "notes": "",
            }
        )
    return pair_rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_pair_package(output_path: Path, pair_rows: list[dict[str, str]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAIR_PACKAGE_COLUMNS)
        writer.writeheader()
        writer.writerows(pair_rows)
    return output_path


def build_annotation_rows(pair_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "pair_id": row["pair_id"],
            "sample_no": row["sample_no"],
            "scenario": row["scenario"],
            "user_text": row["user_text"],
            "c1_text": row["c1_text"],
            "c2_text": row["c2_text"],
            "human_preference": "",
            "human_tie": "",
            "human_invalid": "",
            "human_boundary_winner": "",
            "human_issue_type": "",
            "human_notes": "",
            "annotator_id": "",
        }
        for row in pair_rows
    ]


def write_annotation_template(
    output_path: Path, annotation_rows: list[dict[str, str]]
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HUMAN_ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerows(annotation_rows)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a frozen F9 pairwise candidate package from candidate rows."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotation-output", type=Path)
    args = parser.parse_args()

    pair_rows = build_pair_rows(read_csv(args.input))
    write_pair_package(args.output, pair_rows)
    if args.annotation_output is not None:
        write_annotation_template(args.annotation_output, build_annotation_rows(pair_rows))


if __name__ == "__main__":
    main()
