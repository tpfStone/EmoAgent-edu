# Backend Infrastructure Smoke Acceptance - 2026-05-26

> **历史验收记录**：本文件记录当时验收口径和实跑结果，不代表当前 `/chat` 默认 runtime。当前主链路以入口 README、`docs/specs/README.md` 和 `exp/README.md` 为准。

## Scope

This run validates the backend infrastructure gate that was present in the archived 2026-05-21 `/chat` MVP plan but missing from the current post-MVP planning path.

- PostgreSQL / Alembic migration smoke test
- Redis history store smoke test
- `/chat` orchestrator integration regression with `LLM_PROVIDER=mock`

No public API, schema, business logic, or checked-in `.env` values were changed for this run. Runtime configuration was provided through process-scoped environment variables.

## Environment

- Workspace: `D:\projects\EmoAgent-edu`
- Git branch: `feat/corpus-preference-pipeline`
- Python: `.venv\Scripts\python.exe`
- PostgreSQL: temporary Docker container `emoedu-postgres-smoke`, image `postgres:16-alpine`, database `emoedu_smoke`
- Redis: existing local Redis on `redis://127.0.0.1:6379/0`, container `emoedu-redis`
- LLM: `LLM_PROVIDER=mock`

The PostgreSQL smoke database used:

```text
DATABASE_URL=postgresql+asyncpg://emoedu_user:<redacted>@127.0.0.1:5432/emoedu_smoke
```

## Results

| Gate | Result | Evidence |
| --- | --- | --- |
| PostgreSQL readiness | PASS | `asyncpg` `select 1` returned `postgres_ready=1` |
| Alembic migration | PASS | `python -m alembic upgrade head` ran `20260520_0001` then `20260521_0002` using `PostgresqlImpl` |
| Alembic current | PASS | `python -m alembic current` returned `20260521_0002 (head)` |
| Core table inspection | PASS | `sessions`, `messages`, `turns`, `candidates`, `preference_pairs` all present |
| Redis history store | PASS | Windowed history length `6`, first text `user-1`, last text `assistant-3`, TTL positive |
| Existing `/chat` regression | PASS | `python -m pytest tests/test_handlers/test_chat_handler.py tests/test_services/test_orchestrator_service.py -q` returned `5 passed` |
| Live ASGI `/chat` smoke | PASS | HTTP `200`, response contained `session_id`, `status`, `reply_text`, `risk_level`; status `answered`, risk `green` |
| `/chat` Redis persistence | PASS | Smoke session Redis history contained `2` messages, last role `assistant` |
| `/chat` PostgreSQL persistence | PASS | Smoke session wrote `turns=1`, `messages=2`, `candidates=2` |

## Cleanup

- Redis smoke keys were deleted after each Redis-backed smoke check.
- The PostgreSQL database lived inside the temporary Docker container and should not be treated as persistent evidence.
- The temporary PostgreSQL container was stopped and removed after the run; `docker ps` showed only the existing `emoedu-redis` container afterward.

## Decision

Backend infrastructure acceptance for PostgreSQL/Alembic, Redis history, and `/chat` mock orchestrator integration is closed for this branch state.
