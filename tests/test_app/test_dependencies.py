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
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "enabled",
    )

    assert client.model == "deepseek-v4-pro"
    assert client.thinking_type == "enabled"


def test_default_llm_client_uses_generator_model_and_thinking_mode():
    client = get_llm_client_cached(
        "deepseek",
        "test-key",
        "https://api.deepseek.com",
        "deepseek-v4-flash",
        "disabled",
    )

    assert client.model == "deepseek-v4-flash"
    assert client.thinking_type == "disabled"


def test_settings_default_to_flash_generator_and_v4_pro_critic():
    settings = Settings(_env_file=None)

    assert settings.DEEPSEEK_MODEL == "deepseek-v4-flash"
    assert settings.DEEPSEEK_THINKING == "disabled"
    assert settings.CRITIC_DEEPSEEK_MODEL == "deepseek-v4-pro"
    assert settings.CRITIC_DEEPSEEK_THINKING == "enabled"
    assert settings.CRITIC_LLM_MAX_TOKENS == 4096
    assert settings.CRITIC_LLM_RESPONSE_FORMAT_JSON is True
