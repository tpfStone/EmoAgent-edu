import csv
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_pairs(path: Path):
    fields = [
        "pair_id",
        "sample_no",
        "scenario",
        "user_text",
        "history_json",
        "c1_orientation",
        "c1_text",
        "c2_orientation",
        "c2_text",
        "source_run",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "pair_id": "sample-3",
                "sample_no": "3",
                "scenario": "同伴关系",
                "user_text": "他们没叫我进小群。",
                "history_json": "[]",
                "c1_orientation": "情感共情型",
                "c1_text": "候选一",
                "c2_orientation": "认知共情型",
                "c2_text": "候选二",
                "source_run": "generated",
                "notes": "",
            }
        )


def _mock_env():
    env = os.environ.copy()
    env["LLM_PROVIDER"] = "mock"
    return env


def test_pairwise_judge_cli_runs_from_repo_root(tmp_path):
    pair_path = tmp_path / "pairs.csv"
    output_dir = tmp_path / "judge"
    _write_pairs(pair_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/corpus/f9_pairwise_judge.py",
            "--pair-package",
            str(pair_path),
            "--output-dir",
            str(output_dir),
            "--pairwise-sample-count",
            "1",
        ],
        cwd=ROOT,
        env=_mock_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "f9_pairwise_judge_summary.csv").exists()


def test_pairwise_pointwise_baseline_cli_runs_from_repo_root(tmp_path):
    pair_path = tmp_path / "pairs.csv"
    output_path = tmp_path / "baseline.csv"
    _write_pairs(pair_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/corpus/f9_pairwise_pointwise_baseline.py",
            "--pair-package",
            str(pair_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        env=_mock_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
