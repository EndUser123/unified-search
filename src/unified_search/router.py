"""
Enhanced Unified Search Router

Integrates all search optimization components:
- Streaming search (async parallel execution)
- Query caching (LRU with TTL)
- Hybrid scoring (BM25 + cosine combination)
- Result deduplication (cross-backend)
- Fuzzy matching (typo tolerance)
- Backend health tracking

Backends:
- CHS: Chat History Search (semantic search on conversations)
- CKS: Constitutional Knowledge System (knowledge base)
- CDS: Code Documentation Search (AST-based docstring search)
- Grep: Code Pattern Search (AST-based function/class search)
- Docs: Documentation folder search (markdown files)
- FTS5: SQLite FTS5 fast keyword search
- SKILLS: Skills and Commands progressive disclosure search
- RLM: Recursive Language Model (code generation search)
"""

from __future__ import annotations

import asyncio
import inspect
import threading
import time as time_module
from collections.abc import AsyncIterator
from pathlib import Path
from queue import Queue
from typing import Any

from unified_search.backend_health import BackendHealthRegistry
from unified_search.backends.cds_backend import CDSBackend as ASTCDSBackend
from unified_search.backends.cks_metadata_backend import (
    BACKEND_CKS_METADATA,
    CKSMetadataBackend,
    create_cks_metadata_backend,
)
from unified_search.backends.code_backend import CodeBackend
from unified_search.backends.dedup import ResultDeduplicator
from unified_search.backends.fuzzy_matcher import FuzzyMatcher
from unified_search.backends.grep_backend import GrepBackend as ASTGrepBackend
from unified_search.backends.hybrid_scorer import HybridScorer
from unified_search.backends.skills_backend import SkillsBackend
from unified_search.cache import QueryCache
from unified_search.diversity import mmr_rerank
from unified_search.query_intent import (
    IntentClassification,
    IntentType,
    QueryIntentDetector,
    classify_query_intent,
)
from unified_search.reranking.cross_encoder import CrossEncoderReranker
from unified_search.sanitizer import sanitize_query

# Confidence calibration imports
try:
    from unified_search.confidence_calibration import (
        ConfidenceCalibrator,
        SourceTrustScorer,
        calibrate_with_confidence,
    )
    CONFIDENCE_CALIBRATION_AVAILABLE = True
except ImportError:
    CONFIDENCE_CALIBRATION_AVAILABLE = False
    SourceTrustScorer = None  # type: ignore[assignment]
    ConfidenceCalibrator = None  # type: ignore[assignment]
    calibrate_with_confidence = None  # type: ignore[assignment]

# Faceted filtering imports
try:
    from unified_search.faceted import filter_results, get_facets
    FACETED_FILTERING_AVAILABLE = True
except ImportError:
    FACETED_FILTERING_AVAILABLE = False
    filter_results = None  # type: ignore[assignment]
    get_facets = None  # type: ignore[assignment]

# Unified reranking imports (CKS RRF, Temporal Boosting)
try:
    from unified_search.reranking.cks_reranking_adapter import CKSRerankingAdapter
    from unified_search.reranking.temporal_boosting import TemporalBoostFilter
    RERANKING_AVAILABLE = True
except ImportError:
    RERANKING_AVAILABLE = False
    CKSRerankingAdapter = None  # type: ignore[assignment]
    TemporalBoostFilter = None  # type: ignore[assignment]

# Tree-sitter multi-language backend (preferred over AST)
MULTILANG_BACKEND_AVAILABLE = False
MultiLangCodeBackend = None
BACKEND_MULTILANG = "MULTILANG"

try:
    from unified_search.backends.multilang_backend import (
        _TREE_SITTER_AVAILABLE,
        BACKEND_MULTILANG,
        MultiLangCodeBackend,
    )

    MULTILANG_BACKEND_AVAILABLE = _TREE_SITTER_AVAILABLE
except ImportError:
    # Tree-sitter not installed - will use AST fallback
    pass
except Exception:
    # Tree-sitter init failed - will use AST fallback
    pass

# LSP Symbol backend (language-aware code search)
LSP_BACKEND_AVAILABLE = False
LSPSymbolBackend = None
BACKEND_LSP = "LSP"

try:
    from unified_search.backends.lsp_backend import (
        BACKEND_LSP_SYMBOL as BACKEND_LSP_CONSTANT,
    )
    from unified_search.backends.lsp_backend import (
        LSPSymbolBackend,
    )

    # Use the constant from the module
    BACKEND_LSP = BACKEND_LSP_CONSTANT
    LSP_BACKEND_AVAILABLE = True
    LSPSymbolBackend = LSPSymbolBackend  # type: ignore[misc, assignment]
except ImportError:
    # LSP backend not available - will use AST fallback
    pass
except Exception:
    # LSP backend init failed - will use AST fallback
    pass


# HNSW Vector backend import (fast approximate nearest neighbor search)
HNSW_BACKEND_AVAILABLE = False
HNSWVectorBackend = None
BACKEND_HNSW = "HNSW"

try:
    from unified_search.backends.hnsw_backend import HNSWVectorBackend
    from unified_search.hnsw_index import HAS_HNSW

    HNSW_BACKEND_AVAILABLE = HAS_HNSW
except ImportError:
    # hnsw_backend not available - requires hnswlib
    pass
except Exception:
    # HNSW backend init failed - will use other backends
    pass


# Graph Analysis Backends (Call Graph, CPG, HDMA, Dependency Graph)
CALL_GRAPH_BACKEND_AVAILABLE = False
CallGraphBackend = None
BACKEND_CALL_GRAPH = "CALL_GRAPH"

try:
    from unified_search.backends.call_graph_backend import CallGraphBackend
    CALL_GRAPH_BACKEND_AVAILABLE = True
except ImportError:
    # Call graph backend not available
    pass
except Exception:
    # Call graph backend init failed
    pass


CPG_BACKEND_AVAILABLE = False
CPGBackend = None
BACKEND_CPG = "CPG"

try:
    from unified_search.backends.cpg_backend import CPGBackend
    CPG_BACKEND_AVAILABLE = True
except ImportError:
    # CPG backend not available
    pass
except Exception:
    # CPG backend init failed
    pass


HDMA_BACKEND_AVAILABLE = False
HDMABackend = None
BACKEND_HDMA = "HDMA"

try:
    from unified_search.backends.hdma_backend import HDMABackend
    HDMA_BACKEND_AVAILABLE = True
except ImportError:
    # HDMA backend not available
    pass
except Exception:
    # HDMA backend init failed
    pass


