# Orchestrator MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first `/chat` orchestration layer that runs F1/F2/F3/F4 end to end, records a coherent MVP turn log, and maintains session history.

**Architecture:** `/chat` depends on in-process service instances, not internal HTTP calls. The chat path writes one aggregate record for the whole turn, while standalone module endpoints may keep their existing module logs. History is managed behind a store interface with Redis for runtime and an in-memory test double for unit tests.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async, Alembic, SQLite for current local development, PostgreSQL as the target production database, Redis async client for runtime history.

---

## Decisions From Context

- Add Redis dependency and a dedicated history component. F1-F4 already accept `history`, but no component currently loads or appends history by `session_id`.
- Keep SQLite usable now, and keep PostgreSQL as the future target. Do not remove Alembic. Use Alembic to evolve both SQLite local schema and future PostgreSQL schema.
- Resolve data model mismatch by adding MVP aggregate tables: `sessions`, `messages`, `turns`, `candidates`, `preference_pairs`. Keep existing `safety_gate_logs`, `critic_runs`, and `critic_candidate_scores` unless a later cleanup explicitly removes them.
- Defer 45-corpus manual classification and response review. Record that validation work in `docs/issues/` so it is visible but not blocking orchestrator implementation.
- Implement `/chat` by depending on service instances directly. Do not call `/api/safety`, `/api/scenario`, `/api/generator`, or `/api/critic` over HTTP from inside the same process.
- For `/chat`, prefer unified logging in the orchestrator. To avoid duplicate logs, create chat-specific service dependencies that pass `None` DAOs into F1/F4 services.
- Non-green F1 output is recorded as context. It returns the fixed F1 `referral_message`, appends both the user message and assistant referral to history, and does not call F2/F3/F4.
- Even with unified logging, module failure format still matters. Store `status`, `failed_module`, `failure_reason`, and `fallback_message` on the turn so debugging remains possible.
- F1 non-green and F4 all-boundary are separate branches. F1 yellow/red returns fixed referral text. F4 all-boundary returns the critic fallback or a general safe fallback.
- F4 CASEL weighting needs one guardrail before `/chat` depends on it. Current repo behavior uses `ER + IP + EX + 0.5 * sum(casel_scores)`, which matches the written F4 spec but lets CASEL contribution grow with the number of activated dimensions. Update F4 to use a bounded auxiliary bonus: `ER + IP + EX + 0.5 * mean(casel_scores)` when CASEL is non-empty, otherwise EPITOME-only. This keeps EPITOME dominant while preserving CASEL as a tie/near-tie signal.
- Keep CASEL scoring inside the same judge call for MVP. The current repo spec already chooses the merged prompt to reduce latency and cost. Add a rollback marker: if F9 reliability validation later shows unstable EPITOME or CASEL scoring, split CASEL scoring into a second judge call.

## File Structure

- Modify `requirements.txt`
  - Add Redis async client dependency.
- Modify `app/services/critic_service.py`
  - Bound CASEL contribution by averaging activated CASEL scores before applying the auxiliary weight.
- Modify `docs/specs/f4-critic-epitome-codex-spec.md`
  - Update the scoring formula from per-dimension CASEL sum to bounded CASEL mean.
- Modify `app/config.py`
  - Add `REDIS_URL`, `CHAT_HISTORY_TTL_SECONDS`, and chat fallback config.
- Create `app/services/history_store.py`
  - Define `HistoryStoreProtocol`, `RedisHistoryStore`, and `InMemoryHistoryStore`.
- Modify `app/dependencies.py`
  - Add history store provider.
  - Add chat-specific service providers with DAOs disabled for unified `/chat` logging.
  - Add orchestrator provider.
- Create `app/schemas/chat.py`
  - Define `/chat` request and response models.
- Modify `app/models/models.py`
  - Add aggregate MVP models for sessions, messages, turns, candidates, preference pairs.
- Create Alembic revision `alembic/versions/20260521_0002_mvp_chat_tables.py`
  - Add aggregate tables.
- Modify `alembic/env.py`
  - Convert async DB URLs to sync migration URLs for both PostgreSQL and SQLite.
