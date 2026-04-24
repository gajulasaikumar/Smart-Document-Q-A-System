import re
from dataclasses import dataclass
from typing import Sequence

from openai import OpenAI
from openai import OpenAIError

from app.core.config import get_settings
from app.models.conversation import Message
from app.models.document import Document
from app.models.enums import AnswerStatus, MessageStatus
from app.schemas.conversation import CitationRead
from app.services.retrieval import RetrievedChunk, build_retrieval_query, retrieve_relevant_chunks


SYSTEM_PROMPT = """You answer questions about uploaded business documents.

Rules:
- Use only the provided context.
- If the context does not clearly answer the question, say that the answer is not available in the uploaded documents.
- Do not invent facts, numbers, dates, or policy details.
- Keep the answer concise and cite supporting snippets inline like [1], [2].
- If the user asks a follow-up, rely on the conversation history only to resolve references. The factual answer must still come from the context excerpts.
"""

NOT_FOUND_MESSAGE = (
    "I couldn't find enough support in the uploaded documents to answer that confidently."
)
UNAVAILABLE_MESSAGE = (
    "The answering service is temporarily unavailable right now. Please try the question again shortly."
)


@dataclass(slots=True)
class AnswerResult:
    answer_text: str
    answer_status: AnswerStatus
    message_status: MessageStatus
    citations: list[CitationRead]
    retrieval_query: str


def generate_answer(
    *,
    question: str,
    history_messages: Sequence[Message],
    documents: Sequence[Document],
    db_session,
) -> AnswerResult:
    settings = get_settings()
    retrieval_query = build_retrieval_query(history_messages, question)
    retrieved_chunks = retrieve_relevant_chunks(db_session, documents, retrieval_query)

    if not retrieved_chunks or retrieved_chunks[0].score < settings.retrieval_min_score:
        return AnswerResult(
            answer_text=NOT_FOUND_MESSAGE,
            answer_status=AnswerStatus.NOT_FOUND,
            message_status=MessageStatus.COMPLETED,
            citations=[],
            retrieval_query=retrieval_query,
        )

    context_text, citations = _build_context(retrieved_chunks, settings.qa_max_context_chars)
    history_text = _format_history(history_messages[-settings.question_history_messages :])

    try:
        answer = _call_openai(question=question, history_text=history_text, context_text=context_text)
    except (OpenAIError, RuntimeError):
        return AnswerResult(
            answer_text=UNAVAILABLE_MESSAGE,
            answer_status=AnswerStatus.UNAVAILABLE,
            message_status=MessageStatus.ERROR,
            citations=citations,
            retrieval_query=retrieval_query,
        )

    normalized_answer = answer.strip()
    answer_status = (
        AnswerStatus.NOT_FOUND
        if not normalized_answer or _looks_like_not_found(normalized_answer)
        else AnswerStatus.ANSWERED
    )

    return AnswerResult(
        answer_text=normalized_answer or NOT_FOUND_MESSAGE,
        answer_status=answer_status,
        message_status=MessageStatus.COMPLETED,
        citations=citations,
        retrieval_query=retrieval_query,
    )


def _call_openai(*, question: str, history_text: str, context_text: str) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    prompt = f"""Conversation history:
{history_text or "No prior conversation."}

Context excerpts:
{context_text}

Question:
{question}
"""

    response = client.responses.create(
        model=settings.openai_model,
        instructions=SYSTEM_PROMPT,
        input=prompt,
        max_output_tokens=500,
    )
    return response.output_text or ""


def _format_history(history_messages: Sequence[Message]) -> str:
    if not history_messages:
        return ""
    return "\n".join(f"{message.role.value}: {message.content}" for message in history_messages)


def _build_context(
    retrieved_chunks: Sequence[RetrievedChunk],
    max_chars: int,
) -> tuple[str, list[CitationRead]]:
    sections: list[str] = []
    citations: list[CitationRead] = []
    current_size = 0

    for index, item in enumerate(retrieved_chunks, start=1):
        excerpt = item.chunk.text.strip()
        label = item.document.original_filename
        if item.chunk.page_number is not None:
            label = f"{label}, page {item.chunk.page_number}"
        section = f"[{index}] {label}\n{excerpt}"
        if sections and current_size + len(section) > max_chars:
            break

        sections.append(section)
        current_size += len(section)
        citations.append(
            CitationRead(
                document_id=item.document.id,
                original_filename=item.document.original_filename,
                page_number=item.chunk.page_number,
                chunk_index=item.chunk.chunk_index,
                score=round(item.score, 4),
                excerpt=excerpt[:500],
            ),
        )

    return "\n\n".join(sections), citations


def _looks_like_not_found(answer: str) -> bool:
    return bool(
        re.search(
            r"(not available in the uploaded documents|couldn't find enough support|not in the provided context)",
            answer,
            re.IGNORECASE,
        ),
    )
