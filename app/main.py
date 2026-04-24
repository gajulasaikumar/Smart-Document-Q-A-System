from fastapi import FastAPI

from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": settings.app_name,
        "docs_url": "/docs",
        "health_url": "/health",
    }


app.include_router(health_router)
app.include_router(documents_router, prefix=settings.api_v1_prefix)
app.include_router(conversations_router, prefix=settings.api_v1_prefix)
