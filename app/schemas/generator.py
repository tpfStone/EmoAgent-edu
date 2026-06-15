from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.safety import ConversationMessage
from app.schemas.scenario import EmotionIntensity, ScenarioLabel, SupportMode


GeneratorOrientation = Literal["共情型", "引导反思型"]


class GeneratorGenerateRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    user_message: str = Field(..., min_length=1)
    history: list[ConversationMessage] = Field(default_factory=list)
    scenario: ScenarioLabel
    support_mode: SupportMode = "balanced"
    emotion_intensity: EmotionIntensity = "medium"
    help_seeking: bool = False
    dialogue_stage: str = "first_contact"
    rag_examples: list[str] = Field(default_factory=list)


class GeneratorCandidate(BaseModel):
    candidate_id: str
    orientation: GeneratorOrientation
    text: str = Field(..., min_length=1)


class GeneratorGenerateResponse(BaseModel):
    candidates: list[GeneratorCandidate]
