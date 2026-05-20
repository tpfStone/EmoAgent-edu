from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import SafetyGateLog


class SafetyLogDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_log(
        self,
        session_id: str,
        risk_level: str,
        matched_signals: list[str],
        rationale: str,
        block_generation: bool,
        referral_message: str,
    ) -> SafetyGateLog:
        log = SafetyGateLog(
            session_id=session_id,
            risk_level=risk_level,
            matched_signals=matched_signals,
            rationale=rationale,
            block_generation=block_generation,
            referral_message=referral_message,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log
