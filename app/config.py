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
    LLM_TIMEOUT: float = 10.0
    LLM_MAX_TOKENS: int = 1000
    CRITIC_LLM_MAX_TOKENS: int = 4096

    HISTORY_WINDOW_N: int = 6
    REDIS_URL: str = "redis://localhost:6379/0"
    CHAT_HISTORY_TTL_SECONDS: int = 60 * 60 * 24 * 7
    CHAT_FALLBACK_MESSAGE: str = "我现在有点没反应过来，要不你再说一次？"
    SAFETY_LLM_TEMPERATURE: float = 0.0
    SCENARIO_LLM_TEMPERATURE: float = 0.0
    GENERATOR_LLM_TEMPERATURE: float = 0.8
    CRITIC_LLM_TEMPERATURE: float = 0.1
    CRITIC_LLM_RESPONSE_FORMAT_JSON: bool = True
    CRITIC_SAMPLE_COUNT: int = Field(default=3, ge=1)

    API_TITLE: str = "EmoEdu MAS API"
    API_VERSION: str = "0.1.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
