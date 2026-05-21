import pytest

from app.config import Settings
from app.schemas.safety import ConversationMessage
from app.services.history_store import InMemoryHistoryStore


@pytest.mark.asyncio
async def test_in_memory_history_store_returns_recent_window():
    store = InMemoryHistoryStore()
    for index in range(8):
        await store.append_messages(
            "s1",
            [
                ConversationMessage(role="student", text=f"user-{index}"),
                ConversationMessage(role="assistant", text=f"assistant-{index}"),
            ],
            max_messages=12,
        )

    history = await store.get_history("s1", max_messages=12)

    assert len(history) == 12
    assert history[0].text == "user-2"
    assert history[-1].text == "assistant-7"


@pytest.mark.asyncio
async def test_in_memory_history_store_empty_session_returns_empty_list():
    store = InMemoryHistoryStore()

    history = await store.get_history("missing", max_messages=12)

    assert history == []


def test_chat_history_settings_have_runtime_defaults():
    settings = Settings()

    assert settings.REDIS_URL == "redis://localhost:6379/0"
    assert settings.CHAT_HISTORY_TTL_SECONDS == 60 * 60 * 24 * 7
    assert settings.CHAT_FALLBACK_MESSAGE
