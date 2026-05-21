from typing import Protocol

from redis.asyncio import Redis

from app.schemas.safety import ConversationMessage


class HistoryStoreProtocol(Protocol):
    async def get_history(
        self, session_id: str, max_messages: int
    ) -> list[ConversationMessage]: ...

    async def append_messages(
        self,
        session_id: str,
        messages: list[ConversationMessage],
        max_messages: int,
    ) -> None: ...


class InMemoryHistoryStore:
    def __init__(self):
        self._items: dict[str, list[ConversationMessage]] = {}

    async def get_history(
        self, session_id: str, max_messages: int
    ) -> list[ConversationMessage]:
        return list(self._items.get(session_id, [])[-max_messages:])

    async def append_messages(
        self,
        session_id: str,
        messages: list[ConversationMessage],
        max_messages: int,
    ) -> None:
        current = self._items.setdefault(session_id, [])
        current.extend(messages)
        self._items[session_id] = current[-max_messages:]


class RedisHistoryStore:
    def __init__(self, redis: Redis, ttl_seconds: int):
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"emoedu:history:{session_id}"

    async def get_history(
        self, session_id: str, max_messages: int
    ) -> list[ConversationMessage]:
        values = await self.redis.lrange(self._key(session_id), -max_messages, -1)
        return [ConversationMessage.model_validate_json(value) for value in values]

    async def append_messages(
        self,
        session_id: str,
        messages: list[ConversationMessage],
        max_messages: int,
    ) -> None:
        key = self._key(session_id)
        if messages:
            await self.redis.rpush(
                key, *[message.model_dump_json() for message in messages]
            )
        await self.redis.ltrim(key, -max_messages, -1)
        await self.redis.expire(key, self.ttl_seconds)
