# Validation Gate Plan

> Current runtime boundary: `/chat` uses F1 local safety, F2 support routing, F3 one routed streaming response, and background F4 guidance. This document tracks only unfinished validation gates. It does not change runtime code, APIs, or default paths.

## Scope

These gates decide which experimental assets can later replace or extend the main chain. Until gates pass, the default runtime remains unchanged.

This work can do:

- Repair pairwise input packaging and c1/c2 bias controls.
- Rerun a cleaner pairwise Phase A.3.
- Build a blind human A/B queue.
- Define hard gates for DPO export.
- Run F6/RAG in observe-only or safety-pilot mode.

This work cannot do before gates pass:

- Connect pairwise selector to `/chat`.
- Treat pointwise tiebreak, orientation default, or unresolved pairwise output as DPO-positive data.
- Inject memory/RAG snippets into student prompts by default.

## Gates

| Gate | Required evidence | Output |
| --- | --- | --- |
| Pairwise packaging | balanced/blinded A/B position, no leaked orientation labels or pointwise scores, valid controls | new offline package only |
| Pairwise Phase A.3 | enough human-valid intersection pairs, reverse-order consistency, critic-human agreement, controls pass | `pass` / `inconclusive` / `fail` |
| Human A/B queue | blind schema, annotator IDs, `a|b|tie|invalid`, reason codes, no candidate provenance leak | offline annotation queue |
| DPO export | only stable pairwise or human-validated preferences with source case, trace, and version | exportable training data |
| F6/RAG safety | user isolation, sensitive-content filtering, clear/delete path, prompt-injection smoke | future prompt-injection decision |

## Task 1: Repair pairwise input package and c1 bias

- Add input-package tests for A/B balance, hidden orientation labels, hidden pointwise scores, tie/invalid retention, and candidate provenance.
- Fix only offline packaging scripts under `scripts/corpus/f9_pairwise_*.py`.
- Verify with existing pairwise service tests before producing a new package.

## Task 2: Rerun Pairwise Phase A.3

- Freeze the gate before running.
- Write outputs only under `docs/corpus/f9/pairwise-selection-pilot/`.
- Conclusion must be one of `pass`, `inconclusive`, or `fail`; do not imply runtime migration from an inconclusive result.

## Task 3: Build human A/B blind queue

Minimum row shape:

```json
{
  "case_id": "case-001",
  "prompt": "student input and necessary context",
  "candidate_a": "blind candidate A",
  "candidate_b": "blind candidate B",
  "annotator_id": "rater-1",
  "choice": "a|b|tie|invalid",
  "reason_codes": ["supportive", "safe", "actionable"],
  "created_at": "2026-06-16T00:00:00Z"
}
```

The queue must not expose F3 orientation labels, pointwise scores, critic choices, or source candidate IDs.

## Task 4: Harden DPO export

Reject by default:

- `selection_method=pointwise_tiebreak`
- `selection_method=orientation_default`
- `pairwise_unresolved`
- `human_validated=false`
- old pointwise-only packages
- any rerun conclusion marked `inconclusive`

Allow only stable pairwise or human-validated preferences with explicit source case, judge/human trace, version, winner, and rejected candidate.

## Task 5: F6/RAG safety pilot

- Keep default prompt injection off.
- Add observe-only metrics first.
- Require user isolation, red/yellow content handling, clearing/deletion, and manual snippet inspection before any prompt-injection trial.

## References

- Current boundary: `../specs/exp-integration-map.md`
- Pairwise target spec: `../specs/f4-pairwise-selection-codex-spec.md`
- F9 status: `../corpus/f9/README.md`
