from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.safety import ConversationMessage


ScenarioLabel = Literal["学业压力", "同伴关系", "亲子摩擦", "其他"]


class ScenarioAnalyzeRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    current_message: str = Field(..., min_length=1)
    history: list[ConversationMessage] = Field(default_factory=list)


class ScenarioAnalyzeResponse(BaseModel):
    scenario: ScenarioLabel
    scenario_confidence: float = Field(..., ge=0.0, le=1.0)
    activated_casel: list[str] = Field(default_factory=list)
    rationale: str
