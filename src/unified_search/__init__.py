"""
Search Knowledge Package

A unified search interface combining CHS (Code Health System) and CKS (Code Knowledge System)
search capabilities with enhanced routing and result processing.

Simple Usage:
    >>> from search_knowledge import search
    >>> results = search("query string")
    >>> for hit in results.hits:
    ...     print(f"{hit.score}: {hit.title}")

Advanced Usage:
    >>> from search_knowledge import EnhancedUnifiedSearchRouter
    >>> router = EnhancedUnifiedSearchRouter()
    >>> results = router.search("query string", system="chs")
"""

__version__ = "0.5.0"

# Import the enhanced router from the knowledge.search module
# This is a temporary re-export until search_knowledge/router.py is fully implemented
from unified_search.router import EnhancedUnifiedSearchRouter

# These imports will be functional once the modules are implemented
# from .router import EnhancedUnifiedSearchRouter
# from .knowledge.chs import CHSSearch
# from .knowledge.cks import CKS
# from .models import SearchResults, SearchResult

# Query intent detection (functional - requires intent_classifier.py from T-003)
# TODO: Enable once intent_classifier.py is fully implemented
# from .query_intent import (
#     QueryIntentDetector,
#     QueryIntent,
#     IntentType,
#     IntentDetection,
#     IntentClassification,
#     classify_query_intent,
#     get_intent_description,
# )

# Stub classes for now - will be replaced by actual implementations
class CHSSearch:
    """CHS (Code Health System) search interface."""
    pass


class CKS:
    """CKS (Code Knowledge System) search interface."""
    pass


class SearchResults:
    """Container for search results."""
    def __init__(self, hits, query, metadata=None):
        self.hits = hits
        self.query = query
        self.metadata = metadata or {}


class SearchResult:
    """Individual search result."""
    def __init__(self, score, title, content, metadata=None):
        self.score = score
        self.title = title
        self.content = content
        self.metadata = metadata or {}


def search(query: str, backend=None, **kwargs):
    """
    Simple search interface for querying knowledge systems.

    Args:
        query: Search query string
        backend: Filter to specific backend(s) (singular or list). If None, searches all backends.
        **kwargs: Additional search parameters (limit, system, etc.)

    Returns:
        SearchResults object containing matching hits

    Example:
        >>> results = search("function authentication")
        >>> print(f"Found {len(results.hits)} results")
        >>> results = search("async patterns", backend=["chs", "cks"])
    """
    router = EnhancedUnifiedSearchRouter()

    # Map user-friendly 'backend' parameter to router's 'backends' parameter
    if backend is not None:
        # Convert single backend string to list
        if isinstance(backend, str):
            backend = [backend]
        kwargs['backends'] = backend

    # Get results from router (returns list)
    hits = router.search(query, **kwargs)

    # Wrap in SearchResults object for consistent API
    return SearchResults(hits=hits, query=query)


__all__ = [
    "search",
    "EnhancedUnifiedSearchRouter",
    "CHSSearch",
    "CKS",
    "SearchResults",
    "SearchResult",
    "__version__",
    # Query intent detection (temporarily disabled)
    # "QueryIntentDetector",
    # "QueryIntent",
    # "IntentType",
    # "IntentDetection",
    # "IntentClassification",
    # "classify_query_intent",
    # "get_intent_description",
]
