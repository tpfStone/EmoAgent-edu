from app.config import Settings
from app.services.memory_rag_service import MemoryRAGService


def test_memory_rag_service_search_and_clear(tmp_path):
    service = MemoryRAGService(
        Settings(
            F6_MEMORY_ENABLE=True,
            F6_MEMORY_PERSIST_DIR=str(tmp_path / "memory"),
            F6_MEMORY_EMBEDDING_MODEL="hashing",
            F6_MEMORY_MIN_SCORE=0.0,
        )
    )

    record = service.add_memory(
        anonymous_user_id="anon-1",
        session_id="session-1",
        text="用户最近提到考试前容易紧张，想先从整理错题开始。",
        kind="summary",
        sensitivity="medium",
    )

    assert record is not None
    results = service.search(
        anonymous_user_id="anon-1",
        query="考试紧张 错题",
        min_score=0.0,
    )
    assert results
    assert results[0]["text"].startswith("用户最近提到考试前")
    assert service.cache.stats()["stores"] >= 1

    deleted = service.clear(anonymous_user_id="anon-1")

    assert deleted == 1
    assert service.stats()["records"] == 0
