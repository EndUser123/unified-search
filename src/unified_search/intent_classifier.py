"""Unified Intent Classifier for search-knowledge package.

Embedding-based semantic classification using sentence-transformers.
Fast (~10ms), local, handles word variations automatically.

This is a self-contained module copied from __csf to resolve package dependencies.

Usage:
    from unified_search.intent_classifier import classify_intent

    intent = classify_intent("I need to search for files")
    # Returns: "search"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

# Type alias for intent categories
IntentCategory = Literal[
    "search",
    "read",
    "write",
    "analyze",
    "research",
    "code",
    "test",
    "git",
    "web",
    "existence_claim",
    "other",
]

# Category descriptions with examples for embedding
# These are encoded once and cached
_CATEGORY_DESCRIPTIONS = {
    "search": (
        "search find locate where which searching searches finder locator "
        "look for seek hunt query find discover"
    ),
    "read": (
        "read view show display open check reading viewing "
        "inspect examine examine file look at show me"
    ),
    "write": (
        "write create add insert append writing creation "
        "make generate produce author draft compose"
    ),
    "analyze": (
        "analyze examine investigate audit inspect review analysis "
        "study assess evaluate check diagnose debug"
    ),
    "research": (
        "research look up find information documentation docs "
        "investigate online web search gather"
    ),
    "code": (
        "code implement refactor optimize fix programming "
        "develop engineer function method class variable"
    ),
    "test": (
        "test verify validate assert check testing "
        "specification requirement confirm ensure"
    ),
    "git": (
        "git commit push pull branch merge checkout "
        "version control repository vcs history"
    ),
    "web": (
        "web internet online url website http https "
        "fetch download scrape external api"
    ),
    "existence_claim": (
        "missing absent not found unavailable doesn't exist does not exist "
        "no such cannot find unable locate not available not installed "
        "skill missing file missing command not found is missing are missing "
        "couldn't find unable to find no file no skill no command"
    ),
    "other": "other miscellaneous general catch-all",
}

# Cache directory for embeddings - use package-local cache
_CACHE_DIR = Path(__file__).parent.parent / ".cache" / "embeddings"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_EMBEDDINGS_CACHE_FILE = _CACHE_DIR / "category_embeddings.json"


def _load_or_compute_embeddings() -> dict[str, list[float]]:
    """Load cached embeddings or compute and cache them.

    Returns:
        Dictionary mapping category names to embedding vectors.
    """
    # Try to load from cache
    if _EMBEDDINGS_CACHE_FILE.exists():
        with open(_EMBEDDINGS_CACHE_FILE, encoding='utf-8') as f:
            return json.load(f)

    # Compute embeddings (model loaded here for initial cache generation)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")

    embeddings = {
        category: model.encode(description).tolist()
        for category, description in _CATEGORY_DESCRIPTIONS.items()
    }

    # Cache for future use
    with open(_EMBEDDINGS_CACHE_FILE, "w", encoding='utf-8') as f:
        json.dump(embeddings, f)

    return embeddings


# Load embeddings at module import
_CATEGORY_EMBEDDINGS = _load_or_compute_embeddings()

# Global model reference (lazy-loaded in classify_intent)
_MODEL = None


def _get_model():
    """Get or lazy-load the SentenceTransformer model.

    Returns:
        SentenceTransformer model instance (cached after first load).
    """
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def classify_intent(text: str) -> IntentCategory:
    """Classify text into intent category using embedding similarity.

    Args:
        text: Input text to classify (prompt, tool input, etc.)

    Returns:
        Intent category (search, read, write, analyze, research, code, test, git, web, other).

    Performance:
        ~10ms per classification on CPU after initial model load (~200ms first call).
    """
    import numpy as np

    # Get cached model (lazy-loaded on first call)
    model = _get_model()
    text_embedding = model.encode(text)

    # Compute cosine similarity with each category
    similarities = {}
    for category, category_embedding in _CATEGORY_EMBEDDINGS.items():
        # Cosine similarity: dot product of normalized vectors
        similarity = np.dot(text_embedding, category_embedding) / (
            np.linalg.norm(text_embedding) * np.linalg.norm(category_embedding)
        )
        similarities[category] = similarity

    # Return category with highest similarity
    return max(similarities, key=similarities.get)


__all__ = ["classify_intent", "IntentCategory"]
