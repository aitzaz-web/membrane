"""Local embedding model."""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np


DEFAULT_MODEL = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_model_name() -> str:
    return os.environ.get("MEMBRANE_EMBED_MODEL", DEFAULT_MODEL)


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_model_name())


def embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.array([])
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32)


def embed_text(text: str) -> np.ndarray:
    return embed_texts([text])[0]
