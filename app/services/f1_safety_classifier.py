from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jieba
import joblib
import numpy as np
import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer


LABELS = ["green", "yellow", "red"]
REQUIRED_MODEL_FILES = [
    "hybrid_safety_classifier.pt",
    "feature_scalers.joblib",
    "manual_keywords.json",
    "manual_keywords_grouped.json",
    "model_config.json",
]
RISK_SINGLE_CHARS = {"死", "割", "跳", "药", "刀", "血", "疼", "哭", "恨"}
STOPWORDS = {
    "一个",
    "一些",
    "一种",
    "这个",
    "那个",
    "这些",
    "那些",
    "自己",
    "我们",
    "你们",
    "他们",
    "她们",
    "就是",
    "觉得",
    "感觉",
    "因为",
    "所以",
    "但是",
    "如果",
    "然后",
    "现在",
    "可能",
    "可以",
    "没有",
    "不是",
    "还是",
    "什么",
    "怎么",
    "时候",
    "知道",
    "进行",
    "需要",
    "以及",
    "或者",
    "比较",
    "非常",
    "很多",
    "一下",
    "这样",
    "那样",
    "已经",
    "一直",
    "最近",
    "真的",
}

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
    "消失了",
    "如果我消失",
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
    "结束这一切",
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
SAFE_SHORT_UTTERANCES = {
    "hi",
    "hello",
    "嗨",
    "你好",
    "您好",
    "早",
    "早上好",
    "晚上好",
    "谢谢",
    "再见",
    "拜拜",
}
TECHNICAL_COMMAND_PATTERNS = [
    r"(?m)^\s*(cd|set|python|pnpm|npm|docker|git|uvicorn)\b",
    r"\$env:[a-z0-9_]+\s*=",
    r"\b[a-z]:\\",
    r"\\\.venv\\",
    r"\bpython(?:\.exe)?\s+-m\b",
    r"\buvicorn\b",
    r"--[a-z0-9][a-z0-9-]*",
    r"\b[a-z0-9_]{3,}\s*=\s*[\"']?[^ \t\r\n\"']+",
    r"\.(exe|ps1|py|mjs|json)\b",
]


@dataclass(frozen=True)
class SafetyRuleSignals:
    red_necessary: bool
    idiom_without_intent: bool
    bullying_without_self_harm: bool
    passive_with_negation_without_concrete_signal: bool
    signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class F1SafetyPrediction:
    risk_level: str
    argmax_level: str
    probabilities: dict[str, float]
    matched_keywords: list[str]
    latency_ms: float
    rule_signals: list[str] = field(default_factory=list)


class F1SafetyModelUnavailableError(RuntimeError):
    """Raised when the local F1 safety model artifact directory is incomplete."""


class UnavailableF1SafetyClassifier:
    def __init__(self, reason: str):
        self.reason = reason

    def predict(self, text: str) -> F1SafetyPrediction:
        raise F1SafetyModelUnavailableError(self.reason)


def missing_model_files(model_dir: str | Path) -> list[str]:
    root = Path(model_dir)
    return [name for name in REQUIRED_MODEL_FILES if not (root / name).exists()]


def f1_model_download_command(
    repo_id: str = "Nacgisac/EmoEduF1-bert-base-chinese",
    revision: str = "main",
    local_dir: str = "exp/models/f1_safety_gate",
) -> str:
    return (
        f"hf download {repo_id} --include \"manual-A-pattern-v1/*\" "
        f"--local-dir {local_dir} --revision {revision}"
    )


def build_model_unavailable_message(
    model_dir: str | Path,
    repo_id: str = "Nacgisac/EmoEduF1-bert-base-chinese",
    revision: str = "main",
) -> str:
    missing = missing_model_files(model_dir)
    missing_text = ", ".join(missing) if missing else "unknown model artifact"
    return (
        f"F1 safety model artifacts are missing under {Path(model_dir)}: {missing_text}. "
        "Download them before production use: "
        f"{f1_model_download_command(repo_id=repo_id, revision=revision)}"
    )


