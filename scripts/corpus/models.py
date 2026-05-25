from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PersonaConfig:
    name: str
    persona_basis: str
    regulation_tendency: str
    language_features: str
    description: str


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    description: str
    subscenarios: list[str]


@dataclass(frozen=True)
class GenerationTargets:
    target_preference_pairs_total: int
    minimum_usable_pairs: int
    soft_cap_pairs: int
    probe_per_cell: int


@dataclass(frozen=True)
class GenerationConfig:
    prompt_version: str
    gen_model: str
    intended_use: str
    targets: GenerationTargets
    production_quota_multipliers: dict[str, float]
    personas: list[PersonaConfig]
    scenarios: list[ScenarioConfig]
    probe_cells: list[dict[str, str]]
    variant_tags: list[str]


@dataclass(frozen=True)
class Cell:
    persona: PersonaConfig
    scenario: ScenarioConfig


@dataclass
class RawUtterance:
    id: str
    persona: str
    persona_basis: str
    scenario: str
    text: str
    human_checked: bool
    run_id: str
    subscenario: str
    variant_tags: list[str]
    gen_model: str
    gen_prompt_version: str
    prompt_hash: str
    intended_use: str = "rag_pool | test_input"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RejectedUtterance:
    sample: dict[str, Any]
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PreferencePairRecord:
    sample_id: str
    run_id: str
    session_id: str
    persona: str
    scenario: str
    user_message: str
    winner_id: str
    loser_id: str
    candidates: list[dict[str, Any]]
    scores: list[dict[str, Any]]
    chat_response: dict[str, Any]
    judge_verification_status: str = "unverified"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_generation_config(path: str | Path) -> GenerationConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return GenerationConfig(
        prompt_version=data["prompt_version"],
        gen_model=data["gen_model"],
        intended_use=data["intended_use"],
        targets=GenerationTargets(**data["targets"]),
        production_quota_multipliers={
            str(key): float(value)
            for key, value in data.get("production_quota_multipliers", {}).items()
        },
        personas=[PersonaConfig(**item) for item in data["personas"]],
        scenarios=[ScenarioConfig(**item) for item in data["scenarios"]],
        probe_cells=list(data["probe_cells"]),
        variant_tags=list(data["variant_tags"]),
    )


def expand_cells(config: GenerationConfig) -> list[Cell]:
    return [
        Cell(persona=persona, scenario=scenario)
        for persona in config.personas
        for scenario in config.scenarios
    ]


def select_cells(
    config: GenerationConfig,
    mode: str,
    cells: list[str] | None = None,
) -> list[Cell]:
    all_cells = expand_cells(config)
    if cells:
        wanted = set(cells)
    elif mode == "probe":
        wanted = {
            f"{item['persona']}:{item['scenario']}" for item in config.probe_cells
        }
    else:
        return all_cells

    selected = [
        cell
        for cell in all_cells
        if f"{cell.persona.name}:{cell.scenario.name}" in wanted
    ]
    if len(selected) != len(wanted):
        found = {f"{cell.persona.name}:{cell.scenario.name}" for cell in selected}
        missing = sorted(wanted - found)
        raise ValueError(f"unknown cells: {', '.join(missing)}")
    return selected


def write_jsonl(path: Path, rows: list[dict[str, Any]], append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
