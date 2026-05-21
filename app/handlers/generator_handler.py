from fastapi import APIRouter, Depends

from app.dependencies import get_generator_service
from app.schemas.generator import GeneratorGenerateRequest, GeneratorGenerateResponse
from app.services.generator_service import GeneratorService

router = APIRouter(prefix="/api/generator", tags=["generator"])


@router.post("/generate", response_model=GeneratorGenerateResponse)
async def generate_candidates(
    request: GeneratorGenerateRequest,
    generator_service: GeneratorService = Depends(get_generator_service),
) -> GeneratorGenerateResponse:
    return await generator_service.generate(request)