- Create `app/dao/chat_turn_dao.py`
  - Persist one coherent `/chat` turn, candidates, preference pair, and messages.
- Create `app/services/orchestrator_service.py`
  - Implement F1 -> F2 -> F3 -> F4 flow, short-circuiting, fallback, history append, and unified persistence.
- Create `app/handlers/chat_handler.py`
  - Expose `POST /chat`.
- Modify `app/main.py`
  - Include chat router.
- Create tests:
  - `tests/test_services/test_critic_service.py`
  - `tests/test_services/test_history_store.py`
  - `tests/test_services/test_orchestrator_service.py`
  - `tests/test_handlers/test_chat_handler.py`
  - `tests/test_dao/test_chat_turn_dao.py`
  - `tests/test_alembic_env.py`
- Modify `docs/issues/2026-05-20-f1-f4-development-issues.md` or add `docs/acceptance/orchestrator-mvp/2026-05-21/2026-05-21-orchestrator-deferred-validation.md`
  - Record deferred 45-corpus validation and manual review.

---

### Pre-Task A: Bound F4 CASEL Weighting

**Files:**
- Modify: `app/services/critic_service.py`
- Modify: `tests/test_services/test_critic_service.py`
- Modify: `docs/specs/f4-critic-epitome-codex-spec.md`

- [ ] **Step 1: Update CASEL weighting tests**

In `tests/test_services/test_critic_service.py`, update the existing non-empty CASEL total assertion from the sum-based value to the mean-based value:

```python
assert response.scores[0].weighted_total == 3.75
```

For the existing winner test where both candidates have the same EPITOME score and candidate 2 has two CASEL scores of `2`, update:

```python
assert response.scores[0].weighted_total == 3.0
assert response.scores[1].weighted_total == 4.0
assert response.best_candidate_id == "c2"
```

Add a single-dimension CASEL regression test:

```python
@pytest.mark.asyncio
async def test_single_activated_casel_dimension_uses_mean_without_edge_case(
    fake_llm_client,
):
    llm = fake_llm_client(
        [_score(1, 1, 1, casel={"自我觉察引导": 2})]
    )
    service = CriticService(llm, None, Settings(CRITIC_SAMPLE_COUNT=1))

    response = await service.evaluate(
        _request(
            [_candidate("c1", "听起来你很难受，也能感觉到你在努力撑着。")],
            activated_casel=["自我觉察引导"],
        )
    )

    assert response.scores[0].casel == {"自我觉察引导": 2}
    assert response.scores[0].weighted_total == 4.0
```

The empty CASEL test should remain EPITOME-only and should not divide by zero.

- [ ] **Step 2: Run tests to verify current behavior fails**

Run:

```powershell
python -m pytest tests/test_services/test_critic_service.py -q
```

Expected: FAIL on the updated weighted-total assertions because current code still uses `sum(casel.values())`.

- [ ] **Step 3: Implement bounded CASEL bonus**

In `app/services/critic_service.py`, replace:

```python
CASEL_WEIGHT = 0.5
```

with:

```python
CASEL_TOTAL_WEIGHT = 0.5
```

Add:

```python
@staticmethod
def _casel_bonus(casel: dict[str, int]) -> float:
    if not casel:
        return 0.0
    return CASEL_TOTAL_WEIGHT * (sum(casel.values()) / len(casel))
```

Replace the weighted total calculation with:

