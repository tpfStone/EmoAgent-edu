import json
from pathlib import Path

import pytest

from app.schemas.safety import SafetyAction, SafetyGateResponse
from scripts.corpus.validate_corpus import validate_corpus


def _write_raw(path: Path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _raw_row(sample_id: str, text: str):
    return {
        "id": sample_id,
        "persona": "反刍型",
        "persona_basis": "ERQ-CA: 高反刍",
        "scenario": "同伴关系",
        "text": text,
        "human_checked": False,
        "run_id": "validate-run",
        "subscenario": "群聊排除",
        "variant_tags": ["中等强度"],
        "gen_model": "fake",
        "gen_prompt_version": "v1",
        "prompt_hash": "abc123",
    }


class StaticSafety:
    def __init__(self, risk_level="green", exc=None):
        self.risk_level = risk_level
        self.exc = exc
        self.requests = []

    async def evaluate(self, request):
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return SafetyGateResponse(
            risk_level=self.risk_level,
            matched_signals=[] if self.risk_level == "green" else ["risk"],
            rationale="fake safety",
            action=SafetyAction(
                block_generation=self.risk_level != "green",
                referral_message="",
            ),
        )


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.asyncio
async def test_single_sentence_with_valid_length_can_be_accepted(tmp_path):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(
        raw_path,
        [
            _raw_row(
                "syn_single",
                "今天小组活动没人愿意跟我一组，我一直在想是不是自己平时哪里做得不够好。",
            )
        ],
    )

    result = await validate_corpus(
        raw_path,
        tmp_path / "out",
        safety_service=StaticSafety("green"),
    )
    accepted = json.loads(result.accepted_path.read_text(encoding="utf-8"))["samples"]

    assert result.accepted_count == 1
    assert result.rejected_count == 0
    assert accepted[0]["id"] == "syn_single"


@pytest.mark.asyncio
async def test_text_at_accepted_length_ceiling_can_be_accepted(tmp_path):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(raw_path, [_raw_row("syn_180_chars", "a" * 180)])

    result = await validate_corpus(
        raw_path,
        tmp_path / "out",
        safety_service=StaticSafety("green"),
    )
    accepted = json.loads(result.accepted_path.read_text(encoding="utf-8"))["samples"]

    assert result.accepted_count == 1
    assert result.rejected_count == 0
    assert accepted[0]["id"] == "syn_180_chars"


@pytest.mark.asyncio
async def test_text_between_181_and_220_chars_goes_to_length_review(tmp_path):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(raw_path, [_raw_row("syn_181_chars", "a" * 181)])

    result = await validate_corpus(
        raw_path,
        tmp_path / "out",
        safety_service=StaticSafety("green"),
    )
    length_review = _read_jsonl(tmp_path / "out" / "length_review.jsonl")

    assert result.accepted_count == 0
    assert result.rejected_count == 0
    assert length_review[0]["reason"] == "length_review_required"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sample_id", "text"),
    [
        ("syn_short", "没人叫我。"),
        (
            "syn_long",
            "a" * 221,
        ),
    ],
)
async def test_text_length_out_of_range_is_rejected(tmp_path, sample_id, text):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(raw_path, [_raw_row(sample_id, text)])

    result = await validate_corpus(
        raw_path,
        tmp_path / "out",
        safety_service=StaticSafety("green"),
    )
    rejected = _read_jsonl(result.rejected_path)

    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert rejected[0]["reason"] == "text_length_out_of_range"


@pytest.mark.asyncio
async def test_more_than_five_sentences_is_rejected(tmp_path):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(
        raw_path,
        [
            _raw_row(
                "syn_many_sentences",
                "今天没人叫我。我有点尴尬。我想装没事。但回家后还是很难受。我一直在想原因。是不是我哪里不好？",
            )
        ],
    )

    result = await validate_corpus(
        raw_path,
        tmp_path / "out",
        safety_service=StaticSafety("green"),
    )
    rejected = _read_jsonl(result.rejected_path)

    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert rejected[0]["reason"] == "sentence_count_out_of_range"


@pytest.mark.asyncio
async def test_explicit_crisis_terms_enter_quarantine_before_f1(tmp_path):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(raw_path, [_raw_row("syn_0001", "我觉得活着没意思。消失算了。")])
    safety = StaticSafety("green")

    result = await validate_corpus(raw_path, tmp_path / "out", safety_service=safety)

    assert result.accepted_count == 0
    assert result.quarantined_count == 1
    assert _read_jsonl(result.quarantine_path)[0]["reason"] == "explicit_crisis_signal"
    assert safety.requests == []


@pytest.mark.asyncio
async def test_f1_non_green_and_exceptions_enter_quarantine(tmp_path):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(raw_path, [_raw_row("syn_0002", "他们没叫我一起玩。我一直想是不是我哪里做错了。")])

    yellow_result = await validate_corpus(
        raw_path,
        tmp_path / "yellow",
        safety_service=StaticSafety("yellow"),
    )
    error_result = await validate_corpus(
        raw_path,
        tmp_path / "error",
        safety_service=StaticSafety(exc=RuntimeError("boom")),
    )

    assert yellow_result.quarantined_count == 1
    assert _read_jsonl(yellow_result.quarantine_path)[0]["reason"] == "f1_non_green"
    assert error_result.quarantined_count == 1
    assert _read_jsonl(error_result.quarantine_path)[0]["reason"] == "f1_exception"


@pytest.mark.asyncio
async def test_duplicate_texts_are_rejected_after_one_acceptance(tmp_path):
    raw_path = tmp_path / "raw.jsonl"
    _write_raw(
        raw_path,
        [
            _raw_row("syn_0003", "她最近回消息很冷淡。我一直在想是不是自己说错话了。"),
            _raw_row("syn_0004", "她最近回消息特别冷淡。我一直在想是不是自己说错话了。"),
        ],
    )

    result = await validate_corpus(
        raw_path,
        tmp_path / "out",
        safety_service=StaticSafety("green"),
    )
    accepted = json.loads(result.accepted_path.read_text(encoding="utf-8"))["samples"]
    rejected = _read_jsonl(result.rejected_path)

    assert len(accepted) == 1
    assert result.rejected_count == 1
    assert rejected[0]["reason"] == "duplicate_in_cell"
