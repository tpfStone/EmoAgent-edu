# EmoEdu MAS

[中文](README.md) | English

EmoEdu MAS is a Chinese emotional education multi-agent dialogue system for middle-school students aged 12-15. The goal is to provide age-appropriate, safe, concise, and socially meaningful support while keeping critic, pairwise evaluation, and human calibration as reproducible evidence for offline optimization.

The current product design uses a fast online path and an accurate background path:

```text
Online path: fast
First turn: F1 local safety gate -> F2 scenario/support routing -> F3 one-candidate streaming response -> background F4
Follow-up turns: lightweight CBT-compatible support -> recent context -> optional finished F4 guidance -> streaming response

Background path: accurate
F4 critic -> quality labels and session guidance -> aggregate reports -> prompt / strategy table / DPO data preparation
```

This keeps the theoretical generator-critic and multi-agent foundation, but avoids forcing students to wait for a full two-candidate generation and critic pipeline on every turn.

## Current Status

- Backend: FastAPI, PostgreSQL, Redis history store, SSE streaming, and `/chat` orchestration.
- F1 safety gate: a local classifier using `bert-base-chinese` embeddings, manually audited keyword features, soft rules, and conservative probability thresholds.
- F2 scenario analysis: an LLM module that predicts scenario, CASEL dimensions, support mode, and secondary safety fallback.
- F3 generator: can use local PsyQA-derived strategy priors and support cards when `exp/data/psyqa_labelled.json` is present; missing data leaves support-card enrichment empty or generic, while the online first turn still generates one routed candidate.
- F4 critic: runs in the background and writes `session guidance` for later turns; it does not block the student-facing response.
- Experiments: `exp/` records PsyQA labeling, F1 training, F3 RAG/support probes, and F4 pairwise judge comparisons.
- Default mode: `LLM_PROVIDER=mock`, so local tests can run without an API key. For real interaction, the recommended DeepSeek v4 setup uses `deepseek-v4-flash` online and `deepseek-v4-pro` for background critic work.

## Main APIs

| Endpoint | Purpose | Current Use |
| --- | --- | --- |
| `POST /chat` | Non-streaming orchestration | Returns a full `ChatResponse` |
| `POST /chat/stream` | SSE streaming orchestration | Recommended for the student app |
| `POST /api/safety/classifier/evaluate` | F1 local classifier safety gate | Production F1 endpoint |
| `POST /api/safety/evaluate` | F1 LLM safety gate | Compatibility and comparison |
| `POST /api/scenario/evaluate` | F2 scenario analysis | Outputs scenario, CASEL, support mode, and secondary safety |
| `POST /api/generator/generate` | F3 two-orientation generator | Research/debug endpoint |
| `POST /api/critic/evaluate` | F4 pointwise critic | Module endpoint; background in `/chat` |
| `GET /api/memory/status` | F6 memory/RAG status | Reserved, disabled by default |
| `DELETE /api/memory` | Clear memory/RAG records | By `anonymous_user_id` or `session_id` |

`/chat` and `/chat/stream` request body:

```json
{
  "session_id": "browser-session-id",
  "anonymous_user_id": "optional-stable-browser-user-id",
  "current_message": "我最近考试压力很大，晚上睡不着"
}
```

`anonymous_user_id` is designed for no-login continuity. A browser can keep a stable anonymous user ID, while multiple sessions remain separated by `session_id`.

## Figures

<p>
  <img src="./docs/figures/figure-1-three-phase-lifecycle.svg" alt="EmoEdu MAS three-phase lifecycle" width="760">
</p>

<p>
  <img src="./docs/figures/figure-2-runtime-pipeline.svg" alt="Current chat fast path, background critic, and offline research path" width="760">
</p>

<p>
  <img src="./docs/figures/figure-3-argument-loop.svg" alt="Evidence chain from educational frameworks to offline pairwise and DPO gates" width="760">
</p>

## Quick Start

### 1. Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

To reproduce algorithm experiments and report scripts under `exp/`, install the extra experiment dependencies:

```powershell
python -m pip install -r requirements-exp.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Run tests in mock mode:

```powershell
python -m pytest tests -q
```

### 2. F1 Safety Model

The F1 local safety model is not stored in GitHub. Download it from HuggingFace:

```text
https://huggingface.co/Nacgisac/EmoEduF1-bert-base-chinese/tree/main/manual-A-pattern-v1
```

```powershell
hf auth login

hf download Nacgisac/EmoEduF1-bert-base-chinese `
  --include "manual-A-pattern-v1/*" `
  --local-dir exp/models/f1_safety_gate `
  --revision main
```

Expected local path:

```text
exp/models/f1_safety_gate/manual-A-pattern-v1/
```

Expected files:

```text
hybrid_safety_classifier.pt
feature_scalers.joblib
manual_keywords.json
manual_keywords_grouped.json
model_config.json
summary.json
inference_benchmark.json
manual_keyword_audit.csv
hybrid_test_confusion_matrix.csv
```

`.env` settings:

