from typing import Literal

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: Literal["student", "assistant"]
    text: str = Field(..., min_length=1)


class SafetyGateRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    current_message: str = Field(..., min_length=1)
    history: list[ConversationMessage] = Field(default_factory=list)


class SafetyAction(BaseModel):
    block_generation: bool
    referral_message: str = ""


class SafetyGateResponse(BaseModel):
    risk_level: Literal["green", "yellow", "red"]
    matched_signals: list[str] = Field(default_factory=list)
    rationale: str
    action: SafetyAction
