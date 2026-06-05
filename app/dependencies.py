from functools import lru_cache

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dao.chat_turn_dao import ChatTurnDAO
from app.dao.critic_run_dao import CriticRunDAO
from app.dao.safety_log_dao import SafetyLogDAO
from app.database import get_db
from app.services.generator_service import GeneratorService
from app.services.critic_service import CriticService
from app.services.classifier_safety_gate_service import ClassifierSafetyGateService
from app.services.f1_safety_classifier import (
    F1SafetyClassifier,
    UnavailableF1SafetyClassifier,
    build_model_unavailable_message,
)
from app.services.f3_support_service import F3SupportService
from app.services.history_store import RedisHistoryStore
from app.services.llm_client import DeepSeekLLMClient, LLMClientProtocol, MockLLMClient
from app.services.memory_rag_service import MemoryRAGService
from app.services.orchestrator_service import OrchestratorService, SafetyGateProtocol
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
    deepseek_thinking: str,
    dashscope_api_key: str = "",
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    dashscope_model: str = "qwen3.7-plus",
    dashscope_thinking: str = "disabled",
) -> LLMClientProtocol:
    normalized = provider.lower()
    if normalized == "deepseek":
        return DeepSeekLLMClient(
            api_key=deepseek_api_key,
            base_url=deepseek_base_url,
            model=deepseek_model,
            thinking_type=deepseek_thinking,
        )
    if normalized in {"dashscope", "qwen"}:
        return DeepSeekLLMClient(
            api_key=dashscope_api_key,
            base_url=dashscope_base_url,
            model=dashscope_model,
            thinking_type=dashscope_thinking,
            extra_body_style="dashscope-qwen",
        )
    if normalized in {"dashscope-deepseek", "deepseek-dashscope"}:
        return DeepSeekLLMClient(
            api_key=dashscope_api_key,
            base_url=dashscope_base_url,
            model=dashscope_model,
            thinking_type=dashscope_thinking,
            extra_body_style="dashscope-deepseek",
        )
    return MockLLMClient()


@lru_cache
def get_critic_llm_client_cached(
    provider: str,
    deepseek_api_key: str,
    deepseek_base_url: str,
    deepseek_model: str,
    critic_deepseek_model: str,
    critic_deepseek_thinking: str,
    dashscope_api_key: str = "",
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    dashscope_model: str = "qwen3.7-plus",
    critic_dashscope_model: str = "qwen3.7-plus",
    critic_dashscope_thinking: str = "disabled",
) -> LLMClientProtocol:
    normalized = provider.lower()
    if normalized == "deepseek":
        return DeepSeekLLMClient(
            api_key=deepseek_api_key,
            base_url=deepseek_base_url,
            model=critic_deepseek_model or deepseek_model,
            thinking_type=critic_deepseek_thinking,
        )
    if normalized in {"dashscope", "qwen"}:
        return DeepSeekLLMClient(
            api_key=dashscope_api_key,
            base_url=dashscope_base_url,
            model=critic_dashscope_model or dashscope_model,
            thinking_type=critic_dashscope_thinking,
            extra_body_style="dashscope-qwen",
        )
    if normalized in {"dashscope-deepseek", "deepseek-dashscope"}:
        return DeepSeekLLMClient(
            api_key=dashscope_api_key,
            base_url=dashscope_base_url,
            model=critic_dashscope_model or dashscope_model,
            thinking_type=critic_dashscope_thinking,
            extra_body_style="dashscope-deepseek",
        )
    return MockLLMClient()


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMClientProtocol:
    return get_llm_client_cached(
        settings.LLM_PROVIDER,
        settings.DEEPSEEK_API_KEY,
        settings.DEEPSEEK_BASE_URL,
        settings.DEEPSEEK_MODEL,
        settings.DEEPSEEK_THINKING,
        settings.DASHSCOPE_API_KEY,
        settings.DASHSCOPE_BASE_URL,
        settings.DASHSCOPE_MODEL,
        settings.DASHSCOPE_THINKING,
    )


