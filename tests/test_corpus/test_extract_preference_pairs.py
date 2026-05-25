import json

from scripts.corpus.extract_preference_pairs import extract_preference_pairs


def test_extract_preference_pairs_exports_only_answered_rows_with_pairs(tmp_path):
    accepted_path = tmp_path / "accepted.json"
    accepted_path.write_text(
        json.dumps(
            {
                "samples": [
                    {"id": "syn_0001", "text": "第一条", "persona": "反刍型", "scenario": "同伴关系"},
                    {"id": "syn_0002", "text": "第二条", "persona": "外放型", "scenario": "学业压力"},
                    {"id": "syn_0003", "text": "第三条", "persona": "适应型", "scenario": "亲子摩擦"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    responses = [
        {"status": "answered", "preference_pair": None},
        {
            "status": "blocked_by_safety",
            "preference_pair": {"winner_id": "c1", "loser_id": "c2"},
        },
        {
            "status": "answered",
            "scenario": "亲子摩擦",
            "candidates": [{"candidate_id": "c1"}, {"candidate_id": "c2"}],
            "scores": [{"candidate_id": "c1"}, {"candidate_id": "c2"}],
            "preference_pair": {"winner_id": "c1", "loser_id": "c2"},
        },
    ]
    payloads = []

    def fake_chat(payload):
        payloads.append(payload)
        return responses.pop(0)

    result = extract_preference_pairs(
        accepted_path=accepted_path,
        output_dir=tmp_path / "out",
        run_id="pair-run",
        chat_client=fake_chat,
    )

    pairs = [
        json.loads(line)
        for line in result.preference_pairs_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    chat_rows = [
        json.loads(line)
        for line in result.chat_results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(chat_rows) == 3
    assert len(pairs) == 1
    assert pairs[0]["sample_id"] == "syn_0003"
    assert pairs[0]["winner_id"] == "c1"
    assert pairs[0]["loser_id"] == "c2"
    assert pairs[0]["judge_verification_status"] == "unverified"
    assert payloads[0]["session_id"] == "pair-run-syn_0001-chat-01"


def test_extract_preference_pairs_summary_includes_dpo_diversity_metrics(tmp_path):
    accepted_path = tmp_path / "accepted.json"
    accepted_path.write_text(
        json.dumps(
            {
                "samples": [
                    {"id": "syn_0001", "text": "第一条", "persona": "反刍型", "scenario": "同伴关系"},
                    {"id": "syn_0002", "text": "第二条", "persona": "反刍型", "scenario": "同伴关系"},
                    {"id": "syn_0003", "text": "第三条", "persona": "外放型", "scenario": "学业压力"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    responses = [
        {
            "status": "answered",
            "candidates": [{"candidate_id": "c1"}, {"candidate_id": "c2"}],
            "scores": [
                {
                    "candidate_id": "c1",
                    "weighted_total": 4.0,
                    "epitome": {"EX": 0},
                    "casel": {"自我觉察引导": 1, "关系技能培养": 0},
                },
                {
                    "candidate_id": "c2",
                    "weighted_total": 5.5,
                    "epitome": {"EX": 2},
                    "casel": {"自我觉察引导": 2, "关系技能培养": 2},
                },
            ],
            "preference_pair": {"winner_id": "c2", "loser_id": "c1"},
        },
        {
            "status": "answered",
            "candidates": [{"candidate_id": "c1"}, {"candidate_id": "c2"}],
            "scores": [
                {
                    "candidate_id": "c1",
                    "weighted_total": 5.0,
                    "epitome": {"EX": 1},
                    "casel": {"自我觉察引导": 2, "关系技能培养": 1},
                },
                {
                    "candidate_id": "c2",
                    "weighted_total": 4.5,
                    "epitome": {"EX": 0},
                    "casel": {"自我觉察引导": 1, "关系技能培养": 1},
                },
            ],
            "preference_pair": {"winner_id": "c1", "loser_id": "c2"},
        },
        {
            "status": "answered",
            "candidates": [{"candidate_id": "c1"}, {"candidate_id": "c2"}],
            "scores": [
                {
                    "candidate_id": "c1",
                    "weighted_total": 3.0,
                    "epitome": {"EX": 0},
                    "casel": {"自我管理引导": 0},
                },
                {
                    "candidate_id": "c2",
                    "weighted_total": 5.0,
                    "epitome": {"EX": 2},
                    "casel": {"自我管理引导": 2},
                },
            ],
            "preference_pair": {"winner_id": "c2", "loser_id": "c1"},
        },
    ]

    def fake_chat(_payload):
        return responses.pop(0)

    result = extract_preference_pairs(
        accepted_path=accepted_path,
        output_dir=tmp_path / "out",
        run_id="pair-run",
        chat_client=fake_chat,
    )

    summary = result.summary_path.read_text(encoding="utf-8")

    assert "## DPO Diversity" in summary
    assert "- c2 > c1: 2" in summary
    assert "- c1 > c2: 1" in summary
    assert "- score_delta: min=0.50, median=1.50, max=2.00" in summary
    assert "- EX_delta: min=1.00, median=2.00, max=2.00" in summary
    assert "- CASEL_avg_delta: min=0.50, median=1.50, max=2.00" in summary
    assert "| 反刍型 × 同伴关系 | c2 > c1 | 1 |" in summary
    assert "| 反刍型 × 同伴关系 | c1 > c2 | 1 |" in summary
    assert "| 外放型 × 学业压力 | c2 > c1 | 1 |" in summary
