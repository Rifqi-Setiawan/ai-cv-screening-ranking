"""Embedding generator for candidate profile chunks using MiniLM on CPU."""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

from src.infrastructure.config import settings
from src.infrastructure.logging import logger

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model {settings.EMBEDDING_MODEL} on CPU...")
        _model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")
        logger.info("Embedding model loaded successfully.")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    # MiniLM max tokens is 128, texts are passed per bullet / chunk
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    return embeddings.tolist()
