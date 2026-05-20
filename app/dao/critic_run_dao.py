from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CriticCandidateScore, CriticRun


class CriticRunDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_run(
        self,
        session_id: str,
        user_message: str,
        history: list[dict],
        activated_casel: list[str],
        candidates: list[dict],
        scores: list[dict],
        best_candidate_id: str | None,
        preference_pair: dict | None,
        fallback_message: str,
    ) -> CriticRun:
        run = CriticRun(
            session_id=session_id,
            user_message=user_message,
            history=history,
            activated_casel=activated_casel,
            candidates=candidates,
            best_candidate_id=best_candidate_id,
            preference_pair=preference_pair,
            fallback_message=fallback_message,
        )
        run.candidate_scores = [
            CriticCandidateScore(
                candidate_id=score["candidate_id"],
                epitome=score["epitome"],
                casel=score["casel"],
                boundary_flag=score["boundary_flag"],
                boundary_reason=score["boundary_reason"],
                weighted_total=score["weighted_total"],
                rationale=score["rationale"],
            )
            for score in scores
        ]
        self.db.add(run)
        await self.db.commit()
        return run
