"""Tests for CHS embeddings module with graceful fallback."""

import sys
import warnings
from unittest.mock import Mock, patch

import numpy as np
import pytest

# Mock Windows modules before importing embeddings
sys.modules["win32file"] = Mock()
sys.modules["win32pipe"] = Mock()

from search_knowledge.knowledge.chs.embeddings import (
    EmbeddingClient,
    bytes_to_vector,
    cosine_similarity,
    get_embed_client,
    reset_embed_client,
    validate_embedding_array,
    validate_embedding_blob,
)


class TestEmbeddingClient:
    """Test EmbeddingClient with graceful fallback."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_embed_client()

    def test_singleton_pattern(self):
        """Test that get_embed_client returns singleton instance."""
        client1 = get_embed_client()
        client2 = get_embed_client()
        assert client1 is client2

    def test_reset_singleton(self):
        """Test that reset_embed_client creates new instance."""
        client1 = get_embed_client()
        reset_embed_client()
        client2 = get_embed_client()
        assert client1 is not client2

    @patch("search_knowledge.knowledge.chs.embeddings.platform.system")
    def test_is_available_returns_false_on_non_windows(self, mock_system):
        """Test that is_available returns False on non-Windows platforms."""
        mock_system.return_value = "Linux"
        client = EmbeddingClient()
        assert not client.is_available()

    @patch("search_knowledge.knowledge.chs.embeddings.platform.system")
    def test_is_available_detects_pipe_unavailable(self, mock_system):
        """Test that is_available detects when pipe is unavailable."""
        mock_system.return_value = "Windows"

        # Mock CreateFile to raise an error
        with patch.object(sys.modules["win32file"], "CreateFile", side_effect=Exception("Pipe not found")):
            client = EmbeddingClient()
            assert not client.is_available()

    @patch("search_knowledge.knowledge.chs.embeddings.platform.system")
    def test_is_available_caches_result(self, mock_system):
        """Test that is_available caches the result."""
        mock_system.return_value = "Windows"

        # Mock CreateFile to raise an error
        with patch.object(sys.modules["win32file"], "CreateFile", side_effect=Exception("Pipe not found")):
            client = EmbeddingClient()

            # First call
            assert not client.is_available()

            # Second call should use cache (no additional import attempts)
            assert not client.is_available()

    @patch("search_knowledge.knowledge.chs.embeddings.platform.system")
    def test_embed_texts_returns_none_when_unavailable(self, mock_system):
        """Test that embed_texts returns None when service is unavailable."""
        mock_system.return_value = "Linux"

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Suppress the warning for this test
            client = EmbeddingClient()
            result = client.embed_texts(["test query"])

            assert result is None

    @patch("search_knowledge.knowledge.chs.embeddings.platform.system")
    def test_embed_texts_issues_warning_once(self, mock_system):
        """Test that embed_texts issues warning only once per session."""
        mock_system.return_value = "Linux"

        # Reset the global warning flag directly
        import search_knowledge.knowledge.chs.embeddings as emb_module
        emb_module._fallback_warning_issued = False

        client = EmbeddingClient()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # First call should issue warning
            client.embed_texts(["test"])
            # Check if warning was issued
            warning_messages = [str(warning.message) for warning in w]
            assert any("Semantic embedding service unavailable" in msg for msg in warning_messages), f"No warning found in: {warning_messages}"
            assert any("FTS5 keyword-only search" in msg for msg in warning_messages), f"Expected FTS5 message in: {warning_messages}"

            # Second call should not issue warning (same count)
            client.embed_texts(["test"])
            assert len(w) == len(warning_messages), f"Expected {len(warning_messages)} warnings, got {len(w)}"  # No new warnings

    @patch("search_knowledge.knowledge.chs.embeddings.platform.system")
    def test_embed_texts_handles_exception_gracefully(self, mock_system):
        """Test that embed_texts returns None on exception (graceful degradation)."""
        mock_system.return_value = "Windows"

        # Mock CreateFile to return a handle but then ReadFile to fail
        mock_handle = Mock()
        sys.modules["win32file"].CreateFile = Mock(return_value=mock_handle)
        sys.modules["win32file"].ReadFile = Mock(side_effect=Exception("Read failed"))
        sys.modules["win32file"].WriteFile = Mock(return_value=None)
        sys.modules["win32file"].CloseHandle = Mock(return_value=None)

        client = EmbeddingClient()
        # Force availability to True to test the exception path
        client._available = True

        result = client.embed_texts(["test query"])

        # Should return None on exception (graceful fallback)
        assert result is None

        # Availability should be updated to False after failure
        assert not client.is_available()


class TestUtilityFunctions:
    """Test utility functions."""

    def test_validate_embedding_blob_correct(self):
        """Test validation of correct embedding blob."""
        # Create a 384-dim embedding
        embedding = np.zeros(384, dtype=np.float32)
        blob = embedding.tobytes()

        # Should not raise
        validate_embedding_blob(blob, 384)

    def test_validate_embedding_blob_incorrect_size(self):
        """Test validation fails for incorrect blob size."""
        # Create a 256-dim embedding (wrong size)
        embedding = np.zeros(256, dtype=np.float32)
        blob = embedding.tobytes()

        with pytest.raises(ValueError, match="Embedding size mismatch"):
            validate_embedding_blob(blob, 384)

    def test_validate_embedding_array_correct(self):
        """Test validation of correct embedding array."""
        embedding = np.zeros(384, dtype=np.float32)

        # Should not raise
        validate_embedding_array(embedding, 384)

    def test_validate_embedding_array_wrong_shape(self):
        """Test validation fails for wrong shape."""
        embedding = np.zeros(256, dtype=np.float32)

        with pytest.raises(ValueError, match="Embedding shape mismatch"):
            validate_embedding_array(embedding, 384)

    def test_validate_embedding_array_wrong_dtype(self):
        """Test validation fails for wrong dtype."""
        embedding = np.zeros(384, dtype=np.float64)

        with pytest.raises(ValueError, match="dtype must be float32"):
            validate_embedding_array(embedding, 384)

    def test_bytes_to_vector(self):
        """Test conversion from bytes to vector."""
        # Create test vector
        original = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        blob = original.tobytes()

        # Convert back
        result = bytes_to_vector(blob, 4)

        assert result.shape == (4,)
        assert np.array_equal(result, original)

    def test_cosine_similarity_identical(self):
        """Test cosine similarity of identical vectors."""
        vec = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        similarity = cosine_similarity(vec, vec)

        assert similarity == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity of orthogonal vectors."""
        vec1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        similarity = cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector."""
        vec1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        similarity = cosine_similarity(vec1, vec2)

        assert similarity == 0.0
