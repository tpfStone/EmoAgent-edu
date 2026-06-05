from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

EXP_DIR = Path(__file__).resolve().parent
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

import f1_safety_gate_experiment as f1

RUNS_DIR = Path("exp/runs/f1_keyword_weight_probe")
DEFAULT_WEIGHTS = "1:0,1:0.25,1:0.5,1:1,1:2"
DEFAULT_KEYWORD_SIZES = "50,100,200,400,800,1200"
DEFAULT_STRATEGIES = "jieba_word,char_ngram,mixed"

RATONALE_BOILERPLATE_PATTERNS = [
    r"完全不适合初中生情感教育场景",
    r"不适合初中生情感教育场景",
    r"适合初中生情感教育场景",
    r"初中生情感教育",
    r"适合初中生参考",
    r"适合初中生使用",
    r"可作为策略参考",
    r"作为策略参考",
    r"可作为负例",
    r"作为负例",
    r"直接样例",
    r"样例库",
    r"本项目",
    r"direct_exemplar",
    r"strategy_reference",
    r"negative_example",
    r"reject",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe keyword construction weights with input text and filtered rationale signals."
    )
    parser.add_argument("--data", type=Path, default=f1.DATA_PATH)
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--label-policy", choices=["drop_reject", "reject_to_red"], default="drop_reject")
    parser.add_argument("--weights", type=str, default=DEFAULT_WEIGHTS, help="Comma list like 1:0,1:0.5,1:1.")
    parser.add_argument(
        "--rationale-mode",
        choices=["none", "last", "filtered", "all"],
        default="filtered",
        help="How rationale is used for keyword ranking. Evaluation still only uses input keywords.",
    )
    parser.add_argument("--keyword-sizes", type=str, default=DEFAULT_KEYWORD_SIZES)
    parser.add_argument("--strategies", type=str, default=DEFAULT_STRATEGIES)
    parser.add_argument("--min-token-count", type=float, default=2.0)
    parser.add_argument("--max-keyword-candidates", type=int, default=50000)
    parser.add_argument("--top-k", type=int, default=40, help="Keywords per class exported for human review.")
    return parser.parse_args()


def parse_weights(raw: str) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for item in f1.parse_csv_list(raw):
        if ":" not in item:
            raise ValueError(f"Invalid weight pair: {item}; expected input:rationale")
        left, right = item.split(":", 1)
        pairs.append((float(left), float(right)))
    return pairs


def rationale_last_sentence(text: Any) -> str:
    value = f1.normalize_text(text)
    if not value:
        return ""
    parts = [part.strip() for part in re.split(r"[。！？!?；;]\s*", value) if part.strip()]
    return parts[-1] if parts else value


def rationale_filtered_signal(text: Any) -> str:
    value = f1.normalize_text(text)
    if not value:
        return ""
    sentences = [part.strip() for part in re.split(r"[。！？!?；;]\s*", value) if part.strip()]
    kept: list[str] = []
    for sentence in sentences:
        if any(re.search(pattern, sentence, flags=re.IGNORECASE) for pattern in RATONALE_BOILERPLATE_PATTERNS):
            continue
        if re.search(r"(适合|不适合).*(初中|项目|场景|样例|参考|教育)", sentence):
            continue
        if re.search(r"(可作为|作为).*(策略|负例|样例|参考)", sentence):
            continue
        kept.append(sentence)
    return "。".join(kept)


def rationale_text_by_mode(text: Any, mode: str) -> str:
    if mode == "none":
        return ""
    if mode == "last":
        return rationale_last_sentence(text)
    if mode == "filtered":
        return rationale_filtered_signal(text)
    if mode == "all":
        return f1.normalize_text(text)
    raise ValueError(f"unknown rationale mode: {mode}")


