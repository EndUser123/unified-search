"""
Tests for search_knowledge package __init__.py

Verifies T-002 acceptance criteria:
- `from search_knowledge import search` works
- `search()` returns SearchResults object
- All key classes exported in __all__
"""

import sys


def test_import_search_function():
    """Test that search function can be imported."""
    from search_knowledge import search
    assert callable(search), "search should be a callable function"


def test_search_returns_search_results():
    """Test that search() returns SearchResults object."""
    from search_knowledge import search, SearchResults
    results = search("test query")
    assert isinstance(results, SearchResults), f"Expected SearchResults, got {type(results)}"


def test_search_results_has_query():
    """Test that SearchResults contains the query."""
    from search_knowledge import search
    results = search("test query")
    assert results.query == "test query", f"Expected query='test query', got '{results.query}'"


def test_search_results_has_hits_list():
    """Test that SearchResults has hits attribute (list)."""
    from search_knowledge import search
    results = search("test query")
    assert hasattr(results, 'hits'), "SearchResults should have 'hits' attribute"
    assert isinstance(results.hits, list), f"Expected hits to be list, got {type(results.hits)}"


def test_all_exports_defined():
    """Test that __all__ contains all expected exports."""
    import search_knowledge
    expected_exports = [
        "search",
        "EnhancedUnifiedSearchRouter",
        "CHSSearch",
        "CKS",
        "SearchResults",
        "SearchResult",
        "__version__",
    ]
    assert hasattr(search_knowledge, '__all__'), "Module should have __all__ defined"
    for export in expected_exports:
        assert export in search_knowledge.__all__, f"'{export}' should be in __all__"


def test_all_exports_are_importable():
    """Test that all items in __all__ can actually be imported."""
    import search_knowledge
    for export in search_knowledge.__all__:
        assert hasattr(search_knowledge, export), f"'{export}' in __all__ but not importable from module"


def test_version_defined():
    """Test that __version__ is defined."""
    import search_knowledge
    assert hasattr(search_knowledge, '__version__'), "Module should have __version__"
    assert isinstance(search_knowledge.__version__, str), "__version__ should be a string"


def test_key_classes_exported():
    """Test that all key classes are exported and can be imported."""
    from search_knowledge import (
        EnhancedUnifiedSearchRouter,
        CHSSearch,
        CKS,
        SearchResults,
        SearchResult,
    )
    assert EnhancedUnifiedSearchRouter is not None
    assert CHSSearch is not None
    assert CKS is not None
    assert SearchResults is not None
    assert SearchResult is not None


def test_search_result_class():
    """Test that SearchResult class can be instantiated."""
    from search_knowledge import SearchResult
    result = SearchResult(score=0.95, title="Test", content="Content")
    assert result.score == 0.95
    assert result.title == "Test"
    assert result.content == "Content"


def test_enhanced_router_search_method():
    """Test that EnhancedUnifiedSearchRouter has search method."""
    from search_knowledge import EnhancedUnifiedSearchRouter
    router = EnhancedUnifiedSearchRouter()
    assert hasattr(router, 'search'), "Router should have search method"
    results = router.search("query")
    assert hasattr(results, 'hits'), "Results should have hits attribute"
