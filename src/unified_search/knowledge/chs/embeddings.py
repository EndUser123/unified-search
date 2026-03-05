"""Embeddings integration for CHS with graceful fallback.

Provides wrapper classes for embedding generation via the semantic daemon
named pipe client with automatic fallback to FTS5-only search when the
service is unavailable.

Usage:
    from search_knowledge.knowledge.chs.embeddings import get_embed_client

    client = get_embed_client()
    embeddings = client.embed_texts(["hello world", "test"])
    # Returns None if service unavailable (graceful degradation)
"""
from __future__ import annotations

import logging
import platform
import warnings
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Default embedding dimension for sentence-transformers/all-MiniLM-L6-v2
DEFAULT_EMBEDDING_DIM = 384

# Track whether we've issued the fallback warning
_fallback_warning_issued = False


class EmbeddingClient:
    """Wrapper class for semantic daemon with graceful fallback.

    This class provides embedding generation functionality with automatic
    detection of named pipe availability. When the semantic daemon is
    unavailable, embed_texts() returns None to enable FTS5-only search.

    Attributes:
        _available: Cached availability check result
        _pipe_name: Name of the named pipe to connect to
    """

    def __init__(self, pipe_name: str = "csf_semantic"):
        """Initialize EmbeddingClient.

        Args:
            pipe_name: Name of the semantic daemon named pipe
        """
        self._available: bool | None = None
        self._pipe_name = pipe_name

    def is_available(self) -> bool:
        """Check if the semantic embedding service is available.

        Tests named pipe connectivity and caches the result to avoid
        repeated connection attempts.

        Returns:
            True if the named pipe service is available, False otherwise
        """
        # Return cached result if available
        if self._available is not None:
            return self._available

        # Only Windows supports named pipes
        if platform.system() != "Windows":
            logger.debug("Semantic embedding service only available on Windows")
            self._available = False
            return False

        # Try to connect to the named pipe
        try:
            import win32file
            import win32pipe

            pipe_path = rf"\\.\pipe\{self._pipe_name}"

            # Try to open the pipe with minimal timeout
            # This will fail if the pipe doesn't exist or no instances are available
            handle = win32file.CreateFile(
                pipe_path,
                win32file.GENERIC_READ,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )

            # If we got here, the pipe is available
            win32file.CloseHandle(handle)
            self._available = True
            logger.debug(f"Semantic embedding service available: {pipe_path}")
            return True

        except Exception as e:
            # Pipe not available - cache the result
            logger.debug(f"Semantic embedding service unavailable: {e}")
            self._available = False
            return False

    def embed_texts(self, texts: list[str]) -> list[bytes] | None:
        """Generate embeddings for a list of texts.

        Attempts to use the semantic daemon for embedding generation.
        Returns None if the service is unavailable, enabling graceful
        fallback to FTS5-only search.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors as bytes (serialized numpy arrays),
            or None if the service is unavailable
        """
        global _fallback_warning_issued

        # Check service availability
        if not self.is_available():
            # Issue warning once per session
            if not _fallback_warning_issued:
                warnings.warn(
                    "Semantic embedding service unavailable. CHS will use FTS5 "
                    "keyword-only search. Install semantic daemon for hybrid search.",
                    UserWarning,
                    stacklevel=2
                )
                _fallback_warning_issued = True
            return None

        # Try to connect and generate embeddings
        try:
            import struct
            import win32file

            pipe_path = rf"\\.\pipe\{self._pipe_name}"

            # Connect to pipe
            handle = win32file.CreateFile(
                pipe_path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )

            # Build request
            request = {
                "action": "embed_texts",
                "texts": texts
            }
            request_data = __import__("json").dumps(request).encode("utf-8")
            message = struct.pack("<I", len(request_data)) + request_data

            # Send request
            win32file.WriteFile(handle, message)

            # Read response (length-prefixed)
            result_data = win32file.ReadFile(handle, 4096)
            if len(result_data) < 4:
                return None

            response_length = struct.unpack("<I", result_data[:4])[0]
            response_bytes = result_data[4:4 + response_length]
            response = __import__("json").loads(response_bytes.decode("utf-8"))

            win32file.CloseHandle(handle)

            # Check response status
            if response.get("status") == "success":
                embeddings = response.get("embeddings", [])
                if embeddings:
                    # Convert from lists to bytes
                    result = []
                    for emb in embeddings:
                        arr = np.array(emb, dtype=np.float32)
                        result.append(arr.tobytes())
                    return result
                else:
                    return None
            else:
                logger.warning(f"Embed service returned error: {response.get('error')}")
                return None

        except Exception as e:
            logger.debug(f"Failed to generate embeddings: {e}")
            # Update availability cache on failure
            self._available = False
            return None


def validate_embedding_blob(blob: bytes, expected_dim: int) -> None:
    """Validate an embedding blob has the correct dimensions.

    Args:
        blob: Embedding as bytes (serialized numpy array)
        expected_dim: Expected embedding dimension

    Raises:
        ValueError: If blob size doesn't match expected dimension
    """
    expected_size = expected_dim * 4  # float32 = 4 bytes
    actual_size = len(blob)

    if actual_size != expected_size:
        raise ValueError(
            f"Embedding size mismatch: expected {expected_size} bytes "
            f"({expected_dim} * 4 bytes/float32), got {actual_size} bytes"
        )


def validate_embedding_array(array: np.ndarray, expected_dim: int) -> None:
    """Validate an embedding array has correct shape and dtype.

    Args:
        array: Embedding as numpy array
        expected_dim: Expected embedding dimension

    Raises:
        ValueError: If array shape or dtype is incorrect
    """
    if array.shape != (expected_dim,):
        raise ValueError(
            f"Embedding shape mismatch: expected ({expected_dim},), got {array.shape}"
        )

    if array.dtype != np.float32:
        raise ValueError(
            f"Embedding dtype must be float32, got {array.dtype}"
        )


def bytes_to_vector(blob: bytes, dim: int) -> np.ndarray:
    """Convert embedding blob bytes to numpy array.

    Args:
        blob: Embedding as bytes (serialized numpy array)
        dim: Expected embedding dimension

    Returns:
        Numpy array of shape (dim,) with dtype float32
    """
    return np.frombuffer(blob, dtype=np.float32, count=dim)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec_a: First vector (numpy array)
        vec_b: Second vector (numpy array)

    Returns:
        Cosine similarity score between 0.0 and 1.0
        Returns 0.0 if either vector is a zero vector
    """
    # Handle zero vectors
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    # Calculate cosine similarity
    dot_product = np.dot(vec_a, vec_b)
    similarity = dot_product / (norm_a * norm_b)

    return float(similarity)


# Singleton instance
_embed_client_singleton: EmbeddingClient | None = None


def get_embed_client() -> EmbeddingClient:
    """Get the singleton EmbeddingClient instance.

    Creates a new EmbeddingClient on first call, returns cached instance
    on subsequent calls.

    Returns:
        The singleton EmbeddingClient instance
    """
    global _embed_client_singleton

    if _embed_client_singleton is None:
        _embed_client_singleton = EmbeddingClient()

    return _embed_client_singleton


def reset_embed_client() -> None:
    """Reset the singleton EmbeddingClient instance.

    This is primarily for testing purposes.
    """
    global _embed_client_singleton
    _embed_client_singleton = None
