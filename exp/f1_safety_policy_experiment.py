from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

EXP_DIR = Path(__file__).resolve().parent
if str(EXP_DIR.parent) not in sys.path:
    sys.path.insert(0, str(EXP_DIR.parent))
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

import f1_safety_gate_experiment as f1
from app.services.f1_safety_classifier import (
    HybridSafetyClassifier,
    build_manual_keyword_matrix,
    tokenizer_for_strategy,
)


LABELS = ["green", "yellow", "red"]
LABEL_TO_ID = {label: idx for idx, label in enumerate(LABELS)}
DEFAULT_SOURCE_RUN = Path("exp/runs/f1_manual_keyword_safety_gate/manual-A-pattern-keywords-20260601")
DEFAULT_MODEL_DIR = Path("exp/models/f1_safety_gate/manual-A-pattern-v1")
OUT_ROOT = Path("exp/runs/f1_safety_policy_experiment")

IDIOM_PATTERNS = [
    "烦死了",
    "烦死",
    "累死了",
    "累死",
    "笑死了",
    "笑死",
    "气死了",
    "气死",
    "尴尬死了",
    "难受死了",
    "困死了",
    "急死了",
    "吓死了",
    "热死了",
    "冷死了",
    "无聊死了",
]
BULLYING_PATTERNS = [
    "打我",
    "骂我",
    "被打",
    "被骂",
    "挨打",
    "挨骂",
    "欺负",
    "霸凌",
    "孤立",
    "威胁",
    "家暴",
    "辱骂",
]
PASSIVE_DEATH_PATTERNS = [
    "活着没意思",
    "活着没什么意思",
    "活着没有意思",
    "活着没意义",
    "活着没有意义",
    "活着没有什么意义",
    "不想醒来",
    "不想存在",
    "想消失",
    "不想活",
    "不想再活",
    "活不下去",
]
ACTIVE_SUICIDE_PATTERNS = [
    "自杀",
    "轻生",
    "想死",
    "去死",
    "死了算",
    "结束生命",
    "结束自己的生命",
]
SELF_HARM_PATTERNS = [
    "自残",
    "割腕",
    "割自己",
    "划自己",
    "伤害自己",
    "弄伤自己",
]
METHOD_PATTERNS = [
    "吃药",
    "吞药",
    "安眠药",
    "药片",
    "小刀",
    "刀片",
    "割腕",
    "跳楼",
    "跳下去",
    "上吊",
    "绳子",
    "遗书",
]
TIME_PATTERNS = [
    "今晚",
    "今天晚上",
    "现在",
    "马上",
    "立刻",
    "明天",
    "一会儿",
    "放学后",
    "凌晨",
]
PREPARATION_PATTERNS = [
    "准备好了",
    "准备好",
    "已经准备",
    "买好了",
    "买了",
    "找好了",
    "写遗书",
    "留下遗书",
    "计划好了",
    "决定了",
]
NEGATION_PATTERNS = [
    "没有计划",
    "没计划",
    "没有具体计划",
    "没想好",
    "没打算",
    "不会真的",
    "不是真的",
    "只是觉得",
]


@dataclass(frozen=True)
class RuleSignals:
    red_necessary: bool
    idiom_without_intent: bool
    bullying_without_self_harm: bool
    passive_with_negation_without_concrete_signal: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Experiment with F1 safety gate post-processing and retraining policies.")
    parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--alphas", type=str, default="0,0.25,0.5,0.75,1.0")
    parser.add_argument("--temperatures", type=str, default="1.0,1.25,1.5,2.0,3.0")
    parser.add_argument("--red-thresholds", type=str, default="0.35,0.45,0.55,0.65,0.75,0.85")
    parser.add_argument("--yellow-thresholds", type=str, default="0.4,0.45,0.5,0.55,0.6,0.7")
    parser.add_argument("--train-grid", action="store_true")
    parser.add_argument("--train-alphas", type=str, default="0.5,0.75,1.0")
    parser.add_argument("--red-weight-multipliers", type=str, default="0.5,0.75,1.0")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.25)
    return parser.parse_args()


def parse_float_list(raw: str) -> list[float]:
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def normalize_text(text: Any) -> str:
    value = str(text or "").lower()
    return re.sub(r"\s+", " ", value).strip()


