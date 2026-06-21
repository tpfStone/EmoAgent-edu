# EmoAgent

[中文](README.md) | English

> A safety-first multi-agent emotional education system for Chinese middle-school students aged 12-15.

## Overview

EmoAgent supports emotional expression and social-emotional learning in common middle-school contexts such as academic pressure, peer relationships, and parent-child conflict. It combines a local safety gate, scenario-aware routing, streaming student responses, and a background critic so the student experience stays low-latency while research and quality-improvement evidence remains traceable.

The project is an educational support system, not a diagnostic, psychotherapy, medical, or emergency service. High-risk inputs leave the ordinary generation path and receive fixed safety referral guidance that encourages the student to contact a trusted adult and appropriate public services.

## Why EmoAgent

- **Safety before generation:** every turn passes through the F1 safety gate; the first turn also receives an F2 secondary safety review.
- **Scenario-aware support:** F2 uses scenario, support mode, and configured CASEL mapping to route the first response.
- **Low-latency student experience:** F3 streams one routed candidate online instead of making the student wait for a full two-candidate critic pipeline.
- **Background quality loop:** F4 writes quality labels and session guidance after the response; completed guidance may shape later turns without blocking the current one.
- **Explicit research boundaries:** pairwise selection, F9 human calibration, DPO, and F6 memory/RAG prompt injection remain offline, gated, or disabled unless the code and validation status explicitly change.

## Current Runtime Boundary

| Layer | Current behavior | Student-facing latency |
| --- | --- | --- |
| First turn | F1 local safety gate -> F2 scenario/support routing and secondary safety -> F3 one routed candidate -> SSE stream | Blocking fast path |
| Follow-up turn | F1 safety gate -> recent Redis history -> optional completed F4 guidance -> lightweight streaming generation | Blocking fast path |
| Background quality path | F4 pointwise critic -> quality labels -> Redis session guidance | Does not block the current response |
| Offline research | F3 two-orientation candidates, F4 pairwise experiments, F9 human calibration, DPO preparation | Never part of the default `/chat` blocking path |
| Default-off capability | F6 memory/RAG prompt injection | Must pass a separate privacy and quality gate before enablement |

## Product Surfaces

### Student app

The student-facing interface provides streaming conversation, session continuity, safety referral presentation, and user-controlled record handling without exposing internal agent traces, critic labels, or research diagnostics.

<p align="center">
  <img src="./docs/screenshots/student-app-empty-state.png" alt="Student app empty state" width="900">
</p>

<p align="center"><em>Student app empty state</em></p>

### Research console

The research console exposes diagnostic traces such as risk routing, scenario metadata, generated content, and the background F4 guidance state. It is for research, debugging, and demonstration, not for students.

<p align="center">
  <img src="./docs/screenshots/research-console-single-turn-trace.png" alt="Research console single-turn trace" width="900">
</p>

<p align="center"><em>Research console single-turn trace</em></p>

## Architecture

The three project figures explain the runtime boundary, the current fast/background pipeline, and the evidence chain from the theoretical framework to validation gates.

### 1. Runtime boundary and validation gates

<p align="center">
  <img src="./docs/figures/figure-1-runtime-boundary.svg" alt="EmoAgent runtime boundary and validation gates" width="760">
</p>

### 2. Current `/chat` fast path and background/offline paths

<p align="center">
  <img src="./docs/figures/figure-2-runtime-pipeline.svg" alt="Current EmoAgent runtime, background, and offline paths" width="760">
</p>

### 3. Evidence chain from theory to the pairwise gate

<p align="center">
  <img src="./docs/figures/figure-3-argument-loop.svg" alt="Evidence chain from the theoretical framework to the pairwise validation gate" width="760">
</p>

## Key Features

| Capability | Status | Notes |
| --- | --- | --- |
| F1 local safety classifier | Implemented | Local model can be preloaded; red blocks ordinary generation with fixed referral guidance, while yellow is a non-blocking support state. |
| F2 scenario and support routing | Implemented | Produces scenario, configured CASEL dimensions, support mode, and secondary safety. |
| F3 streaming student response | Implemented | The runtime first turn generates one routed candidate; two orientations remain available for experiments and debugging. |
| F4 background critic guidance | Implemented | Runs after the response and does not block the student. |
| Anonymous session continuity | Implemented | Uses `anonymous_user_id` and `session_id` for no-login continuity. |
| Research console | Implemented | Shows internal traces and background critic status. |
| F4 pairwise selector | Offline / gated | Not the default runtime selector. |
| DPO training loop | Future / gated | Only validated preference pairs may be used. |
| F6 memory/RAG prompt injection | Default off | Requires separate privacy, deletion, isolation, and quality gates. |