```python
weighted_total = float(er + ip + ex + self._casel_bonus(casel))
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/test_services/test_critic_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Update F4 spec**

In `docs/specs/f4-critic-epitome-codex-spec.md`, replace the CASEL scoring formula text with:

```markdown
- **加权总分** = ER + IP + EX + CASEL_TOTAL_WEIGHT * mean(casel_scores)
- **初始权重**：EPITOME 三维各权重 = 1.0；CASEL 辅助维作为整体平均 bonus 计入，`CASEL_TOTAL_WEIGHT = 0.5`。当 `activated_casel=[]` 时，CASEL bonus = 0，保持 EPITOME-only 行为。
```

Also add a note:

```markdown
CASEL 是辅助项，不应随激活维度数量线性膨胀；因此对已激活 CASEL 分数取平均后再加权。
```

- [ ] **Step 6: Record the prompt-splitting rollback marker**

Add this note to `docs/acceptance/orchestrator-mvp/2026-05-21/2026-05-21-orchestrator-deferred-validation.md` in Task 7:

```markdown
F4 judge prompt rollback marker:
- MVP keeps EPITOME and CASEL scoring in one judge call for lower latency and cost.
- If F9 reliability validation shows unstable EPITOME/CASEL scoring, split CASEL into a second judge call and compare agreement.
```

---

### Task 1: Add Config and Redis Dependency

**Files:**
- Modify: `requirements.txt`
- Modify: `app/config.py`
- Test: `tests/test_services/test_history_store.py`

- [ ] **Step 1: Add Redis dependency**

Add this line to `requirements.txt`:

```text
redis>=5.2.0
```

- [ ] **Step 2: Add settings**

Add these fields to `Settings` in `app/config.py`:

```python
    REDIS_URL: str = "redis://localhost:6379/0"
    CHAT_HISTORY_TTL_SECONDS: int = 60 * 60 * 24 * 7
    CHAT_FALLBACK_MESSAGE: str = "我现在有点没反应过来，要不你再说一次？"
```

- [ ] **Step 3: Run tests**

Run:

```powershell
python -m pytest tests -q
```

Expected: existing tests still pass.

---

### Task 2: Create History Store

**Files:**
- Create: `app/services/history_store.py`
- Test: `tests/test_services/test_history_store.py`

- [ ] **Step 1: Write tests**

Create tests that verify:

```python
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
```

Also verify empty sessions return `[]`.

- [ ] **Step 2: Implement store**

Create `app/services/history_store.py` with:

```python
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
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
python -m pytest tests/test_services/test_history_store.py -q
```

Expected: PASS.

---

### Task 3: Add MVP Aggregate Data Model

**Files:**
- Modify: `app/models/models.py`
- Create: `alembic/versions/20260521_0002_mvp_chat_tables.py`
- Modify: `alembic/env.py`
- Test: `tests/test_alembic_env.py`

- [ ] **Step 1: Add URL conversion helper**

In `alembic/env.py`, add:

```python
def to_sync_database_url(url: str) -> str:
    return (
        url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        .replace("sqlite+aiosqlite://", "sqlite://")
    )
```

Use it in both offline and online migration paths:

```python
url=to_sync_database_url(settings.DATABASE_URL)
section["sqlalchemy.url"] = to_sync_database_url(settings.DATABASE_URL)
```

- [ ] **Step 2: Test URL conversion**

Create `tests/test_alembic_env.py`:

```python
from alembic.env import to_sync_database_url


def test_to_sync_database_url_converts_async_postgres():
    assert (
        to_sync_database_url("postgresql+asyncpg://u:p@localhost/db")
        == "postgresql+psycopg2://u:p@localhost/db"
    )


def test_to_sync_database_url_converts_async_sqlite():
    assert (
        to_sync_database_url("sqlite+aiosqlite:///./local-dev.sqlite")
        == "sqlite:///./local-dev.sqlite"
    )
