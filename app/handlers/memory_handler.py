from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_memory_rag_service
from app.services.memory_rag_service import MemoryRAGService

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/status")
async def memory_status(
    memory_service: MemoryRAGService = Depends(get_memory_rag_service),
):
    return memory_service.stats()


@router.delete("")
async def clear_memory(
    anonymous_user_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    memory_service: MemoryRAGService = Depends(get_memory_rag_service),
):
    if not anonymous_user_id and not session_id:
        raise HTTPException(
            status_code=400,
            detail="anonymous_user_id or session_id is required",
        )
    deleted = memory_service.clear(
        anonymous_user_id=anonymous_user_id,
        session_id=session_id,
    )
    return {
        "deleted": deleted,
        "remaining": memory_service.stats()["records"],
        "enabled": memory_service.enabled,
    }
