from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.config import Settings


@dataclass
class MemoryRecord:
    id: int
    anonymous_user_id: str
    session_id: str | None
    text: str
    kind: str
    sensitivity: str
    metadata: dict[str, Any]
    embedding: list[float]
    created_at: float


@dataclass(frozen=True)
class RetrievalCacheConfig:
    ttl_seconds: int
    max_entries: int
    semantic_threshold: float


@dataclass
class RetrievalCacheEntry:
    key: str
    doc_ids: list[int]
    scores: list[float]
    query_embedding: list[float]
    memory_version: int
    expires_at: float


class RetrievalCache:
    def __init__(self, config: RetrievalCacheConfig):
        self.config = config
        self._entries: OrderedDict[str, RetrievalCacheEntry] = OrderedDict()
        self._stats = {
            "lookups": 0,
            "hits": 0,
            "misses": 0,
            "stores": 0,
            "evictions": 0,
        }

    def lookup(
        self,
        *,
        key: str,
        query_embedding: list[float],
        memory_version: int,
    ) -> RetrievalCacheEntry | None:
        self._stats["lookups"] += 1
        now = time.time()
        self._purge_expired(now)
        entry = self._entries.get(key)
        if (
            entry is not None
            and entry.memory_version == memory_version
            and _cosine(query_embedding, entry.query_embedding)
            >= self.config.semantic_threshold
        ):
            self._entries.move_to_end(key)
            self._stats["hits"] += 1
            return entry
        self._stats["misses"] += 1
        return None

    def store(
        self,
        *,
        key: str,
        doc_ids: list[int],
        scores: list[float],
        query_embedding: list[float],
        memory_version: int,
    ) -> None:
        self._entries[key] = RetrievalCacheEntry(
            key=key,
            doc_ids=doc_ids,
            scores=scores,
            query_embedding=query_embedding,
            memory_version=memory_version,
            expires_at=time.time() + self.config.ttl_seconds,
        )
        self._entries.move_to_end(key)
        self._stats["stores"] += 1
        while len(self._entries) > self.config.max_entries:
            self._entries.popitem(last=False)
            self._stats["evictions"] += 1

    def clear(self) -> None:
        self._entries.clear()

    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "entries": len(self._entries),
            "config": asdict(self.config),
        }

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, entry in self._entries.items() if entry.expires_at < now]
        for key in expired:
            self._entries.pop(key, None)
            self._stats["evictions"] += 1


class HashingEmbedder:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.name = f"hashing-{dimension}"

    def embed(self, text: str) -> list[float]:
        vector = np.zeros(self.dimension, dtype=np.float32)
        tokens = re.findall(r"[\w]+", text.lower(), flags=re.UNICODE)
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        return vector.tolist()