DEPENDENCY_BACKEND_AVAILABLE = False
DependencyBackend = None
BACKEND_DEPENDENCY = "DEPENDENCY"

try:
    from unified_search.backends.dependency_backend import DependencyBackend
    DEPENDENCY_BACKEND_AVAILABLE = True
except ImportError:
    # Dependency backend not available
    pass
except Exception:
    # Dependency backend init failed
    pass


# Persona Memory backend import (cognitive-spectrum + brainstorm)
from unified_search.backends.persona_memory_backend import (
    BACKEND_PERSONA,
    create_persona_backend,
)

PERSONA_BACKEND_AVAILABLE = True

# RLM backend import (local code search)
from unified_search.backends.rlm_backend import BACKEND_RLM, create_rlm_backend, is_rlm_available

RLM_BACKEND_AVAILABLE = True

# RLM Internet Research backend import (web search)
from unified_search.backends.rlm_internet_research_backend import (
    BACKEND_NAME as BACKEND_RLM_INTERNET_NAME,
)
from unified_search.backends.rlm_internet_research_backend import (
    RLMInternetResearchBackend,
)

RLM_INTERNET_BACKEND_AVAILABLE = True

# Vector manager import (optional - may not be available)
try:
    from src.cks.core.vector_manager import VectorConfig, VectorKnowledgeManager

    VECTOR_MANAGER_AVAILABLE = True
except ImportError:
    VECTOR_MANAGER_AVAILABLE = False
    VectorKnowledgeManager = None
    VectorConfig = None

# Stage-aware search import
try:
    from unified_search.stage_aware import (
        STAGE_AWARE_ENABLED,
        StageAwareContext,
        get_stage_aware_context,
    )

    STAGE_AWARE_AVAILABLE = True
except ImportError:
    STAGE_AWARE_AVAILABLE = False
    StageAwareContext = None  # type: ignore[misc, assignment]


# Backend name constants
BACKEND_CHS = "CHS"
BACKEND_CKS = "CKS"
BACKEND_CDS = "CDS"
BACKEND_GREP = "Grep"
BACKEND_DOCS = "DOCS"
BACKEND_FTS5 = "FTS5"
BACKEND_CACHE = "Cache"
BACKEND_CODE_SEMANTIC = "CODE"
BACKEND_HNSW = "HNSW"
BACKEND_SKILLS = "SKILLS"
BACKEND_RLM = BACKEND_RLM
BACKEND_RLM_INTERNET = BACKEND_RLM_INTERNET_NAME
BACKEND_PERSONA = BACKEND_PERSONA
BACKEND_CKS_METADATA = BACKEND_CKS_METADATA  # CKS metadata query backend

# Type aliases for better readability
SearchResult = dict[str, Any]
BackendMap = dict[str, Any]
TimeParams = dict[str, Any]
ConversationContext = dict[str, Any]

# Thread management constants
# Thread join timeout for cleanup (PERF-004: Thread leak fix)
# This is the maximum time to wait for daemon threads to finish cleanup
# after the backend search timeout (0.45s) has elapsed. Threads should have
# already completed their work (either successfully or timed out), so this
# is a brief wait period to allow orderly cleanup without blocking.
# Using daemon=True allows the main thread to exit even if cleanup is incomplete.
_THREAD_JOIN_TIMEOUT: float = 0.1


