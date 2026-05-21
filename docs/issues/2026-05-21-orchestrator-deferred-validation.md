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
