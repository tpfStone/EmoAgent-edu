from __future__ import annotations

import argparse
import json
import math
import random
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import jieba
import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from transformers import AutoModel, AutoTokenizer

DATA_PATH = Path("exp/data/psyqa_labelled.json")
RUNS_DIR = Path("exp/runs/f1_safety_gate_experiment")
LABELS = ["green", "yellow", "red"]
LABEL_TO_ID = {label: idx for idx, label in enumerate(LABELS)}
ID_TO_LABEL = {idx: label for label, idx in LABEL_TO_ID.items()}

DEFAULT_KEYWORD_SIZES = [20, 50, 100, 200, 400, 800, 1200]
DEFAULT_STRATEGIES = ["jieba_word", "char_ngram", "mixed"]

STOPWORDS = {
    "一个", "一些", "一种", "这个", "那个", "这些", "那些", "自己", "我们", "你们", "他们", "她们",
    "就是", "觉得", "感觉", "因为", "所以", "但是", "如果", "然后", "现在", "可能", "可以",
    "没有", "不是", "还是", "什么", "怎么", "时候", "知道", "进行", "需要", "以及", "或者",
    "比较", "非常", "很多", "一下", "这样", "那样", "已经", "一直", "最近", "真的", "the",
    "and", "for", "with", "that", "this", "you", "your", "are", "was", "were", "have", "has",
}
RISK_SINGLE_CHARS = {"死", "割", "跳", "药", "刀", "血", "疼", "哭", "恨"}
KEYWORD_BLOCK_SUBSTRINGS = {
    "策略",
    "参考",
    "价值",
    "样例",
    "样本",
    "负例",
    "负面案例",
    "直接样例",
    "初中生",
    "初中",
    "中生",
    "情感教育",
    "教育场景",
    "场景",
    "本项目",
    "适合",
    "不适合",
    "作为",
    "完全",
    "高危",
    "拒绝",
    "用途",
    "标注",
    "成人化",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F1 safety gate keyword probe and BERT hybrid classifier.")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--label-policy", choices=["drop_reject", "reject_to_red"], default="drop_reject")
    parser.add_argument("--keyword-sizes", type=str, default=",".join(str(item) for item in DEFAULT_KEYWORD_SIZES))
    parser.add_argument("--strategies", type=str, default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--input-weight", type=float, default=1.0)
    parser.add_argument("--rationale-weight", type=float, default=3.0)
    parser.add_argument("--min-token-count", type=float, default=2.0)
    parser.add_argument("--max-keyword-candidates", type=int, default=50000)
    parser.add_argument("--skip-hybrid", action="store_true")
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


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_csv_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_int_list(raw: str) -> list[int]:
    return [int(item) for item in parse_csv_list(raw) if int(item) > 0]


def normalize_text(text: Any) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).lower()
    return re.sub(r"\s+", " ", value).strip()


def compact_for_char(text: Any) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", normalize_text(text)))


def is_valid_token(token: str) -> bool:
    token = token.strip().lower()
    if not token or token in STOPWORDS:
        return False
    if any(blocked in token for blocked in KEYWORD_BLOCK_SUBSTRINGS):
        return False
    if token in RISK_SINGLE_CHARS:
        return True
    if re.fullmatch(r"\d+", token):
        return False
    if re.search(r"[\u4e00-\u9fff]", token) and 2 <= len(token) <= 8:
        return True
    return bool(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_\-]{2,20}", token))


def jieba_word_tokens(text: Any) -> list[str]:
    return [token.strip().lower() for token in jieba.lcut(normalize_text(text), cut_all=False) if is_valid_token(token)]


def char_ngram_tokens(text: Any, min_n: int = 1, max_n: int = 4) -> list[str]:
    compact = compact_for_char(text)
    tokens: list[str] = []
    for n in range(min_n, max_n + 1):
        if n == 1:
            tokens.extend(ch for ch in compact if ch in RISK_SINGLE_CHARS)
        else:
            tokens.extend(
                gram
                for gram in (compact[i : i + n] for i in range(max(0, len(compact) - n + 1)))
                if not any(blocked in gram for blocked in KEYWORD_BLOCK_SUBSTRINGS)
            )
    return tokens


