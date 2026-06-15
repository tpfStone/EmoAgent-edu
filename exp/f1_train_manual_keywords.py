from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

EXP_DIR = Path(__file__).resolve().parent
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

import f1_safety_gate_experiment as f1

RUNS_DIR = Path("exp/runs/f1_manual_keyword_safety_gate")
DEFAULT_KEYWORD_MD = Path(
    "exp/runs/f1_keyword_weight_probe/drop-reject-filtered-keywords-20260601/manual_keyword_shortlist.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train F1 safety classifier with manually reviewed keyword list.")
    parser.add_argument("--data", type=Path, default=f1.DATA_PATH)
    parser.add_argument("--keyword-md", type=Path, default=DEFAULT_KEYWORD_MD)
    parser.add_argument("--section-prefix", type=str, default="A")
    parser.add_argument("--keyword-strategy", type=str, default="mixed")
    parser.add_argument("--label-policy", choices=["drop_reject", "reject_to_red"], default="drop_reject")
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--model-name", type=str, default="bert-base-chinese")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--bert-batch-size", type=int, default=32)
    parser.add_argument("--train-batch-size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.25)
    return parser.parse_args()


def split_words(raw: str) -> list[str]:
    words = []
    for item in re.split(r"\s*/\s*", raw.strip()):
        item = item.strip().strip("`").strip()
        if item:
            words.append(item)
    return words


def parse_manual_keywords(path: Path, section_prefix: str) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_section = False
    current_label: str | None = None
    grouped: dict[str, list[str]] = {label: [] for label in f1.LABELS}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            title = stripped[3:].strip()
            in_section = title.startswith(section_prefix)
            current_label = None
            continue
        if not in_section:
            continue
        if stripped.startswith("### "):
            candidate = stripped[4:].strip()
            current_label = candidate if candidate in grouped else None
            continue
        if current_label and stripped and not stripped.startswith("-"):
            grouped[current_label].extend(split_words(stripped))

    deduped: dict[str, list[str]] = {}
    seen_global: set[str] = set()
    for label in f1.LABELS:
        words = []
        for word in grouped[label]:
            if word in seen_global:
                continue
            words.append(word)
            seen_global.add(word)
        deduped[label] = words
    if not any(deduped.values()):
        raise ValueError(f"No keywords found in section {section_prefix!r} from {path}")
    return deduped


def flatten_keywords(grouped: dict[str, list[str]]) -> list[dict[str, Any]]:
    flattened = []
    for label in f1.LABELS:
        for rank, keyword in enumerate(grouped.get(label, []), start=1):
            flattened.append(
                {
                    "keyword": keyword,
                    "target_hint": label,
                    "manual_rank": rank,
                    "score": None,
                    "weighted_count": None,
                    "doc_freq": None,
                    "class_counts": {},
                }
            )
    return flattened


def manual_keyword_hits(text: Any, keyword: str, tokenizer_tokens: Counter[str]) -> int:
    value = f1.normalize_text(text)
    keyword = keyword.strip()
    if not value or not keyword:
        return 0

    token_hits = int(tokenizer_tokens.get(keyword, 0))
    pattern_hits = 0

    # 人工词表里的单字风险词需要特殊处理：有些适合直接子串，有些必须看上下文，避免“打算”等误报。
    if keyword == "打":
        pattern_hits += len(re.findall(r"(打我|打人|被打|挨打|殴打|打骂|打死|打伤|家暴)", value))
    elif keyword == "骂":
        pattern_hits += len(re.findall(r"(骂我|被骂|挨骂|辱骂|谩骂|打骂|责骂)", value))
    elif len(keyword) == 1:
        if keyword in f1.RISK_SINGLE_CHARS:
            pattern_hits += value.count(keyword)
    else:
        pattern_hits += value.count(keyword)

    return token_hits + pattern_hits


def build_manual_keyword_matrix(
    rows: list[dict[str, Any]],
    keywords: list[str],
    tokenizer,
) -> np.ndarray:
    matrix = np.zeros((len(rows), len(keywords)), dtype=np.float32)
    for row_idx, row in enumerate(rows):
        text = row.get("input", "")
        tokens = Counter(tokenizer(text))
        normalizer = math.sqrt(max(1, len(tokens)))
        for col_idx, keyword in enumerate(keywords):
            hits = manual_keyword_hits(text, keyword, tokens)
            if hits:
                matrix[row_idx, col_idx] = math.log1p(hits) / normalizer
    return matrix


def write_keyword_audit(rows: list[dict[str, Any]], keywords: list[dict[str, Any]], strategy: str, out_dir: Path) -> None:
    tokenizer = f1.tokenizer_for_strategy(strategy)
    keyword_texts = [item["keyword"] for item in keywords]
    matrix = build_manual_keyword_matrix(rows, keyword_texts, tokenizer)
    y = f1.label_array(rows)
    records = []
    for idx, item in enumerate(keywords):
        active = matrix[:, idx] > 0
        label_counts = Counter(f1.ID_TO_LABEL[int(label)] for label in y[active])
        records.append(
            {
                "keyword": item["keyword"],
                "target_hint": item["target_hint"],
                "matched_rows": int(active.sum()),
                "green_matches": int(label_counts.get("green", 0)),
                "yellow_matches": int(label_counts.get("yellow", 0)),
                "red_matches": int(label_counts.get("red", 0)),
            }
        )
    import pandas as pd

    pd.DataFrame(records).to_csv(out_dir / "manual_keyword_audit.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    f1.set_seed(args.seed)
    run_id = args.run_id or datetime.now().strftime("manual-keywords-%Y%m%d-%H%M%S")
    out_dir = args.out_dir or (RUNS_DIR / run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = f1.load_rows(args.data, args.label_policy)
    splits = f1.split_rows(rows, args.seed, args.test_size, args.val_size)
    label_counts = Counter(row["target_safety_level"] for row in rows)
    split_counts = {
        split: dict(Counter(rows[idx]["target_safety_level"] for idx in indices))
        for split, indices in splits.items()
    }

    grouped = parse_manual_keywords(args.keyword_md, args.section_prefix)
    keywords = flatten_keywords(grouped)
    (out_dir / "manual_keywords_grouped.json").write_text(json.dumps(grouped, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "manual_keywords.json").write_text(json.dumps(keywords, ensure_ascii=False, indent=2), encoding="utf-8")
    write_keyword_audit(rows, keywords, args.keyword_strategy, out_dir)

    print(f"Loaded rows: {len(rows)}")
    print(f"Label counts: {dict(label_counts)}")
    print(f"Split counts: {split_counts}")
    print(f"Manual keywords: {len(keywords)} ({ {label: len(grouped[label]) for label in f1.LABELS} })")

    # 人工词表是人工先验，不再使用自动关键词的精确 token 特征。
    # 这里临时替换为人工关键词匹配器，让 train_hybrid_model 复用同一套训练与导出逻辑。
    f1.build_keyword_matrix = build_manual_keyword_matrix

    bert_embeddings, bert_meta = f1.extract_bert_embeddings(
        rows=rows,
        model_name=args.model_name,
        local_files_only=args.local_files_only,
        max_length=args.max_length,
        batch_size=args.bert_batch_size,
        out_dir=out_dir,
    )
    hybrid_result = f1.train_hybrid_model(
        rows=rows,
        splits=splits,
        bert_embeddings=bert_embeddings,
        best_keywords=keywords,
        best_strategy=args.keyword_strategy,
        train_batch_size=args.train_batch_size,
        epochs=args.epochs,
        patience=args.patience,
        lr=args.lr,
        dropout=args.dropout,
        out_dir=out_dir,
    )
    summary = {
        "run_id": run_id,
        "data_path": str(args.data),
        "keyword_md": str(args.keyword_md),
        "section_prefix": args.section_prefix,
        "keyword_strategy": args.keyword_strategy,
        "label_policy": args.label_policy,
        "rows": len(rows),
        "label_counts": {label: int(label_counts[label]) for label in f1.LABELS},
        "split_counts": split_counts,
        "keyword_counts": {label: len(grouped[label]) for label in f1.LABELS},
        "bert_meta": bert_meta,
        "hybrid_result": hybrid_result,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    f1.write_report(
        out_dir=out_dir,
        summary={
            "run_id": run_id,
            "data_path": str(args.data),
            "rows": len(rows),
            "label_counts": {label: int(label_counts[label]) for label in f1.LABELS},
            "split_counts": split_counts,
            "best_keyword_probe": {
                "strategy": args.keyword_strategy,
                "keyword_n": len(keywords),
                "val_macro_f1": "manual",
                "test_macro_f1": "manual",
            },
            "bert_meta": bert_meta,
        },
        keyword_results=__import__("pandas").DataFrame(
            [
                {
                    "strategy": args.keyword_strategy,
                    "keyword_n": len(keywords),
                    "val_macro_f1": "manual",
                    "test_macro_f1": "manual",
                }
            ]
        ),
        hybrid_result=hybrid_result,
    )
    print(f"Output directory: {out_dir}")
    print(f"Hybrid test metrics: {hybrid_result['test_metrics']}")


if __name__ == "__main__":
    main()
