import pytest
from sqlalchemy import select

from app.dao.chat_turn_dao import ChatTurnDAO
from app.models.models import (
    ChatCandidate,
    ChatMessage,
    ChatPreferencePair,
    ChatSession,
    ChatTurn,
)
from app.schemas.critic import CandidateScore, EpitomeScore, PreferencePair
from app.schemas.generator import GeneratorCandidate


def _candidate(candidate_id: str, orientation: str, text: str) -> GeneratorCandidate:
    return GeneratorCandidate(
        candidate_id=candidate_id,
        orientation=orientation,
        text=text,
    )


def _score(
    candidate_id: str,
    er: int,
    ip: int,
    ex: int,
    total: float,
    boundary: bool = False,
) -> CandidateScore:
    return CandidateScore(
        candidate_id=candidate_id,
        epitome=EpitomeScore(ER=er, IP=ip, EX=ex),
        casel={"自我觉察引导": 2},
        boundary_flag=boundary,
        boundary_reason="越界" if boundary else "",
        weighted_total=total,
        rationale="测试理由",
    )


@pytest.mark.asyncio
async def test_chat_turn_dao_records_blocked_turn(db_session):
    dao = ChatTurnDAO(db_session)

    turn = await dao.create_turn(
        session_id="s1",
        user_message="我不想存在了",
        assistant_message="fixed referral",
        status="blocked_by_safety",
        risk_level="yellow",
        scenario=None,
        activated_casel=[],
        candidates=[],
        scores=[],
        best_candidate_id=None,
        preference_pair=None,
        failed_module=None,
        failure_reason="",
        fallback_message="",
    )

    messages = (
        await db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == "s1")
        )
    ).scalars().all()

    assert turn.status == "blocked_by_safety"
    assert turn.risk_level == "yellow"
    assert [message.role for message in messages] == ["student", "assistant"]
    assert messages[1].text == "fixed referral"


@pytest.mark.asyncio
async def test_chat_turn_dao_records_answered_turn_with_candidates(db_session):
    dao = ChatTurnDAO(db_session)

    turn = await dao.create_turn(
        session_id="s1",
        user_message="我和朋友闹别扭了。",
        assistant_message="我听见你很难受。",
        status="answered",
        risk_level="green",
        scenario="同伴关系",
        activated_casel=["自我觉察引导"],
        candidates=[
            _candidate("c1", "情感共情型", "我听见你很难受。"),
            _candidate("c2", "认知共情型", "你愿意说说发生了什么吗？"),
        ],
        scores=[
            _score("c1", 2, 2, 1, 5.0),
            _score("c2", 1, 1, 1, 4.0),
        ],
        best_candidate_id="c1",
        preference_pair=PreferencePair(winner_id="c1", loser_id="c2"),
        failed_module=None,
        failure_reason="",
        fallback_message="",
    )

    candidates = (
        await db_session.execute(
            select(ChatCandidate)
            .where(ChatCandidate.turn_id == turn.id)
            .order_by(ChatCandidate.candidate_id)
        )
    ).scalars().all()
    pair = (
        await db_session.execute(
            select(ChatPreferencePair).where(ChatPreferencePair.turn_id == turn.id)
        )
    ).scalar_one()

    assert turn.status == "answered"
    assert turn.scenario == "同伴关系"
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "c1"
    assert candidates[0].epitome_er == 2
    assert candidates[0].casel_scores_json == {"自我觉察引导": 2}
    assert candidates[0].is_winner is True
    assert pair.winner_id == "c1"
    assert pair.loser_id == "c2"


@pytest.mark.asyncio
async def test_chat_turn_dao_records_module_failure_metadata(db_session):
    dao = ChatTurnDAO(db_session)

    turn = await dao.create_turn(
        session_id="s2",
        user_message="这次月考没考好。",
        assistant_message="fallback",
        status="module_failed",
        risk_level="green",
        scenario=None,
        activated_casel=[],
        candidates=[],
        scores=[],
        best_candidate_id=None,
        preference_pair=None,
        failed_module="generator",
        failure_reason="boom",
        fallback_message="fallback",
    )

    session = await db_session.get(ChatSession, "s2")
    saved_turn = await db_session.get(ChatTurn, turn.id)

    assert session is not None
    assert saved_turn is not None
    assert saved_turn.failed_module == "generator"
    assert saved_turn.failure_reason == "boom"
    assert saved_turn.fallback_message == "fallback"
