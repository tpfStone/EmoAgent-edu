from fastapi import APIRouter, Depends

from app.dependencies import get_classifier_safety_gate_service, get_safety_gate_service
from app.schemas.safety import SafetyGateRequest, SafetyGateResponse
from app.services.classifier_safety_gate_service import ClassifierSafetyGateService
from app.services.safety_gate_service import SafetyGateService

router = APIRouter(prefix="/api/safety", tags=["safety"])


@router.post("/evaluate", response_model=SafetyGateResponse)
async def evaluate_safety(
    request: SafetyGateRequest,
    safety_gate_service: SafetyGateService = Depends(get_safety_gate_service),
) -> SafetyGateResponse:
    return await safety_gate_service.evaluate(request)


@router.post("/classifier/evaluate", response_model=SafetyGateResponse)
async def evaluate_safety_with_classifier(
    request: SafetyGateRequest,
    safety_gate_service: ClassifierSafetyGateService = Depends(
        get_classifier_safety_gate_service
    ),
) -> SafetyGateResponse:
    return await safety_gate_service.evaluate(request)