class MiniLMEmbedder:
    def __init__(self, model_path: str):
        import torch
        from transformers import AutoModel, AutoTokenizer

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(
                f"MiniLM model not found at {path}. Use F6_MEMORY_EMBEDDING_MODEL=hashing "
                "or download all-MiniLM-L6-v2 first."
            )
        self.name = str(path)
        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        self.model = AutoModel.from_pretrained(str(path), local_files_only=True).to(self.device)
        self.model.eval()

    def embed(self, text: str) -> list[float]:
        encoded = self.tokenizer(
            [text],
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with self.torch.no_grad():
            output = self.model(**encoded)
        token_embeddings = output.last_hidden_state
        attention_mask = encoded["attention_mask"].unsqueeze(-1).float()
        embedding = (token_embeddings * attention_mask).sum(dim=1) / attention_mask.sum(
            dim=1
        ).clamp(min=1e-9)
        embedding = self.torch.nn.functional.normalize(embedding, p=2, dim=1)
        return embedding[0].detach().cpu().numpy().astype(np.float32).tolist()


class MemoryRAGService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = settings.F6_MEMORY_ENABLE
        self.persist_dir = Path(settings.F6_MEMORY_PERSIST_DIR)
        self.records_file = self.persist_dir / "memory_records.jsonl"
        self.embedder = self._build_embedder(settings)
        self.cache = RetrievalCache(
            RetrievalCacheConfig(
                ttl_seconds=settings.F6_RAG_CACHE_TTL_SECONDS,
                max_entries=settings.F6_RAG_CACHE_MAX_ENTRIES,
                semantic_threshold=settings.F6_RAG_CACHE_SEMANTIC_THRESHOLD,
            )
        )
        self.records: list[MemoryRecord] = []
        self._faiss_index = None
        self._faiss_ids: list[int] = []
        self._next_id = 0
        self._version = 0
        self._load()
        self._rebuild_faiss_index()

    def add_memory(
        self,
        *,
        anonymous_user_id: str,
        text: str,
        session_id: str | None = None,
        kind: str = "summary",
        sensitivity: str = "medium",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord | None:
        if not self.enabled or not anonymous_user_id.strip() or not text.strip():
            return None
        record = MemoryRecord(
            id=self._next_id,
            anonymous_user_id=anonymous_user_id,
            session_id=session_id,
            text=text.strip(),
            kind=kind,
            sensitivity=sensitivity,
            metadata=metadata or {},
            embedding=self.embedder.embed(text),
            created_at=time.time(),
        )
        self._next_id += 1
        self.records.append(record)
        self._add_to_faiss(record)
        self._version += 1
        self.cache.clear()
        self._persist()
        return record

    def search(
        self,
        *,
        anonymous_user_id: str,
        query: str,
        session_id: str | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
        include_high_sensitivity: bool = False,
    ) -> list[dict[str, Any]]:
        if not self.enabled or not anonymous_user_id.strip() or not query.strip():
            return []
        query_embedding = self.embedder.embed(query)
        cache_key = stable_hash(
            {
                "anonymous_user_id": anonymous_user_id,
                "session_id": session_id,
                "query": normalize_query(query),
                "top_k": top_k or self.settings.F6_MEMORY_TOP_K,
                "min_score": min_score if min_score is not None else self.settings.F6_MEMORY_MIN_SCORE,
                "include_high_sensitivity": include_high_sensitivity,
            }
        )
        cached = self.cache.lookup(
            key=cache_key,
            query_embedding=query_embedding,
            memory_version=self._version,
        )
        record_by_id = {record.id: record for record in self.records}
        if cached is not None:
            return [
                self._format_record(record_by_id[doc_id], score)
                for doc_id, score in zip(cached.doc_ids, cached.scores)
                if doc_id in record_by_id
            ]

        limit = top_k or self.settings.F6_MEMORY_TOP_K
        threshold = min_score if min_score is not None else self.settings.F6_MEMORY_MIN_SCORE
        ranked: list[tuple[MemoryRecord, float]] = []
        candidates = self._candidate_records(query_embedding, fetch_k=max(limit * 8, 20))
        for record, vector_score in candidates:
            if record.anonymous_user_id != anonymous_user_id:
                continue
            if session_id is not None and record.session_id != session_id:
                continue
            if not include_high_sensitivity and record.sensitivity == "high":
                continue
            score = self._combined_score(query, query_embedding, record, vector_score=vector_score)
            if score >= threshold:
                ranked.append((record, score))
        ranked.sort(key=lambda item: -item[1])
        results = ranked[:limit]
        self.cache.store(
            key=cache_key,
            doc_ids=[record.id for record, _score in results],
            scores=[score for _record, score in results],
            query_embedding=query_embedding,
            memory_version=self._version,
        )
        return [self._format_record(record, score) for record, score in results]

    def clear(
        self,
        *,
        anonymous_user_id: str | None = None,
        session_id: str | None = None,
    ) -> int:
        if anonymous_user_id is None and session_id is None:
            deleted = len(self.records)
            self.records = []
            self._next_id = 0
            self._faiss_index = None
            self._faiss_ids = []
            self._version += 1
            self.cache.clear()
            if self.persist_dir.exists():
                shutil.rmtree(self.persist_dir)
            return deleted

        before = len(self.records)
        self.records = [
            record
            for record in self.records
            if not self._matches(record, anonymous_user_id=anonymous_user_id, session_id=session_id)
        ]
        deleted = before - len(self.records)
        if deleted:
            self._version += 1
            self.cache.clear()
            self._rebuild_faiss_index()
            self._persist()
        return deleted

    def stats(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "records": len(self.records),
            "embedding_model": self.embedder.name,
            "cache": self.cache.stats(),
        }

    def _combined_score(
        self,
        query: str,
        query_embedding: list[float],
        record: MemoryRecord,
        vector_score: float | None = None,
    ) -> float:
        vector_score = (
            max(_cosine(query_embedding, record.embedding), 0.0)
            if vector_score is None
            else max(vector_score, 0.0)
        )
        lexical_score = _lexical_score(query, record.text)
        age_days = max((time.time() - record.created_at) / (60 * 60 * 24), 0.0)
        recency = 1.0 / (1.0 + math.log1p(age_days))
        return 0.65 * vector_score + 0.30 * lexical_score + 0.05 * recency

    def _candidate_records(
        self,
        query_embedding: list[float],
        *,
        fetch_k: int,
    ) -> list[tuple[MemoryRecord, float]]:
        record_by_id = {record.id: record for record in self.records}
        if self._faiss_index is not None and self._faiss_ids:
            query = np.asarray([query_embedding], dtype=np.float32)
            _normalize_matrix(query)
            scores, positions = self._faiss_index.search(
                query,
                min(fetch_k, len(self._faiss_ids)),
            )
            candidates: list[tuple[MemoryRecord, float]] = []
            for position, score in zip(positions[0], scores[0]):
                if position < 0 or position >= len(self._faiss_ids):
                    continue
                record = record_by_id.get(self._faiss_ids[int(position)])
                if record is not None:
                    candidates.append((record, float(score)))
            return candidates
        return [
            (record, _cosine(query_embedding, record.embedding))
            for record in self.records
        ]

    def _rebuild_faiss_index(self) -> None:
        self._faiss_index = None
        self._faiss_ids = []
        if not self.records:
            return
        try:
            import faiss  # type: ignore
        except Exception:
            return
        vectors = np.asarray([record.embedding for record in self.records], dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] == 0:
            return
        _normalize_matrix(vectors)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        self._faiss_index = index
        self._faiss_ids = [record.id for record in self.records]

    def _add_to_faiss(self, record: MemoryRecord) -> None:
        if self._faiss_index is None:
            self._rebuild_faiss_index()
            return
        vector = np.asarray([record.embedding], dtype=np.float32)
        _normalize_matrix(vector)
        self._faiss_index.add(vector)
        self._faiss_ids.append(record.id)

    def _load(self) -> None:
        if not self.records_file.exists():
            return
        records: list[MemoryRecord] = []
        for line in self.records_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            records.append(MemoryRecord(**payload))
        self.records = records
        self._next_id = max((record.id for record in records), default=-1) + 1

    def _persist(self) -> None:
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        text = "\n".join(
            json.dumps(asdict(record), ensure_ascii=False) for record in self.records
        )
        self.records_file.write_text(text + ("\n" if text else ""), encoding="utf-8")

    @staticmethod
    def _build_embedder(settings: Settings):
        if settings.F6_MEMORY_EMBEDDING_MODEL.lower() in {"minilm", "all-minilm-l6-v2"}:
            return MiniLMEmbedder(settings.F6_MEMORY_MINILM_PATH)
        return HashingEmbedder()

    @staticmethod
    def _matches(
        record: MemoryRecord,
        *,
        anonymous_user_id: str | None,
        session_id: str | None,
    ) -> bool:
        if anonymous_user_id is not None and record.anonymous_user_id != anonymous_user_id:
            return False
        if session_id is not None and record.session_id != session_id:
            return False
        return True

    @staticmethod
    def _format_record(record: MemoryRecord, score: float) -> dict[str, Any]:
        return {
            "id": record.id,
            "text": record.text,
            "kind": record.kind,
            "sensitivity": record.sensitivity,
            "score": round(float(score), 4),
            "session_id": record.session_id,
            "metadata": record.metadata,
        }


def normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())


def stable_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_arr = np.asarray(left, dtype=np.float32)
    right_arr = np.asarray(right, dtype=np.float32)
    denominator = float(np.linalg.norm(left_arr) * np.linalg.norm(right_arr))
    if denominator <= 1e-12:
        return 0.0
    return float(np.dot(left_arr, right_arr) / denominator)


def _normalize_matrix(matrix: np.ndarray) -> None:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.divide(matrix, np.clip(norms, 1e-12, None), out=matrix)


def _lexical_score(query: str, text: str) -> float:
    query_tokens = set(re.findall(r"[\w]+", query.lower(), flags=re.UNICODE))
    text_tokens = set(re.findall(r"[\w]+", text.lower(), flags=re.UNICODE))
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = len(query_tokens & text_tokens)
    return overlap / max(len(query_tokens), 1)
