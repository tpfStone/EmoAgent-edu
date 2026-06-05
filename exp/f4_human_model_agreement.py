from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path("exp/runs/f4_eval_package/f4-pairwise-package-20260603")
PROBE_DIR = Path("exp/runs/f4_pairwise_model_probe/pilot-full-20260603")
ANNOTATION_PATH = PACKAGE_DIR / "human_annotation_template.csv"
RESULTS_PATH = PROBE_DIR / "results.jsonl"
REPORT_PATH = PROBE_DIR / "human_model_agreement_report.md"
DETAIL_CSV_PATH = PROBE_DIR / "human_model_agreement_clean_pairs.csv"
SUMMARY_JSON_PATH = PROBE_DIR / "human_model_agreement_summary.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def normalize_preference(value: str) -> str:
    raw = (value or "").strip()
    if raw in {"A", "B", "tie", "invalid"}:
        return raw
    return ""


def model_prediction(row: dict[str, Any]) -> str:
    evaluation = row.get("evaluation", {})
    if evaluation.get("stable_tie"):
        return "tie"
    return evaluation.get("stable_winner") or "unstable"


def build_detail_rows() -> list[dict[str, Any]]:
    annotations = list(csv.DictReader(ANNOTATION_PATH.open(encoding="utf-8-sig", newline="")))
    clean_annotations = {
        row["pair_id"]: row
        for row in annotations
        if row.get("pair_type") == "clean_f3_orientation_pair"
        and normalize_preference(row.get("human_preference", ""))
    }
    results = [
        row
        for row in load_jsonl(RESULTS_PATH)
        if row.get("pair_id") in clean_annotations
    ]
    detail_rows = []
    for row in results:
        annotation = clean_annotations[row["pair_id"]]
        human = normalize_preference(annotation.get("human_preference", ""))
        prediction = model_prediction(row) if row.get("status") == "ok" else "failed"
        detail_rows.append(
            {
                "model": row.get("model", ""),
                "pair_id": row.get("pair_id", ""),
                "scenario": row.get("scenario", ""),
                "status": row.get("status", ""),
                "human_preference": human,
                "model_prediction": prediction,
                "match": prediction == human,
                "order_ab_winner": row.get("order_ab", {}).get("winner_original", "tie")
                if row.get("status") == "ok"
                else "",
                "order_ba_winner": row.get("order_ba", {}).get("winner_original", "tie")
                if row.get("status") == "ok"
                else "",
                "human_notes": annotation.get("notes", ""),
                "reason_ab": row.get("order_ab", {}).get("reason", "")
                if row.get("status") == "ok"
                else "",
                "reason_ba": row.get("order_ba", {}).get("reason", "")
                if row.get("status") == "ok"
                else "",
                "error": row.get("error", ""),
            }
        )
    return sorted(detail_rows, key=lambda item: (item["model"], item["pair_id"]))