def get_critic_llm_client(
    settings: Settings = Depends(get_settings),
) -> LLMClientProtocol:
    return get_critic_llm_client_cached(
        settings.LLM_PROVIDER,
        settings.DEEPSEEK_API_KEY,
        settings.DEEPSEEK_BASE_URL,
        settings.DEEPSEEK_MODEL,
        settings.CRITIC_DEEPSEEK_MODEL,
        settings.CRITIC_DEEPSEEK_THINKING,
        settings.DASHSCOPE_API_KEY,
        settings.DASHSCOPE_BASE_URL,
        settings.DASHSCOPE_MODEL,
        settings.CRITIC_DASHSCOPE_MODEL,
        settings.CRITIC_DASHSCOPE_THINKING,
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


@lru_cache
def get_f1_safety_classifier_cached(
    model_dir: str,
    bert_model_name: str,
    max_length: int,
    red_threshold: float,
    yellow_or_red_threshold: float,
    local_files_only: bool,
    device: str,
) -> F1SafetyClassifier:
    return F1SafetyClassifier(
        model_dir=model_dir,
        bert_model_name=bert_model_name,
        max_length=max_length,
        red_threshold=red_threshold,
        yellow_or_red_threshold=yellow_or_red_threshold,
        local_files_only=local_files_only,
        device=device,
    )


def get_f1_safety_classifier(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> F1SafetyClassifier | UnavailableF1SafetyClassifier:
    classifier = getattr(request.app.state, "f1_safety_classifier", None)
    if classifier is None:
        try:
            classifier = get_f1_safety_classifier_cached(
                settings.F1_SAFETY_MODEL_DIR,
                settings.F1_SAFETY_BERT_MODEL,
                settings.F1_SAFETY_MAX_LENGTH,
                settings.F1_SAFETY_RED_THRESHOLD,
                settings.F1_SAFETY_YELLOW_OR_RED_THRESHOLD,
                settings.F1_SAFETY_LOCAL_FILES_ONLY,
                settings.F1_SAFETY_DEVICE,
            )
        except Exception as exc:
            message = build_model_unavailable_message(
                settings.F1_SAFETY_MODEL_DIR,
                settings.F1_SAFETY_HF_REPO,
                settings.F1_SAFETY_HF_REVISION,
            )
            if settings.F1_SAFETY_REQUIRED:
                raise RuntimeError(message) from exc
            classifier = UnavailableF1SafetyClassifier(message)
        request.app.state.f1_safety_classifier = classifier
    return classifier


def get_safety_gate_service(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    safety_log_dao: SafetyLogDAO = Depends(get_safety_log_dao),
    settings: Settings = Depends(get_settings),
) -> SafetyGateService:
    return SafetyGateService(llm_client, safety_log_dao, settings)


def get_classifier_safety_gate_service(
    safety_classifier=Depends(get_f1_safety_classifier),
    safety_log_dao: SafetyLogDAO = Depends(get_safety_log_dao),
    settings: Settings = Depends(get_settings),
) -> ClassifierSafetyGateService:
    return ClassifierSafetyGateService(safety_classifier, safety_log_dao, settings)


def get_scenario_service(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    settings: Settings = Depends(get_settings),
) -> ScenarioService:
    return ScenarioService(llm_client, settings)


@lru_cache
def get_f3_support_service_cached(
    support_enable: bool,
    data_path: str,
    top_k: int,
    min_score: float,
) -> F3SupportService:
    return F3SupportService(
        Settings(
            F3_SUPPORT_ENABLE=support_enable,
            F3_PSYQA_LABELLED_PATH=data_path,
            F3_SUPPORT_TOP_K=top_k,
            F3_SUPPORT_MIN_SCORE=min_score,
        )
    )


def get_f3_support_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> F3SupportService:
    support_service = getattr(request.app.state, "f3_support_service", None)
    if support_service is None:
        support_service = get_f3_support_service_cached(
            settings.F3_SUPPORT_ENABLE,
            settings.F3_PSYQA_LABELLED_PATH,
            settings.F3_SUPPORT_TOP_K,
            settings.F3_SUPPORT_MIN_SCORE,
        )
        request.app.state.f3_support_service = support_service
    return support_service


@lru_cache
def get_memory_rag_service_cached(
    memory_enable: bool,
    persist_dir: str,
    embedding_model: str,
    minilm_path: str,
    top_k: int,
    min_score: float,
    cache_ttl_seconds: int,
    cache_max_entries: int,
    cache_semantic_threshold: float,
) -> MemoryRAGService:
    return MemoryRAGService(
        Settings(
            F6_MEMORY_ENABLE=memory_enable,
            F6_MEMORY_PERSIST_DIR=persist_dir,
            F6_MEMORY_EMBEDDING_MODEL=embedding_model,
            F6_MEMORY_MINILM_PATH=minilm_path,
            F6_MEMORY_TOP_K=top_k,
            F6_MEMORY_MIN_SCORE=min_score,
            F6_RAG_CACHE_TTL_SECONDS=cache_ttl_seconds,
            F6_RAG_CACHE_MAX_ENTRIES=cache_max_entries,
            F6_RAG_CACHE_SEMANTIC_THRESHOLD=cache_semantic_threshold,
        )
    )


def get_memory_rag_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> MemoryRAGService:
    memory_service = getattr(request.app.state, "memory_rag_service", None)
    if memory_service is None:
        memory_service = get_memory_rag_service_cached(
            settings.F6_MEMORY_ENABLE,
            settings.F6_MEMORY_PERSIST_DIR,
            settings.F6_MEMORY_EMBEDDING_MODEL,
            settings.F6_MEMORY_MINILM_PATH,
            settings.F6_MEMORY_TOP_K,
            settings.F6_MEMORY_MIN_SCORE,
            settings.F6_RAG_CACHE_TTL_SECONDS,
            settings.F6_RAG_CACHE_MAX_ENTRIES,
            settings.F6_RAG_CACHE_SEMANTIC_THRESHOLD,
        )
        request.app.state.memory_rag_service = memory_service
    return memory_service


def get_generator_service(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    f3_support_service: F3SupportService = Depends(get_f3_support_service),
    settings: Settings = Depends(get_settings),
) -> GeneratorService:
    return GeneratorService(llm_client, settings, f3_support_service)


def get_generator_service_without_f3_support(
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    settings: Settings = Depends(get_settings),
) -> GeneratorService:
    return GeneratorService(llm_client, settings, None)


def get_critic_service(
    llm_client: LLMClientProtocol = Depends(get_critic_llm_client),
    critic_run_dao: CriticRunDAO = Depends(get_critic_run_dao),
    settings: Settings = Depends(get_settings),
) -> CriticService:
    return CriticService(llm_client, critic_run_dao, settings)


def get_chat_safety_gate_service(
    safety_classifier=Depends(get_f1_safety_classifier),
    llm_client: LLMClientProtocol = Depends(get_llm_client),
    settings: Settings = Depends(get_settings),
) -> SafetyGateProtocol:
    if isinstance(safety_classifier, UnavailableF1SafetyClassifier):
        return SafetyGateService(llm_client, None, settings)
    return ClassifierSafetyGateService(safety_classifier, None, settings)


def get_chat_critic_service(
    llm_client: LLMClientProtocol = Depends(get_critic_llm_client),
    settings: Settings = Depends(get_settings),
) -> CriticService:
    return CriticService(llm_client, None, settings)


def get_orchestrator_service(
    safety_service: SafetyGateProtocol = Depends(get_chat_safety_gate_service),
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
