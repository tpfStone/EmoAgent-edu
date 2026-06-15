from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://emoedu_user:password@localhost:5432/emoedu"

    LLM_PROVIDER: str = "mock"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    DEEPSEEK_THINKING: str = "disabled"
    CRITIC_DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    CRITIC_DEEPSEEK_THINKING: str = "enabled"
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_MODEL: str = "qwen3.7-plus"
    DASHSCOPE_THINKING: str = "disabled"
    CRITIC_DASHSCOPE_MODEL: str = "qwen3.7-plus"
    CRITIC_DASHSCOPE_THINKING: str = "disabled"
    LLM_TIMEOUT: float = 10.0
    LLM_MAX_TOKENS: int = 1000
    CRITIC_LLM_MAX_TOKENS: int = 4096

    HISTORY_WINDOW_N: int = 6
    F1_SAFETY_MODEL_DIR: str = "exp/models/f1_safety_gate/manual-A-pattern-v1"
    F1_SAFETY_BERT_MODEL: str = "bert-base-chinese"
    F1_SAFETY_LOCAL_FILES_ONLY: bool = True
    F1_SAFETY_DEVICE: str = "auto"
    F1_SAFETY_MAX_LENGTH: int = 192
    F1_SAFETY_RED_THRESHOLD: float = 0.45
    F1_SAFETY_YELLOW_OR_RED_THRESHOLD: float = 0.55
    F1_SAFETY_PRELOAD: bool = True
    F1_SAFETY_REQUIRED: bool = False
    F1_SAFETY_HF_REPO: str = "Nacgisac/EmoEduF1-bert-base-chinese"
    F1_SAFETY_HF_REVISION: str = "main"
    F3_SUPPORT_ENABLE: bool = True
    F3_SUPPORT_PRELOAD: bool = True
    F3_PSYQA_LABELLED_PATH: str = "exp/data/psyqa_labelled.json"
    F3_SUPPORT_TOP_K: int = Field(default=2, ge=0, le=5)
    F3_SUPPORT_MIN_SCORE: float = Field(default=0.10, ge=0.0, le=1.0)
    F6_MEMORY_ENABLE: bool = False
    F6_MEMORY_PRELOAD: bool = False
    F6_MEMORY_PERSIST_DIR: str = "exp/data/vector_store/faiss_memory"
    F6_MEMORY_EMBEDDING_MODEL: str = "hashing"
    F6_MEMORY_MINILM_PATH: str = "exp/models/embeddings/all-MiniLM-L6-v2"
    F6_MEMORY_TOP_K: int = Field(default=3, ge=0, le=8)
    F6_MEMORY_MIN_SCORE: float = Field(default=0.15, ge=0.0, le=1.0)
    F6_RAG_CACHE_TTL_SECONDS: int = 900
    F6_RAG_CACHE_MAX_ENTRIES: int = 512
    F6_RAG_CACHE_SEMANTIC_THRESHOLD: float = Field(default=0.9, ge=0.0, le=1.0)
    REDIS_URL: str = "redis://localhost:6379/0"
    CHAT_HISTORY_TTL_SECONDS: int = 60 * 60 * 24 * 7
    CHAT_STREAM_CHUNK_SIZE: int = Field(default=2, ge=1, le=12)
    CHAT_FALLBACK_MESSAGE: str = "我现在有点没反应过来，要不你再说一次？"
    SAFETY_LLM_TEMPERATURE: float = 0.0
    SCENARIO_LLM_TEMPERATURE: float = 0.0
    GENERATOR_LLM_TEMPERATURE: float = 0.8
    CRITIC_LLM_TEMPERATURE: float = 0.1
    CRITIC_LLM_RESPONSE_FORMAT_JSON: bool = True
    CRITIC_SAMPLE_COUNT: int = Field(default=3, ge=1)
    ROUTE_SELECTOR_MIN_WEIGHTED_TOTAL: float = Field(default=3.0, ge=0.0)

    API_TITLE: str = "EmoEdu F1/F4 API"
    API_VERSION: str = "0.1.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