def summarize(detail_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in detail_rows:
        by_model[row["model"]].append(row)

    def rate(values: list[bool]) -> float | None:
        if not values:
            return None
        return round(sum(1 for item in values if item) / len(values), 4)

    repeated_human_distribution = Counter(row["human_preference"] for row in detail_rows)
    model_count = max(len(by_model), 1)
    human_distribution = {
        key: int(value / model_count)
        for key, value in repeated_human_distribution.items()
    }
    summary: dict[str, Any] = {
        "human_pair_count": len({row["pair_id"] for row in detail_rows}),
        "human_distribution": human_distribution,
        "models": {},
    }
    for model, rows in sorted(by_model.items()):
        ok_rows = [row for row in rows if row["status"] == "ok"]
        stable_rows = [
            row for row in ok_rows if row["model_prediction"] in {"A", "B", "tie"}
        ]
        ab_rows = [row for row in ok_rows if row["model_prediction"] in {"A", "B"}]
        by_scenario = {}
        for scenario in sorted({row["scenario"] for row in rows}):
            scenario_rows = [row for row in rows if row["scenario"] == scenario]
            by_scenario[scenario] = {
                "n": len(scenario_rows),
                "agreement": rate([bool(row["match"]) for row in scenario_rows]),
                "predictions": dict(Counter(row["model_prediction"] for row in scenario_rows)),
            }
        summary["models"][model] = {
            "n": len(rows),
            "ok": len(ok_rows),
            "failed": len(rows) - len(ok_rows),
            "agreement_all": rate([bool(row["match"]) for row in rows]),
            "agreement_on_ok": rate([bool(row["match"]) for row in ok_rows]),
            "agreement_on_stable": rate([bool(row["match"]) for row in stable_rows]),
            "stable_or_tie_rate": rate(
                [row["model_prediction"] in {"A", "B", "tie"} for row in ok_rows]
            ),
            "stable_ab_rate": rate([row["model_prediction"] in {"A", "B"} for row in ok_rows]),
            "prediction_distribution": dict(Counter(row["model_prediction"] for row in rows)),
            "human_distribution": dict(Counter(row["human_preference"] for row in rows)),
            "by_scenario": by_scenario,
            "mismatches": [
                {
                    "pair_id": row["pair_id"],
                    "scenario": row["scenario"],
                    "human": row["human_preference"],
                    "model": row["model_prediction"],
                    "notes": row["human_notes"],
                }
                for row in rows
                if not row["match"]
            ],
        }
    return summary


def write_detail_csv(detail_rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "model",
        "pair_id",
        "scenario",
        "status",
        "human_preference",
        "model_prediction",
        "match",
        "order_ab_winner",
        "order_ba_winner",
        "human_notes",
        "reason_ab",
        "reason_ba",
        "error",
    ]
    with DETAIL_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(detail_rows)


def render_report(summary: dict[str, Any]) -> str:
    models = summary["models"]
    lines = [
        "# F4 Human-Model Agreement Report",
        "",
        "## Scope",
        "",
        "- Package: `f4-pairwise-package-20260603`",
        "- Model probe: `pilot-full-20260603`",
        f"- Clean pair human labels: `{summary['human_pair_count']}`",
        "- Human labels are only used for `clean_f3_orientation_pair`; automatic negative/boundary/tie checks remain separate.",
        "",
        "## Human Preference Distribution",
        "",
        "| preference | count |",
        "|---|---:|",
    ]
    human_distribution = next(iter(models.values()))["human_distribution"] if models else {}
    for key, value in sorted(human_distribution.items()):
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Model Agreement",
            "",
            "| model | ok | agreement_all | agreement_on_ok | stable_or_tie_rate | stable_ab_rate | prediction_distribution |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for model, value in sorted(
        models.items(),
        key=lambda item: (
            item[1]["agreement_all"] if item[1]["agreement_all"] is not None else -1,
            item[1]["stable_or_tie_rate"] if item[1]["stable_or_tie_rate"] is not None else -1,
        ),
        reverse=True,
    ):
        lines.append(
            "| {model} | {ok}/{n} | {agreement_all} | {agreement_on_ok} | {stable_or_tie_rate} | {stable_ab_rate} | {pred} |".format(
                model=model,
                ok=value["ok"],
                n=value["n"],
                agreement_all=value["agreement_all"],
                agreement_on_ok=value["agreement_on_ok"],
                stable_or_tie_rate=value["stable_or_tie_rate"],
                stable_ab_rate=value["stable_ab_rate"],
                pred=json.dumps(value["prediction_distribution"], ensure_ascii=False),
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The automatic package showed that several models can reliably reject obviously bad or boundary-risk candidates.",
            "- Human labels on clean c1/c2 pairs are a harder task: the judge must decide interaction fit, not just detect bad text.",
            "- Current labels prefer `B` more often. In this package, `B` usually corresponds to the cognitive-empathy candidate, which fits cases where the student asks for help or wants the situation understood.",
            "- This does not mean F3 should always choose c2. Human notes indicate c1 is often better when the student shows strong negative affect and first needs emotional recognition.",
            "",
            "## Product/Algorithm Takeaways",
            "",
            "- F4 should be split into two responsibilities: boundary/audit filtering and clean-candidate preference selection.",
            "- For first contact, keep the full F1-F2-F3-F4 chain to produce a warm and credible initial response.",
            "- In later turns, do not keep only validating emotion. After trust is established, shift to CBT-style support: validate briefly, clarify thought-feeling-behavior links, and offer one small non-coercive next step.",
            "- Avoid rhetorical questions as the first interaction. Questions should be low-pressure and concrete, or replaced by a tentative statement.",
            "- Add a dialogue-stage signal: `first_contact`, `emotional_containment`, `help_seeking`, `cbt_support`, `follow_up`. F3 can use this to decide whether c1/c2/CBT-support is appropriate.",
            "",
            "## Recommended Runtime Policy",
            "",
            "1. Use a strong model such as `qwen3.7-max-2026-05-20` for boundary/audit filtering because it performed well on automatic boundary checks.",
            "2. Do not use any single model as the final clean-pair chooser yet; agreement with human clean-pair preference is still limited.",
            "3. For first-turn clean pairs, apply a conservative router:",
            "   - strong negative affect -> prefer c1 if safe;",
            "   - explicit help-seeking / asks what to do -> prefer c2 if safe and not rhetorical;",
            "   - unclear -> prefer the candidate with less advice, fewer questions, and more concrete grounding.",
            "4. Only store preference pairs for DPO when model judgment, human/rule expectation, and boundary audit agree.",
            "",
            "## Mismatches",
            "",
        ]
    )
    for model, value in sorted(models.items()):
        lines.append(f"### {model}")
        mismatches = value["mismatches"]
        if not mismatches:
            lines.append("- None")
        else:
            for item in mismatches:
                note = str(item["notes"]).replace("\n", " ")
                lines.append(
                    f"- `{item['pair_id']}` / {item['scenario']}: human={item['human']}, model={item['model']}，note={note}"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    detail_rows = build_detail_rows()
    summary = summarize(detail_rows)
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_detail_csv(detail_rows)
    REPORT_PATH.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps({"report": str(REPORT_PATH), "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
