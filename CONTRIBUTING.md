# Contributing to search-knowledge

Thank you for your interest in contributing to search-knowledge! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- Virtual environment tool (venv, conda, etc.)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/search-knowledge.git
cd search-knowledge
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install in development mode:
```bash
pip install -e ".[dev,test]"
```

## Development Workflow

### Code Style

This project uses:
- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

Format your code before committing:
```bash
black src/ tests/
ruff check src/ tests/ --fix
```

### Running Tests

Run the full test suite:
```bash
pytest tests/ -v
```

Run tests with coverage:
```bash
pytest tests/ --cov=search_knowledge --cov-report=html
```

### Type Checking

Run type checker:
```bash
mypy src/search_knowledge/
```

## Submitting Changes

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Commit Message Format

Use clear commit messages:
- `"Add support for new backend"` 
- `"Fix parameter mapping in search() function"`
- `"Update README with installation instructions"`

Avoid: `"update stuff"`, `"fix bugs"`, `"wip"`

### Code Review Guidelines

- Ensure all tests pass
- Add tests for new functionality
- Update documentation if needed
- Keep changes focused and minimal

## Adding New Backends

To add a new search backend:

1. Create backend module in `src/search_knowledge/backends/`
2. Implement the backend interface:
```python
from search_knowledge.backends.base import BackendBase

class MyBackend(BackendBase):
    def search(self, query: str, **kwargs) -> list[SearchResult]:
        # Implementation
        pass
```

3. Add tests in `tests/test_backends/test_my_backend.py`
4. Register backend in router configuration
5. Update README with backend description

## Documentation

Documentation is maintained in:
- `README.md` - User-facing documentation
- `ARCHITECTURE.md` - System design (create if needed)
- Docstrings in code - API documentation

## Questions or Issues?

- Open an issue on GitHub for bugs or feature requests
- Check existing issues first before creating new ones
- Be respectful and constructive in all interactions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
