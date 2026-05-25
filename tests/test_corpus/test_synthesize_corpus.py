import json
from pathlib import Path

import pytest

from scripts.corpus.models import load_generation_config
from scripts.corpus.synthesize_corpus import (
    build_generation_prompt,
    generate_corpus,
)


CONFIG_PATH = Path("docs/corpus/generation_config.json")


class ExplodingLLM:
    async def generate(self, **kwargs):
        raise AssertionError("dry-run must not call the LLM")


class RecordingLLM:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return "这次数学没考好，我有点难受。想先找个人说说。"


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_build_generation_prompt_injects_cell_variant_and_safety_scope():
    config = load_generation_config(CONFIG_PATH)
    persona = next(item for item in config.personas if item.name == "反刍型")
    scenario = next(item for item in config.scenarios if item.name == "同伴关系")

    prompt = build_generation_prompt(
        persona=persona,
        scenario=scenario,
        subscenario="群聊排除",
        variant_tags=["中等强度", "短句"],
    )

    assert "反复纠结" in prompt
    assert "同伴关系" in prompt
    assert "群聊排除" in prompt
    assert "中等强度" in prompt
    assert "不涉及自伤、自杀等危机内容" in prompt
    assert "只输出学生的倾诉内容" in prompt
    assert "1-5" in prompt
    assert "20-180" in prompt
    assert "2-5" not in prompt


@pytest.mark.asyncio
async def test_dry_run_generates_probe_without_calling_llm(tmp_path):
    result = await generate_corpus(
        config_path=CONFIG_PATH,
        output_root=tmp_path,
        run_id="probe-dry",
        mode="probe",
        per_cell=1,
        dry_run=True,
        resume=False,
        llm_client=ExplodingLLM(),
    )

    raw_rows = _read_jsonl(result.raw_path)
    prompt_rows = _read_jsonl(result.prompts_path)

    assert result.generated_count == 3
    assert len(raw_rows) == 3
    assert len(prompt_rows) == 3
    assert {row["persona"] for row in raw_rows} == {"反刍型", "外放型", "适应型"}
    assert all(row["text"] for row in raw_rows)


@pytest.mark.asyncio
async def test_resume_does_not_duplicate_existing_cell_outputs(tmp_path):
    llm = RecordingLLM()

    first = await generate_corpus(
        config_path=CONFIG_PATH,
        output_root=tmp_path,
        run_id="resume-run",
        mode="probe",
        cells=["反刍型:同伴关系"],
        per_cell=1,
        dry_run=False,
        resume=True,
        llm_client=llm,
    )
    second = await generate_corpus(
        config_path=CONFIG_PATH,
        output_root=tmp_path,
        run_id="resume-run",
        mode="probe",
        cells=["反刍型:同伴关系"],
        per_cell=1,
        dry_run=False,
        resume=True,
        llm_client=llm,
    )

    raw_rows = _read_jsonl(first.raw_path)

    assert first.generated_count == 1
    assert second.generated_count == 0
    assert len(raw_rows) == 1
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_production_per_cell_applies_repressive_quota_buffer(tmp_path):
    result = await generate_corpus(
        config_path=CONFIG_PATH,
        output_root=tmp_path,
        run_id="production-buffer",
        mode="production",
        cells=["压抑型:学业压力", "反刍型:同伴关系"],
        per_cell=10,
        dry_run=True,
        resume=False,
        llm_client=ExplodingLLM(),
    )

    raw_rows = _read_jsonl(result.raw_path)
    counts = {}
    for row in raw_rows:
        key = f"{row['persona']}:{row['scenario']}"
        counts[key] = counts.get(key, 0) + 1

    assert result.generated_count == 22
    assert counts == {
        "压抑型:学业压力": 12,
        "反刍型:同伴关系": 10,
    }
