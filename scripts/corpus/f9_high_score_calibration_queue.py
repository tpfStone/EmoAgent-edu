import argparse
import csv
from pathlib import Path


USER_TEXT_COLUMNS = ("用户倾诉", "user_message")
CANDIDATE_TEXT_COLUMNS = ("候选文本", "candidate_text")

OUTPUT_COLUMNS = [
    "row_type",
    "review_order",
    "sample_no",
    "score_side",
    "scenario",
    "candidate_id",
    "orientation",
    "F4_ER",
    "F4_IP",
    "F4_EX",
    "rationale",
    "user_text",
    "candidate_text",
    "human_er_should_be_2",
    "human_ip_should_be_2",
    "human_issue_type",
    "human_notes",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _first_value(row: dict[str, str], columns: tuple[str, ...]) -> str:
    for column in columns:
        value = row.get(column, "")
        if value:
            return value
    return ""


def _score_side(er: str, ip: str) -> str:
    er = str(er).strip()
    ip = str(ip).strip()
    if er == "2" and ip == "2":
        return "ER_IP_2"
    if er != "2" and ip != "2":
        return "ER_IP_not_2"
    if er != "2":
        return "ER_not_2"
    return "IP_not_2"


def _sort_key(row: dict[str, str]) -> tuple[int, str]:
    sample_no = str(row.get("sample_no", "")).strip()
    try:
        return (int(sample_no), sample_no)
    except ValueError:
        return (10**9, sample_no)


def _calibration_output_row(row: dict[str, str], review_order: int) -> dict[str, str]:
    er = row.get("stability_F4_ER", "")
    ip = row.get("stability_F4_IP", "")
    return {
        "row_type": "calibration",
        "review_order": str(review_order),
        "sample_no": str(row.get("sample_no", "")).strip(),
        "score_side": "calibration",
        "scenario": row.get("scenario", ""),
        "candidate_id": row.get("stability_candidate_id", ""),
        "orientation": row.get("stability_orientation", ""),
        "F4_ER": er,
        "F4_IP": ip,
        "F4_EX": row.get("stability_F4_EX", ""),
        "rationale": row.get("stability_rationale", ""),
        "user_text": row.get("student_text", ""),
        "candidate_text": row.get("stability_candidate_text", ""),
        "human_er_should_be_2": row.get("human_er_should_be_2", ""),
        "human_ip_should_be_2": row.get("human_ip_should_be_2", ""),
        "human_issue_type": row.get("human_issue_type", ""),
        "human_notes": row.get("human_notes", ""),
    }


def _review_output_row(row: dict[str, str], review_order: int) -> dict[str, str]:
    er = str(row.get("F4_ER", "")).strip()
    ip = str(row.get("F4_IP", "")).strip()
    return {
        "row_type": "review",
        "review_order": str(review_order),
        "sample_no": str(row.get("sample_no", "")).strip(),
        "score_side": _score_side(er, ip),
        "scenario": row.get("scenario", ""),
        "candidate_id": row.get("candidate_id", ""),
        "orientation": row.get("orientation", ""),
        "F4_ER": er,
        "F4_IP": ip,
        "F4_EX": row.get("F4_EX", ""),
        "rationale": row.get("rationale", ""),
        "user_text": _first_value(row, USER_TEXT_COLUMNS),
        "candidate_text": _first_value(row, CANDIDATE_TEXT_COLUMNS),
        "human_er_should_be_2": "",
        "human_ip_should_be_2": "",
        "human_issue_type": "",
        "human_notes": "",
    }


def build_calibration_queue(
    score_rows: list[dict[str, str]],
    calibration_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    output_rows: list[dict[str, str]] = []
    review_order = 1
    for row in sorted(calibration_rows, key=_sort_key):
        if not str(row.get("sample_no", "")).strip():
            continue
        output_rows.append(_calibration_output_row(row, review_order))
        review_order += 1

    for row in sorted(score_rows, key=_sort_key):
        if not str(row.get("sample_no", "")).strip():
            continue
        output_rows.append(_review_output_row(row, review_order))
        review_order += 1
    return output_rows


def write_calibration_queue(
    input_scores_path: Path,
    calibration_path: Path,
    output_path: Path,
) -> None:
    score_rows = _read_csv(input_scores_path)
    calibration_rows = _read_csv(calibration_path) if calibration_path.exists() else []
    _write_csv(output_path, build_calibration_queue(score_rows, calibration_rows))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a human calibration queue for F9 high-score side review."
    )
    parser.add_argument("--input-scores", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    write_calibration_queue(args.input_scores, args.calibration, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
