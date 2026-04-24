from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.models.document import Document
from app.models.enums import DocumentStatus, MessageRole
from app.schemas.conversation import (
    AskQuestionRequest,
    AskQuestionResponse,
    ConversationCreate,
    ConversationRead,
)
from app.services.qa import generate_answer


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
) -> Conversation:
    documents = _load_documents(db, payload.document_ids)
    conversation = Conversation(title=payload.title)
    conversation.documents.extend(documents)
    db.add(conversation)
    db.commit()
    return _load_conversation(db, conversation.id)


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> Conversation:
    return _load_conversation(db, conversation_id)


@router.post("/{conversation_id}/messages", response_model=AskQuestionResponse)
def ask_question(
    conversation_id: str,
    payload: AskQuestionRequest,
    db: Session = Depends(get_db),
) -> AskQuestionResponse:
    conversation = _load_conversation(db, conversation_id)
    history_messages = list(conversation.messages)

    if payload.document_ids:
        additional_documents = _load_documents(db, payload.document_ids)
        existing_ids = {document.id for document in conversation.documents}
        for document in additional_documents:
            if document.id not in existing_ids:
                conversation.documents.append(document)
        db.commit()
        conversation = _load_conversation(db, conversation_id)

    ready_documents = [
        document
        for document in conversation.documents
        if document.status == DocumentStatus.READY
    ]
    pending_document_ids = [
        document.id
        for document in conversation.documents
        if document.status != DocumentStatus.READY
    ]
    if not ready_documents:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No attached documents are ready yet. Upload a document or wait for processing to finish.",
        )

    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=payload.question,
        citations=[],
        message_metadata={
            "ready_document_ids": [document.id for document in ready_documents],
            "pending_document_ids": pending_document_ids,
        },
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    answer = generate_answer(
        question=payload.question,
        history_messages=history_messages,
        documents=ready_documents,
        db_session=db,
    )

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        status=answer.message_status,
        answer_status=answer.answer_status,
        content=answer.answer_text,
        citations=[citation.model_dump() for citation in answer.citations],
        message_metadata={
            "ready_document_ids": [document.id for document in ready_documents],
            "pending_document_ids": pending_document_ids,
            "retrieval_query": answer.retrieval_query,
        },
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return AskQuestionResponse(
        conversation_id=conversation.id,
        answer_status=answer.answer_status,
        searched_document_ids=[document.id for document in ready_documents],
        pending_document_ids=pending_document_ids,
        user_message=user_message,
        assistant_message=assistant_message,
        citations=answer.citations,
    )


def _load_documents(db: Session, document_ids: list[str]) -> list[Document]:
    if not document_ids:
        return []

    documents = db.execute(
        select(Document).where(Document.id.in_(document_ids)),
    ).scalars().all()
    found_ids = {document.id for document in documents}
    missing_ids = sorted(set(document_ids) - found_ids)
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document(s) not found: {', '.join(missing_ids)}",
        )
    return list(documents)


def _load_conversation(db: Session, conversation_id: str) -> Conversation:
    conversation = db.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.documents),
            selectinload(Conversation.messages),
        )
        .where(Conversation.id == conversation_id),
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conversation
