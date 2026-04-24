from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnswerStatus, MessageRole, MessageStatus
from app.schemas.document import DocumentRead


class CitationRead(BaseModel):
    document_id: str
    original_filename: str
    page_number: int | None
    chunk_index: int
    score: float
    excerpt: str


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: MessageRole
    status: MessageStatus
    answer_status: AnswerStatus | None
    content: str
    citations: list[CitationRead] = Field(default_factory=list)
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str | None = None
    document_ids: list[str] = Field(default_factory=list)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    documents: list[DocumentRead]
    messages: list[MessageRead]
    created_at: datetime
    updated_at: datetime


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    document_ids: list[str] = Field(default_factory=list)


class AskQuestionResponse(BaseModel):
    conversation_id: str
    answer_status: AnswerStatus
    searched_document_ids: list[str] = Field(default_factory=list)
    pending_document_ids: list[str] = Field(default_factory=list)
    user_message: MessageRead
    assistant_message: MessageRead
    citations: list[CitationRead] = Field(default_factory=list)