```

- [ ] **Step 3: Add models**

Add SQLAlchemy models with table names exactly:

```python
class ChatSession(Base):
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ChatMessage(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ChatTurn(Base):
    __tablename__ = "turns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    scenario: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activated_casel: Mapped[list[str]] = mapped_column(SQLAlchemyJSON, nullable=False, default=list)
    best_candidate_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failed_module: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fallback_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
```

Add `ChatCandidate` and `ChatPreferencePair` matching the roadmap fields.

- [ ] **Step 4: Add Alembic migration**

Create `20260521_0002_mvp_chat_tables.py` that creates `sessions`, `messages`, `turns`, `candidates`, and `preference_pairs` with foreign keys and indexes on `session_id`, `turn_id`, and `candidate_id`.

- [ ] **Step 5: Run migration on SQLite**

Run:

```powershell
python -m alembic upgrade head
```

Expected: migration succeeds against current SQLite URL.

---

### Task 4: Add Chat DAO

**Files:**
- Create: `app/dao/chat_turn_dao.py`
- Test: `tests/test_dao/test_chat_turn_dao.py`

- [ ] **Step 1: Write DAO tests**

Test three paths:

```python
async def test_chat_turn_dao_records_blocked_turn(db_session):
    dao = ChatTurnDAO(db_session)
    turn = await dao.create_turn(
        session_id="s1",
        user_message="我不想存在了",
        assistant_message="fixed referral",
        status="blocked_by_safety",
        risk_level="yellow",
        scenario=None,
        activated_casel=[],
        candidates=[],
        scores=[],
        best_candidate_id=None,
        preference_pair=None,
        failed_module=None,
        failure_reason="",
        fallback_message="",
    )

    assert turn.status == "blocked_by_safety"
```

Also test `answered` with two candidates and `module_failed` with failure metadata.

- [ ] **Step 2: Implement DAO**

Implement `ChatTurnDAO.create_turn(...)` so it:

- Upserts `sessions` by `session_id`.
- Inserts `messages` for user and assistant text.
- Inserts one `turns` row.
- Inserts candidate rows when candidate and score data exist.
- Inserts one preference pair when present.
- Commits once.

- [ ] **Step 3: Run DAO tests**

Run:

```powershell
python -m pytest tests/test_dao/test_chat_turn_dao.py -q
```

Expected: PASS.

---

### Task 5: Add Chat Schema and Orchestrator

**Files:**
- Create: `app/schemas/chat.py`
- Create: `app/services/orchestrator_service.py`
- Test: `tests/test_services/test_orchestrator_service.py`

- [ ] **Step 1: Define schema**

Create:

```python
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.critic import CandidateScore, PreferencePair
from app.schemas.generator import GeneratorCandidate
from app.schemas.scenario import ScenarioLabel


ChatStatus = Literal[
    "answered",
    "blocked_by_safety",
    "all_candidates_blocked",
    "module_failed",
]


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    current_message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    session_id: str
    status: ChatStatus
    reply_text: str
    risk_level: Literal["green", "yellow", "red"]
    scenario: ScenarioLabel | None = None
    activated_casel: list[str] = Field(default_factory=list)
    best_candidate_id: str | None = None
    candidates: list[GeneratorCandidate] = Field(default_factory=list)
    scores: list[CandidateScore] = Field(default_factory=list)
    preference_pair: PreferencePair | None = None
    failed_module: str | None = None
    failure_reason: str = ""
```

- [ ] **Step 2: Write orchestrator tests**

Cover these cases:

- Green happy path calls F1/F2/F3/F4 in order, returns selected candidate text, records turn, appends history.
- Yellow/red F1 returns fixed referral, does not call F2/F3/F4, records and appends history.
- F4 all candidates blocked returns critic fallback and records `all_candidates_blocked`.
- Any unexpected module exception returns `CHAT_FALLBACK_MESSAGE`, records `module_failed`, and appends fallback as assistant history.

- [ ] **Step 3: Implement orchestrator**

Core flow:

```python
history = await history_store.get_history(
    request.session_id, settings.HISTORY_WINDOW_N * 2
)
safety = await safety_service.evaluate(
    SafetyGateRequest(
        session_id=request.session_id,
        current_message=request.current_message,
        history=history,
    )
)
if safety.action.block_generation:
    reply_text = safety.action.referral_message
    status = "blocked_by_safety"
    # persist and append history, then return
```

For green path:

```python
scenario = await scenario_service.analyze(...)
generated = await generator_service.generate(..., rag_examples=[])
critic = await critic_service.evaluate(...)
```

Select reply:

```python
if critic.best_candidate_id is None:
    status = "all_candidates_blocked"
    reply_text = critic.fallback_message or settings.CHAT_FALLBACK_MESSAGE
else:
    status = "answered"
    reply_text = next(
        candidate.text
        for candidate in generated.candidates
        if candidate.candidate_id == critic.best_candidate_id
    )
```

Append history after deciding reply:

```python
await history_store.append_messages(
    request.session_id,
    [
        ConversationMessage(role="student", text=request.current_message),
        ConversationMessage(role="assistant", text=reply_text),
    ],
    settings.HISTORY_WINDOW_N * 2,
)
```

- [ ] **Step 4: Run orchestrator tests**

Run:

```powershell
python -m pytest tests/test_services/test_orchestrator_service.py -q
```

Expected: PASS.

---

### Task 6: Wire FastAPI Endpoint

**Files:**
- Modify: `app/dependencies.py`
- Create: `app/handlers/chat_handler.py`
- Modify: `app/main.py`
- Test: `tests/test_handlers/test_chat_handler.py`

- [ ] **Step 1: Add dependencies**

Add:

```python
def get_chat_safety_gate_service(...):
    return SafetyGateService(llm_client, None, settings)


def get_chat_critic_service(...):
    return CriticService(llm_client, None, settings)
```

Keep existing `get_safety_gate_service` and `get_critic_service` for standalone module endpoints.

- [ ] **Step 2: Add route**

Create `app/handlers/chat_handler.py`:

```python
from fastapi import APIRouter, Depends

from app.dependencies import get_orchestrator_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
) -> ChatResponse:
    return await orchestrator_service.chat(request)
