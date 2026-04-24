from threading import Lock

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings


_model: SentenceTransformer | None = None
_model_lock = Lock()


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(get_settings().embedding_model)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.empty((0, 0), dtype="float32")

    vectors = get_embedding_model().encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vectors.astype("float32")
