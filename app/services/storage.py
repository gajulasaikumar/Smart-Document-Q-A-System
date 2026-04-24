import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings


ALLOWED_EXTENSIONS = {".pdf", ".docx"}


class StorageError(Exception):
    """Base error for upload storage failures."""


class UnsupportedDocumentError(StorageError):
    """Raised when an unsupported file type is uploaded."""


class DocumentTooLargeError(StorageError):
    """Raised when an uploaded document exceeds the configured size limit."""


class EmptyDocumentError(StorageError):
    """Raised when the upload stream is empty."""


def save_upload(upload: UploadFile) -> tuple[str, int, str]:
    settings = get_settings()
    original_name = upload.filename or ""
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedDocumentError("Only PDF and DOCX files are supported.")

    stored_filename = f"{uuid.uuid4()}{extension}"
    destination = settings.upload_dir / stored_filename

    total_bytes = 0
    chunk_size = 1024 * 1024

    with destination.open("wb") as buffer:
        while True:
            chunk = upload.file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > settings.max_upload_bytes:
                buffer.close()
                destination.unlink(missing_ok=True)
                raise DocumentTooLargeError(
                    f"Document exceeds the {settings.max_upload_bytes} byte upload limit.",
                )
            buffer.write(chunk)

    if total_bytes == 0:
        destination.unlink(missing_ok=True)
        raise EmptyDocumentError("The uploaded document is empty.")

    return stored_filename, total_bytes, extension


def get_upload_path(stored_filename: str) -> Path:
    return get_settings().upload_dir / stored_filename