```

- [ ] **Step 3: Include router**

Modify `app/main.py`:

```python
from app.handlers import chat_handler, critic_handler, generator_handler, safety_handler, scenario_handler

app.include_router(chat_handler.router)
```

- [ ] **Step 4: Test endpoint**

Use FastAPI dependency overrides to inject a fake orchestrator and assert `POST /chat` returns response JSON.

Run:

```powershell
python -m pytest tests/test_handlers/test_chat_handler.py -q
```

Expected: PASS.

---

### Task 7: Record Deferred Validation

**Files:**
- Create: `docs/acceptance/orchestrator-mvp/2026-05-21/2026-05-21-orchestrator-deferred-validation.md`

- [ ] **Step 1: Add issue note**

Create the issue note with:

```markdown
# Orchestrator Deferred Validation

> Date: 2026-05-21

The first `/chat` orchestrator implementation will not block on manual corpus validation.

Deferred checks:
- Run F2 against `docs/corpus/emoedu-corpus-45-samples.json` and record scenario accuracy.
- Run `/chat` over the 45 samples after mock E2E passes.
- Manually review response reasonableness and inspect persisted `turns`, `candidates`, and `preference_pairs`.

Reason:
- The roadmap lists these as validation and acceptance work.
- They should not block building the orchestrator wiring, history management, or aggregate persistence.

F4 judge prompt rollback marker:
- MVP keeps EPITOME and CASEL scoring in one judge call for lower latency and cost.
- If F9 reliability validation shows unstable EPITOME/CASEL scoring, split CASEL into a second judge call and compare agreement.
```

---

### Task 8: Final Verification

**Files:**
- No new files

- [ ] **Step 1: Run full tests**

Run:

```powershell
python -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run Alembic migration**

Run:

```powershell
python -m alembic upgrade head
```

Expected: succeeds against current SQLite development database.

- [ ] **Step 3: Manual smoke test**

Start the API:

```powershell
uvicorn app.main:app --reload
```

Send:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType "application/json" -Body '{"session_id":"smoke-1","current_message":"这次月考没考好，心情很差"}'
```

Expected:
- JSON response has `status`.
- `risk_level` is present.
- If mock provider returns green, response continues through F2/F3/F4.
- SQLite contains a row in `turns` and matching rows in `messages`.

## Self-Review

- Spec coverage: `/chat`, F1 short-circuit, Redis history, unified logging, data model alignment, SQLite/Alembic continuity, bounded F4 CASEL weighting, F4 all-boundary fallback, judge prompt rollback marker, and deferred 45-corpus validation are covered.
- Placeholder scan: no implementation step uses "TBD" or an unspecified error handling placeholder.
- Type consistency: `ChatRequest.current_message`, `ConversationMessage(role="student"|"assistant")`, `risk_level`, `activated_casel`, `best_candidate_id`, and `preference_pair` match current F1-F4 schemas.
