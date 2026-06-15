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
    "generator_run_id",
    "generated_at",
    "generator_model",
    "generator_thinking",
    "f3_prompt_bundle_hash",
    "notes",
]

PROVENANCE_COLUMNS = [
    "generator_run_id",
    "generated_at",
    "generator_model",
    "generator_thinking",
    "f3_prompt_bundle_hash",
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


def _provenance_value(c1: dict[str, str], c2: dict[str, str], column: str) -> str:
    c1_value = str(c1.get(column, "")).strip()
    c2_value = str(c2.get(column, "")).strip()
    if c1_value and c2_value and c1_value != c2_value:
        raise ValueError(
            f"sample {c1.get('sample_no') or c2.get('sample_no')} has mismatched {column}"
        )
    return c1_value or c2_value


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
                "generator_run_id": _provenance_value(c1, c2, "generator_run_id"),
                "generated_at": _provenance_value(c1, c2, "generated_at"),
                "generator_model": _provenance_value(c1, c2, "generator_model"),
                "generator_thinking": _provenance_value(c1, c2, "generator_thinking"),
                "f3_prompt_bundle_hash": _provenance_value(
                    c1, c2, "f3_prompt_bundle_hash"
                ),
                "notes": "",
            }
        )
    return pair_rows


def validate_pair_provenance(
    pair_rows: list[dict[str, str]],
    expected_f3_prompt_bundle_hash: str | None = None,
) -> None:
    for row in pair_rows:
        missing = [column for column in PROVENANCE_COLUMNS if not row.get(column, "")]
        if missing:
            raise ValueError(
                f"pair {row.get('pair_id', '')} missing provenance: {', '.join(missing)}"
            )
        if (
            expected_f3_prompt_bundle_hash
            and row.get("f3_prompt_bundle_hash") != expected_f3_prompt_bundle_hash
        ):
            raise ValueError(
                f"pair {row.get('pair_id', '')} f3_prompt_bundle_hash "
                f"{row.get('f3_prompt_bundle_hash', '')!r} does not match "
                f"{expected_f3_prompt_bundle_hash!r}"
            )


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
    parser.add_argument("--require-provenance", action="store_true")
    parser.add_argument("--expected-f3-prompt-bundle-hash")
    args = parser.parse_args()

    pair_rows = build_pair_rows(read_csv(args.input))
    if args.require_provenance or args.expected_f3_prompt_bundle_hash:
        validate_pair_provenance(pair_rows, args.expected_f3_prompt_bundle_hash)
    write_pair_package(args.output, pair_rows)
    if args.annotation_output is not None:
        write_annotation_template(args.annotation_output, build_annotation_rows(pair_rows))


if __name__ == "__main__":
    main()
