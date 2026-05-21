from fastapi import APIRouter, Depends

from app.dependencies import get_orchestrator_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
) -> ChatResponse:
    return await orchestrator_service.chat(request)
