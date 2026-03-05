"""
Advanced configuration examples for search-knowledge package.

This example demonstrates:
- Direct router usage
- Custom backend configuration
- Query parameters
- Result ranking and deduplication
"""

from search_knowledge import EnhancedUnifiedSearchRouter

# Example 1: Direct router usage
print("=== Example 1: Direct Router Usage ===")
router = EnhancedUnifiedSearchRouter()

# Search with specific parameters
results = router.search(
    "machine learning",
    backends=["cds", "grep"],
    limit=20,
    fuzzy=True,
    deduplicate=True
)

print(f"Found {len(results)} results")
for hit in results[:5]:
    print(f"  [{hit.score:.2f}] {hit.title}")

# Example 2: Check available backends
print("\n=== Example 2: Available Backends ===")
available = router.get_available_backends()
print("Available backends:")
for backend in available:
    print(f"  - {backend}")

# Example 3: Backend health check
print("\n=== Example 3: Backend Health ===")
health = router.get_backend_health()
for backend, status in health.items():
    print(f"  {backend}: {'✓ Healthy' if status else '✗ Unavailable'}")

# Example 4: Search with caching
print("\n=== Example 4: Query Caching ===")
import time

# First query (cache miss)
start = time.time()
results1 = router.search("cache test", backends=["cds"], limit=5)
time1 = time.time() - start

# Second query (cache hit)
start = time.time()
results2 = router.search("cache test", backends=["cds"], limit=5)
time2 = time.time() - start

print(f"First query: {time1:.3f}s")
print(f"Second query: {time2:.3f}s")
print(f"Speedup: {time1/time2:.1f}x")

# Example 5: Fuzzy matching
print("\n=== Example 5: Fuzzy Matching ===")
# Intentional typo: "asynk" instead of "async"
results = router.search("asynk patterns", backends=["cds"], fuzzy=True, limit=10)
print(f"Found {len(results)} results with typo tolerance")
for hit in results[:3]:
    print(f"  - {hit.title}")
