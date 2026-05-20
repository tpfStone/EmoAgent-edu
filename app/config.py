from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://emoedu_user:password@localhost:5432/emoedu"

    LLM_PROVIDER: str = "mock"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT: float = 10.0
    LLM_MAX_TOKENS: int = 1000

    HISTORY_WINDOW_N: int = 6
    SAFETY_LLM_TEMPERATURE: float = 0.0
    CRITIC_LLM_TEMPERATURE: float = 0.1
    CRITIC_SAMPLE_COUNT: int = Field(default=3, ge=1)

    API_TITLE: str = "EmoEdu F1/F4 API"
    API_VERSION: str = "0.1.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
