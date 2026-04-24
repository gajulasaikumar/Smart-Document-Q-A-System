import re
from dataclasses import dataclass
from typing import Iterable

from app.services.document_parser import ExtractedBlock


@dataclass(slots=True)
class ChunkPayload:
    text: str
    page_number: int | None


def build_chunks(
    blocks: list[ExtractedBlock],
    target_chars: int,
    overlap_chars: int,
) -> list[ChunkPayload]:
    units = list(_iter_units(blocks, max_unit_chars=target_chars))
    if not units:
        return []

    chunks: list[ChunkPayload] = []
    current_units: list[tuple[str, int | None]] = []
    current_length = 0

    for text, page_number in units:
        candidate_length = current_length + len(text) + 1
        if current_units and candidate_length > target_chars:
            chunks.append(_finalize_chunk(current_units))
            current_units = _tail_overlap(current_units, overlap_chars)
            current_length = sum(len(unit_text) + 1 for unit_text, _ in current_units)
        current_units.append((text, page_number))
        current_length += len(text) + 1

    if current_units:
        chunks.append(_finalize_chunk(current_units))

    return _deduplicate_chunks(chunks)


def _iter_units(
    blocks: Iterable[ExtractedBlock],
    max_unit_chars: int,
) -> Iterable[tuple[str, int | None]]:
    for block in blocks:
        for sentence in _split_sentences(block.text):
            if len(sentence) <= max_unit_chars:
                yield sentence, block.page_number
                continue
            yield from _split_long_sentence(sentence, block.page_number, max_unit_chars)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _split_long_sentence(
    sentence: str,
    page_number: int | None,
    max_unit_chars: int,
) -> Iterable[tuple[str, int | None]]:
    words = sentence.split()
    current_words: list[str] = []
    current_length = 0

    for word in words:
        projected = current_length + len(word) + 1
        if current_words and projected > max_unit_chars:
            yield " ".join(current_words), page_number
            current_words = [word]
            current_length = len(word)
        else:
            current_words.append(word)
            current_length = projected

    if current_words:
        yield " ".join(current_words), page_number


def _tail_overlap(
    units: list[tuple[str, int | None]],
    overlap_chars: int,
) -> list[tuple[str, int | None]]:
    overlap: list[tuple[str, int | None]] = []
    total = 0

    for text, page_number in reversed(units):
        overlap.append((text, page_number))
        total += len(text) + 1
        if total >= overlap_chars:
            break

    overlap.reverse()
    return overlap


def _finalize_chunk(units: list[tuple[str, int | None]]) -> ChunkPayload:
    text = " ".join(part for part, _ in units).strip()
    page_number = next((page for _, page in units if page is not None), None)
    return ChunkPayload(text=text, page_number=page_number)


def _deduplicate_chunks(chunks: list[ChunkPayload]) -> list[ChunkPayload]:
    deduplicated: list[ChunkPayload] = []
    seen: set[str] = set()

    for chunk in chunks:
        normalized = chunk.text.strip()
        if not normalized or normalized in seen:
            continue
        deduplicated.append(ChunkPayload(text=normalized, page_number=chunk.page_number))
        seen.add(normalized)

    return deduplicated
