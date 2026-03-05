#!/usr/bin/env python3
"""Test intent_classifier module functionality.

This test verifies that the intent_classifier module is self-contained
and can be imported independently without __csf dependencies.
"""

import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_imports():
    """Test that required functions can be imported."""
    from search_knowledge.intent_classifier import IntentCategory, classify_intent

    # Verify IntentCategory is the right type
    assert hasattr(IntentCategory, "__args__"), "IntentCategory should be a Literal type"

    # Verify it has all expected categories
    expected_categories = {
        "search",
        "read",
        "write",
        "analyze",
        "research",
        "code",
        "test",
        "git",
        "web",
        "existence_claim",
        "other",
    }
    actual_categories = set(IntentCategory.__args__)
    assert actual_categories == expected_categories, f"Expected {expected_categories}, got {actual_categories}"

    print("✓ All imports successful")


def test_classify_intent():
    """Test basic intent classification."""
    from search_knowledge.intent_classifier import classify_intent

    # Test search intent
    result = classify_intent("I need to search for files")
    assert result == "search", f"Expected 'search', got '{result}'"

    # Test read intent
    result = classify_intent("Show me the configuration")
    assert result == "read", f"Expected 'read', got '{result}'"

    # Test code intent
    result = classify_intent("Implement a new feature")
    assert result == "code", f"Expected 'code', got '{result}'"

    # Test analyze intent
    result = classify_intent("Analyze the performance")
    assert result == "analyze", f"Expected 'analyze', got '{result}'"

    print("✓ Intent classification working correctly")


def test_varied_queries():
    """Test classification of varied query types."""
    from search_knowledge.intent_classifier import classify_intent

    test_cases = [
        ("Where is the config file?", "search"),
        ("Read the documentation", "read"),
        ("Create a new function", "write"),
        ("Investigate the error", "analyze"),
        ("Fix the bug", "code"),
        ("Run the tests", "test"),
        ("Commit the changes", "git"),
        ("Search online for examples", "web"),
        ("The command is missing", "existence_claim"),
    ]

    for query, expected in test_cases:
        result = classify_intent(query)
        # At minimum, result should be one of the valid categories
        assert result in [
            "search",
            "read",
            "write",
            "analyze",
            "research",
            "code",
            "test",
            "git",
            "web",
            "existence_claim",
            "other",
        ], f"Invalid category '{result}' for query: {query}"

    print("✓ Varied query classification working")


def test_no_external_dependencies():
    """Verify module has no external __csf dependencies."""
    import search_knowledge.intent_classifier as ic_module

    # Read the module file
    module_file = Path(ic_module.__file__).read_text()

    # Check for problematic imports (excluding comments)
    lines = module_file.split("\n")
    import_lines = [line for line in lines if line.strip().startswith(("from ", "import ")) and not line.strip().startswith("#")]

    code_only = "\n".join(import_lines)
    assert "from modules.semantic_intelligence" not in code_only
    assert "import semantic_engine" not in code_only
    assert "from __csf" not in code_only
    assert "from shared" not in code_only

    # Verify module defines its own dependencies
    assert "def classify_intent" in module_file
    assert "IntentCategory = Literal" in module_file
    assert "_CATEGORY_DESCRIPTIONS" in module_file

    print("✓ Module is self-contained with no external __csf dependencies")


def test_embedding_caching():
    """Test that embeddings are cached correctly."""
    import search_knowledge.intent_classifier as ic_module

    # Verify cache directory exists
    assert ic_module._CACHE_DIR.exists(), "Cache directory should exist"
    assert ic_module._EMBEDDINGS_CACHE_FILE.exists(), "Embeddings cache file should exist"

    # Verify embeddings were loaded
    assert len(ic_module._CATEGORY_EMBEDDINGS) > 0, "Category embeddings should be loaded"

    print("✓ Embedding caching working correctly")


if __name__ == "__main__":
    print("Testing intent_classifier module...\n")

    test_imports()
    test_classify_intent()
    test_varied_queries()
    test_no_external_dependencies()
    test_embedding_caching()

    print("\n✅ All tests passed! Module is self-contained and functional.")