def weighted_tokens_with_last_rationale(
    row: dict[str, Any],
    tokenizer: Callable[[Any], list[str]],
    input_weight: float,
    rationale_weight: float,
    rationale_mode: str,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    if input_weight:
        for token in tokenizer(row.get("input", "")):
            counts[token] += input_weight
    rationale_text = rationale_text_by_mode(row.get("rationale", ""), rationale_mode)
    if rationale_weight and rationale_text:
        for token in tokenizer(rationale_text):
            counts[token] += rationale_weight
    return counts


def rank_keywords_last_rationale(
    train_rows: list[dict[str, Any]],
    tokenizer: Callable[[Any], list[str]],
    input_weight: float,
    rationale_weight: float,
    rationale_mode: str,
    min_token_count: float,
    max_candidates: int,
) -> list[dict[str, Any]]:
    token_class_counts: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(len(f1.LABELS), dtype=np.float64))
    class_totals = np.zeros(len(f1.LABELS), dtype=np.float64)
    doc_freq: Counter[str] = Counter()

    for row in train_rows:
        label_id = row["target_id"]
        counts = weighted_tokens_with_last_rationale(row, tokenizer, input_weight, rationale_weight, rationale_mode)
        for token, value in counts.items():
            token_class_counts[token][label_id] += float(value)
            class_totals[label_id] += float(value)
        for token in counts:
            doc_freq[token] += 1

    global_total = float(class_totals.sum())
    vocab_size = max(1, len(token_class_counts))
    alpha = 0.5
    ranked: list[dict[str, Any]] = []
    for token, counts in token_class_counts.items():
        total = float(counts.sum())
        if total < min_token_count:
            continue
        class_scores = []
        for class_id in range(len(f1.LABELS)):
            c_count = counts[class_id]
            rest_count = total - c_count
            c_total = class_totals[class_id]
            rest_total = global_total - c_total
            p_c = (c_count + alpha) / (c_total + alpha * vocab_size)
            p_rest = (rest_count + alpha) / (rest_total + alpha * vocab_size)
            support = math.log1p(total) * math.sqrt(max(1, doc_freq[token]))
            class_scores.append(float(math.log(p_c / p_rest) * support))
        best_class = int(np.argmax(class_scores))
        ranked.append(
            {
                "keyword": token,
                "score": float(class_scores[best_class]),
                "target_hint": f1.ID_TO_LABEL[best_class],
                "weighted_count": round(total, 3),
                "doc_freq": int(doc_freq[token]),
                "class_counts": {f1.ID_TO_LABEL[i]: round(float(counts[i]), 3) for i in range(len(f1.LABELS))},
            }
        )

    ranked.sort(key=lambda item: (item["score"], item["weighted_count"], item["doc_freq"]), reverse=True)
    return ranked[:max_candidates]


def evaluate_keyword_config(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    tokenizer: Callable[[Any], list[str]],
    keywords: list[str],
) -> dict[str, Any]:
    y_train = f1.label_array(train_rows)
    y_val = f1.label_array(val_rows)
    y_test = f1.label_array(test_rows)
    x_train = f1.build_keyword_matrix(train_rows, keywords, tokenizer)
    x_val = f1.build_keyword_matrix(val_rows, keywords, tokenizer)
    x_test = f1.build_keyword_matrix(test_rows, keywords, tokenizer)

    scaler = StandardScaler()
    x_train = scaler.fit_transform(x_train)
    x_val = scaler.transform(x_val)
    x_test = scaler.transform(x_test)

    clf = LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs")
    clf.fit(x_train, y_train)
    pred_val = clf.predict(x_val)
    pred_test = clf.predict(x_test)
    return {
        **f1.metrics_dict(y_val, pred_val, prefix="val_"),
        **f1.metrics_dict(y_test, pred_test, prefix="test_"),
    }


def keywords_for_review(
    ranked: list[dict[str, Any]],
    strategy: str,
    input_weight: float,
    rationale_weight: float,
    rationale_mode: str,
    keyword_n: int,
    top_k: int,
) -> list[dict[str, Any]]:
    selected = f1.select_top_keywords(ranked, keyword_n)
    rows: list[dict[str, Any]] = []
    for label in f1.LABELS:
        label_items = [item for item in selected if item["target_hint"] == label][:top_k]
        for rank, item in enumerate(label_items, start=1):
            rows.append(
                {
                    "strategy": strategy,
                    "input_weight": input_weight,
                    "rationale_mode": rationale_mode,
                    "rationale_weight": rationale_weight,
                    "keyword_n": keyword_n,
                    "target_hint": label,
                    "rank_in_class": rank,
                    "keyword": item["keyword"],
                    "score": item["score"],
                    "weighted_count": item["weighted_count"],
                    "doc_freq": item["doc_freq"],
                    "green_count": item["class_counts"].get("green", 0),
                    "yellow_count": item["class_counts"].get("yellow", 0),
                    "red_count": item["class_counts"].get("red", 0),
                }
            )
    return rows


