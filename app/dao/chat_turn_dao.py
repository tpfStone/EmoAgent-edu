from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    ChatCandidate,
    ChatMessage,
    ChatPreferencePair,
    ChatSession,
    ChatTurn,
    utc_now,
)
from app.schemas.critic import CandidateScore, PreferencePair
from app.schemas.generator import GeneratorCandidate


class ChatTurnDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        status: str,
        risk_level: str,
        scenario: str | None,
        activated_casel: list[str],
        candidates: list[GeneratorCandidate],
        scores: list[CandidateScore],
        best_candidate_id: str | None,
        preference_pair: PreferencePair | None,
        failed_module: str | None,
        failure_reason: str,
        fallback_message: str,
    ) -> ChatTurn:
        session = await self.db.get(ChatSession, session_id)
        if session is None:
            self.db.add(ChatSession(session_id=session_id))
        else:
            session.updated_at = utc_now()

        self.db.add_all(
            [
                ChatMessage(
                    session_id=session_id,
                    role="student",
                    text=user_message,
                ),
                ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    text=assistant_message,
                ),
            ]
        )
        turn = ChatTurn(
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
            status=status,
            risk_level=risk_level,
            scenario=scenario,
            activated_casel=activated_casel,
            best_candidate_id=best_candidate_id,
            failed_module=failed_module,
            failure_reason=failure_reason,
            fallback_message=fallback_message,
        )
        self.db.add(turn)
        await self.db.flush()

        scores_by_id = {score.candidate_id: score for score in scores}
        for candidate in candidates:
            score = scores_by_id.get(candidate.candidate_id)
            if score is None:
                continue
            self.db.add(
                ChatCandidate(
                    turn_id=turn.id,
                    candidate_id=candidate.candidate_id,
                    orientation=candidate.orientation,
                    text=candidate.text,
                    epitome_er=score.epitome.ER,
                    epitome_ip=score.epitome.IP,
                    epitome_ex=score.epitome.EX,
                    casel_scores_json=score.casel,
                    boundary_flag=score.boundary_flag,
                    boundary_reason=score.boundary_reason,
                    weighted_total=score.weighted_total,
                    is_winner=candidate.candidate_id == best_candidate_id,
                )
            )

        if preference_pair is not None:
            self.db.add(
                ChatPreferencePair(
                    turn_id=turn.id,
                    winner_id=preference_pair.winner_id,
                    loser_id=preference_pair.loser_id,
                )
            )

        await self.db.commit()
        await self.db.refresh(turn)
        return turn
