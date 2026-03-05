"""
Real-world integration examples for search-knowledge package.

This example demonstrates:
- Integration with existing codebase
- Batch queries
- Performance optimization with caching
- Error handling and graceful degradation
"""

from search_knowledge import search, EnhancedUnifiedSearchRouter
import time

# Example 1: Code documentation search
print("=== Example 1: Code Documentation Search ===")

# Find documentation about async/await patterns
results = search(
    "async await patterns",
    backend=["cd"],  # Code Documentation Search only
    limit=10
)

print(f"Found {len(results.hits)} documentation references")
for hit in results.hits[:5]:
    print(f"\n  📄 {hit.title}")
    print(f"     {hit.content[:150]}...")

# Example 2: Pattern search across codebase
print("\n=== Example 2: Pattern Search ===")

# Find all functions related to authentication
results = search(
    "def authenticate",
    backend=["grep"],  # Code Pattern Search
    limit=15
)

print(f"Found {len(results.hits)} function definitions")
for hit in results.hits[:5]:
    location = hit.metadata.get("location", "Unknown")
    print(f"  📍 {location}")
    print(f"     {hit.title}")

# Example 3: Batch queries with caching
print("\n=== Example 3: Batch Queries ===")

queries = [
    "async patterns",
    "error handling",
    "type hints"
]

router = EnhancedUnifiedSearchRouter()

start = time.time()
for query in queries:
    results = router.search(query, backend=["cds", "grep"], limit=5)
    print(f"  '{query}': {len(results)} results")
elapsed = time.time() - start

print(f"\nBatch queries completed in {elapsed:.3f}s")

# Example 4: Error handling
print("\n=== Example 4: Error Handling ===")

try:
    # Search with potentially unavailable backends
    results = search(
        "machine learning",
        backend=["nonexistent_backend", "cds"],  # One invalid, one valid
        limit=10
    )
    
    # Should not raise exception, just skip invalid backends
    print(f"Search succeeded with {len(results.hits)} results")
    print("  (Invalid backends are silently skipped)")
    
except Exception as e:
    print(f"Unexpected error: {e}")
    print("  (This should not happen with graceful degradation)")

# Example 5: Performance with cache
print("\n=== Example 5: Cache Performance ===")

# First search (cache miss)
start = time.time()
results1 = search("performance optimization", backend=["cds"], limit=20)
time1 = time.time() - start

# Second identical search (cache hit)
start = time.time()
results2 = search("performance optimization", backend=["cds"], limit=20)
time2 = time.time() - start

print(f"First search:  {time1*1000:.1f}ms")
print(f"Second search: {time2*1000:.1f}ms")
print(f"Cache speedup: {time1/time2:.1f}x")

# Example 6: Multi-backend fusion
print("\n=== Example 6: Multi-Backend Fusion ===")

results = search(
    "database connection",
    backend=["cds", "grep", "cks"],  # Multiple backends
    limit=20,
    deduplicate=True  # Remove cross-backend duplicates
)

# Group results by backend
backend_counts = {}
for hit in results.hits:
    backend = hit.backend
    backend_counts[backend] = backend_counts.get(backend, 0) + 1

print("Results by backend:")
for backend, count in sorted(backend_counts.items()):
    print(f"  {backend}: {count}")

print(f"\nTotal (after deduplication): {len(results.hits)} unique results")
