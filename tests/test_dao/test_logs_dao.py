import pytest

from app.dao.critic_run_dao import CriticRunDAO
from app.dao.safety_log_dao import SafetyLogDAO


@pytest.mark.asyncio
async def test_safety_log_dao_persists_safety_result(db_session):
    dao = SafetyLogDAO(db_session)

    log = await dao.create_log(
        session_id="session-1",
        risk_level="yellow",
        matched_signals=["活着没意思"],
        rationale="出现被动意念。",
        block_generation=True,
        referral_message="固定转介话术",
    )

    assert log.id is not None
    assert log.risk_level == "yellow"
    assert log.matched_signals == ["活着没意思"]


@pytest.mark.asyncio
async def test_critic_run_dao_persists_run_and_candidate_scores(db_session):
    dao = CriticRunDAO(db_session)

    run = await dao.create_run(
        session_id="session-1",
        user_message="我和朋友闹别扭了。",
        history=[],
        activated_casel=[],
        candidates=[
            {"candidate_id": "c1", "orientation": "情感共情型", "text": "我听见你很难受。"}
        ],
        scores=[
            {
                "candidate_id": "c1",
                "epitome": {"ER": 2, "IP": 2, "EX": 1},
                "casel": {},
                "boundary_flag": False,
                "boundary_reason": "",
                "weighted_total": 5,
                "rationale": "质量较好。",
            }
        ],
        best_candidate_id="c1",
        preference_pair=None,
        fallback_message="",
    )

    assert run.id is not None
    assert run.best_candidate_id == "c1"
    assert len(run.candidate_scores) == 1
    assert run.candidate_scores[0].epitome == {"ER": 2, "IP": 2, "EX": 1}
