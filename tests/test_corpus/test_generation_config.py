from pathlib import Path
import json

from scripts.corpus.models import expand_cells, load_generation_config


CONFIG_PATH = Path("docs/corpus/generation_config.json")
PRODUCTION_QUOTA_AFTER_PROBE_PATH = Path(
    "docs/corpus/production_quota_after_probe_001.json"
)


def test_generation_config_expands_full_grid_and_probe_cells():
    config = load_generation_config(CONFIG_PATH)

    cells = expand_cells(config)

    assert len(config.personas) == 5
    assert len(config.scenarios) == 3
    assert len(cells) == 15
    assert config.probe_cells == [
        {"persona": "反刍型", "scenario": "同伴关系"},
        {"persona": "外放型", "scenario": "学业压力"},
        {"persona": "适应型", "scenario": "亲子摩擦"},
    ]


def test_each_scenario_has_diversity_variants():
    config = load_generation_config(CONFIG_PATH)

    for scenario in config.scenarios:
        assert len(scenario.subscenarios) >= 6


def test_generation_config_declares_repressive_quota_buffer():
    config = load_generation_config(CONFIG_PATH)

    assert config.production_quota_multipliers == {"压抑型": 1.2}


def test_after_probe_production_quota_covers_remaining_twelve_cells():
    config = load_generation_config(CONFIG_PATH)
    quotas = json.loads(PRODUCTION_QUOTA_AFTER_PROBE_PATH.read_text(encoding="utf-8"))
    probe_cells = {
        f"{item['persona']}:{item['scenario']}" for item in config.probe_cells
    }
    all_cells = {
        f"{cell.persona.name}:{cell.scenario.name}" for cell in expand_cells(config)
    }

    assert set(quotas) == all_cells - probe_cells
    assert len(quotas) == 12
    assert sum(quotas.values()) == 1008
    assert all(value == 96 for key, value in quotas.items() if key.startswith("压抑型:"))
    assert all(value == 80 for key, value in quotas.items() if not key.startswith("压抑型:"))
