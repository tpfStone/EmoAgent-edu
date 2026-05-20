import json

import pytest

from app.config import Settings
from app.schemas.critic import CandidateInput, CriticEvaluateRequest
from app.services.critic_service import CriticService


def _candidate(candidate_id: str, text: str, orientation: str = "共情型"):
    return CandidateInput(candidate_id=candidate_id, orientation=orientation, text=text)


def _request(candidates, activated_casel=None):
    return CriticEvaluateRequest(
        session_id="session-1",
        user_message="我和朋友闹别扭了，心里很难受。",
        history=[],
        activated_casel=activated_casel or [],
        candidates=candidates,
    )


def _score(er, ip, ex, boundary=False, reason=""):
    return json.dumps(
        {
            "ER": er,
            "IP": ip,
            "EX": ex,
            "boundary_flag": boundary,
            "boundary_reason": reason,
            "rationale": "测试理由",
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_high_quality_candidate_wins_and_preference_pair_created(
    fake_llm_client, critic_run_dao
):
    llm = fake_llm_client([_score(2, 2, 1), _score(1, 0, 0)])
    service = CriticService(
        llm,
        critic_run_dao,
        Settings(CRITIC_SAMPLE_COUNT=1),
    )

    response = await service.evaluate(
        _request(
            [
                _candidate("c1", "听起来你很在意这段关系，也有点受伤。"),
                _candidate("c2", "别想太多。"),
            ]
        )
    )

    assert response.best_candidate_id == "c1"
    assert response.scores[0].weighted_total == 5
    assert response.scores[1].weighted_total == 1
    assert response.preference_pair is not None
    assert response.preference_pair.winner_id == "c1"
    assert response.preference_pair.loser_id == "c2"
    assert response.scores[0].casel == {}
    assert critic_run_dao.records[0]["best_candidate_id"] == "c1"


@pytest.mark.asyncio
async def test_boundary_candidate_is_excluded(fake_llm_client):
    llm = fake_llm_client(
        [
            _score(2, 2, 2, boundary=True, reason="建议隐瞒家长老师"),
            _score(1, 1, 1),
        ]
    )
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [
                _candidate("c1", "这事别跟你爸妈说。"),
                _candidate("c2", "可以先找一个你信任的大人聊聊。"),
            ]
        )
    )

    assert response.best_candidate_id == "c2"
    assert response.scores[0].boundary_flag is True
    assert response.scores[0].boundary_reason == "建议隐瞒家长老师"


@pytest.mark.asyncio
async def test_all_boundary_candidates_return_fallback(fake_llm_client):
    llm = fake_llm_client(
        [
            _score(2, 2, 2, boundary=True, reason="越界"),
            _score(1, 1, 1, boundary=True, reason="不适龄"),
        ]
    )
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request([_candidate("c1", "bad"), _candidate("c2", "bad")])
    )

    assert response.best_candidate_id is None
    assert response.preference_pair is None
    assert response.fallback_message == "所有候选回应均未通过边界检查，请转人工复核。"


@pytest.mark.asyncio
async def test_single_candidate_has_no_preference_pair(fake_llm_client):
    llm = fake_llm_client([_score(2, 2, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(_request([_candidate("c1", "我听见你很难受。")]))

    assert response.best_candidate_id == "c1"
    assert response.preference_pair is None


@pytest.mark.asyncio
async def test_three_samples_use_median_scores(fake_llm_client):
    llm = fake_llm_client([_score(0, 0, 0), _score(2, 2, 2), _score(1, 1, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=3))

    response = await service.evaluate(_request([_candidate("c1", "我在听你说。")]))

    assert response.scores[0].epitome.ER == 1
    assert response.scores[0].epitome.IP == 1
    assert response.scores[0].epitome.EX == 1
    assert response.scores[0].weighted_total == 3


@pytest.mark.asyncio
async def test_long_empty_answer_receives_only_judge_scores(fake_llm_client):
    llm = fake_llm_client([_score(1, 0, 0)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request([_candidate("c1", "我理解你。" * 100)])
    )

    assert response.scores[0].weighted_total == 1


@pytest.mark.asyncio
async def test_wrong_question_can_keep_ip_zero(fake_llm_client):
    llm = fake_llm_client([_score(1, 0, 1)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(_request([_candidate("c1", "我们聊聊作业吧。")]))

    assert response.scores[0].epitome.IP == 0


@pytest.mark.asyncio
async def test_empty_activated_casel_returns_empty_casel(fake_llm_client):
    llm = fake_llm_client([_score(2, 2, 2)])
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request([_candidate("c1", "你愿意说说发生了什么吗？")], activated_casel=[])
    )

    assert response.scores[0].casel == {}
