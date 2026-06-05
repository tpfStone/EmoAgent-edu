from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA_PATH = Path("exp/data/psyqa_labelled.json")
RUNS_DIR = Path("exp/runs/psyqa_strategy_report")

USE_TIER_ORDER = ["direct_exemplar", "strategy_reference", "negative_example", "reject"]
SCENARIO_ORDER = ["学业压力", "同伴关系", "亲子摩擦", "其他"]
AGE_STAGE_ORDER = ["初中", "高中", "大学", "成人", "不明"]
SAFETY_ORDER = ["green", "yellow", "red", "reject"]
QUALITY_ORDER = ["good", "rewrite", "reject"]
EDU_SCENARIOS = ["学业压力", "同伴关系", "亲子摩擦"]

STRATEGY_ORDER = [
    "Restatement",
    "Approval and Reassurance",
    "Interpretation",
    "Information",
    "Direct Guidance",
    "Self-disclosure",
    "Others",
]

STRATEGY_LABELS = {
    "Restatement": "复述澄清",
    "Approval and Reassurance": "支持安抚",
    "Interpretation": "解释理解",
    "Information": "信息提供",
    "Direct Guidance": "直接指导",
    "Self-disclosure": "自我暴露",
    "Others": "其他",
}

STRATEGY_CODES = {
    "Restatement": "RS",
    "Approval and Reassurance": "AR",
    "Interpretation": "IP",
    "Information": "IN",
    "Direct Guidance": "DG",
    "Self-disclosure": "SD",
    "Others": "OT",
}