def mixed_tokens(text: Any) -> list[str]:
    return jieba_word_tokens(text) + char_ngram_tokens(text, min_n=2, max_n=3)


def tokenizer_for_strategy(strategy: str) -> Callable[[Any], list[str]]:
    if strategy == "jieba_word":
        return jieba_word_tokens
    if strategy == "char_ngram":
        return char_ngram_tokens
    if strategy == "mixed":
        return mixed_tokens
    raise ValueError(f"Unknown keyword strategy: {strategy}")


def load_rows(path: Path, label_policy: str = "drop_reject") -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        rows = json.load(file)
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") not in (None, "ok"):
            continue
        level = str(row.get("safety_level", "")).strip()
        if level == "reject":
            if label_policy == "reject_to_red":
                level = "red"
            else:
                continue
        if level not in LABEL_TO_ID:
            continue
        if not normalize_text(row.get("input", "")):
            continue
        item = dict(row)
        item["target_safety_level"] = level
        item["target_id"] = LABEL_TO_ID[level]
        cleaned.append(item)
    return cleaned


def split_rows(rows: list[dict[str, Any]], seed: int, test_size: float, val_size: float) -> dict[str, list[int]]:
    indices = np.arange(len(rows))
    y = np.array([row["target_id"] for row in rows])
    train_val_idx, test_idx = train_test_split(indices, test_size=test_size, random_state=seed, stratify=y)
    val_relative_size = val_size / (1.0 - test_size)
    train_idx, val_idx = train_test_split(
        train_val_idx,
        test_size=val_relative_size,
        random_state=seed,
        stratify=y[train_val_idx],
    )
    return {"train": train_idx.astype(int).tolist(), "val": val_idx.astype(int).tolist(), "test": test_idx.astype(int).tolist()}


def rows_by_indices(rows: list[dict[str, Any]], indices: list[int]) -> list[dict[str, Any]]:
    return [rows[idx] for idx in indices]


def label_array(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.array([row["target_id"] for row in rows], dtype=np.int64)


def weighted_source_tokens(
    row: dict[str, Any],
    tokenizer: Callable[[Any], list[str]],
    input_weight: float,
    rationale_weight: float,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for token in tokenizer(row.get("input", "")):
        counts[token] += input_weight
    for token in tokenizer(row.get("rationale", "")):
        counts[token] += rationale_weight
    return counts


def rank_keywords(
    train_rows: list[dict[str, Any]],
    tokenizer: Callable[[Any], list[str]],
    input_weight: float,
    rationale_weight: float,
    min_token_count: float,
    max_candidates: int,
) -> list[dict[str, Any]]:
    token_class_counts: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(len(LABELS), dtype=np.float64))
    class_totals = np.zeros(len(LABELS), dtype=np.float64)
    doc_freq: Counter[str] = Counter()

    for row in train_rows:
        label_id = row["target_id"]
        counts = weighted_source_tokens(row, tokenizer, input_weight, rationale_weight)
        for token, value in counts.items():
            token_class_counts[token][label_id] += float(value)
            class_totals[label_id] += float(value)
        for token in counts:
            doc_freq[token] += 1

    global_total = float(class_totals.sum())
    vocab_size = max(1, len(token_class_counts))
    ranked: list[dict[str, Any]] = []
    alpha = 0.5

    for token, counts in token_class_counts.items():
        total = float(counts.sum())
        if total < min_token_count:
            continue
        class_scores = []
        for class_id in range(len(LABELS)):
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
                "target_hint": ID_TO_LABEL[best_class],
                "weighted_count": round(total, 3),
                "doc_freq": int(doc_freq[token]),
                "class_counts": {ID_TO_LABEL[i]: round(float(counts[i]), 3) for i in range(len(LABELS))},
            }
        )

    ranked.sort(key=lambda item: (item["score"], item["weighted_count"], item["doc_freq"]), reverse=True)
    return ranked[:max_candidates]


