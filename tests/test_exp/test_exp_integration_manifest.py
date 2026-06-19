from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_exp_integration_map_records_runtime_and_offline_boundaries():
    content = (ROOT / "docs/specs/exp-integration-map.md").read_text(
        encoding="utf-8"
    )

    assert "Phase 2A 已完成事实" in content
    assert "F3 single routed generation" in content
    assert "F4 pointwise critic" in content
    assert "F4 pairwise selector" in content
    assert "F6 memory/RAG prompt injection" in content
    assert "Pairwise、DPO、F6/RAG 均不得" in content


def test_exp_data_readme_records_public_data_boundary():
    content = (ROOT / "exp/data/README.md").read_text(encoding="utf-8")

    assert "exp/data/psyqa_labelled.json" in content
    assert "public repository does not include" in content
    assert "application can still run" in content


def test_full_psyqa_json_is_not_tracked_by_git():
    if not (ROOT / ".git").exists():
        return

    result = subprocess.run(
        ["git", "ls-files", "exp/data/psyqa_labelled.json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip() == ""
