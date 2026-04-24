from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Smart Document Q&A API", alias="APP_NAME")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    database_url: str = Field(
        default="postgresql+psycopg://smartdoc:smartdoc@db:5432/smart_document",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://redis:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="redis://redis:6379/1",
        alias="CELERY_RESULT_BACKEND",
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_timeout_seconds: int = Field(default=45, alias="OPENAI_TIMEOUT_SECONDS")

    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL",
    )

    data_dir: Path = Field(default=Path("data"), alias="DATA_DIR")
    max_upload_bytes: int = Field(default=15 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    chunk_target_chars: int = Field(default=900, alias="CHUNK_TARGET_CHARS")
    chunk_overlap_chars: int = Field(default=180, alias="CHUNK_OVERLAP_CHARS")
    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")
    retrieval_per_document_k: int = Field(default=3, alias="RETRIEVAL_PER_DOCUMENT_K")
    retrieval_min_score: float = Field(default=0.28, alias="RETRIEVAL_MIN_SCORE")
    qa_max_context_chars: int = Field(default=6000, alias="QA_MAX_CONTEXT_CHARS")
    question_history_messages: int = Field(default=6, alias="QUESTION_HISTORY_MESSAGES")

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def vector_dir(self) -> Path:
        return self.data_dir / "vectors"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.vector_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
