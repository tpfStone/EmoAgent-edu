# Specs Map

This directory is the implementation contract layer. It summarizes current code
behavior, the completed Phase 2A runtime boundary, and the Phase 2B gates that
are still offline or future work.

## Current Runtime

- `/chat` and `/chat/stream`: F1 local safety gate -> F2 scenario/support/safety routing -> F3 one routed candidate streaming response -> background F4 guidance.
- Follow-up turns: lightweight CBT-compatible generation with recent history; completed F4 guidance is injected only when available.
- F3 support-card enrichment is optional. The default local path remains `exp/data/psyqa_labelled.json`, but the public repository does not include the full data file.
- F4 pointwise is a module endpoint and background quality signal, not an online blocking selector.
- F4 pairwise, F9, and DPO remain offline/future gates.
- F6 memory/RAG exists as a service but is disabled by default and is not injected into the student prompt before passing a gate.

## Key Files

| File | Status | Notes |
| --- | --- | --- |
| `f1-safety-gate-codex-spec.md` | Phase 2A completed | Local classifier safety gate; yellow/red short-circuit generation. |
| `f2-scenario-analysis-codex-spec.md` | Phase 2A completed | Scenario, CASEL, support mode, and secondary safety. |
| `f3-multi-orientation-generator-codex-spec.md` | Phase 2A completed + offline retained | Runtime single candidate; c1/c2 retained for experiments. |
| `f4-critic-epitome-codex-spec.md` | Phase 2A completed + diagnostics | Background quality labels/session guidance. |
| `f4-pairwise-selection-codex-spec.md` | Phase 2B target | Pairwise remains offline until validation gates pass. |
| `f9-reliability-guide.md` | Research gate | Human/model reliability evaluation. |
| `exp-integration-map.md` | Current boundary | Runtime/offline/default-off map for `exp` assets. |
