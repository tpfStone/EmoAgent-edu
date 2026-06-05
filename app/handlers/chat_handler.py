import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_orchestrator_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
) -> ChatResponse:
    return await orchestrator_service.chat(request)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
) -> StreamingResponse:
    return StreamingResponse(
        _chat_stream_events(request, orchestrator_service),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _chat_stream_events(
    request: ChatRequest,
    orchestrator_service: OrchestratorService,
) -> AsyncIterator[str]:
    try:
        yield _sse("stage", {"name": "received"})
        if hasattr(orchestrator_service, "stream_chat"):
            async for event, payload in orchestrator_service.stream_chat(request):
                yield _sse(event, payload)
            return

        response = await orchestrator_service.chat(request)
        metadata = response.model_dump(exclude={"reply_text"})
        yield _sse("metadata", metadata)

        chunk_size = orchestrator_service.settings.CHAT_STREAM_CHUNK_SIZE
        for chunk in _chunks(response.reply_text, chunk_size):
            yield _sse("delta", {"text": chunk})
            await asyncio.sleep(0)

        yield _sse("done", response.model_dump())
    except Exception as exc:
        yield _sse(
            "error",
            {
                "session_id": request.session_id,
                "anonymous_user_id": request.anonymous_user_id,
                "message": str(exc),
            },
        )


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _chunks(text: str, size: int) -> list[str]:
    if not text:
        return []
    safe_size = max(size, 1)
    return [text[index : index + safe_size] for index in range(0, len(text), safe_size)]
