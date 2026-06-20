# Project Background and Technical Implementation Draft

> Working draft for review. This file is intentionally placed at the repository root as a temporary writing aid and can be deleted before commit.

## Project Background

### 1. Project Context

EmoEdu MAS is a Chinese emotional education multi-agent dialogue system designed for middle-school students aged 12 to 15. The system focuses on everyday emotional education scenarios rather than clinical mental-health intervention. Its current scope centers on three high-frequency adolescent contexts: academic pressure, peer relationships, and parent-child friction.

The project responds to a practical tension in educational AI: students need timely, safe, and age-appropriate emotional support, while research-oriented quality evaluation, pairwise comparison, and preference-data construction are too slow and uncertain to run synchronously in every live conversation. EmoEdu therefore separates the product runtime path from the research and optimization path.

### 2. Target Users and Scope

The primary users are Chinese junior high school students who may express stress, interpersonal frustration, family conflict, or general emotional distress through short text conversations. This age group is old enough to express feelings through text, but still requires strict safety boundaries, careful language, and avoidance of adult-like coaching or clinical framing.

The project deliberately avoids positioning itself as a crisis intervention tool or therapy system. When safety risks are detected, the system should stop ordinary generation and provide referral-oriented guidance, including trusted adults and appropriate support channels.

### 3. Educational and Psychological Rationale

The system design draws on three layers of conceptual support:

- CASEL provides the broad social and emotional learning dimensions, including self-awareness, self-management, social awareness, relationship skills, and responsible decision-making.
- EPITOME provides response-level empathy evaluation dimensions, especially emotional reaction, interpretation, and exploration.
- IRI provides a theoretical distinction between affective empathy and cognitive empathy, which helps motivate different generation orientations.

The project adapts the lifecycle logic of a multi-agent assessment framework into a generation system. Instead of using agents only to score an answer, EmoEdu uses a generator-critic structure: generation produces a candidate response, and critic components evaluate or improve the system through background guidance and offline evidence.

### 4. Core Design Shift

Earlier versions of the system explored a full synchronous chain in which each user turn could generate multiple candidates and run critic selection before responding. The current product design shifts to a fast online path plus a more accurate background/offline path.

The online path prioritizes response latency, safety, and conversational continuity. The background path preserves research value by producing quality labels, session guidance, pairwise evidence, and possible future DPO candidate data.

This separation is important because current pairwise and human-alignment evidence is not yet strong enough to justify treating model-judge preferences as authoritative training labels or as a default online selector.

### 5. Safety and Ethical Boundary

Safety is the first runtime boundary. The F1 safety gate classifies each user message with conversation history into green, yellow, or red risk levels. Yellow and red cases should block normal generation and return a referral-style response. Red-risk content must not trigger extended AI crisis counseling.

The system is designed for minors, so safety also includes non-crisis boundaries: no inappropriate dependency, no isolation from trusted adults, no clinical diagnosis, no private-channel guidance, and no unsupported factual completion about the student's situation.

### 6. Data Strategy

The public repository does not include the full PsyQA-derived labelled data. Reproducibility users must provide `exp/data/psyqa_labelled.json` locally if they want full experiment reproduction or richer F3 support-card behavior.

When the data file is missing, the application and default test suite still run. F3 support-card enrichment becomes empty or generic, but the runtime API and orchestration path remain unchanged.

Synthetic and PsyQA-derived data are treated as support material, not as unquestioned ground truth. The current project stance is that DPO training data must be gated by pairwise reliability and human calibration before it can become a formal training source.

### 7. Current Research Boundary

F4 pairwise selection, F9 reliability evaluation, long-term RAG injection, and DPO remain offline or future-gated capabilities. The current pairwise evidence is useful for diagnostics and future work, but not sufficient to unlock default runtime selection or DPO training.

The project can therefore be described as an implemented fast-path emotional education system with a background critic and a reproducible offline research pipeline, rather than as a completed self-improving DPO system.

## Technical Implementation

### 1. Repository Structure

The backend is implemented under `app/` with FastAPI service layers, Pydantic schemas, DAO modules, and orchestration logic. The frontend is implemented under `frontend/` as a pnpm workspace with separate student and research-console applications plus a shared API/type package. Algorithm experiments and reproducibility scripts live under `exp/`. Documentation is organized under `docs/`, with runtime specs in `docs/specs/`, overview documents in `docs/overview/`, and historical or research evidence under `docs/corpus/` and `docs/archive/`.

### 2. Runtime Architecture

The main backend entry point is `app.main:app`. It registers module endpoints for safety, scenario analysis, generation, critic evaluation, memory, and chat orchestration.

The main user-facing APIs are:

- `POST /chat` for non-streaming orchestration.
- `POST /chat/stream` for SSE streaming orchestration.
- `POST /api/safety/classifier/evaluate` for the F1 local classifier.
- `POST /api/scenario/evaluate` for F2 scenario analysis.
- `POST /api/generator/generate` for F3 module-level candidate generation.
- `POST /api/critic/evaluate` for F4 module-level pointwise critic evaluation.
- `GET /api/critic/guidance/{session_id}` for research-console inspection of background F4 guidance.
- `GET /api/memory/status` and `DELETE /api/memory` for reserved F6 memory/RAG management.

### 3. First-Turn Online Flow

The first user turn follows the fast online path:

```text
F1 local safety gate
-> F2 scenario/support routing and secondary safety
-> F3 one routed candidate
-> streaming student-facing response
-> background F4 critic task
```