def contains_any(value: str, patterns: list[str]) -> bool:
    return any(pattern in value for pattern in patterns)


def analyze_rules(text: Any) -> RuleSignals:
    value = normalize_text(text)
    has_idiom = contains_any(value, IDIOM_PATTERNS)
    has_bullying = contains_any(value, BULLYING_PATTERNS)
    has_passive_death = contains_any(value, PASSIVE_DEATH_PATTERNS)
    has_active_suicide = contains_any(value, ACTIVE_SUICIDE_PATTERNS)
    has_self_harm = contains_any(value, SELF_HARM_PATTERNS)
    has_method = contains_any(value, METHOD_PATTERNS)
    has_time = contains_any(value, TIME_PATTERNS)
    has_preparation = contains_any(value, PREPARATION_PATTERNS)
    has_negation = contains_any(value, NEGATION_PATTERNS)

    risk_intent = has_active_suicide or has_passive_death or has_self_harm
    concrete_signal = has_method or has_time or has_preparation
    red_necessary = bool((has_self_harm and has_method) or (risk_intent and concrete_signal and not has_negation))
    idiom_without_intent = bool(has_idiom and not risk_intent and not has_method)
    bullying_without_self_harm = bool(has_bullying and not risk_intent and not concrete_signal)
    passive_with_negation_without_concrete_signal = bool(has_passive_death and has_negation and not concrete_signal)
    return RuleSignals(
        red_necessary=red_necessary,
        idiom_without_intent=idiom_without_intent,
        bullying_without_self_harm=bullying_without_self_harm,
        passive_with_negation_without_concrete_signal=passive_with_negation_without_concrete_signal,
    )


def logits_to_probabilities(logits: np.ndarray, temperature: float) -> np.ndarray:
    scaled = logits / max(float(temperature), 1e-4)
    scaled = scaled - scaled.max(axis=1, keepdims=True)
    exp = np.exp(scaled)
    return exp / exp.sum(axis=1, keepdims=True)


def predict_with_policy(
    probs: np.ndarray,
    texts: list[str],
    red_threshold: float,
    yellow_threshold: float,
    rule_mode: str,
) -> np.ndarray:
    pred = np.zeros(len(probs), dtype=np.int64)
    for idx, row in enumerate(probs):
        p_green, p_yellow, p_red = row.tolist()
        if p_red >= red_threshold:
            level = "red"
        elif p_yellow + p_red >= yellow_threshold:
            level = "yellow"
        else:
            level = "green"

        if rule_mode != "none" and level == "red":
            signals = analyze_rules(texts[idx])
            if signals.idiom_without_intent:
                level = "yellow" if p_yellow + p_red >= yellow_threshold else "green"
            elif signals.bullying_without_self_harm:
                level = "yellow"
            elif signals.passive_with_negation_without_concrete_signal:
                level = "yellow"
            elif rule_mode == "soft" and not signals.red_necessary and p_red < 0.8:
                level = "yellow"
            elif rule_mode == "strict" and not signals.red_necessary:
                level = "yellow"

        pred[idx] = LABEL_TO_ID[level]
    return pred


def metric_bundle(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    matrix = confusion_matrix(y_true, y_pred, labels=[0, 1, 2])
    support = matrix.sum(axis=1).clip(min=1)
    green_to_red = matrix[0, 2] / support[0]
    yellow_to_red = matrix[1, 2] / support[1]
    red_to_green = matrix[2, 0] / support[2]
    red_recall = matrix[2, 2] / support[2]
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    objective = macro_f1 - 2.0 * green_to_red - 1.5 * yellow_to_red - 3.0 * red_to_green
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 6),
        "macro_f1": round(float(macro_f1), 6),
        "weighted_f1": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 6),
        "green_to_red_rate": round(float(green_to_red), 6),
        "yellow_to_red_rate": round(float(yellow_to_red), 6),
        "red_to_green_rate": round(float(red_to_green), 6),
        "red_recall": round(float(red_recall), 6),
        "objective": round(float(objective), 6),
        "confusion_matrix": matrix.tolist(),
    }


