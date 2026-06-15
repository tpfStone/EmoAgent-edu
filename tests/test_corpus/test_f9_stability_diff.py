import csv
from pathlib import Path

from scripts.corpus.f9_stability_diff import (
    OUTPUT_COLUMNS,
    high_score_diff_rows,
    write_review_queue,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_high_score_diff_rows_keep_only_new_er_ip_two_rows():
    main_rows = [
        {
            "sample_no": "1",
            "scenario": "同伴关系",
            "candidate_id": "c1",
            "orientation": "共情型",
            "F4_ER": "1",
            "F4_IP": "1",
            "F4_EX": "0",
            "rationale": "main low",
            "用户倾诉": "他们没叫我出去玩。",
            "候选文本": "main low",
        },
        {
            "sample_no": "2",
            "scenario": "同伴关系",
            "candidate_id": "c2",
            "orientation": "引导反思型",
            "F4_ER": "2",
            "F4_IP": "2",
            "F4_EX": "2",
            "rationale": "main high",
            "用户倾诉": "他们没叫我出去玩。",
            "候选文本": "main high",
        },
    ]
    stability_rows = [
        {
            "sample_no": "1",
            "scenario": "同伴关系",
            "candidate_id": "c2",
            "orientation": "引导反思型",
            "F4_ER": "2",
            "F4_IP": "2",
            "F4_EX": "2",
            "rationale": "stability extra high",
            "用户倾诉": "他们没叫我出去玩。",
            "候选文本": "stability extra high",
        },
        {
            "sample_no": "2",
            "scenario": "同伴关系",
            "candidate_id": "c2",
            "orientation": "引导反思型",
            "F4_ER": "2",
            "F4_IP": "2",
            "F4_EX": "2",
            "rationale": "stability already high",
            "用户倾诉": "他们没叫我出去玩。",
            "候选文本": "stability already high",
        },
        {
            "sample_no": "3",
            "scenario": "学业压力",
            "candidate_id": "c1",
            "orientation": "共情型",
            "F4_ER": "2",
            "F4_IP": "1",
            "F4_EX": "0",
            "rationale": "not both high",
            "用户倾诉": "作业太多了。",
            "候选文本": "not both high",
        },
    ]

    output_rows = high_score_diff_rows(main_rows, stability_rows)

    assert len(output_rows) == 1
    assert output_rows[0]["sample_no"] == "1"
    assert output_rows[0]["scenario"] == "同伴关系"
    assert output_rows[0]["student_text"] == "他们没叫我出去玩。"
    assert output_rows[0]["main_F4_ER"] == "1"
    assert output_rows[0]["main_F4_IP"] == "1"
    assert output_rows[0]["stability_F4_ER"] == "2"
    assert output_rows[0]["stability_F4_IP"] == "2"
    assert output_rows[0]["stability_candidate_text"] == "stability extra high"
    assert output_rows[0]["human_er_should_be_2"] == ""
    assert output_rows[0]["human_ip_should_be_2"] == ""
    assert output_rows[0]["human_issue_type"] == ""
    assert output_rows[0]["human_notes"] == ""


def test_write_review_queue_outputs_human_blank_columns(tmp_path):
    main_path = tmp_path / "main.csv"
    stability_path = tmp_path / "stability.csv"
    output_path = tmp_path / "review.csv"
    fieldnames = [
        "sample_no",
        "scenario",
        "candidate_id",
        "orientation",
        "F4_ER",
        "F4_IP",
        "F4_EX",
        "rationale",
        "用户倾诉",
        "候选文本",
    ]
    _write_csv(
        main_path,
        fieldnames,
        [
            {
                "sample_no": "1",
                "scenario": "同伴关系",
                "candidate_id": "c1",
                "orientation": "共情型",
                "F4_ER": "1",
                "F4_IP": "1",
                "F4_EX": "0",
                "rationale": "main low",
                "用户倾诉": "他们没叫我出去玩。",
                "候选文本": "main low",
            }
        ],
    )
    _write_csv(
        stability_path,
        fieldnames,
        [
            {
                "sample_no": "1",
                "scenario": "同伴关系",
                "candidate_id": "c2",
                "orientation": "引导反思型",
                "F4_ER": "2",
                "F4_IP": "2",
                "F4_EX": "2",
                "rationale": "stability extra high",
                "用户倾诉": "他们没叫我出去玩。",
                "候选文本": "stability extra high",
            }
        ],
    )

    write_review_queue(main_path, stability_path, output_path)

    rows = _read_csv(output_path)
    assert rows[0]["sample_no"] == "1"
    assert rows[0]["scenario"] == "同伴关系"
    assert rows[0]["student_text"] == "他们没叫我出去玩。"
    assert rows[0]["human_er_should_be_2"] == ""
    assert rows[0]["human_ip_should_be_2"] == ""
    assert rows[0]["human_issue_type"] == ""
    assert rows[0]["human_notes"] == ""
    assert list(rows[0].keys()) == OUTPUT_COLUMNS


def test_write_review_queue_uses_excel_friendly_utf8_bom(tmp_path):
    main_path = tmp_path / "main.csv"
    stability_path = tmp_path / "stability.csv"
    output_path = tmp_path / "review.csv"
    fieldnames = [
        "sample_no",
        "scenario",
        "candidate_id",
        "orientation",
        "F4_ER",
        "F4_IP",
        "F4_EX",
        "rationale",
        "用户倾诉",
        "候选文本",
    ]
    _write_csv(
        main_path,
        fieldnames,
        [
            {
                "sample_no": "1",
                "scenario": "同伴关系",
                "candidate_id": "c1",
                "orientation": "共情型",
                "F4_ER": "1",
                "F4_IP": "1",
                "F4_EX": "0",
                "rationale": "main low",
                "用户倾诉": "他们没叫我出去玩。",
                "候选文本": "main low",
            }
        ],
    )
    _write_csv(
        stability_path,
        fieldnames,
        [
            {
                "sample_no": "1",
                "scenario": "同伴关系",
                "candidate_id": "c2",
                "orientation": "引导反思型",
                "F4_ER": "2",
                "F4_IP": "2",
                "F4_EX": "2",
                "rationale": "stability extra high",
                "用户倾诉": "他们没叫我出去玩。",
                "候选文本": "stability extra high",
            }
        ],
    )

    write_review_queue(main_path, stability_path, output_path)

    assert output_path.read_bytes().startswith(b"\xef\xbb\xbf")
