from fastapi import APIRouter, Depends

from app.dependencies import get_critic_service, get_orchestrator_service
from app.schemas.critic import (
    CriticEvaluateRequest,
    CriticEvaluateResponse,
    CriticGuidanceStatusResponse,
)
from app.services.critic_service import CriticService
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(prefix="/api/critic", tags=["critic"])


@router.post("/evaluate", response_model=CriticEvaluateResponse)
async def evaluate_critic(
    request: CriticEvaluateRequest,
    critic_service: CriticService = Depends(get_critic_service),
) -> CriticEvaluateResponse:
    return await critic_service.evaluate(request)


@router.get("/guidance/{session_id}", response_model=CriticGuidanceStatusResponse)
async def get_critic_guidance_status(
    session_id: str,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
) -> CriticGuidanceStatusResponse:
    return await orchestrator_service.get_f4_guidance_status(session_id)