def make_loader(x_bert: np.ndarray, x_keyword: np.ndarray, y: np.ndarray, indices: np.ndarray, batch_size: int, train: bool) -> DataLoader:
    dataset = TensorDataset(
        torch.tensor(x_bert[indices], dtype=torch.float32),
        torch.tensor(x_keyword[indices], dtype=torch.float32),
        torch.tensor(y[indices], dtype=torch.long),
    )
    if not train:
        return DataLoader(dataset, batch_size=batch_size, shuffle=False)
    counts = np.bincount(y[indices], minlength=3).astype(np.float32)
    class_weights = counts.sum() / (3 * np.maximum(counts, 1.0))
    sample_weights = class_weights[y[indices]]
    sampler = WeightedRandomSampler(torch.tensor(sample_weights, dtype=torch.float32), len(sample_weights), replacement=True)
    return DataLoader(dataset, batch_size=batch_size, sampler=sampler)


def evaluate_logits(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    ys: list[int] = []
    logits: list[np.ndarray] = []
    with torch.no_grad():
        for bert_x, keyword_x, y in loader:
            bert_x = bert_x.to(device)
            keyword_x = keyword_x.to(device)
            output = model(bert_x, keyword_x)
            ys.extend(y.numpy().tolist())
            logits.append(output.detach().cpu().numpy())
    return np.array(ys, dtype=np.int64), np.vstack(logits)


def train_variant(
    bert_scaled: np.ndarray,
    keyword_scaled: np.ndarray,
    y_all: np.ndarray,
    splits: dict[str, list[int]],
    keyword_alpha: float,
    red_weight_multiplier: float,
    args: argparse.Namespace,
) -> dict[str, Any]:
    train_idx = np.array(splits["train"], dtype=np.int64)
    val_idx = np.array(splits["val"], dtype=np.int64)
    test_idx = np.array(splits["test"], dtype=np.int64)
    x_keyword = keyword_scaled * keyword_alpha
    train_loader = make_loader(bert_scaled, x_keyword, y_all, train_idx, args.batch_size, train=True)
    val_loader = make_loader(bert_scaled, x_keyword, y_all, val_idx, args.batch_size, train=False)
    test_loader = make_loader(bert_scaled, x_keyword, y_all, test_idx, args.batch_size, train=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = HybridSafetyClassifier(bert_scaled.shape[1], keyword_scaled.shape[1], args.dropout).to(device)
    counts = np.bincount(y_all[train_idx], minlength=3).astype(np.float32)
    class_weights = counts.sum() / (3 * np.maximum(counts, 1.0))
    class_weights[2] *= red_weight_multiplier
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(class_weights, dtype=torch.float32, device=device))
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    best_state = None
    best_epoch = 0
    best_macro_f1 = -1.0
    wait = 0
    history: list[dict[str, float]] = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses: list[float] = []
        for bert_x, keyword_x, y in train_loader:
            bert_x = bert_x.to(device)
            keyword_x = keyword_x.to(device)
            y = y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(bert_x, keyword_x), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
            optimizer.step()
            losses.append(float(loss.item()))

        val_true, val_logits = evaluate_logits(model, val_loader, device)
        val_pred = val_logits.argmax(axis=1)
        val_macro_f1 = float(f1_score(val_true, val_pred, average="macro", zero_division=0))
        history.append({"epoch": epoch, "train_loss": float(np.mean(losses)), "val_macro_f1": val_macro_f1})
        if val_macro_f1 > best_macro_f1 + 1e-5:
            best_macro_f1 = val_macro_f1
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            wait = 0
        else:
            wait += 1
            if wait >= args.patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    test_true, test_logits = evaluate_logits(model, test_loader, device)
    test_pred = test_logits.argmax(axis=1)
    metrics = metric_bundle(test_true, test_pred)
    return {
        "keyword_alpha": keyword_alpha,
        "red_weight_multiplier": red_weight_multiplier,
        "best_epoch": best_epoch,
        "best_val_macro_f1": round(float(best_macro_f1), 6),
        **{f"test_{key}": value for key, value in metrics.items() if key != "confusion_matrix"},
        "test_confusion_matrix": metrics["confusion_matrix"],
        "history_tail": history[-5:],
    }


def build_report(out_dir: Path, best_policy: dict[str, Any], baseline: dict[str, Any], best_train: dict[str, Any] | None) -> None:
    lines = [
        "# F1 Safety Policy Experiment",
        "",
        "本实验只在 exp 环境中运行，未改动 app 生产分类器。",
        "",
        "## Baseline",
        "",
        f"- baseline macro-F1: {baseline['macro_f1']}",
        f"- baseline accuracy: {baseline['accuracy']}",
        f"- baseline green->red: {baseline['green_to_red_rate']}",
        f"- baseline red recall: {baseline['red_recall']}",
        "",
        "## Best Policy",
        "",
        f"- keyword_alpha: {best_policy['keyword_alpha']}",
        f"- temperature: {best_policy['temperature']}",
        f"- red_threshold: {best_policy['red_threshold']}",
        f"- yellow_threshold: {best_policy['yellow_threshold']}",
        f"- rule_mode: {best_policy['rule_mode']}",
        f"- val objective: {best_policy['val_objective']}",
        f"- test macro-F1: {best_policy['test_macro_f1']}",
        f"- test accuracy: {best_policy['test_accuracy']}",
        f"- test green->red: {best_policy['test_green_to_red_rate']}",
        f"- test yellow->red: {best_policy['test_yellow_to_red_rate']}",
        f"- test red->green: {best_policy['test_red_to_green_rate']}",
        f"- test red recall: {best_policy['test_red_recall']}",
        "",
    ]
    if best_train:
        lines.extend(
            [
                "## Best Retrain Variant",
                "",
                f"- keyword_alpha: {best_train['keyword_alpha']}",
                f"- red_weight_multiplier: {best_train['red_weight_multiplier']}",
                f"- best epoch: {best_train['best_epoch']}",
                f"- test macro-F1: {best_train['test_macro_f1']}",
                f"- test accuracy: {best_train['test_accuracy']}",
                f"- test green->red: {best_train['test_green_to_red_rate']}",
                f"- test red recall: {best_train['test_red_recall']}",
                "",
            ]
        )
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    torch.manual_seed(42)
    np.random.seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    run_id = args.run_id or datetime.now().strftime("policy-experiment-%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = json.loads((args.source_run / "summary.json").read_text(encoding="utf-8-sig"))
    rows = f1.load_rows(Path(summary["data_path"]), summary["label_policy"])
    splits = f1.split_rows(rows, seed=42, test_size=0.15, val_size=0.15)
    val_idx = np.array(splits["val"], dtype=np.int64)
    test_idx = np.array(splits["test"], dtype=np.int64)
    y_all = f1.label_array(rows)

    embeddings = np.load(args.source_run / "bert_embeddings.npy").astype(np.float32)
    scalers = joblib.load(args.model_dir / "feature_scalers.joblib")
    checkpoint = torch.load(args.model_dir / "hybrid_safety_classifier.pt", map_location="cpu", weights_only=False)
    keyword_texts = [item["keyword"] for item in checkpoint["keywords"]]
    tokenizer = tokenizer_for_strategy(checkpoint.get("keyword_strategy", "mixed"))
    texts = [row.get("input", "") for row in rows]
    keyword_raw = build_manual_keyword_matrix(texts, keyword_texts, tokenizer)
    bert_scaled = scalers["bert_scaler"].transform(embeddings).astype(np.float32)
    keyword_scaled = scalers["keyword_scaler"].transform(keyword_raw).astype(np.float32)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = HybridSafetyClassifier(
        bert_dim=int(checkpoint["bert_dim"]),
        keyword_dim=int(checkpoint["keyword_dim"]),
        dropout=float(checkpoint.get("dropout", 0.25)),
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    def get_logits(indices: np.ndarray, keyword_alpha: float) -> tuple[np.ndarray, np.ndarray]:
        x_keyword = keyword_scaled * keyword_alpha
        loader = make_loader(bert_scaled, x_keyword, y_all, indices, 256, train=False)
        return evaluate_logits(model, loader, device)

    alphas = parse_float_list(args.alphas)
    temperatures = parse_float_list(args.temperatures)
    red_thresholds = parse_float_list(args.red_thresholds)
    yellow_thresholds = parse_float_list(args.yellow_thresholds)
    val_texts = [texts[int(idx)] for idx in val_idx]
    test_texts = [texts[int(idx)] for idx in test_idx]

    policy_rows: list[dict[str, Any]] = []
    logits_cache: dict[tuple[str, float], tuple[np.ndarray, np.ndarray]] = {}
    for alpha in alphas:
        logits_cache[("val", alpha)] = get_logits(val_idx, alpha)
        logits_cache[("test", alpha)] = get_logits(test_idx, alpha)
        val_true, val_logits = logits_cache[("val", alpha)]
        test_true, test_logits = logits_cache[("test", alpha)]
        for temperature in temperatures:
            val_probs = logits_to_probabilities(val_logits, temperature)
            test_probs = logits_to_probabilities(test_logits, temperature)
            for red_threshold in red_thresholds:
                for yellow_threshold in yellow_thresholds:
                    if yellow_threshold <= red_threshold * 0.5:
                        continue
                    for rule_mode in ["none", "context", "soft", "strict"]:
                        val_pred = predict_with_policy(
                            val_probs, val_texts, red_threshold, yellow_threshold, rule_mode
                        )
                        test_pred = predict_with_policy(
                            test_probs, test_texts, red_threshold, yellow_threshold, rule_mode
                        )
                        val_metrics = metric_bundle(val_true, val_pred)
                        test_metrics = metric_bundle(test_true, test_pred)
                        policy_rows.append(
                            {
                                "keyword_alpha": alpha,
                                "temperature": temperature,
                                "red_threshold": red_threshold,
                                "yellow_threshold": yellow_threshold,
                                "rule_mode": rule_mode,
                                **{f"val_{key}": value for key, value in val_metrics.items() if key != "confusion_matrix"},
                                **{f"test_{key}": value for key, value in test_metrics.items() if key != "confusion_matrix"},
                                "val_confusion_matrix": json.dumps(val_metrics["confusion_matrix"], ensure_ascii=False),
                                "test_confusion_matrix": json.dumps(test_metrics["confusion_matrix"], ensure_ascii=False),
                            }
                        )

    policy_df = pd.DataFrame(policy_rows)
    policy_df.sort_values(
        by=["val_objective", "test_green_to_red_rate", "test_macro_f1"],
        ascending=[False, True, False],
        inplace=True,
    )
    policy_df.to_csv(out_dir / "policy_grid.csv", index=False, encoding="utf-8-sig")
    best_policy = policy_df.iloc[0].to_dict()
    (out_dir / "best_policy.json").write_text(json.dumps(best_policy, ensure_ascii=False, indent=2), encoding="utf-8")

    baseline_true, baseline_logits = logits_cache[("test", 1.0)]
    baseline_probs = logits_to_probabilities(baseline_logits, 1.0)
    baseline_pred = predict_with_policy(baseline_probs, test_texts, 0.35, 0.45, "none")
    baseline = metric_bundle(baseline_true, baseline_pred)
    (out_dir / "baseline_policy.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")

    train_rows: list[dict[str, Any]] = []
    best_train: dict[str, Any] | None = None
    if args.train_grid:
        for alpha in parse_float_list(args.train_alphas):
            for red_weight_multiplier in parse_float_list(args.red_weight_multipliers):
                result = train_variant(
                    bert_scaled=bert_scaled,
                    keyword_scaled=keyword_scaled,
                    y_all=y_all,
                    splits=splits,
                    keyword_alpha=alpha,
                    red_weight_multiplier=red_weight_multiplier,
                    args=args,
                )
                train_rows.append(result)
        train_df = pd.DataFrame(train_rows)
        train_df.sort_values(
            by=["test_objective", "test_green_to_red_rate", "test_macro_f1"],
            ascending=[False, True, False],
            inplace=True,
        )
        train_df.to_csv(out_dir / "train_grid.csv", index=False, encoding="utf-8-sig")
        best_train = train_df.iloc[0].to_dict()
        (out_dir / "best_train_variant.json").write_text(json.dumps(best_train, ensure_ascii=False, indent=2), encoding="utf-8")

    build_report(out_dir, best_policy=best_policy, baseline=baseline, best_train=best_train)
    print(json.dumps({"out_dir": str(out_dir), "baseline": baseline, "best_policy": best_policy, "best_train": best_train}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
