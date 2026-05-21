from functools import lru_cache

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dao.chat_turn_dao import ChatTurnDAO
from app.dao.critic_run_dao import CriticRunDAO
from app.dao.safety_log_dao import SafetyLogDAO
from app.database import get_db
from app.services.generator_service import GeneratorService
from app.services.critic_service import CriticService
from app.services.history_store import RedisHistoryStore
from app.services.llm_client import DeepSeekLLMClient, LLMClientProtocol, MockLLMClient
from app.services.orchestrator_service import OrchestratorService
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


@lru_cache
def get_redis_client_cached(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)


def get_redis_client(settings: Settings = Depends(get_settings)) -> Redis:
    return get_redis_client_cached(settings.REDIS_URL)


def get_history_store(
    redis_client: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
) -> RedisHistoryStore:
    return RedisHistoryStore(redis_client, settings.CHAT_HISTORY_TTL_SECONDS)


def get_safety_log_dao(db: AsyncSession = Depends(get_db)) -> SafetyLogDAO:
    return SafetyLogDAO(db)


def get_critic_run_dao(db: AsyncSession = Depends(get_db)) -> CriticRunDAO:
    return CriticRunDAO(db)


def get_chat_turn_dao(db: AsyncSession = Depends(get_db)) -> ChatTurnDAO:
    return ChatTurnDAO(db)


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


def get_chat_safety_gate_service(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    settings: Settings = Depends(get_settings),
) -> SafetyGateService:
    return SafetyGateService(llm_client, None, settings)


def get_chat_critic_service(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    settings: Settings = Depends(get_settings),
) -> CriticService:
    return CriticService(llm_client, None, settings)


def get_orchestrator_service(
    safety_service: SafetyGateService = Depends(get_chat_safety_gate_service),
    scenario_service: ScenarioService = Depends(get_scenario_service),
    generator_service: GeneratorService = Depends(get_generator_service),
    critic_service: CriticService = Depends(get_chat_critic_service),
    history_store: RedisHistoryStore = Depends(get_history_store),
    chat_turn_dao: ChatTurnDAO = Depends(get_chat_turn_dao),
    settings: Settings = Depends(get_settings),
) -> OrchestratorService:
    return OrchestratorService(
        safety_service=safety_service,
        scenario_service=scenario_service,
        generator_service=generator_service,
        critic_service=critic_service,
        history_store=history_store,
        chat_turn_dao=chat_turn_dao,
        settings=settings,
    )