def select_top_keywords(ranked: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    if n >= len(ranked):
        return ranked
    quota = max(1, math.ceil(n / len(LABELS)))
    selected: list[dict[str, Any]] = []
    selected_set: set[str] = set()
    for label in LABELS:
        for item in [row for row in ranked if row["target_hint"] == label][:quota]:
            if item["keyword"] not in selected_set:
                selected.append(item)
                selected_set.add(item["keyword"])
            if len(selected) >= n:
                return selected[:n]
    for item in ranked:
        if item["keyword"] not in selected_set:
            selected.append(item)
            selected_set.add(item["keyword"])
        if len(selected) >= n:
            break
    return selected[:n]


def build_keyword_matrix(rows: list[dict[str, Any]], keywords: list[str], tokenizer: Callable[[Any], list[str]]) -> np.ndarray:
    index = {keyword: idx for idx, keyword in enumerate(keywords)}
    x = np.zeros((len(rows), len(keywords)), dtype=np.float32)
    for row_idx, row in enumerate(rows):
        counts = Counter(tokenizer(row.get("input", "")))
        token_total = max(1, sum(counts.values()))
        for token, count in counts.items():
            col = index.get(token)
            if col is not None:
                x[row_idx, col] = math.log1p(count) / math.sqrt(token_total)
    return x


def metrics_dict(y_true: np.ndarray, y_pred: np.ndarray, prefix: str = "") -> dict[str, float]:
    return {
        f"{prefix}accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        f"{prefix}balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 6),
        f"{prefix}macro_f1": round(float(f1_score(y_true, y_pred, average="macro")), 6),
        f"{prefix}weighted_f1": round(float(f1_score(y_true, y_pred, average="weighted")), 6),
    }


def run_keyword_probe(
    rows: list[dict[str, Any]],
    splits: dict[str, list[int]],
    strategies: list[str],
    keyword_sizes: list[int],
    input_weight: float,
    rationale_weight: float,
    min_token_count: float,
    max_keyword_candidates: int,
    out_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    train_rows = rows_by_indices(rows, splits["train"])
    val_rows = rows_by_indices(rows, splits["val"])
    test_rows = rows_by_indices(rows, splits["test"])
    y_train = label_array(train_rows)
    y_val = label_array(val_rows)
    y_test = label_array(test_rows)

    all_results: list[dict[str, Any]] = []
    ranked_by_strategy: dict[str, list[dict[str, Any]]] = {}
    for strategy in strategies:
        tokenizer = tokenizer_for_strategy(strategy)
        started = time.time()
        ranked = rank_keywords(train_rows, tokenizer, input_weight, rationale_weight, min_token_count, max_keyword_candidates)
        ranked_by_strategy[strategy] = ranked
        print(f"[{strategy}] ranked {len(ranked)} keyword candidates in {time.time() - started:.1f}s")

        for n in keyword_sizes:
            selected_items = select_top_keywords(ranked, n)
            keywords = [item["keyword"] for item in selected_items]
            x_train = build_keyword_matrix(train_rows, keywords, tokenizer)
            x_val = build_keyword_matrix(val_rows, keywords, tokenizer)
            x_test = build_keyword_matrix(test_rows, keywords, tokenizer)
            scaler = StandardScaler()
            x_train = scaler.fit_transform(x_train)
            x_val = scaler.transform(x_val)
            x_test = scaler.transform(x_test)
            clf = LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs")
            clf.fit(x_train, y_train)
            pred_val = clf.predict(x_val)
            pred_test = clf.predict(x_test)
            row = {
                "strategy": strategy,
                "keyword_n": len(keywords),
                **metrics_dict(y_val, pred_val, prefix="val_"),
                **metrics_dict(y_test, pred_test, prefix="test_"),
            }
            all_results.append(row)
            print(
                f"[{strategy:10s} n={len(keywords):4d}] "
                f"val_macro_f1={row['val_macro_f1']:.4f} test_macro_f1={row['test_macro_f1']:.4f}"
            )

    results_df = pd.DataFrame(all_results).sort_values(
        by=["val_macro_f1", "val_balanced_accuracy", "test_macro_f1"], ascending=False
    )
    best_row = results_df.iloc[0].to_dict()
    best_keywords = select_top_keywords(ranked_by_strategy[str(best_row["strategy"])], int(best_row["keyword_n"]))
    results_df.to_csv(out_dir / "keyword_probe_results.csv", index=False, encoding="utf-8")
    (out_dir / "best_keywords.json").write_text(json.dumps(best_keywords, ensure_ascii=False, indent=2), encoding="utf-8")
    return best_row, best_keywords, results_df


def extract_bert_embeddings(
    rows: list[dict[str, Any]],
    model_name: str,
    local_files_only: bool,
    max_length: int,
    batch_size: int,
    out_dir: Path,
) -> tuple[np.ndarray, dict[str, Any]]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=local_files_only)
    model = AutoModel.from_pretrained(model_name, local_files_only=local_files_only)
    model.to(device)
    model.eval()
    texts = [str(row.get("input", "")) for row in rows]
    embeddings: list[np.ndarray] = []
    truncated = 0
    started = time.time()

    with torch.no_grad():
        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start : start + batch_size]
            lengths = [len(tokenizer.encode(text, add_special_tokens=True, truncation=False)) for text in batch_texts]
            truncated += sum(length > max_length for length in lengths)
            encoded = tokenizer(batch_texts, padding=True, truncation=True, max_length=max_length, return_tensors="pt")
            encoded = {key: value.to(device) for key, value in encoded.items()}
            output = model(**encoded)
            hidden = output.last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)
            embeddings.append(pooled.detach().cpu().numpy().astype(np.float32))
            print(f"BERT embeddings: {min(start + batch_size, len(texts))}/{len(texts)}", end="\r")
    print()
    x = np.vstack(embeddings)
    meta = {
        "model_name": model_name,
        "device": str(device),
        "max_length": max_length,
        "batch_size": batch_size,
        "embedding_dim": int(x.shape[1]),
        "truncated_count": int(truncated),
        "truncated_rate": round(float(truncated / max(1, len(rows))), 6),
        "seconds": round(time.time() - started, 3),
    }
    np.save(out_dir / "bert_embeddings.npy", x)
    return x, meta