## Quick Start: Default Local Mode

The public default configuration uses `mock` for local development, automated tests, and interface checks without external credentials. Formal demos or evidence collection should switch to a live provider and record the actual provider, model, and configuration. Screenshots or videos that use `mock` should be visibly labelled.

### Install

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env

# Frontend
pnpm --dir frontend install
```

### Run the interfaces

```powershell
# Terminal 1 - backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 - student app
pnpm --dir frontend dev:student

# Terminal 3 - research console
pnpm --dir frontend dev:console
```

Open:

- Student app: <http://localhost:5173>
- Research console: <http://localhost:5174>
- Backend API: <http://127.0.0.1:8000>
- API documentation: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

## Full Local Setup: Live Mode

### 1. Configure the backend

Copy `.env.example` to `.env`, then configure the provider you actually use. Never commit `.env` or expose keys in a demo.

DeepSeek:

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled
CRITIC_DEEPSEEK_MODEL=deepseek-v4-pro
CRITIC_DEEPSEEK_THINKING=enabled
```

DashScope:

```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen3.7-plus
DASHSCOPE_THINKING=disabled
CRITIC_DASHSCOPE_MODEL=qwen3.7-plus
CRITIC_DASHSCOPE_THINKING=disabled
```

### 2. Restore the F1 safety model

The F1 local safety model is not committed to GitHub. Download it from Hugging Face:

```powershell
hf auth login

hf download Nacgisac/EmoEduF1-bert-base-chinese `
  --include "manual-A-pattern-v1/*" `
  --local-dir exp/models/f1_safety_gate `
  --revision main
```

Expected directory:

```text
exp/models/f1_safety_gate/manual-A-pattern-v1/
```

Current defaults in `.env.example`:

```env
F1_SAFETY_MODEL_DIR=exp/models/f1_safety_gate/manual-A-pattern-v1
F1_SAFETY_PRELOAD=true
F1_SAFETY_REQUIRED=false
F1_SAFETY_HF_REPO=Nacgisac/EmoEduF1-bert-base-chinese
F1_SAFETY_HF_REVISION=main
```

For formal reproduction or production demos, set:

```env
F1_SAFETY_REQUIRED=true
```

### 3. Start database, Redis, and migrations

The default database example uses PostgreSQL:

```env
DATABASE_URL=postgresql+asyncpg://emoagent_user:password@localhost:5432/emoagent
```

For temporary local development, SQLite is also supported:

```env
DATABASE_URL=sqlite+aiosqlite:///./local-dev.sqlite
```

Run migrations:

```powershell
alembic upgrade head
```

Redis stores chat history and background F4 guidance:

```env
REDIS_URL=redis://localhost:6379/0
```

If Redis is not installed locally, start one with Docker:

```powershell
docker run --name emoagent-redis -p 6379:6379 -d redis:7-alpine
```

Reuse the same container later:

```powershell
docker start emoagent-redis
docker exec emoagent-redis redis-cli ping
```

Expected output:

```text
PONG
```

### 4. Start live applications

```powershell
# Terminal 1 - backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 - student app
$env:VITE_API_MODE="live"
pnpm --dir frontend dev:student

