from fastapi import APIRouter, Depends

from app.dependencies import get_critic_service
from app.schemas.critic import CriticEvaluateRequest, CriticEvaluateResponse
from app.services.critic_service import CriticService

router = APIRouter(prefix="/api/critic", tags=["critic"])


@router.post("/evaluate", response_model=CriticEvaluateResponse)
async def evaluate_critic(
    request: CriticEvaluateRequest,
    critic_service: CriticService = Depends(get_critic_service),
) -> CriticEvaluateResponse:
    return await critic_service.evaluate(request)
