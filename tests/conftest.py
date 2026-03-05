"""Pytest configuration and fixtures for search-knowledge package tests.

This module provides shared fixtures for testing the search-knowledge package,
including temporary database paths, mock daemon clients, sample search results,
and configured router instances.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from search_knowledge import EnhancedUnifiedSearchRouter, SearchResult


@pytest.fixture
def temp_db_path(tmp_path):
    """Temporary database path for tests.

    Uses pytest's tmp_path fixture to create a temporary file path
    that can be used for SQLite databases during testing.

    Args:
        tmp_path: Pytest's built-in temporary directory fixture

    Returns:
        Path object pointing to a temporary database file location
    """
    return tmp_path / "test.db"


@pytest.fixture
def mock_daemon_client():
    """Mock daemon client for embedding services.

    Provides a mock EmbeddingClient that simulates the semantic daemon
    behavior without requiring actual named pipe connections.

    Returns:
        Mock object with is_available and embed_texts methods configured
        to return values indicating service unavailability (graceful fallback)
    """
    mock_client = Mock()
    # Simulate service unavailable (graceful degradation to FTS5)
    mock_client.is_available.return_value = False
    # Return None to trigger FTS5-only search behavior
    mock_client.embed_texts.return_value = None
    return mock_client


@pytest.fixture
def sample_search_results():
    """Sample search results for testing.

    Provides a list of SearchResult objects representing typical
    search results from various backends (cds, grep, chs, etc.).

    Returns:
        List of SearchResult objects with diverse backend types and scores
    """
    return [
        SearchResult(
            score=0.9,
            title="Test Result 1",
            content="This is a test snippet from CDS backend",
            metadata={"backend": "cds", "path": "/path/to/file1.py", "line": 10}
        ),
        SearchResult(
            score=0.8,
            title="Test Result 2",
            content="Another test snippet from Grep backend",
            metadata={"backend": "grep", "path": "/path/to/file2.py", "line": 20}
        ),
        SearchResult(
            score=0.7,
            title="Test Result 3",
            content="Semantic search result from CHS backend",
            metadata={"backend": "chs", "path": "/path/to/file3.py", "line": 30}
        ),
        SearchResult(
            score=0.6,
            title="Test Result 4",
            content="Documentation search result",
            metadata={"backend": "docs", "path": "/docs/readme.md", "line": 1}
        ),
    ]


@pytest.fixture
def router_with_backends(temp_db_path):
    """Router instance with configured test backends.

    Creates an EnhancedUnifiedSearchRouter configured for testing
    with minimal dependencies, using temporary paths and test backends.

    Args:
        temp_db_path: Fixture providing temporary database path

    Returns:
        EnhancedUnifiedSearchRouter instance configured for testing
    """
    router = EnhancedUnifiedSearchRouter()
    # Configure for testing with minimal dependencies
    # The router can be further customized in individual tests
    return router
