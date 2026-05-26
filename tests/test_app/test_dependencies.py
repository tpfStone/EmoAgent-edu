from app.config import Settings
from app.dependencies import (
    get_critic_llm_client_cached,
    get_llm_client_cached,
)


def test_critic_llm_client_uses_critic_deepseek_model():
    client = get_critic_llm_client_cached(
        "deepseek",
        "test-key",
        "https://api.deepseek.com",
        "deepseek-chat",
        "deepseek-v4-pro",
    )

    assert client.model == "deepseek-v4-pro"


def test_default_llm_client_keeps_base_deepseek_model_for_generator_side():
    client = get_llm_client_cached(
        "deepseek",
        "test-key",
        "https://api.deepseek.com",
        "deepseek-chat",
    )

    assert client.model == "deepseek-chat"


def test_settings_default_to_v4_pro_for_critic_only():
    settings = Settings()

    assert settings.DEEPSEEK_MODEL == "deepseek-chat"
    assert settings.CRITIC_DEEPSEEK_MODEL == "deepseek-v4-pro"
    assert settings.CRITIC_LLM_MAX_TOKENS == 4096
    assert settings.CRITIC_LLM_RESPONSE_FORMAT_JSON is True
