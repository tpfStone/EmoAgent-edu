import argparse
import csv
from pathlib import Path


OUTPUT_COLUMNS = [
    "sample_no",
    "scenario",
    "student_text",
    "main_candidate_id",
    "main_orientation",
    "main_F4_ER",
    "main_F4_IP",
    "main_F4_EX",
    "stability_candidate_id",
    "stability_orientation",
    "stability_F4_ER",
    "stability_F4_IP",
    "stability_F4_EX",
    "stability_rationale",
    "stability_candidate_text",
    "human_er_should_be_2",
    "human_ip_should_be_2",
    "human_issue_type",
    "human_notes",
]

USER_TEXT_COLUMNS = ("用户倾诉", "ç”¨æˆ·å€¾è¯‰", "user_message")
CANDIDATE_TEXT_COLUMNS = ("候选文本", "å€™é€‰æ–‡æœ¬", "candidate_text")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _is_er_ip_two(row: dict[str, str]) -> bool:
    return str(row.get("F4_ER", "")).strip() == "2" and str(
        row.get("F4_IP", "")
    ).strip() == "2"


def _by_sample_no(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(row.get("sample_no", "")).strip(): row for row in rows}


def _first_value(row: dict[str, str], columns: tuple[str, ...]) -> str:
    for column in columns:
        value = row.get(column, "")
        if value:
            return value
    return ""


def high_score_diff_rows(
    main_rows: list[dict[str, str]], stability_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    main_by_sample = _by_sample_no(main_rows)
    review_rows: list[dict[str, str]] = []

    for stability_row in stability_rows:
        sample_no = str(stability_row.get("sample_no", "")).strip()
        if not sample_no or not _is_er_ip_two(stability_row):
            continue

        main_row = main_by_sample.get(sample_no, {})
        if _is_er_ip_two(main_row):
            continue

        review_rows.append(
            {
                "sample_no": sample_no,
                "scenario": stability_row.get("scenario", main_row.get("scenario", "")),
                "student_text": _first_value(stability_row, USER_TEXT_COLUMNS)
                or _first_value(main_row, USER_TEXT_COLUMNS),
                "main_candidate_id": main_row.get("candidate_id", ""),
                "main_orientation": main_row.get("orientation", ""),
                "main_F4_ER": main_row.get("F4_ER", ""),
                "main_F4_IP": main_row.get("F4_IP", ""),
                "main_F4_EX": main_row.get("F4_EX", ""),
                "stability_candidate_id": stability_row.get("candidate_id", ""),
                "stability_orientation": stability_row.get("orientation", ""),
                "stability_F4_ER": stability_row.get("F4_ER", ""),
                "stability_F4_IP": stability_row.get("F4_IP", ""),
                "stability_F4_EX": stability_row.get("F4_EX", ""),
                "stability_rationale": stability_row.get("rationale", ""),
                "stability_candidate_text": _first_value(
                    stability_row, CANDIDATE_TEXT_COLUMNS
                ),
                "human_er_should_be_2": "",
                "human_ip_should_be_2": "",
                "human_issue_type": "",
                "human_notes": "",
            }
        )

    return sorted(review_rows, key=lambda row: int(row["sample_no"]))


def write_review_queue(main_path: Path, stability_path: Path, output_path: Path) -> None:
    main_rows = _read_csv(main_path)
    stability_rows = _read_csv(stability_path)
    _write_csv(output_path, high_score_diff_rows(main_rows, stability_rows))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a human-only F9 high-score stability diff review queue."
    )
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--stability", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    write_review_queue(args.main, args.stability, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