class SafetyFeatureDataset(Dataset):
    def __init__(self, bert_x: np.ndarray, keyword_x: np.ndarray, y: np.ndarray):
        self.bert_x = torch.tensor(bert_x, dtype=torch.float32)
        self.keyword_x = torch.tensor(keyword_x, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        return int(len(self.y))

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.bert_x[idx], self.keyword_x[idx], self.y[idx]


class HybridSafetyClassifier(nn.Module):
    def __init__(self, bert_dim: int, keyword_dim: int, dropout: float):
        super().__init__()
        keyword_hidden = min(128, max(24, keyword_dim // 4))
        self.bert_branch = nn.Sequential(nn.Linear(bert_dim, 256), nn.LayerNorm(256), nn.GELU(), nn.Dropout(dropout))
        self.keyword_branch = nn.Sequential(
            nn.Linear(keyword_dim, keyword_hidden),
            nn.LayerNorm(keyword_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.classifier = nn.Sequential(
            nn.Linear(256 + keyword_hidden, 160),
            nn.LayerNorm(160),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(160, len(LABELS)),
        )

    def forward(self, bert_x: torch.Tensor, keyword_x: torch.Tensor) -> torch.Tensor:
        return self.classifier(torch.cat([self.bert_branch(bert_x), self.keyword_branch(keyword_x)], dim=-1))


def evaluate_model(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, dict[str, float], np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    loss_fn = nn.CrossEntropyLoss()
    losses: list[float] = []
    y_true: list[int] = []
    y_pred: list[int] = []
    probs: list[np.ndarray] = []
    with torch.no_grad():
        for bert_x, keyword_x, y in loader:
            bert_x = bert_x.to(device)
            keyword_x = keyword_x.to(device)
            y = y.to(device)
            logits = model(bert_x, keyword_x)
            prob = torch.softmax(logits, dim=-1)
            losses.append(float(loss_fn(logits, y).item()))
            y_true.extend(y.detach().cpu().numpy().tolist())
            y_pred.extend(torch.argmax(prob, dim=-1).detach().cpu().numpy().tolist())
            probs.append(prob.detach().cpu().numpy())
    y_true_arr = np.array(y_true, dtype=np.int64)
    y_pred_arr = np.array(y_pred, dtype=np.int64)
    prob_arr = np.vstack(probs) if probs else np.zeros((0, len(LABELS)), dtype=np.float32)
    return float(np.mean(losses) if losses else 0.0), metrics_dict(y_true_arr, y_pred_arr), y_true_arr, y_pred_arr, prob_arr


def train_hybrid_model(
    rows: list[dict[str, Any]],
    splits: dict[str, list[int]],
    bert_embeddings: np.ndarray,
    best_keywords: list[dict[str, Any]],
    best_strategy: str,
    train_batch_size: int,
    epochs: int,
    patience: int,
    lr: float,
    dropout: float,
    out_dir: Path,
) -> dict[str, Any]:
    tokenizer = tokenizer_for_strategy(best_strategy)
    keywords = [item["keyword"] for item in best_keywords]
    keyword_x = build_keyword_matrix(rows, keywords, tokenizer)
    y_all = label_array(rows)
    train_idx = np.array(splits["train"], dtype=np.int64)
    val_idx = np.array(splits["val"], dtype=np.int64)
    test_idx = np.array(splits["test"], dtype=np.int64)

    bert_scaler = StandardScaler()
    keyword_scaler = StandardScaler()
    bert_scaled = np.zeros_like(bert_embeddings, dtype=np.float32)
    keyword_scaled = np.zeros_like(keyword_x, dtype=np.float32)
    bert_scaled[train_idx] = bert_scaler.fit_transform(bert_embeddings[train_idx]).astype(np.float32)
    keyword_scaled[train_idx] = keyword_scaler.fit_transform(keyword_x[train_idx]).astype(np.float32)
    for idx in [val_idx, test_idx]:
        bert_scaled[idx] = bert_scaler.transform(bert_embeddings[idx]).astype(np.float32)
        keyword_scaled[idx] = keyword_scaler.transform(keyword_x[idx]).astype(np.float32)
    joblib.dump({"bert_scaler": bert_scaler, "keyword_scaler": keyword_scaler}, out_dir / "feature_scalers.joblib")

    train_ds = SafetyFeatureDataset(bert_scaled[train_idx], keyword_scaled[train_idx], y_all[train_idx])
    val_ds = SafetyFeatureDataset(bert_scaled[val_idx], keyword_scaled[val_idx], y_all[val_idx])
    test_ds = SafetyFeatureDataset(bert_scaled[test_idx], keyword_scaled[test_idx], y_all[test_idx])
    train_counts = np.bincount(y_all[train_idx], minlength=len(LABELS)).astype(np.float32)
    class_weights = train_counts.sum() / (len(LABELS) * np.maximum(train_counts, 1.0))
    sample_weights = class_weights[y_all[train_idx]]
    sampler = WeightedRandomSampler(torch.tensor(sample_weights, dtype=torch.float32), len(sample_weights), replacement=True)
    train_loader = DataLoader(train_ds, batch_size=train_batch_size, sampler=sampler)
    val_loader = DataLoader(val_ds, batch_size=train_batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=train_batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = HybridSafetyClassifier(bert_embeddings.shape[1], len(keywords), dropout).to(device)
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(class_weights, dtype=torch.float32).to(device))
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    best_state = None
    best_val_macro_f1 = -1.0
    best_epoch = 0
    wait = 0
    history: list[dict[str, Any]] = []

    for epoch in range(1, epochs + 1):
        model.train()
        train_losses: list[float] = []
        for bert_x, keyword_batch, y in train_loader:
            bert_x = bert_x.to(device)
            keyword_batch = keyword_batch.to(device)
            y = y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(bert_x, keyword_batch), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
            optimizer.step()
            train_losses.append(float(loss.item()))
        val_loss, val_metrics, _, _, _ = evaluate_model(model, val_loader, device)
        record = {
            "epoch": epoch,
            "train_loss": round(float(np.mean(train_losses)), 6),
            "val_loss": round(float(val_loss), 6),
            **{f"val_{key}": value for key, value in val_metrics.items()},
        }
        history.append(record)
        print(
            f"epoch={epoch:02d} train_loss={record['train_loss']:.4f} "
            f"val_macro_f1={record['val_macro_f1']:.4f} val_bal_acc={record['val_balanced_accuracy']:.4f}"
        )
        if val_metrics["macro_f1"] > best_val_macro_f1 + 1e-5:
            best_val_macro_f1 = float(val_metrics["macro_f1"])
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                print(f"Early stopping at epoch {epoch}; best epoch {best_epoch}")
                break
    if best_state is not None:
        model.load_state_dict(best_state)

    val_loss, val_metrics, _, _, _ = evaluate_model(model, val_loader, device)
    test_loss, test_metrics, test_true, test_pred, test_probs = evaluate_model(model, test_loader, device)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "labels": LABELS,
            "keyword_strategy": best_strategy,
            "keywords": best_keywords,
            "bert_dim": int(bert_embeddings.shape[1]),
            "keyword_dim": len(keywords),
            "dropout": dropout,
        },
        out_dir / "hybrid_safety_classifier.pt",
    )
    pd.DataFrame(history).to_csv(out_dir / "hybrid_training_history.csv", index=False, encoding="utf-8")
    pd.DataFrame(confusion_matrix(test_true, test_pred, labels=list(range(len(LABELS)))), index=LABELS, columns=LABELS).to_csv(
        out_dir / "hybrid_test_confusion_matrix.csv", encoding="utf-8-sig"
    )
    with (out_dir / "hybrid_test_predictions.jsonl").open("w", encoding="utf-8") as file:
        for local_idx, row_idx in enumerate(test_idx):
            file.write(
                json.dumps(
                    {
                        "row_index": int(row_idx),
                        "source_index": rows[int(row_idx)].get("source_index"),
                        "true_label": ID_TO_LABEL[int(test_true[local_idx])],
                        "pred_label": ID_TO_LABEL[int(test_pred[local_idx])],
                        "probabilities": {LABELS[i]: round(float(test_probs[local_idx, i]), 6) for i in range(len(LABELS))},
                        "input": rows[int(row_idx)].get("input", ""),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return {
        "best_epoch": best_epoch,
        "class_weights": {LABELS[i]: round(float(class_weights[i]), 6) for i in range(len(LABELS))},
        "val_loss": round(float(val_loss), 6),
        "test_loss": round(float(test_loss), 6),
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "test_classification_report": classification_report(test_true, test_pred, target_names=LABELS, digits=4, output_dict=True),
        "test_confusion_matrix": confusion_matrix(test_true, test_pred, labels=list(range(len(LABELS)))).tolist(),
    }


def write_report(out_dir: Path, summary: dict[str, Any], keyword_results: pd.DataFrame, hybrid_result: dict[str, Any] | None) -> None:
    best = summary["best_keyword_probe"]
    top_rows = keyword_results.head(10).to_string(index=False)
    lines = [
        "# F1 Safety Gate Keyword + BERT Experiment",
        "",
        f"Run id: `{summary['run_id']}`",
        f"Data: `{summary['data_path']}`",
        "",
        "## Dataset",
        "",
        f"- rows: {summary['rows']}",
        f"- labels: {json.dumps(summary['label_counts'], ensure_ascii=False)}",
        f"- split: {json.dumps(summary['split_counts'], ensure_ascii=False)}",
        "- label policy: `safety_level=reject` is merged into `red`.",
        "",
        "## Keyword Probe",
        "",
        f"- best strategy: `{best['strategy']}`",
        f"- best n: `{int(best['keyword_n'])}`",
        f"- val macro-F1: `{best['val_macro_f1']}`",
        f"- test macro-F1: `{best['test_macro_f1']}`",
        "",
        "```text",
        top_rows,
        "```",
        "",
    ]
    if hybrid_result is None:
        lines.extend(["## Hybrid Model", "", "Hybrid training was skipped or failed before model loading.", ""])
    else:
        confusion = pd.DataFrame(hybrid_result["test_confusion_matrix"], index=LABELS, columns=LABELS).to_string()
        lines.extend(
            [
                "## Hybrid Model",
                "",
                f"- BERT model: `{summary['bert_meta']['model_name']}`",
                f"- device: `{summary['bert_meta']['device']}`",
                f"- max_length: `{summary['bert_meta']['max_length']}`",
                f"- truncation rate: `{summary['bert_meta']['truncated_rate']}`",
                f"- best epoch: `{hybrid_result['best_epoch']}`",
                f"- val macro-F1: `{hybrid_result['val_metrics']['macro_f1']}`",
                f"- test macro-F1: `{hybrid_result['test_metrics']['macro_f1']}`",
                f"- test balanced accuracy: `{hybrid_result['test_metrics']['balanced_accuracy']}`",
                "",
                "```text",
                confusion,
                "```",
                "",
            ]
        )
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    run_id = args.run_id or datetime.now().strftime("f1-safety-%Y%m%d-%H%M%S")
    out_dir = args.out_dir or (RUNS_DIR / run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(args.data, args.label_policy)
    splits = split_rows(rows, args.seed, args.test_size, args.val_size)
    (out_dir / "splits.json").write_text(
        json.dumps({"seed": args.seed, "splits": splits, "labels": LABELS, "label_policy": args.label_policy}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    label_counts = Counter(row["target_safety_level"] for row in rows)
    split_counts = {split: dict(Counter(rows[idx]["target_safety_level"] for idx in indices)) for split, indices in splits.items()}
    print(f"Loaded rows: {len(rows)}")
    print(f"Label counts: {dict(label_counts)}")
    print(f"Split counts: {split_counts}")

    best_probe, best_keywords, keyword_results = run_keyword_probe(
        rows=rows,
        splits=splits,
        strategies=parse_csv_list(args.strategies),
        keyword_sizes=parse_int_list(args.keyword_sizes),
        input_weight=args.input_weight,
        rationale_weight=args.rationale_weight,
        min_token_count=args.min_token_count,
        max_keyword_candidates=args.max_keyword_candidates,
        out_dir=out_dir,
    )
    summary: dict[str, Any] = {
        "run_id": run_id,
        "data_path": str(args.data),
        "rows": len(rows),
        "labels": LABELS,
        "label_policy": args.label_policy,
        "label_counts": {label: int(label_counts[label]) for label in LABELS},
        "split_counts": split_counts,
        "keyword_sizes": parse_int_list(args.keyword_sizes),
        "strategies": parse_csv_list(args.strategies),
        "input_weight": args.input_weight,
        "rationale_weight": args.rationale_weight,
        "best_keyword_probe": best_probe,
    }
    hybrid_result = None
    if not args.skip_hybrid:
        try:
            bert_embeddings, bert_meta = extract_bert_embeddings(
                rows=rows,
                model_name=args.model_name,
                local_files_only=args.local_files_only,
                max_length=args.max_length,
                batch_size=args.bert_batch_size,
                out_dir=out_dir,
            )
            summary["bert_meta"] = bert_meta
            hybrid_result = train_hybrid_model(
                rows=rows,
                splits=splits,
                bert_embeddings=bert_embeddings,
                best_keywords=best_keywords,
                best_strategy=str(best_probe["strategy"]),
                train_batch_size=args.train_batch_size,
                epochs=args.epochs,
                patience=args.patience,
                lr=args.lr,
                dropout=args.dropout,
                out_dir=out_dir,
            )
            summary["hybrid_result"] = hybrid_result
        except Exception as exc:
            summary["hybrid_error"] = f"{type(exc).__name__}: {exc}"
            print(f"Hybrid training failed: {summary['hybrid_error']}")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out_dir, summary, keyword_results, hybrid_result)
    print(f"Output directory: {out_dir}")
    print(f"Best keyword probe: {best_probe}")
    if hybrid_result is not None:
        print(f"Hybrid test metrics: {hybrid_result['test_metrics']}")
    elif "hybrid_error" in summary:
        print(f"Hybrid error: {summary['hybrid_error']}")


if __name__ == "__main__":
    main()
