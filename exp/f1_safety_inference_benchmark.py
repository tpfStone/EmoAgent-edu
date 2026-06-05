from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

EXP_DIR = Path(__file__).resolve().parent
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

import f1_safety_gate_experiment as f1
import f1_train_manual_keywords as manual_train

DEFAULT_MODEL_DIR = Path("exp/models/f1_safety_gate/manual-A-pattern-v1")
DEFAULT_TEXTS = [
    "最近考试压力很大，晚上会一直想今天没学好的地方，但我只是很烦，不知道怎么调整。",
    "我最近每天都失眠，觉得活着没什么意思，但我没有具体计划，只是很累。",
    "我想自杀，已经准备好了药，今晚不想再撑下去了。",
    "同学总是在背后骂我，我一想到去学校就哭，感觉自己快撑不住了。",
    "爸妈总是拿我和别人比，我很生气，也很想反抗，但不知道怎么说。",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark F1 safety gate inference latency.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--model-name", type=str, default=None)
    parser.add_argument("--max-length", type=int, default=None)
    parser.add_argument("--red-threshold", type=float, default=None)
    parser.add_argument("--yellow-or-red-threshold", type=float, default=None)
    parser.add_argument("--texts-file", type=Path, default=None)
    parser.add_argument("--repeat", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def load_texts(path: Path | None) -> list[str]:
    if path is None:
        return DEFAULT_TEXTS
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(item) for item in data]
    return [line.strip() for line in raw.splitlines() if line.strip()]


class F1SafetyPredictor:
    def __init__(
        self,
        model_dir: Path,
        model_name: str | None,
        max_length: int | None,
        red_threshold: float | None,
        yellow_or_red_threshold: float | None,
        local_files_only: bool,
    ):
        started = time.perf_counter()
        self.model_dir = model_dir
        self.config = json.loads((model_dir / "model_config.json").read_text(encoding="utf-8-sig"))
        self.model_name = model_name or self.config.get("bert_model_name", "bert-base-chinese")
        self.max_length = int(max_length or self.config.get("max_length", 192))
        thresholds = self.config.get("thresholds", {})
        self.red_threshold = float(red_threshold if red_threshold is not None else thresholds.get("red_threshold", 0.35))
        self.yellow_or_red_threshold = float(
            yellow_or_red_threshold if yellow_or_red_threshold is not None else thresholds.get("yellow_or_red_threshold", 0.45)
        )
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=local_files_only)
        self.bert = AutoModel.from_pretrained(self.model_name, local_files_only=local_files_only).to(self.device)
        self.bert.eval()

        checkpoint = torch.load(model_dir / "hybrid_safety_classifier.pt", map_location=self.device)
        self.labels = checkpoint["labels"]
        self.keywords = checkpoint["keywords"]
        self.keyword_texts = [item["keyword"] for item in self.keywords]
        self.keyword_strategy = checkpoint.get("keyword_strategy", "mixed")
        self.keyword_tokenizer = f1.tokenizer_for_strategy(self.keyword_strategy)
        self.scalers = joblib.load(model_dir / "feature_scalers.joblib")
        self.classifier = f1.HybridSafetyClassifier(
            bert_dim=int(checkpoint["bert_dim"]),
            keyword_dim=int(checkpoint["keyword_dim"]),
            dropout=float(checkpoint.get("dropout", 0.25)),
        ).to(self.device)
        self.classifier.load_state_dict(checkpoint["model_state_dict"])
        self.classifier.eval()
        self.load_seconds = time.perf_counter() - started

    def _sync(self) -> None:
        if self.device.type == "cuda":
            torch.cuda.synchronize()

    def _bert_embed(self, text: str) -> np.ndarray:
        encoded = self.tokenizer(
            [text],
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with torch.no_grad():
            output = self.bert(**encoded)
            hidden = output.last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)
        return pooled.detach().cpu().numpy().astype(np.float32)

    def predict(self, text: str) -> dict[str, Any]:
        self._sync()
        started = time.perf_counter()
        bert_x = self._bert_embed(text)
        keyword_x = manual_train.build_manual_keyword_matrix(
            [{"input": text}],
            self.keyword_texts,
            self.keyword_tokenizer,
        )
        bert_x = self.scalers["bert_scaler"].transform(bert_x).astype(np.float32)
        keyword_x = self.scalers["keyword_scaler"].transform(keyword_x).astype(np.float32)
        with torch.no_grad():
            logits = self.classifier(
                torch.tensor(bert_x, dtype=torch.float32, device=self.device),
                torch.tensor(keyword_x, dtype=torch.float32, device=self.device),
            )
            probs = torch.softmax(logits, dim=-1).detach().cpu().numpy()[0]
        self._sync()
        latency_ms = (time.perf_counter() - started) * 1000.0
        prob_map = {self.labels[idx]: float(probs[idx]) for idx in range(len(self.labels))}
        decision = self.apply_thresholds(prob_map)
        return {
            "decision": decision,
            "argmax": self.labels[int(np.argmax(probs))],
            "probabilities": {label: round(value, 6) for label, value in prob_map.items()},
            "latency_ms": round(latency_ms, 3),
        }

    def apply_thresholds(self, probabilities: dict[str, float]) -> str:
        p_red = probabilities.get("red", 0.0)
        p_yellow_or_red = probabilities.get("yellow", 0.0) + p_red
        if p_red >= self.red_threshold:
            return "red"
        if p_yellow_or_red >= self.yellow_or_red_threshold:
            return "yellow"
        return "green"


def latency_summary(values: list[float]) -> dict[str, float]:
    values = sorted(values)
    p95_index = max(0, min(len(values) - 1, int(round(0.95 * (len(values) - 1)))))
    return {
        "count": len(values),
        "mean_ms": round(statistics.mean(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "min_ms": round(values[0], 3),
        "max_ms": round(values[-1], 3),
        "p95_ms": round(values[p95_index], 3),
    }


def main() -> None:
    args = parse_args()
    predictor = F1SafetyPredictor(
        model_dir=args.model_dir,
        model_name=args.model_name,
        max_length=args.max_length,
        red_threshold=args.red_threshold,
        yellow_or_red_threshold=args.yellow_or_red_threshold,
        local_files_only=args.local_files_only,
    )
    texts = load_texts(args.texts_file)
    for _ in range(args.warmup):
        predictor.predict(texts[0])

    predictions = []
    latencies: list[float] = []
    for text in texts:
        first = predictor.predict(text)
        predictions.append({"text": text, **first})
        for _ in range(args.repeat):
            result = predictor.predict(text)
            latencies.append(float(result["latency_ms"]))

    result = {
        "model_dir": str(args.model_dir),
        "device": str(predictor.device),
        "load_seconds": round(predictor.load_seconds, 3),
        "max_length": predictor.max_length,
        "thresholds": {
            "red_threshold": predictor.red_threshold,
            "yellow_or_red_threshold": predictor.yellow_or_red_threshold,
        },
        "latency": latency_summary(latencies),
        "predictions": predictions,
    }
    output_path = args.model_dir / "inference_benchmark.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

