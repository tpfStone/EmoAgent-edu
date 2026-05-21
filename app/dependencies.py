from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dao.critic_run_dao import CriticRunDAO
from app.dao.safety_log_dao import SafetyLogDAO
from app.database import get_db
from app.services.generator_service import GeneratorService
from app.services.critic_service import CriticService
from app.services.llm_client import DeepSeekLLMClient, LLMClientProtocol, MockLLMClient
from app.services.scenario_service import ScenarioService
from app.services.safety_gate_service import SafetyGateService


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_llm_client_cached(
    provider: str,
    deepseek_api_key: str,
    deepseek_base_url: str,
    deepseek_model: str,
) -> LLMClientProtocol:
    if provider.lower() == "deepseek":
        return DeepSeekLLMClient(
            api_key=deepseek_api_key,
            base_url=deepseek_base_url,
            model=deepseek_model,
        )
    return MockLLMClient()


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMClientProtocol:
    return get_llm_client_cached(
        settings.LLM_PROVIDER,
        settings.DEEPSEEK_API_KEY,
        settings.DEEPSEEK_BASE_URL,
        settings.DEEPSEEK_MODEL,
    )


def get_safety_log_dao(db: AsyncSession = Depends(get_db)) -> SafetyLogDAO:
    return SafetyLogDAO(db)


def get_critic_run_dao(db: AsyncSession = Depends(get_db)) -> CriticRunDAO:
    return CriticRunDAO(db)


def get_safety_gate_service(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    safety_log_dao: SafetyLogDAO = Depends(get_safety_log_dao),
    settings: Settings = Depends(get_settings),
) -> SafetyGateService:
    return SafetyGateService(llm_client, safety_log_dao, settings)


def get_scenario_service(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    settings: Settings = Depends(get_settings),
) -> ScenarioService:
    return ScenarioService(llm_client, settings)


def get_generator_service(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    settings: Settings = Depends(get_settings),
) -> GeneratorService:
    return GeneratorService(llm_client, settings)


def get_critic_service(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    critic_run_dao: CriticRunDAO = Depends(get_critic_run_dao),
    settings: Settings = Depends(get_settings),
) -> CriticService:
    return CriticService(llm_client, critic_run_dao, settings)