# Terminal 3 - research console
$env:VITE_API_MODE="live"
pnpm --dir frontend dev:console
```

Check the backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Configuration Modes

| Mode | Purpose | External credentials | Evidence use |
| --- | --- | --- | --- |
| `mock` | UI development, automated tests, offline walkthrough | No | Only when visibly labelled as mock |
| `deepseek` | Live generation and critic via DeepSeek-compatible configuration | Yes | Yes, after recording exact model/config |
| `dashscope` | Live generation and critic via DashScope OpenAI-compatible configuration | Yes | Yes, after recording exact model/config |

## API Summary

| Endpoint | Purpose | Runtime role |
| --- | --- | --- |
| `POST /chat` | Non-streaming orchestrated response | Fast-path complete response |
| `POST /chat/stream` | SSE orchestrated response | Recommended student path |
| `POST /api/safety/classifier/evaluate` | F1 local classifier | Default safety gate |
| `POST /api/safety/evaluate` | LLM safety compatibility endpoint | Comparison and compatibility |
| `POST /api/scenario/evaluate` | F2 scenario analysis | First-turn routing and secondary safety |
| `POST /api/generator/generate` | F3 candidate generation module | Experiments and debugging |
| `POST /api/critic/evaluate` | F4 pointwise critic module | Synchronous module endpoint; background in `/chat` |
| `GET /api/critic/guidance/{session_id}` | Background F4 status | Research and diagnostics |
| `GET /api/memory/status` | F6 status | Default-off capability |
| `DELETE /api/memory` | Delete memory/RAG data | User or session data control |

### Chat request example

```json
{
  "session_id": "browser-session-id",
  "anonymous_user_id": "optional-stable-browser-user-id",
  "current_message": "我最近考试压力很大，晚上睡不着"
}
```

## Tests

Recommended check order:

```powershell
python -m pytest tests -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
python -m pytest tests/test_exp/test_exp_smoke.py -q
```

## Evaluation and Evidence

The root README should avoid presenting historical experiment outputs as current runtime guarantees. Timestamped methods, metrics, limitations, and reproduction commands should live in:

- [`exp/README.md`](exp/README.md): current algorithm experiments and evidence.
- [`exp/artifacts.manifest.json`](exp/artifacts.manifest.json): runtime/background/offline/archive inventory for experiment assets.
- [`docs/specs/README.md`](docs/specs/README.md): implementation contracts and runtime boundaries.
- [`docs/specs/exp-integration-map.md`](docs/specs/exp-integration-map.md): runtime/background/offline/default-off asset map.
- [`docs/overview/emoedu-post-mvp-guide.md`](docs/overview/emoedu-post-mvp-guide.md): next validation gates and research roadmap.

### Claims boundary

- The local F1 classifier is a first safety screen, not a complete clinical risk assessment.
- F2 provides a second safety review on the first LLM-mediated turn.
- F4 pointwise output is used for background diagnostics and session guidance.
- Pairwise preference, F9 reliability, and DPO remain gated until human validation criteria are met.
- Historical validation summaries should be labelled as historical evidence, not live measurements.

## Safety, Privacy, and Data Policy

- Do not submit or demonstrate real identifiable conversations from minors.
- Do not expose API keys, database credentials, internal prompts, or sensitive logs.
- Red safety results interrupt ordinary generation and use fixed referral guidance; yellow is non-blocking and carries support/referral wording for support handling; safety module failures use `safety_status=unavailable`, stop ordinary generation, and return a neutral unavailable message.
- Anonymous continuity uses configured identifiers; storage, retention, deletion, and isolation behavior should be checked against the current commit.
- The public repository does not contain the complete PsyQA-derived labelled dataset. Local absence may reduce support-card enrichment, but it should not silently change the documented API contract.
- F6 memory/RAG prompt injection remains disabled by default until privacy and quality gates pass.

## Repository Map

```text
app/                 FastAPI application and runtime services
frontend/            Student app, research console, and shared frontend layer
docs/overview/       Project rationale, roadmap, and planning notes
docs/specs/          F1-F4/F9 implementation contracts and runtime boundaries
docs/figures/        Architecture and evidence-chain figures
exp/                 Offline experiments, reports, and local model/data entry points
scripts/             Utility scripts used by local workflows
tests/               Backend, orchestration, frontend, and experiment smoke tests
alembic/             Database migration files
```

## Documentation

Recommended reading order:

1. This README - product overview and reproduction entry point.
2. [`exp/README.md`](exp/README.md) - current experiment conclusions and evidence.
3. [`docs/specs/README.md`](docs/specs/README.md) - current implementation boundary.
4. [`docs/specs/exp-integration-map.md`](docs/specs/exp-integration-map.md) - asset integration map.
5. [`docs/overview/emoedu-post-mvp-guide.md`](docs/overview/emoedu-post-mvp-guide.md) - next validation gates.
