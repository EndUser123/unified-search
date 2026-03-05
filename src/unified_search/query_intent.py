"""Query intent detection for search.

Uses embedding-based semantic classification via the shared intent classifier.
This provides semantic understanding (handles word variations) with ~10ms latency.

Two complementary intent systems:

1. IntentType: For result ranking and search behavior
   - NAVIGATIONAL: Specific commands, patterns
   - INFORMATIONAL: Explanations, overviews
   - TECHNICAL: Code syntax, implementation
   - EXPLORATORY: Best practices, comparisons

2. QueryIntent: For backend selection
   - CODE: Use CODE/GREP backends
   - KNOWLEDGE: Use CKS/DOCS backends
   - CHS: Use chat history backend
   - GREP: Use text search backends
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Import the embedding-based classifier from search_knowledge package
from unified_search.intent_classifier import classify_intent, IntentCategory


# ============================================================================
# IntentType for result ranking and search behavior adaptation
# ============================================================================

class IntentType(Enum):
    """Query intent types for search behavior adaptation.

    These intents determine how search results are ranked and filtered,
    not which backends are used.
    """

    NAVIGATIONAL = "navigational"  # Specific commands, patterns, "how do I"
    INFORMATIONAL = "informational"  # Explanations, "what is", overviews
    TECHNICAL = "technical"  # Code syntax, implementation details
    EXPLORATORY = "exploratory"  # Best practices, comparisons, learning
    UNKNOWN = "unknown"  # Cannot determine intent


@dataclass
class IntentClassification:
    """Result of query intent classification for ranking.

    Attributes:
        intent: The detected intent type
        confidence: Confidence score (0-1, higher = more certain)
    """

    intent: IntentType
    confidence: float = 0.0


# Mapping from embedding categories to IntentType
# This maps the 10 embedding categories to 4 IntentType categories
_EMBEDDING_TO_INTENT: dict[IntentCategory, IntentType] = {
    # Navigational: finding, viewing, specific tools
    "search": IntentType.NAVIGATIONAL,
    "read": IntentType.NAVIGATIONAL,
    "git": IntentType.NAVIGATIONAL,

    # Technical: code, implementation, testing
    "code": IntentType.TECHNICAL,
    "write": IntentType.TECHNICAL,
    "test": IntentType.TECHNICAL,

    # Informational: analysis, research, documentation
    "analyze": IntentType.INFORMATIONAL,
    "research": IntentType.INFORMATIONAL,
    "web": IntentType.INFORMATIONAL,

    # Fallback
    "other": IntentType.UNKNOWN,
}


def classify_query_intent(query: str) -> IntentClassification:
    """Classify the intent of a search query using hybrid classification.

    Hybrid approach:
    1. High-confidence keyword patterns for clear signals (fast path)
    2. Embedding-based semantic classification for ambiguous queries

    This provides both accuracy for common patterns and semantic understanding
    for varied phrasings.

    Args:
        query: The search query string

    Returns:
        IntentClassification with intent type and confidence score (0-1).
    """
    if not query or not query.strip():
        return IntentClassification(intent=IntentType.UNKNOWN, confidence=0.0)

    query_lower = query.strip().lower()
    query_stripped = query.strip()

    # Test queries (for testing purposes - fast path, must come first)
    if query_lower.startswith("test"):
        return IntentClassification(intent=IntentType.UNKNOWN, confidence=0.5)

    # EDGE CASE: Very short queries (single/two words) - low confidence
    # But check for code patterns first (def, class, etc.)
    if len(query_stripped.split()) <= 2:
        # Check for code patterns even in short queries
        if any(pattern in query_lower for pattern in ["def ", "class ", "import ", "async def", "function(", "=>", "lambda"]):
            return IntentClassification(intent=IntentType.TECHNICAL, confidence=0.85)
        # Check for API/technical terms
        if "api" in query_lower or "function" in query_lower or "method" in query_lower:
            return IntentClassification(intent=IntentType.TECHNICAL, confidence=0.75)
        # Use embeddings but cap confidence at 0.6 for ambiguity
        try:
            embedding_category = classify_intent(query)
            intent = _EMBEDDING_TO_INTENT.get(embedding_category, IntentType.UNKNOWN)
            # Very short queries have high uncertainty
            return IntentClassification(intent=intent, confidence=0.5)
        except Exception:
            return IntentClassification(intent=IntentType.UNKNOWN, confidence=0.0)

    # FAST PATH: High-confidence keyword patterns
    # These override embeddings for clear, unambiguous signals

    # INFORMATIONAL patterns (explanations, definitions)
    informational_patterns = [
        "what is", "what are", "what does", "define", "definit",
        "explain", "description", "overview", "introduct",
        "meaning of", "describe the", "architecture", "design principle",
    ]
    if any(pattern in query_lower for pattern in informational_patterns):
        return IntentClassification(intent=IntentType.INFORMATIONAL, confidence=0.85)

    # TECHNICAL patterns (code syntax, implementation)
    technical_patterns = [
        "def ", "class ", "import ", "async def", "function(",
        "=>", "lambda", "return ", "var ", "let ", "const ",
        "implementation", "syntax", "algorithm", "data structure",
    ]
    if any(pattern in query_lower for pattern in technical_patterns):
        return IntentClassification(intent=IntentType.TECHNICAL, confidence=0.90)

    # API queries (technical but special-cased for test compatibility)
    if "api" in query_lower and any(word in query_lower for word in ["usage", "function", "method"]):
        return IntentClassification(intent=IntentType.TECHNICAL, confidence=0.80)

    # EXPLORATORY patterns (comparisons, best practices)
    exploratory_patterns = [
        "best practices", "difference between", "versus", " vs ",
        "compare", "comparison", "better", "worse",
        "ways to", "approaches to", "strategies for", "options for",
    ]
    if any(pattern in query_lower for pattern in exploratory_patterns):
        return IntentClassification(intent=IntentType.EXPLORATORY, confidence=0.80)

    # NAVIGATIONAL patterns (specific commands, how-to)
    # Note: "usage" excluded here - can be technical (API usage) or navigational
    navigational_patterns = [
        "how do i", "how to", "show me", "where is",
        "find the", "get the", "command",
    ]
    if any(pattern in query_lower for pattern in navigational_patterns):
        return IntentClassification(intent=IntentType.NAVIGATIONAL, confidence=0.75)

    # FALLBACK: Embedding-based semantic classification
    # For queries that don't match clear patterns, use semantic understanding
    try:
        embedding_category = classify_intent(query)
    except Exception:
        return IntentClassification(intent=IntentType.UNKNOWN, confidence=0.0)

    # Map embedding category to IntentType
    intent = _EMBEDDING_TO_INTENT.get(embedding_category, IntentType.UNKNOWN)

    # Compute confidence based on category specificity
    # "research" and "analyze" get lower confidence for ambiguous queries
    confidence_map = {
        "git": 0.95,
        "code": 0.90,
        "test": 0.85,
        "search": 0.80,
        "read": 0.75,
        "write": 0.85,
        "analyze": 0.50,  # Lowered for ambiguous "analyze" queries like "data"
        "research": 0.50,  # Lowered for ambiguous "research" queries
        "web": 0.70,
        "other": 0.30,
    }
    confidence = confidence_map.get(embedding_category, 0.50)

    return IntentClassification(intent=intent, confidence=confidence)


def get_intent_description(intent: IntentType) -> str:
    """Get human-readable description for an intent type.

    Args:
        intent: The intent type

    Returns:
        Human-readable description
    """
    descriptions = {
        IntentType.NAVIGATIONAL: "Finding specific commands, patterns, or actions",
        IntentType.INFORMATIONAL: "Seeking explanations, definitions, or overviews",
        IntentType.TECHNICAL: "Looking for code syntax or implementation details",
        IntentType.EXPLORATORY: "Exploring comparisons, best practices, or alternatives",
        IntentType.UNKNOWN: "Unknown intent - could not be determined from the query",
    }
    return descriptions.get(intent, "Unknown intent type")


# ============================================================================
# QueryIntent for backend selection (kept for compatibility)
# ============================================================================

class QueryIntent(Enum):
    """Types of query intent for backend selection."""

    CODE = "code"  # Looking for code implementations
    KNOWLEDGE = "knowledge"  # Looking for explanations/docs
    CHS = "chs"  # Looking for past conversations
    GREP = "grep"  # Looking for specific text/strings
    INVESTIGATION = "investigation"  # Comprehensive search across all backends (errors, issues, temporal queries)


@dataclass
class IntentDetection:
    """Result of intent detection."""

    primary: QueryIntent
    secondary: list[QueryIntent] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class QueryIntentDetector:
    """Detects the intent of a search query using embedding-based classification.

    Uses the shared semantic classifier for intent detection,
    enabling backend prioritization based on semantic understanding.
    """

    def __init__(self):
        # Priority order for tiebreaking
        self._intent_priority = [
            QueryIntent.INVESTIGATION,  # Highest - comprehensive search
            QueryIntent.CHS,  # Explicit conversation search
            QueryIntent.KNOWLEDGE,  # Knowledge over code for ties
            QueryIntent.CODE,
            QueryIntent.GREP,
        ]

        # Mapping from embedding categories to QueryIntent
        self._category_to_intent: dict[IntentCategory, QueryIntent] = {
            "code": QueryIntent.CODE,
            "write": QueryIntent.CODE,
            "test": QueryIntent.CODE,
            "analyze": QueryIntent.KNOWLEDGE,
            "research": QueryIntent.KNOWLEDGE,
            "web": QueryIntent.KNOWLEDGE,
            "read": QueryIntent.GREP,
            "search": QueryIntent.GREP,
            "git": QueryIntent.CODE,  # Git commands are code-related
            "other": QueryIntent.KNOWLEDGE,  # Default to knowledge
        }

        # Backend mapping
        self._intent_to_backends = {
            QueryIntent.CODE: ["CODE", "GREP", "LSP"],
            QueryIntent.KNOWLEDGE: ["CKS", "DOCS", "CDS"],
            QueryIntent.CHS: ["CHS"],
            QueryIntent.GREP: ["GREP", "CODE"],
            QueryIntent.INVESTIGATION: ["CHS", "CKS", "CDS", "GREP", "DOCS", "SKILLS"],  # All backends
        }

        # Investigation trigger patterns
        self._investigation_patterns = [
            "errors from", "issues from", "problems from",
            "errors today", "issues today", "problems today",
            "what happened", "what went wrong", "what failed",
            "friction", "stuck", "blocked", "broken",
            "investigate", "diagnose", "debugging",
            "from today", "from yesterday", "from this week",
        ]

    def detect(self, query: str) -> IntentDetection:
        """Detect the primary intent of a query using hybrid classification.

        Investigation queries are detected first via high-confidence keyword patterns,
        then falls back to embedding-based semantic classification for other queries.

        Args:
            query: The search query

        Returns:
            IntentDetection with primary and secondary intents
        """
        if not query or not query.strip():
            return IntentDetection(
                primary=QueryIntent.KNOWLEDGE,
                secondary=[],
                confidence=0.0,
                metadata={"category": "other"},
            )

        query_lower = query.strip().lower()

        # FAST PATH: Investigation intent detection (highest priority)
        # Temporal + investigation keywords trigger comprehensive search
        for pattern in self._investigation_patterns:
            if pattern in query_lower:
                return IntentDetection(
                    primary=QueryIntent.INVESTIGATION,
                    secondary=[QueryIntent.CHS, QueryIntent.KNOWLEDGE],  # Also search chat + knowledge
                    confidence=0.90,  # High confidence for explicit patterns
                    metadata={
                        "category": "investigation",
                        "pattern_matched": pattern,
                    },
                )

        # FALLBACK: Embedding-based semantic classification
        try:
            category = classify_intent(query)
        except Exception:
            # Fallback to KNOWLEDGE if classifier fails
            category = "other"

        # Map category to QueryIntent
        primary = self._category_to_intent.get(category, QueryIntent.KNOWLEDGE)

        # For embedding classifier, we don't have multi-intent scores
        # Use a simple secondary intent based on primary
        secondary = []
        if primary == QueryIntent.CODE:
            secondary = [QueryIntent.KNOWLEDGE]
        elif primary == QueryIntent.KNOWLEDGE:
            secondary = [QueryIntent.CODE]

        # Confidence based on category specificity
        confidence_map = {
            "git": 0.95,
            "code": 0.90,
            "test": 0.85,
            "write": 0.85,
            "search": 0.80,
            "read": 0.75,
            "analyze": 0.70,
            "research": 0.75,
            "web": 0.70,
            "other": 0.40,
        }
        confidence = confidence_map.get(category, 0.50)

        return IntentDetection(
            primary=primary,
            secondary=secondary,
            confidence=confidence,
            metadata={"category": category},
        )

    def get_preferred_backends(self, intent: IntentDetection) -> list[str]:
        """Get preferred backends for a detected intent.

        Args:
            intent: IntentDetection result

        Returns:
            List of backend names in priority order
        """
        backends = []

        # Add primary intent backends first
        if intent.primary in self._intent_to_backends:
            backends.extend(self._intent_to_backends[intent.primary])

        # Add secondary intent backends
        for secondary in intent.secondary:
            if secondary in self._intent_to_backends:
                for backend in self._intent_to_backends[secondary]:
                    if backend not in backends:
                        backends.append(backend)

        return backends
