# Experimental Data

This directory is the default local location for PsyQA-derived labelled data used by
the experiment scripts and the optional F3 support-card runtime reference.

The public repository does not include the full labelled dataset:

- Place the full file at `exp/data/psyqa_labelled.json` to reproduce F1/F3/F4
  experiments that depend on PsyQA-derived annotations.
- Do not commit `exp/data/psyqa_labelled.json` or sample JSON exports.
- If `exp/data/psyqa_labelled.json` is missing, the application can still run.
  F3 support-card enrichment and strategy priors will be empty or generic, while
  the designed runtime path and default data path remain unchanged.

The F1 safety model artifacts are restored separately from HuggingFace under
`exp/models/f1_safety_gate/`; they are not stored in this directory.