```env
F1_SAFETY_MODEL_DIR=exp/models/f1_safety_gate/manual-A-pattern-v1
F1_SAFETY_PRELOAD=true
F1_SAFETY_REQUIRED=false
F1_SAFETY_HF_REPO=Nacgisac/EmoEduF1-bert-base-chinese
F1_SAFETY_HF_REVISION=main
```

When `F1_SAFETY_REQUIRED=false`, missing model artifacts will not crash the service; `/chat` falls back to the LLM/mock safety gate. For production or formal reproduction, set:

```env
F1_SAFETY_REQUIRED=true
```

Then startup fails fast with a clear HuggingFace download command if the model is missing.

### 3. DeepSeek / DashScope API Key

Recommended real LLM interaction uses the DeepSeek OpenAI-compatible API. The F1 safety gate uses the local classifier and does not depend on DeepSeek. DeepSeek is used for F2 scenario/support routing, F3 response generation, and background F4 critic work.

1. Create a DeepSeek API key.
2. Make sure the account has available quota.
3. Add the following to `.env`:

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled
CRITIC_DEEPSEEK_MODEL=deepseek-v4-pro
CRITIC_DEEPSEEK_THINKING=enabled
```

`deepseek-v4-flash` is used for low-latency online responses. `deepseek-v4-pro` is used for background F4 critic and quality evaluation. The old `deepseek-chat` alias is only suitable for temporary compatibility checks and is not recommended for formal reproduction.

For real LLM interaction, use Alibaba Cloud Model Studio / DashScope in OpenAI-compatible mode:

1. Open Alibaba Cloud Model Studio.
2. Enable the target model service.
3. Create an API key.
4. Make sure the selected model has available quota, or disable "free tier only" if needed.

`.env`:

```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen3.7-plus
DASHSCOPE_THINKING=disabled
CRITIC_DASHSCOPE_MODEL=qwen3.7-plus
CRITIC_DASHSCOPE_THINKING=disabled
```

For local tests or mock frontend demos:

```env
LLM_PROVIDER=mock
```

### 4. PostgreSQL and Redis

PostgreSQL:

```env
DATABASE_URL=postgresql+asyncpg://emoedu_user:password@localhost:5432/emoedu
```

Run migrations:

```powershell
alembic upgrade head
```

Redis stores chat history and background F4 guidance:

```env
REDIS_URL=redis://localhost:6379/0
```

Start backend:

```powershell
uvicorn app.main:app --reload
```

Useful URLs:

- API: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

### 5. Frontend

```powershell
pnpm --dir frontend install
```

Mock mode:

```powershell
pnpm --dir frontend dev:student
pnpm --dir frontend dev:console
```

Live backend mode:

```powershell
$env:VITE_API_MODE="live"
pnpm --dir frontend dev:student
```

Common checks:

```powershell
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
```

- Student app: http://localhost:5173
- Research console: http://localhost:5174

## Tests

Recommended check order:

```powershell
python -m pytest tests -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
python -m pytest tests/test_exp/test_exp_smoke.py -q
```

## Data Policy

The public repository does not include the full PsyQA-derived labelled data, and
sample JSON exports should not be committed. To reproduce the full experiments,
prepare the data locally at:

```text
exp/data/psyqa_labelled.json
```

When this file is missing, the application and default tests can still run. F3
strategy priors and support cards will be empty or generic, but the default path,
runtime code, and API design remain unchanged.

## Experiments

Algorithm experiments are kept under `exp/`:

- `exp/README.md`: experiment workflow, key results, issues, and reproduction commands.
- `exp/data/README.md`: public data boundary. The full `psyqa_labelled.json` file must be provided locally by reproducibility users and is not committed.
- `exp/models/f1_safety_gate/manual-A-pattern-v1/`: local F1 classifier artifacts downloaded from HuggingFace.
- `exp/runs/`: F1/F3/F4 experiment outputs. Raw run artifacts are large and are ignored by default; key results are summarized in `exp/README.md`.

The default test suite only checks `exp/*.py` syntax and entrypoint structure. Full experiment runs also need `requirements-exp.txt`, `.env`, model files, API keys, local `exp/data/psyqa_labelled.json`, and local `exp/runs/` data.

The core experimental conclusion is that full multi-agent reasoning should remain available for offline validation and background quality control, while the student-facing system should stay fast and readable.

## Documentation

- `docs/README.md`: documentation overview and reading path.
- `docs/README_EN.md`: English documentation map.
- `docs/specs/`: F1-F4, F4 pairwise, F9 specs, and the current integration boundary in `README.md` / `exp-integration-map.md`.
- `docs/specs/README_EN.md`: English specs summary.
- `docs/plans/`: unfinished phase plans; currently Phase 2B gates.
- `docs/overview/`: project plan and development roadmap.
- `docs/frontend/`: frontend design and demo notes.
- `docs/corpus/`: historical corpus, F9, and pairwise pilot records.
- `docs/issues/`: development issue records.
- `docs/figures/`: SVG figures.

## Production Principle

Do not put every research agent into the online blocking path. The online path should be fast, safe, and conversational. The background path should be accurate, auditable, and useful for future prompt updates, reports, pairwise calibration, and DPO.
