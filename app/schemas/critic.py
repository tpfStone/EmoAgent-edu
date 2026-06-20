from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.safety import ConversationMessage


class CandidateInput(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    orientation: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class CriticEvaluateRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    user_message: str = Field(..., min_length=1)
    history: list[ConversationMessage] = Field(default_factory=list)
    activated_casel: list[str] = Field(default_factory=list)
    candidates: list[CandidateInput] = Field(..., min_length=1)


class EpitomeScore(BaseModel):
    ER: int = Field(..., ge=0, le=2)
    IP: int = Field(..., ge=0, le=2)
    EX: int = Field(..., ge=0, le=2)


class CandidateScore(BaseModel):
    candidate_id: str
    epitome: EpitomeScore
    casel: dict[str, int] = Field(default_factory=dict)
    boundary_flag: bool
    boundary_reason: str = ""
    weighted_total: float
    rationale: str = ""


class PreferencePair(BaseModel):
    winner_id: str
    loser_id: str


class CriticEvaluateResponse(BaseModel):
    best_candidate_id: str | None
    scores: list[CandidateScore]
    preference_pair: PreferencePair | None = None
    fallback_message: str = ""


class CriticGuidanceStatusResponse(BaseModel):
    session_id: str
    status: Literal["missing", "pending", "ready", "failed"]
    guidance: str = ""
    scores: list[CandidateScore] = Field(default_factory=list)
    error: str = ""
    updated_at: str | None = None
