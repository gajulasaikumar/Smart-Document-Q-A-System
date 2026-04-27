from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="Smart Document Q&A API",
        routes=app.routes,
    )

    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation.get("responses", {}).pop("422", None)

    components = openapi_schema.get("components", {}).get("schemas", {})
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


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