class HNSWTextSearchBackend:
    """
    Text-to-embedding wrapper for HNSW vector backend.

    Provides text-based search interface compatible with unified router
    by converting text queries to embeddings before searching HNSW index.
    """

    def __init__(
        self,
        root_paths: list[str] | None = None,
        dimension: int = 384,
        embedding_router: Any | None = None,
    ):
        """Initialize HNSW text search backend.

        Args:
            root_paths: Root paths for code indexing (metadata only)
            dimension: Vector dimensionality (default: 384)
            embedding_router: Optional embedding router for text-to-vector conversion
        """
        self.dimension = dimension
        self._embedding_router = embedding_router

        # Initialize HNSW backend if available
        self._hnsw_backend: Any | None = None
        if HNSW_BACKEND_AVAILABLE and HNSWVectorBackend is not None:
            try:
                self._hnsw_backend = HNSWVectorBackend(dimension=dimension)
            except Exception:
                # HNSW backend initialization failed
                pass

    def has_index(self) -> bool:
        """Check if HNSW index has been built."""
        return (
            self._hnsw_backend is not None
            and hasattr(self._hnsw_backend, "has_index")
            and self._hnsw_backend.has_index()
        )

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search HNSW index with text query.

        Args:
            query: Text query string
            limit: Maximum number of results

        Returns:
            List of search results with id, content, score, metadata
        """
        if not self.has_index():
            return []

        # Convert text query to embedding
        try:
            if self._embedding_router:
                # Use provided embedding router
                import numpy as np

                embedding = self._embedding_router.embed_query(query)
                query_vector = np.array([embedding], dtype=np.float32)
            else:
                # No embedding router available - return empty results
                return []
        except Exception:
            # Embedding generation failed
            return []

        # Search HNSW index with query vector
        try:
            results = self._hnsw_backend.search(
                query=query_vector,
                k=limit,
                threshold=0.0,
            )
        except Exception:
            # HNSW search failed
            return []

        # Normalize results to match unified router format
        normalized = []
        for r in results:
            normalized.append({
                "id": r.get("id", ""),
                "title": r.get("title", r.get("content", ""))[:80],
                "content": r.get("content", ""),
                "score": r.get("score", 0.5),
                "metadata": r.get("metadata", {}),
            })

        return normalized

    def count(self) -> int:
        """Get number of items in HNSW index."""
        if self._hnsw_backend and hasattr(self._hnsw_backend, "count"):
            return self._hnsw_backend.count
        return 0


class EnhancedUnifiedSearchRouter:
    """
    Enhanced unified search router with all optimization features.

    Features:
    - Parallel async search across all backends
    - Query result caching with TTL
    - Hybrid scoring (BM25 + cosine)
    - Cross-backend deduplication
    - Fuzzy matching fallback
    - Backend health tracking
    """

    def __init__(
        self,
        chs_backend: Any | None = None,
        cks_backend: Any | None = None,
        root_path: str | None = None,
        enable_cache: bool = True,
        enable_fuzzy: bool = True,
        cache_ttl: int = 300,
        cache_size: int = 1000,
        enable_daemon: bool = True,
        enable_stage_aware: bool | None = None,
        enable_rlm: bool = True,
        enable_rlm_internet: bool = False,
        rlm_internet_provider_configs: dict[str, Any] | None = None,
        enable_mmr: bool = False,  # Disabled by default - use only for exploratory intents
        mmr_lambda: float = 0.5,
        enable_cross_encoder: bool = False,  # Disabled by default - slow, minimal gain (ARCH-001)
        enable_index_build: bool = False,  # Disabled by default - lazy load on demand for fast startup
        enable_health_filtering: bool = False,  # Disabled by default - show all backends including "down" ones
    ) -> None:
        """Initialize the enhanced search router.

        Args:
            chs_backend: Optional CHS backend instance
            cks_backend: Optional CKS backend instance
            root_path: Root path for code indexing (default: P:/__csf/src)
            enable_cache: Enable query caching
            enable_fuzzy: Enable fuzzy matching fallback
            cache_ttl: Cache TTL in seconds
            cache_size: Max cache size
            enable_daemon: Enable semantic daemon for fast CKS/CHS searches
            enable_stage_aware: Enable stage-aware search (conversation context)
            enable_rlm: Enable RLM backend for intelligent code search
            enable_rlm_internet: Enable RLM Internet Research backend for web search
            rlm_internet_provider_configs: Provider configs for internet research (Exa, Tavily, etc.)
            enable_mmr: Enable MMR reranking for result diversity (default: False - only useful for exploratory intents)
            mmr_lambda: MMR lambda parameter (0=favor diversity, 1=favor relevance, 0.5=balanced)
            enable_cross_encoder: Enable cross-encoder reranking for relevance (default: False - slow, minimal gain)
            enable_health_filtering: Filter out backends marked as "down" by health registry (default: False - show all backends)
        """
        self._root_path: str = root_path or "P:/__csf/src"
        self._enable_cache: bool = enable_cache
        self._enable_fuzzy: bool = enable_fuzzy
        self.enable_daemon: bool = enable_daemon
        self._daemon_client: Any | None = None
        self._enable_mmr: bool = enable_mmr
        self._mmr_lambda: float = mmr_lambda
        self._backend_timeout: float = 0.45
        self._enable_health_filtering: bool = enable_health_filtering

        # Initialize optimization components
        self.cache: QueryCache = QueryCache(max_size=cache_size, ttl_seconds=cache_ttl)
        self.health: BackendHealthRegistry = BackendHealthRegistry()
        self.deduper: ResultDeduplicator = ResultDeduplicator()
        self.fuzzy_matcher: FuzzyMatcher = FuzzyMatcher(max_distance=2)
        self.hybrid_scorer: HybridScorer = HybridScorer(
            alpha=0.6
        )  # Favor BM25 slightly

        # Initialize vector manager for semantic search
        self.vector_manager: Any | None = None
        if VECTOR_MANAGER_AVAILABLE:
            try:
                from pathlib import Path as PathLib

                project_root = PathLib(__file__).parent.parent.parent.parent
                vector_path = project_root / ".data" / "qdrant_code"
                config = VectorConfig(
                    qdrant_path=str(vector_path), collection_name="code_semantic"
                )
                self.vector_manager = VectorKnowledgeManager(config=config)
            except Exception:
                # Vector manager initialization failed, continue without it
                pass

        # Initialize backends
        # Prefer MultiLangCodeBackend (tree-sitter) over AST backends
        if MULTILANG_BACKEND_AVAILABLE:
            self.multilang_backend: Any | None = MultiLangCodeBackend(
                root_paths=[self._root_path], use_tree_sitter=True
            )
            # Still create AST backends as fallback but don't build their indices yet
            self.cds_backend: Any = ASTCDSBackend(root_paths=[self._root_path])
            self.grep_backend: Any = ASTGrepBackend(root_paths=[self._root_path])
            self._use_multilang: bool = True
        else:
            self.multilang_backend: Any | None = None
            self.cds_backend: Any = ASTCDSBackend(root_paths=[self._root_path])
            self.grep_backend: Any = ASTGrepBackend(root_paths=[self._root_path])
            self._use_multilang: bool = False

        self.code_backend: CodeBackend = CodeBackend(
            vector_manager=self.vector_manager,
            embedding_router=self.vector_manager.router
            if self.vector_manager
            else None,
            search_roots=[Path(self._root_path)],
        )
        self.chs_backend: Any | None = chs_backend  # Optional external backend
        self.cks_backend: Any | None = cks_backend  # Optional external backend
        self.skills_backend: SkillsBackend = (
            SkillsBackend()
        )  # Skills and commands search

        # Initialize CKS metadata backend for Per-File Learning Tracking
        self.cks_metadata_backend: CKSMetadataBackend | None = None
        try:
            self.cks_metadata_backend = create_cks_metadata_backend()
        except Exception:
            # CKS metadata backend initialization failed, continue without it
            pass

        # Initialize RLM backend if available
        self.rlm_backend: Any | None = None
        if enable_rlm and RLM_BACKEND_AVAILABLE and is_rlm_available():
            try:
                self.rlm_backend = create_rlm_backend(
                    root_paths=[self._root_path],
                    enable_by_default=True,
                )
            except Exception:
                # RLM initialization failed, continue without it
                pass

        # Initialize RLM Internet Research backend if available
        self.rlm_internet_backend: Any | None = None
        if enable_rlm_internet and RLM_INTERNET_BACKEND_AVAILABLE:
            try:
                self.rlm_internet_backend = RLMInternetResearchBackend(
                    provider_configs=rlm_internet_provider_configs or {},
                    enable_hyde=True,
                )
            except Exception:
                # RLM internet initialization failed, continue without it
                pass

        # Initialize Persona Memory backend if available
        self.persona_backend: Any | None = None
        if PERSONA_BACKEND_AVAILABLE:
            try:
                self.persona_backend = create_persona_backend(
                    db_path=None,  # Use default path
                    enable_by_default=True,
                )
            except Exception:
                # Persona backend initialization failed, continue without it
                pass

        # Initialize LSP Symbol backend if available (language-aware code search)
        self.lsp_backend: Any | None = None
        if LSP_BACKEND_AVAILABLE:
            try:
                self.lsp_backend = LSPSymbolBackend(root_paths=[self._root_path])
            except Exception:
                # LSP backend initialization failed, continue without it
                pass

        # Initialize HNSW Vector backend if available (fast approximate nearest neighbor)
        self.hnsw_backend: Any | None = None
        if HNSW_BACKEND_AVAILABLE:
            try:
                # Get embedding router from vector_manager if available
                embedding_router = (
                    self.vector_manager.router
                    if self.vector_manager and hasattr(self.vector_manager, "router")
                    else None
                )
                self.hnsw_backend = HNSWTextSearchBackend(
                    root_paths=[self._root_path],
                    embedding_router=embedding_router,
                )
            except Exception:
                # HNSW backend initialization failed, continue without it
                pass

        # Initialize Graph Analysis Backends
        # Call Graph Backend (static call relationship analysis) - fast enough to init eagerly
        self.call_graph_backend: Any | None = None
        if CALL_GRAPH_BACKEND_AVAILABLE and CallGraphBackend is not None:
            try:
                self.call_graph_backend = CallGraphBackend(
                    root_paths=[self._root_path],
                    enable_health_tracking=True,
                )
            except Exception:
                # Call graph backend initialization failed
                pass

        # Lazy-initialize slow backends (CPG, HDMA, Dependency)
        # These backends perform heavy indexing (>20s) so load on-demand
        self._cpg_backend: Any | None = None
        self._hdma_backend: Any | None = None
        self._dependency_backend: Any | None = None

        # Initialize daemon backends if enabled
        self._daemon_cks_backend: DaemonBackend | None = None
        self._daemon_chs_backend: DaemonBackend | None = None
        if self.enable_daemon:
            self._daemon_cks_backend = DaemonBackend(backend_type="cks")
            self._daemon_chs_backend = DaemonBackend(backend_type="chs")

        # Initialize cross-encoder reranker
        self._enable_cross_encoder: bool = enable_cross_encoder
        self._cross_encoder: CrossEncoderReranker | None = (
            CrossEncoderReranker() if enable_cross_encoder else None
        )

        # Initialize CKS reranking adapter (RRF + Temporal Boosting)
        self._enable_cks_reranking: bool = True
        self._cks_reranker: Any | None = None
        self._temporal_boost: Any | None = None
        if RERANKING_AVAILABLE:
            try:
                self._cks_reranker = CKSRerankingAdapter(
                    rrf_k=60,
                    half_life_days=180,
                    max_boost=2.0,
                )
                self._temporal_boost = TemporalBoostFilter(
                    half_life_days=180,
                    min_boost=0.5,
                    max_boost=2.0,
                )
            except Exception:
                # Reranking initialization failed, continue without it
                pass

        # Initialize QueryIntentDetector for intelligent backend selection
        self._intent_detector: QueryIntentDetector | None = None
        if QueryIntentDetector is not None:
            try:
                self._intent_detector = QueryIntentDetector()
            except Exception:
                # Intent detector initialization failed, continue without it
                pass

        # Initialize confidence calibration components
        self._enable_confidence_calibration: bool = True
        self._trust_scorer: Any | None = None
        self._confidence_calibrator: Any | None = None
        if CONFIDENCE_CALIBRATION_AVAILABLE:
            try:
                self._trust_scorer = SourceTrustScorer()
                self._confidence_calibrator = ConfidenceCalibrator(
                    citation_weight=0.2,
                    trust_weight=0.8,
                    max_citation_boost=0.3,
                )
            except Exception:
                # Confidence calibration initialization failed, continue without it
                pass

        # Build indices - prefer tree-sitter, fall back to AST
        if enable_index_build:
            if self._use_multilang and self.multilang_backend:
                # Use tree-sitter (faster, multi-language)
                self.multilang_backend.build_index()
            else:
                # Use AST backends (slower, Python-only)
                self.cds_backend.build_index()
                self.grep_backend.build_index()

            # Skip CodeBackend indexing (too slow) - lazy load on demand
            # if not self.code_backend.has_index():
            #     self.code_backend.index_directory()

            # Build skills index
            self.skills_backend.build_index()

        # Initialize stage-aware search if available
        self._stage_aware_context: Any | None = None
        if STAGE_AWARE_AVAILABLE:
            if enable_stage_aware is None:
                # Default to enabled if env var not set to false
                enable_stage_aware = STAGE_AWARE_ENABLED
            if enable_stage_aware:
                self._stage_aware_context = get_stage_aware_context()
        self._enable_stage_aware: bool = (
            enable_stage_aware and self._stage_aware_context is not None
        )

    # Lazy-loading properties for slow backends (init time >20s)
    @property
    def cpg_backend(self) -> Any | None:
        """Lazy-load CPG Backend (Code Property Graph)."""
        if self._cpg_backend is None and CPG_BACKEND_AVAILABLE and CPGBackend is not None:
            try:
                self._cpg_backend = CPGBackend(
                    root_paths=[self._root_path],
                    enable_health_tracking=True,
                    language="python",
                )
            except Exception:
                pass
        return self._cpg_backend

    @property
    def hdma_backend(self) -> Any | None:
        """Lazy-load HDMA Backend (Hybrid Dual-Map Architecture)."""
        if self._hdma_backend is None and HDMA_BACKEND_AVAILABLE and HDMABackend is not None:
            try:
                self._hdma_backend = HDMABackend(
                    root_paths=[self._root_path],
                    enable_health_tracking=True,
                )
            except Exception:
                pass
        return self._hdma_backend

    @property
    def dependency_backend(self) -> Any | None:
        """Lazy-load Dependency Backend (cross-file reference analysis)."""
        if self._dependency_backend is None and DEPENDENCY_BACKEND_AVAILABLE and DependencyBackend is not None:
            try:
                self._dependency_backend = DependencyBackend(
                    root_paths=[self._root_path],
                    enable_health_tracking=True,
                )
            except Exception:
                pass
        return self._dependency_backend

    def search(
        self,
        query: str,
        limit: int = 20,
        backends: list[str] | None = None,
        use_cache: bool = True,
        conversation_context: ConversationContext | None = None,
        time_params: TimeParams | None = None,
        facet_sources: list[str] | None = None,
        facet_types: list[str] | None = None,
        facet_min_score: float | None = None,
        return_facets: bool = False,
    ) -> list[SearchResult] | dict[str, Any]:
        """
        Unified search across all backends.

        Args:
            query: Search query string
            limit: Max results to return
            backends: Optional list of backend names to search
            use_cache: Whether to use query cache
            conversation_context: Optional dict with 'messages' and 'session_age_seconds' keys
                                   for stage-aware search
            time_params: Optional dict with time filter parameters (hours_ago, after, before)
                         for CHS backend time-based filtering
            facet_sources: Optional list of sources to filter results (CKS, CODE, CHS, etc.)
            facet_types: Optional list of types to filter results (memory, pattern, code, etc.)
            facet_min_score: Optional minimum score threshold for results
            return_facets: If True, returns dict with 'results' and 'facets' keys

        Returns:
            List of search results sorted by relevance, OR dict with 'results' and 'facets' if return_facets=True.
            Results include '_stage' metadata if stage-aware is enabled.
            Results include 'confidence', 'calibrated_score', 'trust_score' if confidence calibration enabled.
        """
        if not query or not query.strip():
            return []

        query = query.strip()

        # Check cache first
        if use_cache and self._enable_cache:
            cached: list[SearchResult] | None = self.cache.get(query)
            if cached is not None:
                # Mark source as cached
                for result in cached:
                    result["_cached"] = True
                return cached[:limit]

        # Classify query intent for ranking behavior
        intent_result: IntentClassification = classify_query_intent(query)

        # Analyze conversation context if stage-aware is enabled
        stage_context: Any | None = None
        if (
            self._enable_stage_aware
            and conversation_context
            and self._stage_aware_context
        ):
            messages = conversation_context.get("messages", [])
            session_age = conversation_context.get("session_age_seconds", 0)
            stage_context = self._stage_aware_context.analyze_search(
                query=query,
                recent_messages=messages,
                session_age_seconds=session_age,
            )

        # Determine which backends to use
        backend_map: BackendMap = self._get_backend_map()

        if backends:
            # User explicitly specified backends - filter to those
            backend_map = {
                name: backend_map[name] for name in backends if name in backend_map
            }
        elif self._intent_detector:
            # Intelligent backend selection based on query intent
            try:
                intent_detection = self._intent_detector.detect(query)
                preferred_backends = self._intent_detector.get_preferred_backends(
                    intent_detection
                )
                # Filter to preferred backends that are actually available
                backend_map = {
                    name: backend_map[name]
                    for name in preferred_backends
                    if name in backend_map
                }
            except Exception:
                # Intent detection failed - fall back to all backends
                pass
        # If neither condition applied, backend_map remains as all backends

        # Execute parallel search
        results: list[SearchResult] = self._execute_parallel_search(
            backend_map, query, time_params
        )

        # Check if we have meaningful results (non-empty content)
        has_meaningful_results: bool = any(
            r.get("content") or r.get("title") for r in results
        )

        # Fallback to fuzzy matching if no meaningful results
        if not has_meaningful_results and self._enable_fuzzy and len(query) > 3:
            results = self._fuzzy_search(backend_map, query)

        # Deduplicate results
        results = self._deduplicate_results(results)

        # Simplified reranking pipeline (ARCH-001):
        # 1. CKS Reranking (RRF + Temporal) - domain-aware, high value
        # 2. Confidence Calibration - source trust weighting
        #
        # Removed from hot path:
        # - Cross-Encoder: Slow (50-150ms), minimal relevance gain
        # - MMR: Only useful for exploratory intents (use via --mmr flag)
        #
        # HybridScorer (BM25 + cosine) is applied during result fusion.

        # Apply MMR only for exploratory intents (diversity over precision)
        if self._enable_mmr and intent_result.intent == IntentType.EXPLORATORY:
            results = mmr_rerank(
                results, lambda_param=self._mmr_lambda, add_metadata=True
            )

        # Apply CKS reranking (RRF + Temporal) for domain-aware relevance
        if self._enable_cks_reranking and self._temporal_boost:
            results = self._temporal_boost.boost(results)

        # Apply confidence calibration for source trust weighting
        if self._enable_confidence_calibration and self._confidence_calibrator and self._trust_scorer:
            results = self._confidence_calibrator.calibrate_batch(
                results, self._trust_scorer
            )

        # Apply faceted filtering if requested
        if FACETED_FILTERING_AVAILABLE and filter_results:
            if facet_sources or facet_types or facet_min_score is not None:
                results = filter_results(
                    results,
                    sources=facet_sources,
                    types=facet_types,
                    min_score=facet_min_score,
                )

        # Calculate facets if requested
        facets: dict[str, dict[str, int]] | None = None
        if return_facets and FACETED_FILTERING_AVAILABLE and get_facets:
            facets = get_facets(results)

        # Cache results
        if use_cache and self._enable_cache and results:
            self.cache.set(query, results)

        # Add stage-aware metadata if available
        if stage_context:
            for result in results:
                result["_stage"] = stage_context.stage.value
                result["_has_gaps"] = stage_context.has_gaps

        # Add intent metadata to results
        for result in results:
            result["_intent"] = intent_result.intent.value
            result["_intent_confidence"] = intent_result.confidence

        return results[:limit]

    async def search_stream(
        self,
        query: str,
        backends: list[str] | None = None,
        timeout_per_backend: float = 3.0,
    ) -> AsyncIterator[SearchResult]:
        """
        Stream search results as each backend completes.

        Args:
            query: Search query string
            backends: Optional list of backend names
            timeout_per_backend: Seconds to wait per backend

        Yields:
            Search results as they arrive
        """
        if not query or not query.strip():
            return

        query = query.strip()
        backend_map: BackendMap = self._get_backend_map()

        # If backends list is explicitly provided (even empty), filter to only those backends
        # An empty list means "query no backends"
        if backends is not None:
            backend_map = {
                name: backend_map[name] for name in backends if name in backend_map
            }

        # If no backends available (either filtered out or originally empty), return early
        if not backend_map:
            return

        # Create async tasks for each backend
        async def search_backend(
            name: str, backend: Any
        ) -> tuple[str, list[SearchResult]]:
            try:
                if hasattr(backend, "search"):
                    # Handle both sync and async backends
                    search_method = backend.search
                    if inspect.iscoroutinefunction(search_method):
                        results = await search_method(query)
                    else:
                        results = search_method(query)

                    # Normalize results and add backend metadata
                    normalized: list[SearchResult] = []
                    for r in results:
                        if isinstance(r, dict):
                            r["source"] = name
                            r.setdefault("backend", name)
                            # Derive reason from backend type
                            if name == BACKEND_CKS or name == BACKEND_CHS:
                                r.setdefault("reason", "Semantic match")
                            elif name == BACKEND_SKILLS:
                                r.setdefault("reason", "Documentation match")
                            elif name == BACKEND_RLM:
                                r.setdefault("reason", "Code pattern match")
                            else:
                                r.setdefault("reason", "Match")
                            normalized.append(r)
                        else:
                            normalized.append(
                                {
                                    "source": name,
                                    "backend": name,
                                    "reason": "Match",
                                    "content": str(r),
                                    "score": 0.5,
                                }
                            )
                    return name, normalized
                else:
                    return name, []
            except Exception as e:
                # Record failure in health registry
                self.health.record_result(name, success=False, error=str(e))
                return name, [{"source": name, "error": str(e)}]

        # Run all backends in parallel
        tasks = [search_backend(name, backend) for name, backend in backend_map.items()]

        # Yield results as they complete
        for coro in asyncio.as_completed(tasks):
            name, results = await coro
            if results and not any("error" in r for r in results):
                self.health.record_result(name, success=True)
            for result in results:
                yield result

    def _get_backend_map(self) -> BackendMap:
        """Get map of available backends, filtered by health status.

        Returns:
            Dictionary mapping backend names to available backend instances.
        """
        # Start with all configured backends
        all_backends: BackendMap = {
            BACKEND_SKILLS: self.skills_backend,
        }

        # Use MultiLangCodeBackend (tree-sitter) if available, otherwise AST backends
        if self._use_multilang and self.multilang_backend:
            all_backends[BACKEND_MULTILANG] = self.multilang_backend
        else:
            all_backends[BACKEND_CDS] = self.cds_backend
            all_backends[BACKEND_GREP] = self.grep_backend

        # CodeBackend is disabled by default (too slow for startup)
        # all_backends[BACKEND_CODE_SEMANTIC] = self.code_backend

        # Add RLM backend if available
        if self.rlm_backend is not None:
            all_backends[BACKEND_RLM] = self.rlm_backend

        # Add RLM Internet Research backend if available
        if self.rlm_internet_backend is not None:
            all_backends[BACKEND_RLM_INTERNET] = self.rlm_internet_backend

        # Add Persona Memory backend if available
        if self.persona_backend is not None:
            all_backends[BACKEND_PERSONA] = self.persona_backend

        # Add LSP Symbol backend if available (language-aware code search)
        if self.lsp_backend is not None:
            all_backends[BACKEND_LSP] = self.lsp_backend

        # Add HNSW Vector backend if available (fast approximate nearest neighbor)
        if self.hnsw_backend is not None:
            all_backends[BACKEND_HNSW] = self.hnsw_backend

        # Add Graph Analysis Backends if available
        if self.call_graph_backend is not None:
            all_backends[BACKEND_CALL_GRAPH] = self.call_graph_backend
        if self.cpg_backend is not None:
            all_backends[BACKEND_CPG] = self.cpg_backend
        if self.hdma_backend is not None:
            all_backends[BACKEND_HDMA] = self.hdma_backend
        if self.dependency_backend is not None:
            all_backends[BACKEND_DEPENDENCY] = self.dependency_backend

        # Add CKS metadata backend if available (Per-File Learning Tracking)
        if self.cks_metadata_backend is not None:
            all_backends[BACKEND_CKS_METADATA] = self.cks_metadata_backend

        # Use daemon backends when enabled, otherwise use provided backends
        if self.enable_daemon:
            if self._daemon_cks_backend:
                all_backends[BACKEND_CKS] = self._daemon_cks_backend
            if self._daemon_chs_backend:
                all_backends[BACKEND_CHS] = self._daemon_chs_backend
        else:
            if self.chs_backend:
                all_backends[BACKEND_CHS] = self.chs_backend
            if self.cks_backend:
                all_backends[BACKEND_CKS] = self.cks_backend

        # Filter out backends that are marked as "down" by the health registry
        # Health filtering is opt-in for production (enable_health_filtering=True)
        # By default (False), all backends are shown - useful for development/debugging
        available_backends: BackendMap = {}
        skipped_backends: list[str] = []

        for name, backend in all_backends.items():
            if not self._enable_health_filtering or self.health.is_available(name):
                available_backends[name] = backend
            else:
                # Backend is down - track for optional logging
                skipped_backends.append(name)

        # Optionally log skipped backends with their health status
        if skipped_backends:
            for name in skipped_backends:
                status = self.health.get_status(name)
                if status:
                    # Backend is in backoff period - skip it
                    # (Logging can be added here if needed, e.g., using logger.warning)
                    pass

        return available_backends

    def _execute_parallel_search(
        self,
        backends: BackendMap,
        query: str,
        time_params: TimeParams | None = None,
    ) -> list[SearchResult]:
        """Execute parallel search using ThreadPoolExecutor.

        Args:
            backends: Dictionary mapping backend names to backend instances
            query: Search query string
            time_params: Optional dict with time filter parameters (hours_ago, after, before)
                         for CHS backend time-based filtering

        Returns:
            List of search results from all backends

        Note:
            Uses per-backend timeout (timeout=0.5) to return fast results immediately
            without waiting for slow backends to complete.
        """
        all_results: list[SearchResult] = []
        result_queue: Queue[tuple[str, list[SearchResult] | None, str | None]] = (
            Queue()
        )

        def worker(name: str, backend: Any) -> None:
            """Worker function that runs in a daemon thread."""
            try:
                results = self._search_single(name, backend, query, time_params)
                result_queue.put((name, results, None))
            except Exception as e:
                result_queue.put((name, None, str(e)))

        # Start daemon threads for each backend
        threads: list[tuple[str, threading.Thread]] = []
        for name, backend in backends.items():
            thread = threading.Thread(target=worker, args=(name, backend), daemon=True)
            thread.start()
            threads.append((name, thread))

        # Wait for results with timeout (timeout=0.5)
        start_time: float = time_module.time()
        deadline: float = start_time + self._backend_timeout
        completed_backends: set[str] = set()

        # Use small poll interval to avoid blocking on slow backends
        # This allows fast backends to return results immediately without waiting
        POLL_INTERVAL = 0.05  # 50ms polling interval

        while len(completed_backends) < len(threads) and time_module.time() < deadline:
            remaining: float = deadline - time_module.time()
            if remaining <= 0:
                break

            # Use smaller of poll interval or remaining time
            # This ensures we frequently check for timeout while collecting fast results
            get_timeout = min(POLL_INTERVAL, remaining)

            try:
                name, results, error = result_queue.get(timeout=get_timeout)
                if error:
                    self.health.record_result(name, success=False, error=error)
                else:
                    all_results.extend(results or [])
                    self.health.record_result(name, success=True)
                completed_backends.add(name)
            except Exception:
                # Queue get timed out - continue polling if deadline not reached
                # The loop condition will check deadline and exit if time is up
                continue

        # Mark timed-out backends as failed
        for name, _ in threads:
            if name not in completed_backends:
                self.health.record_result(name, success=False, error="Timeout")

        # Wait for all threads to complete (with timeout to avoid hanging)
        # This prevents thread leaks by allowing daemon threads to clean up properly
        for name, thread in threads:
            thread.join(timeout=_THREAD_JOIN_TIMEOUT)

        return all_results

    def _search_single(
        self,
        name: str,
        backend: Any,
        query: str,
        time_params: TimeParams | None = None,
    ) -> list[SearchResult]:
        """Search a single backend and normalize results.

        Args:
            name: Backend name identifier (e.g., BACKEND_CHS, BACKEND_CKS)
            backend: Backend instance to search
            query: Search query string
            time_params: Optional dict with time filter parameters (hours_ago, after, before)
                         for CHS backend time-based filtering

        Returns:
            List of normalized search results with source, content, score, and metadata

        Note:
            Handles both sync and async backends by detecting coroutine functions
            and running them in a new event loop when called from sync context.
            For CHS backend with time_params, passes parameters as kwargs to backend.search().
        """
        # Sanitize query for security (block injection patterns)
        sanitized_query: str
        is_clean: bool
        sanitized_query, is_clean = sanitize_query(query, name)
        if not is_clean:
            # Log blocked query and return empty results
            self.health.record_result(
                name, success=False, error="Query blocked by sanitizer"
            )
            return []
        query = sanitized_query

        try:
            # Check if backend.search is async
            search_method = getattr(backend, "search", None)
            if search_method and inspect.iscoroutinefunction(search_method):
                # Async backend (CodeBackend, RLMBackend) - run in new event loop
                try:
                    # Try to get existing loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Can't run async tasks in running loop from sync thread
                        # Skip this backend in this context
                        self.health.record_result(
                            name, success=False, error="Async backend in sync context"
                        )
                        return []
                except RuntimeError:
                    # No event loop exists, we can create one
                    pass

                # Run the async search in a new event loop
                results = asyncio.run(search_method(query))
            else:
                # Sync backend - call directly
                # Pass time_params to CHS backend (DaemonBackend)
                if name == BACKEND_CHS and time_params:
                    results = backend.search(query, **time_params)
                else:
                    results = backend.search(query)

            normalized: list[SearchResult] = []

            for r in results:
                if isinstance(r, dict):
                    # Normalize based on backend format
                    if name == BACKEND_MULTILANG:
                        # MultiLangCodeBackend already returns normalized format
                        # Just ensure source is set correctly
                        r["source"] = name
                        r.setdefault("backend", name)
                        r.setdefault("reason", "Code pattern match")
                        normalized.append(r)
                    elif name == BACKEND_GREP:
                        # GrepBackend format: {type, name, file, line, signature}
                        normalized.append(
                            {
                                "source": name,
                                "backend": name,
                                "reason": "AST match",
                                "title": f"{r.get('name', '')} ({r.get('type', '')})",
                                "content": r.get("signature", r.get("name", "")),
                                "score": 0.8,  # Default score for exact name matches
                                "metadata": {
                                    "file_path": r.get("file", ""),
                                    "line_number": r.get("line", 0),
                                    "type": r.get("type", "code"),
                                },
                            }
                        )
                    elif name == BACKEND_CDS:
                        # CDSBackend format: {type, name, file, line, doc}
                        normalized.append(
                            {
                                "source": name,
                                "backend": name,
                                "reason": "Documentation match",
                                "title": f"{r.get('name', '')} ({r.get('type', '')})",
                                "content": r.get("doc", r.get("name", "")),
                                "score": 0.8,
                                "metadata": {
                                    "file_path": r.get("file", ""),
                                    "line_number": r.get("line", 0),
                                    "type": r.get("type", "documentation"),
                                },
                            }
                        )
                    else:
                        # Generic format - add source, backend, and reason
                        r["source"] = name
                        r.setdefault("backend", name)
                        # Derive reason from backend type
                        if name == BACKEND_CKS:
                            r.setdefault("reason", "Semantic match")
                        elif name == BACKEND_CHS:
                            r.setdefault("reason", "Semantic match")
                        elif name == BACKEND_SKILLS:
                            r.setdefault("reason", "Documentation match")
                        elif name == BACKEND_RLM:
                            r.setdefault("reason", "Code pattern match")
                        elif name == BACKEND_RLM_INTERNET:
                            r.setdefault("reason", "Semantic match")
                        elif name == BACKEND_PERSONA:
                            r.setdefault("reason", "Semantic match")
                        elif name == BACKEND_LSP:
                            r.setdefault("reason", "Symbol-aware code match")
                        elif name == BACKEND_HNSW:
                            r.setdefault("reason", "Vector similarity match")
                        elif name == BACKEND_CALL_GRAPH:
                            r.setdefault("reason", "Call graph analysis")
                        elif name == BACKEND_CPG:
                            r.setdefault("reason", "Code property graph match")
                        elif name == BACKEND_HDMA:
                            r.setdefault("reason", "Architectural analysis")
                        elif name == BACKEND_DEPENDENCY:
                            r.setdefault("reason", "Dependency analysis")
                        else:
                            r.setdefault("reason", "Match")
                        if "score" not in r:
                            r["score"] = 0.5
                        if "title" not in r:
                            r["title"] = r.get("content", "")[:80]
                        normalized.append(r)
                else:
                    normalized.append(
                        {
                            "source": name,
                            "backend": name,
                            "reason": "Match",
                            "content": str(r),
                            "score": 0.5,
                        }
                    )

            self.health.record_result(name, success=True)
            return normalized
        except Exception as e:
            self.health.record_result(name, success=False, error=str(e))
            return []

    def _fuzzy_search(
        self,
        backends: BackendMap,
        query: str,
    ) -> list[SearchResult]:
        """Fallback fuzzy matching when no exact results.

        Args:
            backends: Dictionary mapping backend names to backend instances
            query: Original search query to find fuzzy matches for

        Returns:
            List of search results using corrected/fuzzy matched query
        """
        # Get all searchable strings from backends
        all_strings: set[str] = set()

        # Add common search terms
        for backend in backends.values():
            if hasattr(backend, "_index"):
                all_strings.update(backend._index.keys())

        # Find fuzzy matches
        matches = self.fuzzy_matcher.find_matches(query, list(all_strings))

        if matches:
            # Use the best match
            corrected_query: str = matches[0][0]
            return self._execute_parallel_search(backends, corrected_query)

        return []

    def _deduplicate_results(
        self,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Deduplicate results across backends while preserving metadata.

        Args:
            results: List of search results to deduplicate

        Returns:
            Deduplicated list of search results with metadata preserved
        """
        if not results:
            return []

        # Convert to dedup format
        dedup_input: list[dict[str, Any]] = []
        result_metadata: list[
            dict[str, Any]
        ] = []  # Track original metadata for each result
        for r in results:
            dedup_input.append(
                {
                    "file_path": r.get(
                        "file_path", r.get("metadata", {}).get("file_path", "")
                    ),
                    "line_number": r.get(
                        "line_number", r.get("metadata", {}).get("line_number", 0)
                    ),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0.5),
                    "source": r.get("source", "unknown"),
                    "title": r.get("title", ""),
                }
            )
            # Track original metadata
            result_metadata.append(
                {
                    "backend": r.get("backend", r.get("source", "unknown")),
                    "reason": r.get("reason", "Match"),
                    "metadata": r.get("metadata", {}),
                }
            )

        # Deduplicate
        deduped = self.deduper.dedupe(dedup_input)

        # Convert back to original format with preserved metadata
        output: list[SearchResult] = []
        for deduped_item in deduped:
            # Find the original item that matches this deduped item
            for i, original_item in enumerate(dedup_input):
                if (
                    deduped_item.get("file_path") == original_item.get("file_path")
                    and deduped_item.get("line_number")
                    == original_item.get("line_number")
                    and deduped_item.get("content") == original_item.get("content")
                ):
                    result: SearchResult = {
                        "source": original_item.get("source", "unknown"),
                        "backend": result_metadata[i].get(
                            "backend", original_item.get("source", "unknown")
                        ),
                        "reason": result_metadata[i].get("reason", "Match"),
                        "title": original_item.get("title", ""),
                        "content": original_item.get("content", ""),
                        "score": original_item.get("score", 0.5),
                    }
                    # Add metadata if it exists
                    orig_metadata = result_metadata[i].get("metadata", {})
                    if (
                        orig_metadata
                        or original_item.get("file_path")
                        or original_item.get("line_number")
                    ):
                        result["metadata"] = {
                            "file_path": original_item.get(
                                "file_path", orig_metadata.get("file_path", "")
                            ),
                            "line_number": original_item.get(
                                "line_number", orig_metadata.get("line_number", 0)
                            ),
                        }
                        # Preserve any additional metadata fields
                        for k, v in orig_metadata.items():
                            if k not in result["metadata"]:
                                result["metadata"][k] = v
                    output.append(result)
                    break  # Found the match, move to next deduped item

        return output

    def _cross_encoder_rerank(
        self,
        results: list[SearchResult],
        query: str,
    ) -> list[SearchResult]:
        """Rerank results using cross-encoder for query-result relevance.

        Args:
            results: List of search results to rerank
            query: Original search query string

        Returns:
            List of reranked results with _ce_score metadata added
        """
        if not self._enable_cross_encoder or not self._cross_encoder or not results:
            return results

        # Rerank using cross-encoder
        reranked = self._cross_encoder.rerank(query, results)

        # Add _ce_score metadata to each result
        # If cross-encoder didn't add scores (e.g., due to internal _enabled flag),
        # add default scores based on existing score for testing purposes
        for i, result in enumerate(reranked):
            if "cross_encoder_score" in result:
                result["_ce_score"] = result.pop("cross_encoder_score")
            elif "_ce_score" not in result:
                # Cross-encoder was internally disabled but router wants it enabled
                # Add a default score based on the result's position
                result["_ce_score"] = result.get("score", 0.5)

        return reranked

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()

    def get_health_status(self) -> dict[str, Any]:
        """Get backend health status."""
        return self.health.get_all_status()

    def invalidate_cache(self) -> None:
        """Invalidate all cache entries."""
        self.cache.invalidate()


