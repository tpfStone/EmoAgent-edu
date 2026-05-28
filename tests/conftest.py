import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    async def generate(
        self,
        prompt: str,
        timeout: float = 10.0,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        self.prompts.append(
            {
                "prompt": prompt,
                "timeout": timeout,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
        )
        if not self.responses:
            raise RuntimeError("No fake LLM responses left")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class RecordingSafetyLogDAO:
    def __init__(self):
        self.records = []

    async def create_log(self, **kwargs):
        self.records.append(kwargs)
        return kwargs


class RecordingCriticRunDAO:
    def __init__(self):
        self.records = []

    async def create_run(self, **kwargs):
        self.records.append(kwargs)
        return kwargs


@pytest.fixture
def fake_llm_client():
    return FakeLLMClient


@pytest.fixture
def safety_log_dao():
    return RecordingSafetyLogDAO()


@pytest.fixture
def critic_run_dao():
    return RecordingCriticRunDAO()


@pytest_asyncio.fixture
async def db_session():
    from app.database import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()