PALETTE = {
    "direct_exemplar": "#3B82F6",
    "strategy_reference": "#22C55E",
    "negative_example": "#F59E0B",
    "reject": "#EF4444",
    "green": "#22C55E",
    "yellow": "#F59E0B",
    "red": "#EF4444",
    "good": "#3B82F6",
    "rewrite": "#F59E0B",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize annotated PsyQA strategy distributions for EmoEdu experiments.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Path to annotated PsyQA JSON array.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Output directory. Defaults to exp/runs/psyqa_strategy_report/<run-id>.")
    parser.add_argument("--run-id", type=str, default=None, help="Run id used when --out-dir is not provided.")
    parser.add_argument("--top-n", type=int, default=20, help="Top-N reject reasons and sequence patterns to export.")
    return parser.parse_args()


def configure_matplotlib() -> None:
    # Matplotlib 默认字体不一定支持中文。这里按 Windows/macOS/Linux 常见字体顺序寻找可用字体。
    from matplotlib import font_manager

    installed = {font.name for font in font_manager.fontManager.ttflist}
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "PingFang SC",
        "WenQuanYi Micro Hei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    chosen = next((name for name in candidates if name in installed), "DejaVu Sans")
    plt.rcParams["font.sans-serif"] = [chosen, "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        rows = json.load(file)
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a JSON array")
    return rows


def safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def build_sample_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        seq = [str(item) for item in safe_list(row.get("psyqa_strategy_sequence")) if str(item).strip()]
        reject_reasons = [str(item) for item in safe_list(row.get("reject_reasons")) if str(item).strip()]
        records.append(
            {
                "row_index": idx,
                "source_index": row.get("source_index", idx),
                "status": row.get("status", "unknown"),
                "use_tier": row.get("use_tier", "unknown"),
                "scenario": row.get("scenario", "unknown"),
                "age_stage": row.get("age_stage", "unknown"),
                "minor_suitability": bool(row.get("minor_suitability", False)),
                "safety_level": row.get("safety_level", "unknown"),
                "quality_label": row.get("quality_label", "unknown"),
                "input_chars": len(str(row.get("input", ""))),
                "output_chars": len(str(row.get("output", ""))),
                "strategy_occurrences": len(seq),
                "unique_strategy_count": len(set(seq)),
                "strategy_sequence_key": " > ".join(STRATEGY_CODES.get(item, item) for item in seq),
                "reject_reason_count": len(reject_reasons),
            }
        )
    return pd.DataFrame.from_records(records)


def build_strategy_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        seq = [str(item) for item in safe_list(row.get("psyqa_strategy_sequence")) if str(item).strip()]
        for pos, strategy in enumerate(seq):
            records.append(
                {
                    "row_index": idx,
                    "source_index": row.get("source_index", idx),
                    "position": pos,
                    "strategy": strategy,
                    "strategy_label": STRATEGY_LABELS.get(strategy, strategy),
                    "use_tier": row.get("use_tier", "unknown"),
                    "scenario": row.get("scenario", "unknown"),
                    "age_stage": row.get("age_stage", "unknown"),
                    "safety_level": row.get("safety_level", "unknown"),
                    "quality_label": row.get("quality_label", "unknown"),
                }
            )
    return pd.DataFrame.from_records(records)


def build_reject_reason_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        for reason in safe_list(row.get("reject_reasons")):
            reason = str(reason).strip()
            if not reason:
                continue
            records.append(
                {
                    "row_index": idx,
                    "source_index": row.get("source_index", idx),
                    "reason": reason,
                    "use_tier": row.get("use_tier", "unknown"),
                    "scenario": row.get("scenario", "unknown"),
                    "age_stage": row.get("age_stage", "unknown"),
                }
            )
    return pd.DataFrame.from_records(records)


def ordered_value_counts(series: pd.Series, order: list[str] | None = None) -> pd.Series:
    counts = series.fillna("unknown").astype(str).value_counts()
    if not order:
        return counts
    ordered = [item for item in order if item in counts.index]
    ordered.extend([item for item in counts.index if item not in ordered])
    return counts.reindex(ordered)


def add_bar_labels(ax: plt.Axes, orientation: str = "vertical", fmt: str = "{:.0f}") -> None:
    for patch in ax.patches:
        if orientation == "horizontal":
            width = patch.get_width()
            if width <= 0 or math.isnan(width):
                continue
            ax.text(width, patch.get_y() + patch.get_height() / 2, "  " + fmt.format(width), va="center", fontsize=9)
        else:
            height = patch.get_height()
            if height <= 0 or math.isnan(height):
                continue
            ax.text(patch.get_x() + patch.get_width() / 2, height, fmt.format(height), ha="center", va="bottom", fontsize=9)


def save_figure(fig: plt.Figure, figures_dir: Path, filename: str) -> Path:
    figures_dir.mkdir(parents=True, exist_ok=True)
    path = figures_dir / filename
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_dataset_overview(df: pd.DataFrame, figures_dir: Path) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.5))
    configs = [
        ("use_tier", "样本用途分布", USE_TIER_ORDER),
        ("scenario", "情境分布", SCENARIO_ORDER),
        ("age_stage", "年龄阶段分布", AGE_STAGE_ORDER),
        ("safety_level", "安全等级分布", SAFETY_ORDER),
    ]
    for ax, (column, title, order) in zip(axes.ravel(), configs):
        counts = ordered_value_counts(df[column], order)
        colors = [PALETTE.get(item, "#64748B") for item in counts.index]
        ax.bar(counts.index.astype(str), counts.values, color=colors)
        ax.set_title(title, fontsize=13, pad=12)
        ax.set_ylabel("样本数")
        ax.tick_params(axis="x", labelrotation=25)
        ax.grid(axis="y", linestyle="--", alpha=0.25)
        add_bar_labels(ax)
    return save_figure(fig, figures_dir, "01_dataset_overview.png")


