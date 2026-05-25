import csv
from pathlib import Path

from scripts.corpus.f9_validation import (
    GENERATED_GLOBAL_QUALITY_FLAG_MAX,
    GOLDEN_SAMPLE_NOS,
    RERUN_GLOBAL_QUALITY_FLAG_MAX,
    F9_BLIND_COLUMNS,
    _score_fieldnames,
    build_report,
    detect_f3_global_quality_flags,
    detect_f3_regression_flags,
    f4_expectation_passed,
    load_cases,
    low_score_review_rows,
    make_blind_row,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_load_cases_joins_analysis_and_blind_history(tmp_path):
    analysis = tmp_path / "analysis.csv"
    blind = tmp_path / "blind.csv"
    _write_csv(
        analysis,
        ["sample_no", "scenario", "orientation", "用户倾诉", "候选文本"],
        [
            {
                "sample_no": "3",
                "scenario": "同伴关系",
                "orientation": "共情型",
                "用户倾诉": "他们没叫我。",
                "候选文本": "旧候选",
            },
            {
                "sample_no": "15",
                "scenario": "学业压力",
                "orientation": "引导反思型",
                "用户倾诉": "作业很多。",
                "候选文本": "旧候选2",
            },
        ],
    )
    _write_csv(
        blind,
        ["sample_no", "对话历史"],
        [
            {"sample_no": "3", "对话历史": '[{"role":"student","text":"前文"}]'},
            {"sample_no": "15", "对话历史": ""},
        ],
    )

    cases = load_cases(analysis, blind, [15, 3])

    assert [case.sample_no for case in cases] == [15, 3]
    assert cases[1].history[0].text == "前文"
    assert cases[0].history == []


def test_detect_f3_regression_flags_matches_sample_expectations():
    flags = detect_f3_regression_flags(
        22,
        "你以后不再相信他，这说明你挺有主见的。",
    )

    assert "contains:有主见" in flags


def test_detect_f3_regression_flags_keeps_sample_specific_fact_completion_rules():
    flags = detect_f3_regression_flags(
        27,
        "他们也许只是跟坐得近的人一组，可能只是话题没兴趣。",
    )

    assert "contains:坐得近" in flags
    assert "contains:话题没兴趣" in flags


def test_detect_f3_global_quality_flags_matches_quality_reframe_patterns():
    flags = detect_f3_global_quality_flags(
        "这说明你很有数，也挺难得，能看出你有判断力。"
    )

    assert "global_contains:说明你" in flags
    assert "global_contains:挺难得" in flags
    assert "global_contains:很有数" in flags
    assert "global_contains:判断力" in flags


def test_f4_expectation_passed_handles_key_golden_cases():
    assert f4_expectation_passed(22, er=1, ip=2, ex=0, boundary=False)
    assert not f4_expectation_passed(22, er=2, ip=2, ex=0, boundary=False)
    assert not f4_expectation_passed(22, er=1, ip=1, ex=0, boundary=True)
    assert f4_expectation_passed(16, er=2, ip=2, ex=2, boundary=False)
    assert not f4_expectation_passed(16, er=2, ip=2, ex=2, boundary=True)
    assert f4_expectation_passed(40, er=2, ip=2, ex=1, boundary=False)
    assert not f4_expectation_passed(40, er=2, ip=2, ex=2, boundary=False)


def test_make_blind_row_contains_no_f4_scores():
    row = make_blind_row(
        sample_no=1,
        scenario="同伴关系",
        orientation="共情型",
        user_message="我很难受。",
        history_json="[]",
        candidate_text="候选",
    )

    assert list(row.keys()) == F9_BLIND_COLUMNS
    assert "F4_ER" not in row
    assert row["A_ER"] == ""
    assert row["B_EX"] == ""


def test_golden_sample_order_keeps_positive_controls():
    assert GOLDEN_SAMPLE_NOS == [3, 11, 16, 19, 22, 25, 27, 31, 40, 15]


def _report_row(
    sample_no: int,
    *,
    candidate_id: str = "c1",
    er: int = 2,
    ip: int = 2,
    ex: int = 0,
    flags: str = "",
    global_flags: str = "",
    f3_pass: str = "true",
    f4_pass: str = "true",
    boundary: str = "false",
) -> dict[str, str]:
    row = {field: "" for field in _score_fieldnames()}
    row.update(
        {
            "sample_no": str(sample_no),
            "source": "test",
            "candidate_id": candidate_id,
            "detected_flags": flags,
            "global_quality_flags": global_flags,
            "f3_regression_pass": f3_pass,
            "F4_ER": str(er),
            "F4_IP": str(ip),
            "F4_EX": str(ex),
            "boundary_flag": boundary,
            "f4_expectation_pass": f4_pass,
        }
    )
    return row


def _manifest(row_count: int = 40) -> dict:
    return {
        "llm_provider": "deepseek",
        "deepseek_model": "deepseek-chat",
        "critic_sample_count": 3,
        "golden_sample_nos": GOLDEN_SAMPLE_NOS,
        "f9_rerun_rows": row_count,
        "blind_annotation_path": "docs\\corpus\\f9\\validation\\rerun\\f9_rerun_blind_annotation.csv",
        "f4_holdout_path": "docs\\corpus\\f9\\validation\\rerun\\f9_rerun_f4_scores_holdout.csv",
        "rerun_scores_path": "docs\\corpus\\f9\\validation\\rerun\\f9_rerun_selected_scores.csv",
    }


def test_build_report_marks_gate_fail_with_blocking_reasons():
    generated_rows = [
        _report_row(27, candidate_id="c2", flags="contains:坐得近", f3_pass="false")
    ]
    old_rows = [
        *[_report_row(i, er=1, ip=1, f4_pass="true") for i in range(1, 5)],
        *[_report_row(i, er=2, ip=2, f4_pass="false") for i in range(5, 11)],
    ]
    rerun_rows = [
        *[_report_row(i, er=2, ip=2) for i in range(1, 38)],
        _report_row(38, er=2, ip=1),
        _report_row(39, er=1, ip=1),
        _report_row(40, er=1, ip=1),
    ]

    report = build_report(generated_rows, old_rows, rerun_rows, _manifest())

    assert "## Gate Decision" in report
    assert "- decision: FAIL" in report
    assert "旧坏候选 F4 复评通过 4/10，低于 8/10 门槛。" in report
    assert "旧坏候选 ER/IP 同时 2/2 为 6/10，高于 2/10 上限。" in report
    assert "重跑样本 ER=2 为 38/40，IP=2 为 37/40，仍接近满分饱和。" in report
    assert "F3 golden 检测到 1 条 flagged rows" in report


def test_build_report_applies_separate_global_quality_thresholds():
    generated_rows = [
        *[
            _report_row(
                i,
                global_flags="global_contains:说明你",
                f3_pass="false",
            )
            for i in range(1, GENERATED_GLOBAL_QUALITY_FLAG_MAX + 2)
        ],
        *[
            _report_row(i)
            for i in range(GENERATED_GLOBAL_QUALITY_FLAG_MAX + 2, 21)
        ],
    ]
    old_rows = [
        _report_row(i, er=1, ip=1, f4_pass="true")
        for i in range(1, 11)
    ]
    rerun_rows = [
        *[
            _report_row(
                i,
                er=1,
                ip=1,
                global_flags="global_contains:挺难得",
                f3_pass="false",
            )
            for i in range(1, RERUN_GLOBAL_QUALITY_FLAG_MAX + 2)
        ],
        *[
            _report_row(i, er=1, ip=1)
            for i in range(RERUN_GLOBAL_QUALITY_FLAG_MAX + 2, 41)
        ],
    ]

    report = build_report(generated_rows, old_rows, rerun_rows, _manifest())

    assert "- decision: FAIL" in report
    assert (
        f"generated_global_quality_flagged_rows: "
        f"{GENERATED_GLOBAL_QUALITY_FLAG_MAX + 1}/20 "
        f"(上限: <= {GENERATED_GLOBAL_QUALITY_FLAG_MAX}/20)"
    ) in report
    assert (
        f"rerun_global_quality_flagged_rows: "
        f"{RERUN_GLOBAL_QUALITY_FLAG_MAX + 1}/40 "
        f"(上限: <= {RERUN_GLOBAL_QUALITY_FLAG_MAX}/40)"
    ) in report


def test_build_report_allows_small_global_quality_probe_budget():
    generated_rows = [
        *[
            _report_row(
                i,
                er=1,
                ip=1,
                global_flags="global_contains:说明你",
                f3_pass="false",
            )
            for i in range(1, GENERATED_GLOBAL_QUALITY_FLAG_MAX + 1)
        ],
        *[
            _report_row(i, er=1, ip=1)
            for i in range(GENERATED_GLOBAL_QUALITY_FLAG_MAX + 1, 21)
        ],
    ]
    old_rows = [
        _report_row(i, er=1, ip=1, f4_pass="true")
        for i in range(1, 11)
    ]
    rerun_rows = [
        *[
            _report_row(
                i,
                er=1,
                ip=1,
                global_flags="global_contains:挺难得",
                f3_pass="false",
            )
            for i in range(1, RERUN_GLOBAL_QUALITY_FLAG_MAX + 1)
        ],
        *[
            _report_row(i, er=1, ip=1)
            for i in range(RERUN_GLOBAL_QUALITY_FLAG_MAX + 1, 41)
        ],
    ]

    report = build_report(generated_rows, old_rows, rerun_rows, _manifest())

    assert "- decision: PASS" in report


def test_low_score_review_rows_lists_targeted_er_ip_drops():
    rows = [
        _report_row(16, er=2, ip=2, ex=2),
        _report_row(25, candidate_id="c2", er=1, ip=1, ex=0),
        _report_row(35, candidate_id="c1", er=2, ip=1, ex=1),
        _report_row(1, candidate_id="c1", er=1, ip=1, ex=1),
    ]

    queue = low_score_review_rows(rows)

    assert [(row["sample_no"], row["candidate_id"]) for row in queue] == [
        ("25", "c2"),
        ("35", "c1"),
    ]


def test_build_report_counts_integer_f4_scores_from_runtime_rows():
    generated_rows = []
    old_rows = [_report_row(i, er=1, ip=1, f4_pass="true") for i in range(1, 11)]
    rerun_rows = [
        {
            **_report_row(i),
            "F4_ER": 2 if i <= 33 else 1,
            "F4_IP": 2 if i <= 34 else 1,
        }
        for i in range(1, 41)
    ]

    report = build_report(generated_rows, old_rows, rerun_rows, _manifest())

    assert "重跑样本 ER=2 为 33/40，IP=2 为 34/40，仍接近满分饱和。" in report


def test_build_report_marks_gate_pass_when_thresholds_are_met():
    generated_rows = [_report_row(i, er=2, ip=2) for i in range(1, 5)]
    old_rows = [
        *[_report_row(i, er=1, ip=1, f4_pass="true") for i in range(1, 9)],
        *[_report_row(i, er=2, ip=2, f4_pass="false") for i in range(9, 11)],
    ]
    rerun_rows = [
        *[_report_row(i, er=2, ip=2) for i in range(1, 33)],
        *[_report_row(i, er=1, ip=1) for i in range(33, 41)],
    ]

    report = build_report(generated_rows, old_rows, rerun_rows, _manifest())

    assert "- decision: PASS" in report
    assert "无；自动准入通过，可进入人工 F9 准备。" in report
