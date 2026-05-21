from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.critic import CandidateScore, PreferencePair
from app.schemas.generator import GeneratorCandidate
from app.schemas.scenario import ScenarioLabel


ChatStatus = Literal[
    "answered",
    "blocked_by_safety",
    "all_candidates_blocked",
    "module_failed",
]


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    current_message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    session_id: str
    status: ChatStatus
    reply_text: str
    risk_level: Literal["green", "yellow", "red"]
    scenario: ScenarioLabel | None = None
    activated_casel: list[str] = Field(default_factory=list)
    best_candidate_id: str | None = None
    candidates: list[GeneratorCandidate] = Field(default_factory=list)
    scores: list[CandidateScore] = Field(default_factory=list)
    preference_pair: PreferencePair | None = None
    failed_module: str | None = None
    failure_reason: str = ""
