from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import JSON as SQLAlchemyJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class SafetyGateLog(Base):
    __tablename__ = "safety_gate_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    matched_signals: Mapped[list[str]] = mapped_column(SQLAlchemyJSON, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    block_generation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    referral_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CriticRun(Base):
    __tablename__ = "critic_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    history: Mapped[list[dict]] = mapped_column(SQLAlchemyJSON, nullable=False)
    activated_casel: Mapped[list[str]] = mapped_column(SQLAlchemyJSON, nullable=False)
    candidates: Mapped[list[dict]] = mapped_column(SQLAlchemyJSON, nullable=False)
    best_candidate_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preference_pair: Mapped[dict | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    fallback_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    candidate_scores: Mapped[list["CriticCandidateScore"]] = relationship(
        "CriticCandidateScore",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class CriticCandidateScore(Base):
    __tablename__ = "critic_candidate_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("critic_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    epitome: Mapped[dict] = mapped_column(SQLAlchemyJSON, nullable=False)
    casel: Mapped[dict] = mapped_column(SQLAlchemyJSON, nullable=False)
    boundary_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    boundary_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weighted_total: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    run: Mapped[CriticRun] = relationship("CriticRun", back_populates="candidate_scores")