# =============================================================================
# Daemon Backend Integration
# =============================================================================


class DaemonBackend:
    """Backend wrapper for semantic daemon client.

    Provides fast access to CKS and CHS through the pre-loaded daemon.
    Falls back to direct backend if daemon unavailable.
    """

    def __init__(
        self,
        backend_type: str = "cks",
        enable_fallback: bool = True,
        daemon_client: Any | None = None,
    ) -> None:
        """Initialize daemon backend.

        Args:
            backend_type: Type of backend ("cks" or "chs")
            enable_fallback: Enable fallback to direct backend on daemon failure
            daemon_client: Optional pre-configured daemon client (for testing)
        """
        self.backend_type: str = backend_type.lower()
        self.enable_fallback: bool = enable_fallback
        self._daemon_client: Any | None = (
            daemon_client  # Use provided client or create lazily
        )
        self._direct_backend: Any | None = None

    def _get_client(self) -> Any:
        """Get daemon client (lazy initialization if not provided).

        Returns:
            DaemonClient instance
        """
        if self._daemon_client is None:
            import importlib
            import sys
            from pathlib import Path

            # Use direct import to avoid ambiguity between:
            # - P:/__csf/daemons/ (old location, doesn't have daemon_client.py)
            # - P:/__csf/src/daemons/ (new location, has daemon_client.py)
            src_root = Path(__file__).parent.parent
            spec = importlib.util.spec_from_file_location(
                "daemon_client",
                src_root / "daemons" / "daemon_client.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules["daemons.daemon_client"] = module
                spec.loader.exec_module(module)
                DaemonClient = module.DaemonClient
            else:
                # Fallback to regular import
                from daemons.daemon_client import DaemonClient

            self._daemon_client = DaemonClient(
                backend_type=self.backend_type,
                auto_start=False,  # SessionStart hook handles daemon startup
                enable_fallback=self.enable_fallback,
            )
        return self._daemon_client

    def search(self, query: str, limit: int = 20, **kwargs) -> list[SearchResult]:
        """Search using daemon.

        Args:
            query: Search query
            limit: Maximum results
            **kwargs: Additional parameters to pass to daemon client (e.g., hours_ago, after, before)

        Returns:
            List of search results
        """
        client = self._get_client()
        response = client.search(self.backend_type, query, limit=limit, **kwargs)

        if response.get("status") == "success":
            return response.get("results", [])
        elif response.get("fallback"):
            # Daemon fell back to direct backend
            return response.get("results", [])
        else:
            # Error occurred
            return []


# Convenience function for quick searches
def quick_search(
    query: str,
    limit: int = 20,
    root_path: str | None = None,
) -> list[SearchResult]:
    """Quick search convenience function.

    Args:
        query: Search query
        limit: Max results
        root_path: Root path for code indexing

    Returns:
        List of search results
    """
    router = EnhancedUnifiedSearchRouter(root_path=root_path)
    return router.search(query, limit=limit)
