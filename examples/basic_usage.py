"""
Basic usage examples for search-knowledge package.

This example demonstrates:
- Simple search across all backends
- Accessing search results
- Filtering by backend
- Limiting results
"""

from search_knowledge import search

# Example 1: Simple search across all backends
print("=== Example 1: Simple Search ===")
results = search("async patterns")
print(f"Found {len(results.hits)} results")
print(f"Query: {results.query}")

for hit in results.hits[:3]:
    print(f"  [{hit.score:.2f}] {hit.title}")

# Example 2: Filter to specific backend
print("\n=== Example 2: Backend Filter ===")
results = search("vector embeddings", backend=["chs", "cks"], limit=5)
print(f"Found {len(results.hits)} results from CHS/CKS")

for hit in results.hits[:3]:
    print(f"  [{hit.backend}] {hit.title}")

# Example 3: Limit results
print("\n=== Example 3: Limited Results ===")
results = search("test query", limit=3)
print(f"Top 3 results:")
for hit in results.hits:
    print(f"  - {hit.title}")

# Example 4: Multiple backends
print("\n=== Example 4: Multiple Backends ===")
results = search("authentication", backend=["cds", "grep"], limit=10)
print(f"Searched CDS + Grep: {len(results.hits)} results")

backend_counts = {}
for hit in results.hits:
    backend = hit.backend
    backend_counts[backend] = backend_counts.get(backend, 0) + 1

print("Results by backend:")
for backend, count in backend_counts.items():
    print(f"  {backend}: {count}")
