"""
Knowledge systems usage examples for search-knowledge package.

This example demonstrates:
- CHS (Chat History Search) usage
- CKS (Constitutional Knowledge System) usage
- Hybrid search with semantic embeddings
- FTS5 fallback behavior
"""

from search_knowledge import CHSSearch, CKS, search

# Example 1: CHS (Chat History Search)
print("=== Example 1: Chat History Search ===")
try:
    chs = CHSSearch()
    
    # Basic search
    results = chs.search("async patterns", limit=5)
    print(f"CHS found {len(results)} results")
    
    for result in results[:3]:
        print(f"  [{result.score:.2f}] {result.metadata.get('timestamp', 'N/A')}")
        print(f"    {result.content[:100]}...")
    
except Exception as e:
    print(f"CHS not available: {e}")
    print("  (CHS requires sentence-transformers and configured database)")

# Example 2: CKS (Constitutional Knowledge System)
print("\n=== Example 2: Knowledge System ===")
try:
    cks = CKS()
    
    # Query knowledge base
    results = cks.query("authentication patterns", limit=5)
    print(f"CKS found {len(results)} results")
    
    for result in results[:3]:
        print(f"  [{result.score:.2f}] {result.title}")
        print(f"    Source: {result.metadata.get('source', 'N/A')}")
    
except Exception as e:
    print(f"CKS not available: {e}")
    print("  (CKS requires faiss-cpu and configured database)")

# Example 3: Unified search with knowledge backends
print("\n=== Example 3: Unified Knowledge Search ===")
results = search(
    "machine learning algorithms",
    backend=["chs", "cks"],
    limit=10
)

print(f"Unified search found {len(results.hits)} results")

# Group by backend
backend_groups = {}
for hit in results.hits:
    backend = hit.backend
    if backend not in backend_groups:
        backend_groups[backend] = []
    backend_groups[backend].append(hit)

for backend, hits in backend_groups.items():
    print(f"\n{backend}: {len(hits)} results")
    for hit in hits[:2]:
        print(f"  - {hit.title}")

# Example 4: Graceful degradation
print("\n=== Example 4: Graceful Degradation ===")
# Search with backends that may not be available
results = search(
    "test query",
    backend=["chs", "cks", "cds"],  # Mix of optional and required
    limit=10
)

print(f"Search returned {len(results.hits)} results")
print("  (Unavailable backends are skipped automatically)")

# Example 5: Hybrid search
print("\n=== Example 5: Hybrid Search (FTS5 + Semantic) ===")
try:
    # CHS hybrid search requires semantic embeddings
    results = search(
        "conversational patterns",
        backend=["chs"],
        limit=5
    )
    
    if len(results.hits) > 0:
        print(f"Hybrid search found {len(results.hits)} results")
        for hit in results.hits[:3]:
            score_type = hit.metadata.get("score_type", "unknown")
            print(f"  [{hit.score:.2f} ({score_type})] {hit.title}")
    else:
        print("No results (CHS may be using FTS5-only mode)")
        
except Exception as e:
    print(f"Hybrid search not available: {e}")
    print("  (Falls back to FTS5 keyword search when embeddings unavailable)")
