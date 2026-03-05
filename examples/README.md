# Examples

Collection of runnable examples demonstrating search-knowledge features.

## Prerequisites

Install search-knowledge:
```bash
pip install search-knowledge[all]
```

## Basic Usage

```bash
python basic_usage.py
```

Demonstrates:
- Simple search across all backends
- Accessing search results
- Filtering by backend
- Limiting results

## Advanced Configuration

```bash
python advanced_config.py
```

Demonstrates:
- Direct router usage
- Custom backend configuration
- Query parameters
- Result ranking and deduplication

## Knowledge Systems

```bash
python knowledge_systems.py
```

Demonstrates:
- CHS (Chat History Search) usage
- CKS (Constitutional Knowledge System) usage
- Hybrid search with semantic embeddings
- FTS5 fallback behavior

## Real-World Integration

```bash
python real_world.py
```

Demonstrates:
- Integration with existing codebase
- Batch queries
- Performance optimization with caching
- Error handling and graceful degradation
