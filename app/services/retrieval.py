import re
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.conversation import Message
from app.models.document import Document, DocumentChunk
from app.models.enums import MessageRole
from app.services.embeddings import embed_texts
from app.services.vector_store import DocumentVectorStore


@dataclass(slots=True)
class RetrievedChunk:
    document: Document
    chunk: DocumentChunk
    score: float


def build_retrieval_query(history_messages: Sequence[Message], question: str) -> str:
    is_follow_up = len(question.split()) < 12 or bool(
        re.search(r"\b(it|they|them|this|that|those|these|its|their)\b", question, re.IGNORECASE),
    )
    if not is_follow_up:
        return question

    prior_questions = [
        message.content
        for message in history_messages
        if message.role == MessageRole.USER
    ]
    relevant_history = prior_questions[-2:]
    if not relevant_history:
        return question
    return "\n".join([*relevant_history, question])


def retrieve_relevant_chunks(
    db: Session,
    documents: Sequence[Document],
    query: str,
) -> list[RetrievedChunk]:
    settings = get_settings()
    if not documents:
        return []

    query_embedding = embed_texts([query])[0]
    store = DocumentVectorStore(settings.vector_dir)

    score_by_chunk_id: dict[str, float] = {}
    for document in documents:
        matches = store.search(document.id, query_embedding, settings.retrieval_per_document_k)
        for match in matches:
            current_score = score_by_chunk_id.get(match.chunk_id)
            if current_score is None or match.score > current_score:
                score_by_chunk_id[match.chunk_id] = match.score

    if not score_by_chunk_id:
        return []

    chunk_ids = list(score_by_chunk_id)
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.id.in_(chunk_ids)),
    ).all()

    chunk_map: dict[str, tuple[DocumentChunk, Document]] = {
        chunk.id: (chunk, document)
        for chunk, document in rows
    }

    ordered_matches = sorted(score_by_chunk_id.items(), key=lambda item: item[1], reverse=True)
    results: list[RetrievedChunk] = []

    for chunk_id, score in ordered_matches[: settings.retrieval_top_k]:
        chunk_and_document = chunk_map.get(chunk_id)
        if chunk_and_document is None:
            continue
        chunk, document = chunk_and_document
        results.append(RetrievedChunk(document=document, chunk=chunk, score=score))

    return results