F1 runs first and can block normal generation for yellow or red risk. If F1 passes, F2 predicts the scenario, activated CASEL dimensions, support mode, emotion intensity, help-seeking signal, and secondary safety. If F2 secondary safety blocks, the system returns a referral response. Otherwise, F3 generates a single candidate selected by the support route. The student receives this response without waiting for F4.

### 4. Follow-Up Online Flow

Follow-up turns also begin with F1. The system reads recent history from Redis, evaluates safety, and then uses lightweight follow-up generation. If background F4 guidance has already been written and is ready, the guidance can be injected into the prompt. If guidance is pending, missing, or failed, the system does not wait.

```text
recent history
-> F1 local safety gate
-> optional completed F4 guidance
-> lightweight follow-up generation
-> streaming response
```

This design keeps every turn safety-gated while avoiding full F2/F4 latency on every message.

### 5. F1 Safety Gate

F1 uses a local classifier rather than an LLM prompt in the default `/chat` path. The classifier combines `bert-base-chinese` text features, manually audited keyword features, soft rules, and conservative thresholds. Model artifacts are downloaded locally from HuggingFace and are not committed to GitHub.

Important runtime settings include:

- `F1_SAFETY_MODEL_DIR`
- `F1_SAFETY_PRELOAD`
- `F1_SAFETY_REQUIRED`
- `F1_SAFETY_RED_THRESHOLD`
- `F1_SAFETY_YELLOW_OR_RED_THRESHOLD`
- `HISTORY_WINDOW_N`

When `F1_SAFETY_REQUIRED=false`, missing model artifacts do not crash the service; the system can fall back for local testing. For production or formal reproduction, `F1_SAFETY_REQUIRED=true` is recommended.

### 6. F2 Scenario Analysis

F2 is an LLM-based scenario and support-routing module. It returns:

- `scenario`
- `activated_casel`
- `support_mode`
- `emotion_intensity`
- `help_seeking`
- `secondary_safety`
- rationale fields used for diagnostics

The scenario output maps user messages into the current core categories: academic pressure, peer relationships, parent-child friction, or other. The support mode then guides which F3 orientation is used for the first-turn single candidate.

### 7. F3 Generation

F3 retains two conceptual orientations:

- `c1` emotional empathy oriented response.
- `c2` guided reflection or cognitive empathy oriented response.

The module endpoint can still generate c1/c2 candidates for experiments and debugging, but the `/chat` runtime first turn generates only one routed candidate. The route is derived from F2 output. For example, `emotion_first` or high emotion intensity prefers c1, while solution-seeking requests prefer c2.

F3 can optionally use PsyQA-derived strategy priors and support cards through `F3SupportService`. If the local data is unavailable, support enrichment degrades gracefully.

### 8. F4 Background Critic

F4 pointwise critic is no longer an online blocking selector. After the first response is finalized, the orchestrator schedules a background critic task. The critic evaluates the generated response, writes Redis guidance, and exposes status through `GET /api/critic/guidance/{session_id}`.

Guidance states include:

- `missing`
- `pending`
- `ready`
- `failed`

When status is `ready`, the research console can inspect guidance and background scores. Follow-up generation may use the textual guidance, but the student-facing response never waits for pending guidance.

### 9. F4 Pairwise, F9, and DPO

Pairwise selection exists as a research target and offline toolchain, not as the current default runtime. The current implementation retains pointwise fields such as `scores`, `weighted_total`, and `preference_pair` for compatibility, diagnostics, and historical analysis.

Formal DPO training remains gated. Preference pairs from old pointwise scoring, orientation defaults, or unverified pairwise outputs should not be treated as training-ready. The next research milestone is to establish a stable pairwise/human A/B gate with sufficient effective samples and acceptable critic-human agreement.

### 10. Frontend Implementation

The frontend workspace contains:

- `student`: the student-facing emotional companion UI.
- `console`: the internal research analysis console.
- `shared`: shared API contracts, mock samples, and fetch wrappers.

The student app is intentionally narrow. It should render only the reply and basic safety/referral state needed by the user. It must not expose internal candidates, scores, weighted totals, failure reasons, or preference-pair fields.

The research console can inspect the full trace, including candidates, critic scores, preference pairs, and background F4 guidance. This separation prevents internal diagnostic information from leaking into the student experience.

### 11. Persistence and Infrastructure

PostgreSQL stores structured chat and evaluation records through SQLAlchemy and Alembic migrations. Redis stores recent chat history and background F4 guidance with TTL. The frontend can run in mock mode by default, or live mode through Vite proxying to the local FastAPI backend.

Default local development uses `LLM_PROVIDER=mock`, which allows the test suite and frontend demos to run without external API keys.

### 12. Verification Status

The current repository has automated coverage across backend services, handlers, experiment entrypoints, and frontend behavior. Recent local verification showed:

- Backend test suite passed with 205 tests using the repository `.venv`.
- Frontend test suite passed.
- Frontend typecheck passed.
- Frontend production build passed.

Remaining verification risks are not basic runtime failures, but research-readiness boundaries: pairwise reliability, DPO gating, F6/RAG privacy and deletion guarantees, and final paper-ready citation coverage.

## Draft Notes for Later Editing

- Replace informal framework descriptions with fully formatted citations before paper submission.
- Keep pairwise and DPO language conservative until a new validation gate passes.
- Update API title from the older F1/F4 wording to MAS wording if the project wants OpenAPI metadata to match the README.
- Treat `docs/overview/docs-review-matrix.md` as historical unless it is refreshed to the current integrated repository state.
