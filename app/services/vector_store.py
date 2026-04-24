import json
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np


@dataclass(slots=True)
class VectorMatch:
    chunk_id: str
    score: float
    position: int


class DocumentVectorStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write(self, document_id: str, embeddings: np.ndarray, chunk_ids: list[str]) -> None:
        if embeddings.size == 0:
            raise ValueError("Cannot build a FAISS index from empty embeddings.")
        if len(chunk_ids) != len(embeddings):
            raise ValueError("Chunk id count must match embedding count.")

        index = faiss.IndexFlatIP(int(embeddings.shape[1]))
        index.add(embeddings)

        faiss.write_index(index, str(self._index_path(document_id)))
        self._metadata_path(document_id).write_text(
            json.dumps({"chunk_ids": chunk_ids}, indent=2),
            encoding="utf-8",
        )

    def search(self, document_id: str, query_embedding: np.ndarray, top_k: int) -> list[VectorMatch]:
        index_path = self._index_path(document_id)
        metadata_path = self._metadata_path(document_id)
        if not index_path.exists() or not metadata_path.exists():
            return []

        index = faiss.read_index(str(index_path))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        chunk_ids: list[str] = metadata["chunk_ids"]

        scores, positions = index.search(query_embedding.reshape(1, -1).astype("float32"), top_k)
        matches: list[VectorMatch] = []

        for score, position in zip(scores[0], positions[0], strict=False):
            if position == -1:
                continue
            matches.append(
                VectorMatch(
                    chunk_id=chunk_ids[position],
                    score=float(score),
                    position=int(position),
                ),
            )
        return matches

    def delete(self, document_id: str) -> None:
        self._index_path(document_id).unlink(missing_ok=True)
        self._metadata_path(document_id).unlink(missing_ok=True)

    def _index_path(self, document_id: str) -> Path:
        return self.base_dir / f"{document_id}.faiss"

    def _metadata_path(self, document_id: str) -> Path:
        return self.base_dir / f"{document_id}.json"