class HybridSafetyClassifier(nn.Module):
    def __init__(self, bert_dim: int, keyword_dim: int, dropout: float):
        super().__init__()
        keyword_hidden = min(128, max(24, keyword_dim // 4))
        self.bert_branch = nn.Sequential(
            nn.Linear(bert_dim, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(dropout),
        )
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
        bert_h = self.bert_branch(bert_x)
        keyword_h = self.keyword_branch(keyword_x)
        return self.classifier(torch.cat([bert_h, keyword_h], dim=-1))


def normalize_text(text: Any) -> str:
    value = str(text or "").lower()
    return re.sub(r"\s+", " ", value).strip()


def compact_for_char(text: Any) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", normalize_text(text)))


def contains_any(value: str, patterns: list[str]) -> bool:
    return any(pattern in value for pattern in patterns)


def is_safe_short_utterance(text: Any) -> bool:
    return compact_for_char(text) in SAFE_SHORT_UTTERANCES


def is_technical_command_text(text: Any) -> bool:
    value = str(text or "")
    if not value.strip():
        return False

    lower_value = value.lower()
    marker_count = sum(
        1 for pattern in TECHNICAL_COMMAND_PATTERNS if re.search(pattern, lower_value)
    )
    nonempty_line_count = sum(1 for line in value.splitlines() if line.strip())
    has_env_assignment = bool(re.search(r"\$env:[a-z0-9_]+\s*=", lower_value))
    has_command_flag = bool(re.search(r"--[a-z0-9][a-z0-9-]*", lower_value))
    has_executable = bool(re.search(r"\bpython(?:\.exe)?\b|\.exe\b", lower_value))

    return (
        marker_count >= 4
        or (nonempty_line_count >= 2 and marker_count >= 3)
        or (has_env_assignment and has_command_flag and has_executable)
    )


def analyze_safety_rule_signals(text: Any) -> SafetyRuleSignals:
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

    signals: list[str] = []
    if has_idiom:
        signals.append("idiom_expression")
    if has_bullying:
        signals.append("bullying_context")
    if has_passive_death:
        signals.append("passive_death_ideation")
    if has_active_suicide:
        signals.append("active_suicide_ideation")
    if has_self_harm:
        signals.append("self_harm_expression")
    if has_method:
        signals.append("method_signal")
    if has_time:
        signals.append("time_signal")
    if has_preparation:
        signals.append("preparation_signal")
    if has_negation:
        signals.append("negation_or_downgrade")

    risk_intent = has_active_suicide or has_passive_death or has_self_harm
    concrete_signal = has_method or has_time or has_preparation
    red_necessary = bool((has_self_harm and has_method) or (risk_intent and concrete_signal and not has_negation))
    idiom_without_intent = bool(has_idiom and not risk_intent and not has_method)
    bullying_without_self_harm = bool(has_bullying and not risk_intent and not concrete_signal)
    passive_with_negation_without_concrete_signal = bool(has_passive_death and has_negation and not concrete_signal)
    return SafetyRuleSignals(
        red_necessary=red_necessary,
        idiom_without_intent=idiom_without_intent,
        bullying_without_self_harm=bullying_without_self_harm,
        passive_with_negation_without_concrete_signal=passive_with_negation_without_concrete_signal,
        signals=signals,
    )


def apply_soft_rule_postprocess(
    candidate_level: str,
    probabilities: dict[str, float],
    text: Any,
    yellow_or_red_threshold: float,
) -> tuple[str, SafetyRuleSignals]:
    signals = analyze_safety_rule_signals(text)
    p_red = probabilities.get("red", 0.0)
    p_yellow_or_red = probabilities.get("yellow", 0.0) + p_red
    risk_intent_signals = {
        "passive_death_ideation",
        "active_suicide_ideation",
        "self_harm_expression",
    }
    has_risk_intent = any(signal in signals.signals for signal in risk_intent_signals)

    if is_safe_short_utterance(text) and not signals.signals:
        return "green", signals
    if signals.red_necessary:
        return "red", signals
    if has_risk_intent:
        return "yellow", signals
    if is_technical_command_text(text):
        return "green", signals
    if (
        candidate_level == "yellow"
        and not signals.signals
        and p_yellow_or_red < yellow_or_red_threshold + 0.10
    ):
        return "green", signals
    if candidate_level != "red":
        return candidate_level, signals

    if signals.idiom_without_intent:
        level = "yellow" if p_yellow_or_red >= yellow_or_red_threshold else "green"
    elif signals.bullying_without_self_harm:
        level = "yellow"
    elif signals.passive_with_negation_without_concrete_signal:
        level = "yellow"
    elif not signals.red_necessary and p_red < 0.8:
        level = "yellow"
    else:
        level = "red"
    return level, signals


def is_valid_token(token: str) -> bool:
    token = token.strip().lower()
    if not token or token in STOPWORDS:
        return False
    if token in RISK_SINGLE_CHARS:
        return True
    if re.fullmatch(r"\d+", token):
        return False
    if re.search(r"[\u4e00-\u9fff]", token) and 2 <= len(token) <= 8:
        return True
    return bool(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_\-]{2,20}", token))


def jieba_word_tokens(text: Any) -> list[str]:
    return [
        token.strip().lower()
        for token in jieba.lcut(normalize_text(text), cut_all=False)
        if is_valid_token(token)
    ]


def char_ngram_tokens(text: Any, min_n: int = 1, max_n: int = 4) -> list[str]:
    compact = compact_for_char(text)
    tokens: list[str] = []
    for n in range(min_n, max_n + 1):
        if n == 1:
            tokens.extend(ch for ch in compact if ch in RISK_SINGLE_CHARS)
        else:
            tokens.extend(compact[i : i + n] for i in range(max(0, len(compact) - n + 1)))
    return tokens


def mixed_tokens(text: Any) -> list[str]:
    return jieba_word_tokens(text) + char_ngram_tokens(text, min_n=2, max_n=3)


def tokenizer_for_strategy(strategy: str):
    if strategy == "jieba_word":
        return jieba_word_tokens
    if strategy == "char_ngram":
        return char_ngram_tokens
    return mixed_tokens


def manual_keyword_hits(text: Any, keyword: str, tokenizer_tokens: Counter[str]) -> int:
    value = normalize_text(text)
    keyword = keyword.strip()
    if not value or not keyword:
        return 0

    token_hits = int(tokenizer_tokens.get(keyword, 0))
    pattern_hits = 0

    # 单字词需要用上下文约束，否则“打算”等普通词会误触发。
    if keyword == "打":
        pattern_hits += len(re.findall(r"(打我|打人|被打|挨打|殴打|打骂|打死|打伤|家暴)", value))
    elif keyword == "骂":
        pattern_hits += len(re.findall(r"(骂我|被骂|挨骂|辱骂|谩骂|打骂|责骂)", value))
    elif len(keyword) == 1:
        if keyword in RISK_SINGLE_CHARS:
            pattern_hits += value.count(keyword)
    else:
        pattern_hits += value.count(keyword)

    return token_hits + pattern_hits


def build_manual_keyword_matrix(texts: list[str], keywords: list[str], tokenizer) -> np.ndarray:
    matrix = np.zeros((len(texts), len(keywords)), dtype=np.float32)
    for row_idx, text in enumerate(texts):
        tokens = Counter(tokenizer(text))
        normalizer = math.sqrt(max(1, len(tokens)))
        for col_idx, keyword in enumerate(keywords):
            hits = manual_keyword_hits(text, keyword, tokens)
            if hits:
                matrix[row_idx, col_idx] = math.log1p(hits) / normalizer
    return matrix


class F1SafetyClassifier:
    def __init__(
        self,
        model_dir: str | Path,
        bert_model_name: str | None = None,
        max_length: int | None = None,
        red_threshold: float | None = None,
        yellow_or_red_threshold: float | None = None,
        local_files_only: bool = True,
        device: str = "auto",
    ):
        self.model_dir = Path(model_dir)
        missing = missing_model_files(self.model_dir)
        if missing:
            raise F1SafetyModelUnavailableError(
                build_model_unavailable_message(self.model_dir)
            )
        self.config = self._read_config(self.model_dir / "model_config.json")
        self.bert_model_name = bert_model_name or self.config.get("bert_model_name", "bert-base-chinese")
        self.max_length = int(max_length or self.config.get("max_length", 192))
        thresholds = self.config.get("thresholds", {})
        self.red_threshold = float(
            red_threshold if red_threshold is not None else thresholds.get("red_threshold", 0.35)
        )
        self.yellow_or_red_threshold = float(
            yellow_or_red_threshold
            if yellow_or_red_threshold is not None
            else thresholds.get("yellow_or_red_threshold", 0.45)
        )
        self.device = self._resolve_device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.bert_model_name,
            local_files_only=local_files_only,
        )
        self.bert = AutoModel.from_pretrained(
            self.bert_model_name,
            local_files_only=local_files_only,
        ).to(self.device)
        self.bert.eval()

        checkpoint = torch.load(
            self.model_dir / "hybrid_safety_classifier.pt",
            map_location=self.device,
            weights_only=False,
        )
        self.labels = list(checkpoint["labels"])
        self.keywords = list(checkpoint["keywords"])
        self.keyword_texts = [item["keyword"] for item in self.keywords]
        self.keyword_strategy = checkpoint.get("keyword_strategy", "mixed")
        self.keyword_tokenizer = tokenizer_for_strategy(self.keyword_strategy)
        self.scalers = joblib.load(self.model_dir / "feature_scalers.joblib")
        self.classifier = HybridSafetyClassifier(
            bert_dim=int(checkpoint["bert_dim"]),
            keyword_dim=int(checkpoint["keyword_dim"]),
            dropout=float(checkpoint.get("dropout", 0.25)),
        ).to(self.device)
        self.classifier.load_state_dict(checkpoint["model_state_dict"])
        self.classifier.eval()

    @staticmethod
    def _read_config(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8-sig"))

    @staticmethod
    def _resolve_device(device: str) -> torch.device:
        if device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device)

    def predict(self, text: str) -> F1SafetyPrediction:
        started = time.perf_counter()
        bert_x = self._bert_embedding(text)
        keyword_x = build_manual_keyword_matrix(
            [text],
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
        probabilities = {self.labels[idx]: float(probs[idx]) for idx in range(len(self.labels))}
        risk_level, rule_signals = self._apply_thresholds(probabilities, text)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return F1SafetyPrediction(
            risk_level=risk_level,
            argmax_level=self.labels[int(np.argmax(probs))],
            probabilities=probabilities,
            matched_keywords=self._matched_keywords(text),
            latency_ms=latency_ms,
            rule_signals=rule_signals.signals,
        )

    def _bert_embedding(self, text: str) -> np.ndarray:
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

    def _matched_keywords(self, text: str) -> list[str]:
        tokens = Counter(self.keyword_tokenizer(text))
        matched: list[str] = []
        seen: set[str] = set()
        for keyword in self.keyword_texts:
            if keyword in seen:
                continue
            if manual_keyword_hits(text, keyword, tokens) > 0:
                matched.append(keyword)
                seen.add(keyword)
        return matched

    def _apply_thresholds(
        self, probabilities: dict[str, float], text: str
    ) -> tuple[str, SafetyRuleSignals]:
        p_red = probabilities.get("red", 0.0)
        p_yellow_or_red = probabilities.get("yellow", 0.0) + p_red
        if p_red >= self.red_threshold:
            candidate_level = "red"
        elif p_yellow_or_red >= self.yellow_or_red_threshold:
            candidate_level = "yellow"
        else:
            candidate_level = "green"
        return apply_soft_rule_postprocess(
            candidate_level,
            probabilities,
            text,
            self.yellow_or_red_threshold,
        )
