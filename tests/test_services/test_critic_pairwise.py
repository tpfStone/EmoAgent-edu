import json

import pytest

from app.config import Settings
from app.schemas.safety import ConversationMessage
from app.services.critic_pairwise import (
    CriticPairwiseService,
    PairwiseCandidate,
    PairwiseContext,
    PairwiseSampleResult,
    aggregate_pairwise_samples,
)
from app.services.llm_client import MockLLMClient


def _candidate(candidate_id: str, text: str, orientation: str = "共情型"):
    return PairwiseCandidate(
        candidate_id=candidate_id,
        orientation=orientation,
        text=text,
    )


def _context():
    return PairwiseContext(
        pair_id="p001",
        session_id="session-1",
        user_message="我听说同学在背后说我爱表现。",
        history=[ConversationMessage(role="student", text="前文")],
    )


def _judge(winner: str, reason: str = "A 更具体"):
    return json.dumps(
        {
            "winner": winner,
            "reason": reason,
            "boundary_concern": False,
            "boundary_reason": "",
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_judge_sample_maps_two_independent_orders_to_same_candidate(
    fake_llm_client,
):
    llm = fake_llm_client([_judge("A"), _judge("B")])
    service = CriticPairwiseService(llm, Settings(CRITIC_SAMPLE_COUNT=1))

    result = await service.judge_sample(
        _context(),
        _candidate("c1", "你反复想是不是自己做错了，会很堵。"),
        _candidate("c2", "别太在意，大家都会这样。", "引导反思型"),
        sample_no=1,
    )

    assert result.pair_id == "p001"
    assert result.sample_no == 1
    assert result.judgment_1_winner_id == "c1"
    assert result.judgment_2_winner_id == "c1"
    assert result.stable is True
    assert result.stable_winner_id == "c1"
    assert result.invalid is False
    assert len(llm.prompts) == 2
    assert "回应A" in llm.prompts[0]["prompt"]
    assert "回应B" in llm.prompts[1]["prompt"]
    assert llm.prompts[0]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_judge_sample_marks_position_conflict_unstable(fake_llm_client):
    llm = fake_llm_client([_judge("A"), _judge("A")])
    service = CriticPairwiseService(llm, Settings(CRITIC_SAMPLE_COUNT=1))

    result = await service.judge_sample(
        _context(),
        _candidate("c1", "候选一"),
        _candidate("c2", "候选二", "引导反思型"),
        sample_no=1,
    )

    assert result.judgment_1_winner_id == "c1"
    assert result.judgment_2_winner_id == "c2"
    assert result.stable is False
    assert result.stable_winner_id is None
    assert result.invalid is False


@pytest.mark.asyncio
async def test_judge_sample_marks_parse_failure_invalid(fake_llm_client):
    llm = fake_llm_client(["not json", _judge("B")])
    service = CriticPairwiseService(llm, Settings(CRITIC_SAMPLE_COUNT=1))

    result = await service.judge_sample(
        _context(),
        _candidate("c1", "候选一"),
        _candidate("c2", "候选二", "引导反思型"),
        sample_no=1,
    )

    assert result.invalid is True
    assert result.stable is False
    assert result.stable_winner_id is None
    assert "parse_failure" in result.reason


def test_aggregate_pairwise_samples_reports_majority_with_unstable():
    result = aggregate_pairwise_samples(
        "p001",
        [
            PairwiseSampleResult("p001", 1, "c1", "c1", True, "c1", False, "c1 wins"),
            PairwiseSampleResult("p001", 2, "c1", None, False, None, False, "tie"),
            PairwiseSampleResult("p001", 3, "c1", "c1", True, "c1", False, "c1 wins"),
        ],
        candidate_ids=["c1", "c2"],
    )

    assert result.pairwise_stable is True
    assert result.winner_id == "c1"
    assert result.stable_votes == {"c1": 2, "c2": 0}
    assert result.unstable_count == 1
    assert result.invalid_count == 0
    assert result.pairwise_confidence == "majority_with_unstable"
    assert result.selection_method == "pairwise_stable"


def test_aggregate_pairwise_samples_reports_split_majority():
    result = aggregate_pairwise_samples(
        "p001",
        [
            PairwiseSampleResult("p001", 1, "c1", "c1", True, "c1", False, "c1 wins"),
            PairwiseSampleResult("p001", 2, "c2", "c2", True, "c2", False, "c2 wins"),
            PairwiseSampleResult("p001", 3, "c1", "c1", True, "c1", False, "c1 wins"),
        ],
        candidate_ids=["c1", "c2"],
    )

    assert result.pairwise_stable is True
    assert result.winner_id == "c1"
    assert result.stable_votes == {"c1": 2, "c2": 1}
    assert result.pairwise_confidence == "split_majority"
    assert result.selection_method == "pairwise_stable"


def test_aggregate_pairwise_samples_with_invalid_is_not_main_agreement_ready():
    result = aggregate_pairwise_samples(
        "p001",
        [
            PairwiseSampleResult("p001", 1, "c1", "c1", True, "c1", False, "c1 wins"),
            PairwiseSampleResult("p001", 2, None, None, False, None, True, "parse_failure"),
            PairwiseSampleResult("p001", 3, "c1", "c1", True, "c1", False, "c1 wins"),
        ],
        candidate_ids=["c1", "c2"],
    )

    assert result.pairwise_stable is False
    assert result.winner_id is None
    assert result.invalid_count == 1
    assert result.selection_method == "invalid"


@pytest.mark.asyncio
async def test_project_mock_llm_returns_valid_pairwise_json():
    service = CriticPairwiseService(
        MockLLMClient(),
        Settings(CRITIC_SAMPLE_COUNT=1),
    )

    result = await service.judge_sample(
        _context(),
        _candidate("c1", "候选一"),
        _candidate("c2", "候选二", "引导反思型"),
        sample_no=1,
    )

    assert result.invalid is False
    assert result.stable is True
    assert result.stable_winner_id == "c1"
