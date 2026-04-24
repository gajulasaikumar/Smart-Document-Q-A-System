from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    content_type: str
    file_extension: str
    file_size_bytes: int
    status: DocumentStatus
    progress: int
    page_count: int
    chunk_count: int
    error_message: str | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime
