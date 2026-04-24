from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import delete

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.document import Document, DocumentChunk
from app.models.enums import DocumentStatus
from app.services.chunking import build_chunks
from app.services.document_parser import ExtractedBlock, parse_document
from app.services.embeddings import embed_texts
from app.services.storage import get_upload_path
from app.services.vector_store import DocumentVectorStore


logger = get_task_logger(__name__)


@celery_app.task(name="app.tasks.documents.process_document")
def process_document(document_id: str) -> None:
    settings = get_settings()
    vector_store = DocumentVectorStore(settings.vector_dir)
    db = SessionLocal()

    try:
        document = db.get(Document, document_id)
        if document is None:
            logger.warning("Document %s was not found for processing.", document_id)
            return

        document.status = DocumentStatus.PROCESSING
        document.progress = 5
        document.error_message = None
        db.commit()

        file_path = get_upload_path(document.stored_filename)
        extracted_blocks = parse_document(file_path, document.file_extension)
        document.progress = 30
        document.page_count = _estimate_page_count(extracted_blocks)
        db.commit()

        chunks = build_chunks(
            extracted_blocks,
            target_chars=settings.chunk_target_chars,
            overlap_chars=settings.chunk_overlap_chars,
        )
        if not chunks:
            raise ValueError("No chunks were generated from the document text.")

        document.progress = 55
        db.commit()

        embeddings = embed_texts([chunk.text for chunk in chunks])
        document.progress = 80
        db.commit()

        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        chunk_rows: list[DocumentChunk] = []
        for index, chunk in enumerate(chunks):
            row = DocumentChunk(
                document_id=document_id,
                chunk_index=index,
                vector_position=index,
                page_number=chunk.page_number,
                character_count=len(chunk.text),
                text=chunk.text,
            )
            db.add(row)
            chunk_rows.append(row)

        db.flush()
        vector_store.write(document_id, embeddings, [row.id for row in chunk_rows])

        document.status = DocumentStatus.READY
        document.progress = 100
        document.chunk_count = len(chunk_rows)
        document.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Document %s processed successfully.", document_id)
    except Exception as exc:
        logger.exception("Failed to process document %s", document_id)
        db.rollback()
        vector_store.delete(document_id)

        document = db.get(Document, document_id)
        if document is not None:
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            document.status = DocumentStatus.FAILED
            document.progress = 100
            document.chunk_count = 0
            document.error_message = str(exc)
            document.processed_at = None
            db.commit()
        raise
    finally:
        db.close()


def _estimate_page_count(blocks: list[ExtractedBlock]) -> int:
    page_numbers = {block.page_number for block in blocks if block.page_number is not None}
    return len(page_numbers) if page_numbers else 1
