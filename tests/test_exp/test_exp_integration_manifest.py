from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "exp" / "artifacts.manifest.json"
INTEGRATION_MAP_PATH = ROOT / "docs" / "specs" / "exp-integration-map.md"
SPECS_INDEX_PATH = ROOT / "docs" / "specs" / "README.md"
PROJECT_README_PATH = ROOT / "README.md"
F4_SPEC_PATH = ROOT / "docs" / "specs" / "f4-critic-epitome-codex-spec.md"

EXPECTED_ARTIFACTS = {
    "psyqa_labelled_data": "runtime_reference",
    "f1_safety_model_manual_a_pattern_v1": "runtime",
    "f1_training_scripts": "offline",
    "f3_support_runtime_service": "runtime_reference",
    "f3_probe_scripts": "offline",
    "f4_pointwise_background_critic": "background",
    "f4_pairwise_eval_toolchain": "offline",
    "f9_reliability_archive": "archive",
}

ALLOWED_TIERS = {"runtime", "runtime_reference", "background", "offline", "archive"}
APP_DIR = ROOT / "app"
EXP_SCRIPT_NAMES = {path.stem for path in (ROOT / "exp").glob("*.py")}


def test_exp_artifacts_manifest_exists_and_classifies_core_assets():
    manifest = _load_manifest()
    artifacts = {item["id"]: item for item in manifest["artifacts"]}

    assert manifest["schema_version"] == 1
    assert set(EXPECTED_ARTIFACTS).issubset(artifacts)

    for artifact_id, expected_tier in EXPECTED_ARTIFACTS.items():
        artifact = artifacts[artifact_id]
        assert artifact["integration_tier"] == expected_tier
        assert artifact["integration_tier"] in ALLOWED_TIERS
        assert artifact["path"]
        assert artifact["runtime_usage"]
        assert artifact["owner_docs"]
        assert isinstance(artifact["tests"], list)


def test_runtime_artifacts_point_to_services_not_experiment_scripts():
    manifest = _load_manifest()

    for artifact in manifest["artifacts"]:
        tier = artifact["integration_tier"]
        if tier not in {"runtime", "runtime_reference", "background"}:
            continue

        runtime_entrypoints = artifact.get("runtime_entrypoints", [])
        assert runtime_entrypoints, artifact["id"]
        assert all(entry.startswith("app/") for entry in runtime_entrypoints)
        assert all(not entry.startswith("exp/") for entry in runtime_entrypoints)


def test_app_code_does_not_import_exp_scripts_directly():
    offenders: list[str] = []

    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name == "exp" or name in EXP_SCRIPT_NAMES:
                        offenders.append(f"{path.relative_to(ROOT)} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module == "exp" or module in EXP_SCRIPT_NAMES:
                    offenders.append(f"{path.relative_to(ROOT)} imports {node.module}")

    assert offenders == []


def test_docs_link_exp_integration_map_from_public_indexes():
    assert INTEGRATION_MAP_PATH.exists()
    specs_index = SPECS_INDEX_PATH.read_text(encoding="utf-8")
    project_readme = PROJECT_README_PATH.read_text(encoding="utf-8")

    assert "exp-integration-map.md" in specs_index
    assert "exp/artifacts.manifest.json" in project_readme


def test_docs_record_phase_two_observability_and_f6_boundary():
    integration_map = INTEGRATION_MAP_PATH.read_text(encoding="utf-8")
    specs_index = SPECS_INDEX_PATH.read_text(encoding="utf-8")
    f4_spec = F4_SPEC_PATH.read_text(encoding="utf-8")

    assert "/api/critic/guidance/{session_id}" in integration_map
    assert "/api/critic/guidance/{session_id}" in specs_index
    assert "/api/critic/guidance/{session_id}" in f4_spec
    assert "F6_MEMORY_ENABLE=false" in integration_map
    assert "不注入 `/chat` prompt" in integration_map


def test_exp_integration_map_records_runtime_and_offline_boundaries():
    content = INTEGRATION_MAP_PATH.read_text(encoding="utf-8")

    assert "当前已实现的 runtime 事实" in content
    assert "F3 single routed generation" in content
    assert "F4 pointwise critic" in content
    assert "F4 pairwise selector" in content
    assert "F6 memory/RAG prompt injection" in content
    assert "Pairwise, DPO, long-term RAG" in content


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


def _load_manifest() -> dict:
    assert MANIFEST_PATH.exists(), "exp/artifacts.manifest.json must exist"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
