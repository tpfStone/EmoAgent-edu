# Documentation Map

[中文](README.md)

The English documentation is the recommended review path. Detailed working
records and historical notes are linked from the documentation map when they
are useful for deeper inspection.

## Current Runtime

- Student-facing first turn: F1 local safety gate -> F2 scenario/support routing -> F3 one routed streaming response.
- Follow-up turns still run F1 first, then lightweight support with recent history; completed F4 guidance is used only when ready.
- Background path: F4 pointwise critic writes quality labels and `session guidance`; it does not block the student-facing response.
- Offline/future path: pairwise, F9 reliability, DPO, and F6/RAG prompt injection are not default runtime behavior.
- Data policy: the full PsyQA-derived labelled data is not published. Reproducibility users must provide `exp/data/psyqa_labelled.json` locally.

## Reading Path

1. `../README_EN.md`: project overview, setup, APIs, figures, and data policy.
2. `specs/README_EN.md`: module status summary for F1/F2/F3/F4/F6/F9.
3. `specs/exp-integration-map.md`: exact runtime/offline/default-off boundary.
4. `../exp/README_EN.md`: experiment directory purpose and reproduction data note.
5. `plans/validation-gates.md`: unfinished validation gates.

## Directory Map

| Path | Purpose |
| --- | --- |
| `specs/` | Implementation contracts and current integration boundary. |
| `plans/` | Unfinished validation gates. |
| `corpus/` | Historical corpus, F9, and pairwise pilot records. |
| `frontend/` | Frontend design and demo notes. |
| `overview/` | Project planning and roadmap documents. |
| `acceptance/` | Acceptance and smoke-test records. |
| `issues/` | Development issue records. |
| `figures/` | SVG figures used by the READMEs. |
| `archive/` | Historical plans, not current runtime guidance. |
