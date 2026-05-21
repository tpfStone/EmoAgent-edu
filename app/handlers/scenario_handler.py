from fastapi import APIRouter, Depends

from app.dependencies import get_scenario_service
from app.schemas.scenario import ScenarioAnalyzeRequest, ScenarioAnalyzeResponse
from app.services.scenario_service import ScenarioService

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


@router.post("/evaluate", response_model=ScenarioAnalyzeResponse)
async def evaluate_scenario(
    request: ScenarioAnalyzeRequest,
    scenario_service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioAnalyzeResponse:
    return await scenario_service.analyze(request)
