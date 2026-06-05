from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.handlers import (
    chat_handler,
    critic_handler,
    generator_handler,
    memory_handler,
    safety_handler,
    scenario_handler,
)
from app.services.f1_safety_classifier import (
    F1SafetyClassifier,
    UnavailableF1SafetyClassifier,
    build_model_unavailable_message,
)
from app.services.f3_support_service import F3SupportService
from app.services.memory_rag_service import MemoryRAGService

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.F1_SAFETY_PRELOAD:
        try:
            app.state.f1_safety_classifier = F1SafetyClassifier(
                model_dir=settings.F1_SAFETY_MODEL_DIR,
                bert_model_name=settings.F1_SAFETY_BERT_MODEL,
                max_length=settings.F1_SAFETY_MAX_LENGTH,
                red_threshold=settings.F1_SAFETY_RED_THRESHOLD,
                yellow_or_red_threshold=settings.F1_SAFETY_YELLOW_OR_RED_THRESHOLD,
                local_files_only=settings.F1_SAFETY_LOCAL_FILES_ONLY,
                device=settings.F1_SAFETY_DEVICE,
            )
        except Exception as exc:
            message = build_model_unavailable_message(
                settings.F1_SAFETY_MODEL_DIR,
                settings.F1_SAFETY_HF_REPO,
                settings.F1_SAFETY_HF_REVISION,
            )
            if settings.F1_SAFETY_REQUIRED:
                raise RuntimeError(message) from exc
            app.state.f1_safety_classifier = UnavailableF1SafetyClassifier(message)
            app.state.f1_safety_classifier_error = message
    if settings.F3_SUPPORT_PRELOAD:
        app.state.f3_support_service = F3SupportService(settings)
    if settings.F6_MEMORY_PRELOAD:
        app.state.memory_rag_service = MemoryRAGService(settings)
    yield


app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    lifespan=lifespan,
)

app.include_router(safety_handler.router)
app.include_router(scenario_handler.router)
app.include_router(generator_handler.router)
app.include_router(critic_handler.router)
app.include_router(memory_handler.router)
app.include_router(chat_handler.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
