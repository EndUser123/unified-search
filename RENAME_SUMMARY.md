# Package Rename: search-knowledge → unified-search

**Date**: 2026-03-05  
**Status**: ✅ COMPLETE

## Changes Made

### Directory Structure
```
P:/packages/search-knowledge/          # Outer directory (unchanged due to Windows file locking)
└── src/unified_search/                # ✅ Renamed from search_knowledge/
    ├── __init__.py
    ├── backend_health.py
    ├── cache.py
    ├── intent_classifier.py
    ├── knowledge/
    ├── query_intent.py
    └── router.py
```

### Package Metadata (pyproject.toml)
- ✅ Package name: `unified-search` (was `search-knowledge`)
- ✅ CLI command: `unified-search` (was `search-knowledge`)
- ✅ URLs updated: github.com/csf-nip/unified-search
- ✅ Dependencies: unified-search[all] (was search-knowledge[all])

### Import Paths
- ✅ Internal imports: `from unified_search.xxx import ...`
- ✅ Public API: `from unified_search import search, EnhancedUnifiedSearchRouter`
- ✅ __csf integration: Updated to `from unified_search import ...`

### Documentation
- ✅ README.md: All references updated to unified-search/unified_search
- ✅ MANIFEST.in: Package paths updated
- ✅ Package description: "Unified Search" (was "Search Knowledge")

## Installation

**New installation commands:**
```bash
# Basic installation
pip install unified-search

# Full installation
pip install unified-search[all]

# Development
pip install -e "packages/search-knowledge[all,dev]"
```

**New CLI command:**
```bash
unified-search "query text"
```

**New Python API:**
```python
from unified_search import search
results = search("async patterns")
```

## Breaking Changes

- **PyPI package name**: `pip install unified-search` (not `search-knowledge`)
- **CLI command**: `unified-search` (not `search-knowledge`)
- **Import paths**: `from unified_search import ...` (not `from search_knowledge import ...`)

## Compatibility

- ✅ __csf integration updated and working
- ✅ All internal imports resolved
- ✅ Version: 0.5.0 (stable beta)
- ✅ No functionality changes (metadata only)

## Next Steps

1. ✅ Package rename complete
2. ✅ All imports updated
3. ✅ Documentation updated
4. ✅ __csf integration updated
5. ⏭️ Ready for GitHub publication as "unified-search"
