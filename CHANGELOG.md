# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial package extraction from __csf monorepo
- EnhancedUnifiedSearchRouter with 9+ search backends
- Query caching with LRU + TTL (5-minute default, 1000 entries)
- Backend health tracking with exponential backoff
- Hybrid scoring (BM25 + cosine similarity fusion)
- Cross-backend deduplication
- Fuzzy matching for typo tolerance
- Graceful degradation when optional backends unavailable
- CHS FTS5 fallback when semantic embeddings unavailable
- Comprehensive README with installation and usage examples
- Integration tests for __csf compatibility
- MIT license
- CI/CD workflow with multi-Python version testing

### Fixed
- Parameter name mismatch: `backend` → `backends` mapping in public API
- Return type inconsistency: wrapped router results in SearchResults object
- Integration test failures from parameter naming issues

## [0.1.0] - 2026-03-04

### Added
- Initial release of search-knowledge package
- Support for 10+ search backends:
  - CDS (Code Documentation Search)
  - Grep (Code Pattern Search)
  - Skills (Skills & Commands)
  - CHS (Chat History Search)
  - CKS (Constitutional Knowledge System)
  - KG (Knowledge Graph)
  - MultiLang (Multi-language Code Search)
  - RLM (Recursive Language Model)
  - Persona Memory
  - Code (Code analysis)
- Simple `search()` function API
- EnhancedUnifiedSearchRouter for advanced usage
- Query intent detection
- Cache management
- Backend health tracking
- Comprehensive documentation
- Test suite with 46 passing tests

[Unreleased]: https://github.com/yourusername/search-knowledge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/search-knowledge/releases/tag/v0.1.0