def plot_education_and_direct_profile(df: pd.DataFrame, figures_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    tier_by_scenario = pd.crosstab(df["scenario"], df["use_tier"])
    tier_by_scenario = tier_by_scenario.reindex(index=SCENARIO_ORDER, columns=USE_TIER_ORDER, fill_value=0)
    bottom = np.zeros(len(tier_by_scenario.index))
    for tier in USE_TIER_ORDER:
        axes[0].bar(
            tier_by_scenario.index,
            tier_by_scenario[tier].values,
            bottom=bottom,
            label=tier,
            color=PALETTE.get(tier, "#64748B"),
        )
        bottom += tier_by_scenario[tier].values
    axes[0].set_title("各情境下的样本用途构成", fontsize=13, pad=12)
    axes[0].set_ylabel("样本数")
    axes[0].tick_params(axis="x", labelrotation=20)
    axes[0].grid(axis="y", linestyle="--", alpha=0.25)
    axes[0].legend(fontsize=9)

    direct_df = df[df["use_tier"] == "direct_exemplar"]
    direct_age = pd.crosstab(direct_df["scenario"], direct_df["age_stage"])
    direct_age = direct_age.reindex(index=SCENARIO_ORDER, columns=AGE_STAGE_ORDER, fill_value=0)
    age_colors = ["#2563EB", "#7C3AED", "#14B8A6", "#F97316", "#94A3B8"]
    bottom = np.zeros(len(direct_age.index))
    for idx, age in enumerate(AGE_STAGE_ORDER):
        axes[1].bar(direct_age.index, direct_age[age].values, bottom=bottom, label=age, color=age_colors[idx])
        bottom += direct_age[age].values
    axes[1].set_title("direct_exemplar 的情境与年龄构成", fontsize=13, pad=12)
    axes[1].set_ylabel("样本数")
    axes[1].tick_params(axis="x", labelrotation=20)
    axes[1].grid(axis="y", linestyle="--", alpha=0.25)
    axes[1].legend(fontsize=9)

    return save_figure(fig, figures_dir, "02_education_and_direct_profile.png")


def plot_strategy_distribution(sample_df: pd.DataFrame, strategy_df: pd.DataFrame, figures_dir: Path) -> Path:
    if strategy_df.empty:
        raise ValueError("No strategy records found")

    occurrence = ordered_value_counts(strategy_df["strategy"], STRATEGY_ORDER)
    coverage = strategy_df.drop_duplicates(["row_index", "strategy"])["strategy"].value_counts()
    coverage = coverage.reindex(occurrence.index).fillna(0)

    labels = [STRATEGY_LABELS.get(item, item) for item in occurrence.index]
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.barh(y - 0.18, occurrence.values, height=0.36, label="出现次数", color="#2563EB")
    ax.barh(y + 0.18, coverage.values, height=0.36, label="覆盖样本数", color="#22C55E")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title("PsyQA 策略总体分布：出现次数 vs 覆盖样本数", fontsize=13, pad=12)
    ax.set_xlabel("数量")
    ax.grid(axis="x", linestyle="--", alpha=0.25)
    ax.legend()
    for yi, value in enumerate(occurrence.values):
        ax.text(value, yi - 0.18, f"  {int(value)}", va="center", fontsize=9)
    for yi, value in enumerate(coverage.values):
        ax.text(value, yi + 0.18, f"  {int(value)}", va="center", fontsize=9)

    return save_figure(fig, figures_dir, "03_strategy_distribution.png")


def ordered_matrix(frame: pd.DataFrame, row_col: str, strategy_col: str = "strategy", row_order: list[str] | None = None) -> pd.DataFrame:
    matrix = pd.crosstab(frame[row_col], frame[strategy_col])
    rows = row_order or list(matrix.index)
    rows = [item for item in rows if item in matrix.index] + [item for item in matrix.index if item not in rows]
    cols = [item for item in STRATEGY_ORDER if item in matrix.columns] + [item for item in matrix.columns if item not in STRATEGY_ORDER]
    matrix = matrix.reindex(index=rows, columns=cols, fill_value=0)
    return matrix


def plot_heatmap(matrix: pd.DataFrame, title: str, figures_dir: Path, filename: str, percent: bool = True) -> Path:
    if percent:
        values = matrix.div(matrix.sum(axis=1).replace(0, np.nan), axis=0).fillna(0) * 100
        cbar_label = "行内占比 %"
        fmt = "{:.1f}"
    else:
        values = matrix.astype(float)
        cbar_label = "次数"
        fmt = "{:.0f}"

    fig, ax = plt.subplots(figsize=(12, max(4.5, 0.72 * len(values.index) + 2)))
    image = ax.imshow(values.values, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(np.arange(len(values.columns)))
    ax.set_xticklabels([STRATEGY_LABELS.get(item, item) for item in values.columns], rotation=25, ha="right")
    ax.set_yticks(np.arange(len(values.index)))
    ax.set_yticklabels(values.index)
    ax.set_title(title, fontsize=13, pad=12)

    threshold = np.nanmax(values.values) * 0.55 if values.size else 0
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values.iat[i, j]
            if value == 0:
                continue
            color = "white" if value >= threshold else "#0F172A"
            ax.text(j, i, fmt.format(value), ha="center", va="center", fontsize=8, color=color)

    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label(cbar_label)
    return save_figure(fig, figures_dir, filename)


def plot_transition_heatmap(rows: list[dict[str, Any]], figures_dir: Path) -> Path:
    counter: Counter[tuple[str, str]] = Counter()
    for row in rows:
        seq = [str(item) for item in safe_list(row.get("psyqa_strategy_sequence")) if str(item).strip()]
        for left, right in zip(seq, seq[1:]):
            counter[(left, right)] += 1

    strategies = [item for item in STRATEGY_ORDER if any(item in pair for pair in counter)]
    for left, right in counter:
        if left not in strategies:
            strategies.append(left)
        if right not in strategies:
            strategies.append(right)

    matrix = pd.DataFrame(0, index=strategies, columns=strategies, dtype=int)
    for (left, right), count in counter.items():
        matrix.loc[left, right] = count

    matrix.index = [STRATEGY_LABELS.get(item, item) for item in matrix.index]
    matrix.columns = [STRATEGY_LABELS.get(item, item) for item in matrix.columns]
    return plot_heatmap(matrix, "相邻策略转移分布：上一策略 -> 下一策略", figures_dir, "06_strategy_transition_heatmap.png", percent=True)


def plot_reject_reasons(reason_df: pd.DataFrame, figures_dir: Path, top_n: int) -> Path | None:
    if reason_df.empty:
        return None
    counts = reason_df["reason"].value_counts().head(top_n).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(12, max(5, top_n * 0.34)))
    ax.barh(counts.index, counts.values, color="#EF4444")
    ax.set_title(f"Top {len(counts)} 排除/负例原因", fontsize=13, pad=12)
    ax.set_xlabel("出现次数")
    ax.grid(axis="x", linestyle="--", alpha=0.25)
    add_bar_labels(ax, orientation="horizontal")
    return save_figure(fig, figures_dir, "07_reject_reasons.png")


def plot_length_complexity(df: pd.DataFrame, figures_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    tiers = [tier for tier in USE_TIER_ORDER if tier in set(df["use_tier"])]
    output_groups = [df[df["use_tier"] == tier]["output_chars"].clip(upper=df["output_chars"].quantile(0.98)).values for tier in tiers]
    strategy_groups = [df[df["use_tier"] == tier]["strategy_occurrences"].values for tier in tiers]

    axes[0].boxplot(output_groups, tick_labels=tiers, showfliers=False, patch_artist=True)
    axes[0].set_title("不同用途样本的回复长度分布", fontsize=13, pad=12)
    axes[0].set_ylabel("output 字符数（98% 分位截断）")
    axes[0].tick_params(axis="x", labelrotation=20)
    axes[0].grid(axis="y", linestyle="--", alpha=0.25)

    axes[1].boxplot(strategy_groups, tick_labels=tiers, showfliers=False, patch_artist=True)
    axes[1].set_title("不同用途样本的策略密度分布", fontsize=13, pad=12)
    axes[1].set_ylabel("单条回复内策略出现次数")
    axes[1].tick_params(axis="x", labelrotation=20)
    axes[1].grid(axis="y", linestyle="--", alpha=0.25)

    return save_figure(fig, figures_dir, "08_length_and_strategy_density.png")


def export_tables(df: pd.DataFrame, strategy_df: pd.DataFrame, reason_df: pd.DataFrame, out_dir: Path, top_n: int) -> dict[str, Path]:
    tables_dir = out_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    pd.crosstab(df["scenario"], df["use_tier"]).to_csv(tables_dir / "scenario_by_use_tier.csv", encoding="utf-8-sig")
    paths["scenario_by_use_tier"] = tables_dir / "scenario_by_use_tier.csv"

    if not strategy_df.empty:
        strategy_stats = pd.DataFrame(
            {
                "occurrences": strategy_df["strategy"].value_counts(),
                "sample_coverage": strategy_df.drop_duplicates(["row_index", "strategy"])["strategy"].value_counts(),
            }
        ).fillna(0).astype(int)
        strategy_stats["strategy_label"] = [STRATEGY_LABELS.get(idx, idx) for idx in strategy_stats.index]
        strategy_stats.to_csv(tables_dir / "strategy_stats.csv", encoding="utf-8-sig")
        paths["strategy_stats"] = tables_dir / "strategy_stats.csv"

    sequence_counts = df[df["strategy_sequence_key"] != ""]["strategy_sequence_key"].value_counts().head(top_n)
    sequence_counts.to_frame("count").to_csv(tables_dir / "top_strategy_sequences.csv", encoding="utf-8-sig")
    paths["top_strategy_sequences"] = tables_dir / "top_strategy_sequences.csv"

    if not reason_df.empty:
        reason_df["reason"].value_counts().head(top_n).to_frame("count").to_csv(
            tables_dir / "top_reject_reasons.csv", encoding="utf-8-sig"
        )
        paths["top_reject_reasons"] = tables_dir / "top_reject_reasons.csv"

    return paths


def as_count_dict(series: pd.Series, order: list[str] | None = None) -> dict[str, int]:
    counts = ordered_value_counts(series, order)
    return {str(key): int(value) for key, value in counts.items()}


def make_summary(df: pd.DataFrame, strategy_df: pd.DataFrame, reason_df: pd.DataFrame) -> dict[str, Any]:
    direct = df[df["use_tier"] == "direct_exemplar"]
    direct_edu = direct[direct["scenario"].isin(EDU_SCENARIOS)]
    strategy_counts = strategy_df["strategy"].value_counts() if not strategy_df.empty else pd.Series(dtype=int)
    reason_counts = reason_df["reason"].value_counts() if not reason_df.empty else pd.Series(dtype=int)

    return {
        "total_rows": int(len(df)),
        "ok_rows": int((df["status"] == "ok").sum()) if "status" in df else None,
        "use_tier_counts": as_count_dict(df["use_tier"], USE_TIER_ORDER),
        "scenario_counts": as_count_dict(df["scenario"], SCENARIO_ORDER),
        "age_stage_counts": as_count_dict(df["age_stage"], AGE_STAGE_ORDER),
        "safety_level_counts": as_count_dict(df["safety_level"], SAFETY_ORDER),
        "quality_label_counts": as_count_dict(df["quality_label"], QUALITY_ORDER),
        "minor_suitability_count": int(df["minor_suitability"].sum()),
        "direct_exemplar_count": int(len(direct)),
        "direct_exemplar_edu_count": int(len(direct_edu)),
        "direct_exemplar_by_scenario": as_count_dict(direct["scenario"], SCENARIO_ORDER),
        "avg_output_chars_by_use_tier": {
            str(key): round(float(value), 2) for key, value in df.groupby("use_tier")["output_chars"].mean().items()
        },
        "avg_strategy_occurrences_by_use_tier": {
            str(key): round(float(value), 2) for key, value in df.groupby("use_tier")["strategy_occurrences"].mean().items()
        },
        "top_strategies": {str(key): int(value) for key, value in strategy_counts.head(20).items()},
        "top_reject_reasons": {str(key): int(value) for key, value in reason_counts.head(20).items()},
    }


def write_report(out_dir: Path, figures: list[Path], summary: dict[str, Any]) -> Path:
    report_path = out_dir / "report.md"
    lines = [
        "# PsyQA 标注数据策略分布可视化报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 核心指标",
        "",
        f"- 总样本数：{summary['total_rows']}",
        f"- direct_exemplar：{summary['direct_exemplar_count']}，其中教育三类情境：{summary['direct_exemplar_edu_count']}",
        f"- minor_suitability=True：{summary['minor_suitability_count']}",
        f"- use_tier：{json.dumps(summary['use_tier_counts'], ensure_ascii=False)}",
        f"- scenario：{json.dumps(summary['scenario_counts'], ensure_ascii=False)}",
        f"- quality_label：{json.dumps(summary['quality_label_counts'], ensure_ascii=False)}",
        "",
        "## 策略分布要点",
        "",
    ]

    for strategy, count in list(summary["top_strategies"].items())[:10]:
        label = STRATEGY_LABELS.get(strategy, strategy)
        lines.append(f"- {label}（{strategy}）：{count}")

    lines.extend(["", "## 图表", ""])
    for figure in figures:
        rel = figure.relative_to(out_dir).as_posix()
        title = figure.stem.replace("_", " ")
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"![{title}]({rel})")
        lines.append("")

    lines.extend(
        [
            "## 给后续 critic 实验的使用建议",
            "",
            "- `direct_exemplar` 适合作为 F3/F4 的正向教育情境输入，尤其是学业压力、同伴关系、亲子摩擦三类。",
            "- `negative_example` 和 `reject` 更适合作为 critic 的质量与安全审计样本，用来检测说教、成人化、过长、危机处理等问题。",
            "- 策略热力图能帮助检查某些策略是否被过度使用，例如 Direct Guidance 过高时，生成器可能容易从支持转向说教。",
            "- 策略转移图适合用于构建候选回复的结构性约束，例如先承接情绪，再解释理解，最后给低负担行动。",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    args = parse_args()
    configure_matplotlib()

    run_id = args.run_id or datetime.now().strftime("psyqa-strategy-%Y%m%d-%H%M%S")
    out_dir = args.out_dir or (RUNS_DIR / run_id)
    figures_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(args.data)
    sample_df = build_sample_frame(rows)
    strategy_df = build_strategy_frame(rows)
    reason_df = build_reject_reason_frame(rows)

    figures: list[Path] = []
    figures.append(plot_dataset_overview(sample_df, figures_dir))
    figures.append(plot_education_and_direct_profile(sample_df, figures_dir))
    figures.append(plot_strategy_distribution(sample_df, strategy_df, figures_dir))

    strategy_by_tier = ordered_matrix(strategy_df, "use_tier", row_order=USE_TIER_ORDER)
    figures.append(plot_heatmap(strategy_by_tier, "不同样本用途下的策略占比", figures_dir, "04_strategy_by_use_tier_heatmap.png"))

    strategy_by_scenario = ordered_matrix(strategy_df, "scenario", row_order=SCENARIO_ORDER)
    figures.append(plot_heatmap(strategy_by_scenario, "不同教育/生活情境下的策略占比", figures_dir, "05_strategy_by_scenario_heatmap.png"))

    figures.append(plot_transition_heatmap(rows, figures_dir))

    reject_figure = plot_reject_reasons(reason_df, figures_dir, args.top_n)
    if reject_figure is not None:
        figures.append(reject_figure)

    figures.append(plot_length_complexity(sample_df, figures_dir))

    table_paths = export_tables(sample_df, strategy_df, reason_df, out_dir, args.top_n)
    summary = make_summary(sample_df, strategy_df, reason_df)
    summary["data_path"] = str(args.data)
    summary["output_dir"] = str(out_dir)
    summary["figures"] = [str(path) for path in figures]
    summary["tables"] = {key: str(path) for key, path in table_paths.items()}

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = write_report(out_dir, figures, summary)

    print(f"Loaded rows: {len(rows)}")
    print(f"Strategy records: {len(strategy_df)}")
    print(f"Reject reason records: {len(reason_df)}")
    print(f"Output directory: {out_dir}")
    print(f"Report: {report_path}")
    print(f"Summary: {summary_path}")
    print("Figures:")
    for path in figures:
        print(f"- {path}")


if __name__ == "__main__":
    main()

