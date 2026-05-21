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


class ChatSession(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    turns: Mapped[list["ChatTurn"]] = relationship(
        "ChatTurn",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")


class ChatTurn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    scenario: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activated_casel: Mapped[list[str]] = mapped_column(
        SQLAlchemyJSON, nullable=False, default=list
    )
    best_candidate_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failed_module: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fallback_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="turns")
    candidates: Mapped[list["ChatCandidate"]] = relationship(
        "ChatCandidate",
        back_populates="turn",
        cascade="all, delete-orphan",
    )
    preference_pairs: Mapped[list["ChatPreferencePair"]] = relationship(
        "ChatPreferencePair",
        back_populates="turn",
        cascade="all, delete-orphan",
    )


class ChatCandidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn_id: Mapped[int] = mapped_column(
        ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    orientation: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    epitome_er: Mapped[int] = mapped_column(Integer, nullable=False)
    epitome_ip: Mapped[int] = mapped_column(Integer, nullable=False)
    epitome_ex: Mapped[int] = mapped_column(Integer, nullable=False)
    casel_scores_json: Mapped[dict] = mapped_column(SQLAlchemyJSON, nullable=False)
    boundary_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    boundary_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weighted_total: Mapped[float] = mapped_column(Float, nullable=False)
    is_winner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    turn: Mapped[ChatTurn] = relationship("ChatTurn", back_populates="candidates")


class ChatPreferencePair(Base):
    __tablename__ = "preference_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turn_id: Mapped[int] = mapped_column(
        ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    winner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    loser_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    turn: Mapped[ChatTurn] = relationship("ChatTurn", back_populates="preference_pairs")
