from fastapi import FastAPI

from app.config import Settings
from app.handlers import critic_handler, safety_handler

settings = Settings()

app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION)

app.include_router(safety_handler.router)
app.include_router(critic_handler.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