def write_review_markdown(path: Path, top_configs: pd.DataFrame, review_df: pd.DataFrame) -> None:
    lines = [
        "# F1 Safety Keyword Weight Probe Review",
        "",
        "关键词由 `input` 和 `rationale` 最后一句共同统计构建；模型评估时只使用 `input` 中的关键词频次。",
        "",
        "## Top Configs",
        "",
        top_configs.to_markdown(index=False),
        "",
        "## Human Review Keyword Lists",
        "",
    ]
    for _, config in top_configs.iterrows():
        mask = (
            (review_df["strategy"] == config["strategy"])
            & (review_df["input_weight"] == config["input_weight"])
            & (review_df["rationale_mode"] == config["rationale_mode"])
            & (review_df["rationale_weight"] == config["rationale_weight"])
            & (review_df["keyword_n"] == config["keyword_n"])
        )
        subset = review_df[mask]
        lines.append(
            f"### {config['strategy']} | input={config['input_weight']} | rationale_mode={config['rationale_mode']} | rationale={config['rationale_weight']} | n={int(config['keyword_n'])}"
        )
        lines.append("")
        for label in f1.LABELS:
            label_words = subset[subset["target_hint"] == label]["keyword"].head(30).tolist()
            lines.append(f"- {label}: " + " / ".join(label_words))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    f1.set_seed(args.seed)
    run_id = args.run_id or datetime.now().strftime("f1-keyword-weight-%Y%m%d-%H%M%S")
    out_dir = args.out_dir or (RUNS_DIR / run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = f1.load_rows(args.data, args.label_policy)
    splits = f1.split_rows(rows, args.seed, args.test_size, args.val_size)
    train_rows = f1.rows_by_indices(rows, splits["train"])
    val_rows = f1.rows_by_indices(rows, splits["val"])
    test_rows = f1.rows_by_indices(rows, splits["test"])

    strategies = f1.parse_csv_list(args.strategies)
    keyword_sizes = f1.parse_int_list(args.keyword_sizes)
    weights = parse_weights(args.weights)
    all_results: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    ranked_dir = out_dir / "ranked_keywords"
    ranked_dir.mkdir(exist_ok=True)

    print(f"Loaded rows: {len(rows)}")
    print(f"Weights: {weights}")
    print(f"Rationale mode: {args.rationale_mode}")
    print(f"Strategies: {strategies}")
    print(f"Keyword sizes: {keyword_sizes}")

    for input_weight, rationale_weight in weights:
        for strategy in strategies:
            tokenizer = f1.tokenizer_for_strategy(strategy)
            started = time.time()
            ranked = rank_keywords_last_rationale(
                train_rows,
                tokenizer,
                input_weight=input_weight,
                rationale_weight=rationale_weight,
                rationale_mode=args.rationale_mode,
                min_token_count=args.min_token_count,
                max_candidates=args.max_keyword_candidates,
            )
            ranked_path = ranked_dir / f"{strategy}_input{input_weight:g}_{args.rationale_mode}{rationale_weight:g}.json"
            ranked_path.write_text(json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8")
            print(
                f"[{strategy} input={input_weight:g} rationale_{args.rationale_mode}={rationale_weight:g}] "
                f"ranked {len(ranked)} candidates in {time.time() - started:.1f}s"
            )
            for keyword_n in keyword_sizes:
                selected = f1.select_top_keywords(ranked, keyword_n)
                keywords = [item["keyword"] for item in selected]
                metrics = evaluate_keyword_config(train_rows, val_rows, test_rows, tokenizer, keywords)
                record = {
                    "strategy": strategy,
                    "input_weight": input_weight,
                    "rationale_mode": args.rationale_mode,
                    "rationale_weight": rationale_weight,
                    "keyword_n": len(keywords),
                    **metrics,
                }
                all_results.append(record)
                print(
                    f"  n={len(keywords):4d} "
                    f"val_macro_f1={record['val_macro_f1']:.4f} test_macro_f1={record['test_macro_f1']:.4f}"
                )
            best_n_for_config = max(
                [
                    row
                    for row in all_results
                    if row["strategy"] == strategy
                    and row["input_weight"] == input_weight
                    and row["rationale_mode"] == args.rationale_mode
                    and row["rationale_weight"] == rationale_weight
                ],
                key=lambda row: (row["val_macro_f1"], row["val_balanced_accuracy"]),
            )["keyword_n"]
            review_rows.extend(
                keywords_for_review(
                    ranked,
                    strategy,
                    input_weight,
                    rationale_weight,
                    args.rationale_mode,
                    int(best_n_for_config),
                    args.top_k,
                )
            )

    results_df = pd.DataFrame(all_results).sort_values(
        by=["val_macro_f1", "val_balanced_accuracy", "test_macro_f1"], ascending=False
    )
    review_df = pd.DataFrame(review_rows)
    results_df.to_csv(out_dir / "weight_probe_results.csv", index=False, encoding="utf-8")
    review_df.to_csv(out_dir / "keyword_review_candidates.csv", index=False, encoding="utf-8-sig")

    top_configs = results_df.head(10)
    write_review_markdown(out_dir / "keyword_review.md", top_configs, review_df)
    summary = {
        "run_id": run_id,
        "data_path": str(args.data),
        "rows": len(rows),
        "label_policy": args.label_policy,
        "rationale_mode": args.rationale_mode,
        "weights": [{"input": i, "rationale": r} for i, r in weights],
        "strategies": strategies,
        "keyword_sizes": keyword_sizes,
        "best_config": top_configs.iloc[0].to_dict(),
        "outputs": {
            "results_csv": str(out_dir / "weight_probe_results.csv"),
            "review_csv": str(out_dir / "keyword_review_candidates.csv"),
            "review_md": str(out_dir / "keyword_review.md"),
            "ranked_keywords_dir": str(ranked_dir),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Output directory: {out_dir}")
    print("Best config:")
    print(top_configs.iloc[0].to_dict())


if __name__ == "__main__":
    main()
