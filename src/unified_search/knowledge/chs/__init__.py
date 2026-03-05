"""CHS (Chat History Search) knowledge system.

Provides semantic search over chat history with graceful fallback
to FTS5-only search when the semantic embedding service is unavailable.
"""

from .embeddings import (
    EmbeddingClient,
    bytes_to_vector,
    cosine_similarity,
    get_embed_client,
    reset_embed_client,
    validate_embedding_array,
    validate_embedding_blob,
)

__all__ = [
    "EmbeddingClient",
    "bytes_to_vector",
    "cosine_similarity",
    "get_embed_client",
    "reset_embed_client",
    "validate_embedding_array",
    "validate_embedding_blob",
]
