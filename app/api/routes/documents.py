from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.database import get_db
from app.models.document import Document
from app.schemas.document import DocumentRead
from app.services.storage import (
    DocumentTooLargeError,
    EmptyDocumentError,
    UnsupportedDocumentError,
    save_upload,
)
from app.tasks.documents import process_document


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Document:
    try:
        stored_filename, file_size_bytes, extension = save_upload(file)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (DocumentTooLargeError, EmptyDocumentError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = Document(
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        content_type=file.content_type or "application/octet-stream",
        file_extension=extension,
        file_size_bytes=file_size_bytes,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    process_document.delay(document.id)
    return document


@router.get("", response_model=list[DocumentRead])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    documents = db.execute(select(Document).order_by(Document.created_at.desc())).scalars().all()
    return list(documents)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document
