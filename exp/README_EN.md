# EmoEdu Exp Overview

[中文](README.md)

`exp/` contains the algorithm-side experiment scripts and records: PsyQA-derived
labelling, F1 safety classifier work, F3 support-card probes, and F4 pairwise /
critic evaluation.

## Data Policy

The public repository does not include the full PsyQA-derived labelled data.
Full reproduction requires a local file at:

```text
exp/data/psyqa_labelled.json
```

If the file is missing, the application and default tests can still run. F3
support-card enrichment and strategy priors become empty or generic; the default
runtime path, API design, and data path do not change.

Do not commit `exp/data/psyqa_labelled.json` or sample JSON exports. See
`data/README.md`.

## Runtime Boundary

- Runtime: F1 local safety gate, F2 support routing, F3 one routed response, and background F4 guidance.
- Offline/research: F3 c1/c2 probes, F4 pairwise packages, F9 reliability, and future DPO data preparation.
- Default-off/future: F6/RAG prompt injection.

## Reproduction Notes

Default smoke tests only check experiment script syntax and entrypoints:

```powershell
python -m pytest tests/test_exp/test_exp_smoke.py -q
```

Full experiment runs also require `requirements-exp.txt`, `.env`, model files,
API keys, local `exp/data/psyqa_labelled.json`, and any local `exp/runs/`
artifacts needed for the specific report.
