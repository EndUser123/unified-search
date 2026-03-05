"""Tests for BackendHealthRegistry."""

import json
import time
from pathlib import Path

import pytest

from search_knowledge.backend_health import BackendHealth, BackendHealthRegistry, HealthStatus


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry state before each test."""
    registry = BackendHealthRegistry()
    registry._reset()
    yield
    registry._reset()


def test_singleton_pattern():
    """Test that BackendHealthRegistry is a singleton."""
    registry1 = BackendHealthRegistry()
    registry2 = BackendHealthRegistry()
    assert registry1 is registry2


def test_backend_health_creation():
    """Test BackendHealth dataclass creation."""
    health = BackendHealth(
        name="test_backend",
        status="ready",
        consecutive_failures=0,
        last_error=None,
        next_retry=0.0,
    )
    assert health.name == "test_backend"
    assert health.status == "ready"
    assert health.consecutive_failures == 0
    assert health.last_error is None
    assert health.next_retry == 0.0


def test_record_success():
    """Test recording success resets failure count."""
    registry = BackendHealthRegistry()

    # Record success for new backend
    registry.record_result("test_backend", success=True)
    status = registry.get_status("test_backend")

    assert status is not None
    assert status.status == "ready"
    assert status.consecutive_failures == 0
    assert status.last_error is None


def test_record_failure_degraded():
    """Test recording failure marks backend as degraded."""
    registry = BackendHealthRegistry()

    registry.record_result("test_backend", success=False, error="Test error")
    status = registry.get_status("test_backend")

    assert status is not None
    assert status.status == "degraded"
    assert status.consecutive_failures == 1
    assert status.last_error == "Test error"


def test_record_failure_down():
    """Test recording 3+ failures marks backend as down."""
    registry = BackendHealthRegistry()

    # Record 3 failures
    for i in range(3):
        registry.record_result("test_backend", success=False, error=f"Error {i+1}")

    status = registry.get_status("test_backend")

    assert status is not None
    assert status.status == "down"
    assert status.consecutive_failures == 3


def test_exponential_backoff():
    """Test exponential backoff calculation."""
    registry = BackendHealthRegistry()

    # First failure: 5 seconds
    registry.record_result("test_backend", success=False, error="Error 1")
    status = registry.get_status("test_backend")
    # Allow small margin for timing differences
    assert status.next_retry - time.time() >= 4.9

    # Second failure: 10 seconds
    registry.record_result("test_backend", success=False, error="Error 2")
    status = registry.get_status("test_backend")
    assert status.next_retry - time.time() >= 9.9

    # Third failure: 20 seconds
    registry.record_result("test_backend", success=False, error="Error 3")
    status = registry.get_status("test_backend")
    assert status.next_retry - time.time() >= 19.9

    # Fourth failure: 40 seconds
    registry.record_result("test_backend", success=False, error="Error 4")
    status = registry.get_status("test_backend")
    assert status.next_retry - time.time() >= 39.9


def test_backoff_cap():
    """Test that backoff caps at 300 seconds."""
    registry = BackendHealthRegistry()

    # Record many failures
    for i in range(10):
        registry.record_result("test_backend", success=False, error=f"Error {i+1}")

    status = registry.get_status("test_backend")
    # After 7 failures, should cap at 300 seconds
    # Allow small margin for timing differences
    assert status.next_retry - time.time() >= 299
    assert status.next_retry - time.time() < 310  # Should not exceed cap significantly


def test_should_retry():
    """Test should_retry method."""
    health = BackendHealth(
        name="test",
        status="down",
        consecutive_failures=3,
        last_error="Error",
        next_retry=time.time() - 1,  # Past time
    )
    assert health.should_retry()

    health.next_retry = time.time() + 100  # Future time
    assert not health.should_retry()


def test_is_available_ready():
    """Test is_available returns True for ready backend."""
    registry = BackendHealthRegistry()
    registry.record_result("test_backend", success=True)

    assert registry.is_available("test_backend")


def test_is_available_degraded():
    """Test is_available returns True for degraded backend."""
    registry = BackendHealthRegistry()
    registry.record_result("test_backend", success=False, error="Error")

    assert registry.is_available("test_backend")


def test_is_available_down_in_backoff():
    """Test is_available returns False for down backend during backoff."""
    registry = BackendHealthRegistry()

    # Record 3 failures to mark as down
    for i in range(3):
        registry.record_result("test_backend", success=False, error=f"Error {i+1}")

    assert not registry.is_available("test_backend")


def test_is_available_down_after_backoff():
    """Test is_available returns True for down backend after backoff period."""
    registry = BackendHealthRegistry()

    # Record 3 failures to mark as down
    for i in range(3):
        registry.record_result("test_backend", success=False, error=f"Error {i+1}")

    # Manually set next_retry to past
    status = registry.get_status("test_backend")
    status.next_retry = time.time() - 1

    assert registry.is_available("test_backend")


def test_is_available_unknown_backend():
    """Test is_available returns True for unknown backend."""
    registry = BackendHealthRegistry()
    assert registry.is_available("unknown_backend")


def test_get_all_status():
    """Test getting all backend statuses."""
    registry = BackendHealthRegistry()

    registry.record_result("backend1", success=True)
    registry.record_result("backend2", success=False, error="Error")

    all_status = registry.get_all_status()

    assert len(all_status) == 2
    assert "backend1" in all_status
    assert "backend2" in all_status
    assert all_status["backend1"].status == "ready"
    assert all_status["backend2"].status == "degraded"


def test_state_persistence():
    """Test that state is persisted to disk."""
    registry = BackendHealthRegistry()

    registry.record_result("test_backend", success=False, error="Test error")

    # Get storage path
    storage_path = Path.home() / ".search-knowledge" / "backend_health.json"
    assert storage_path.exists()

    # Load and verify content
    data = json.loads(storage_path.read_text())
    assert "test_backend" in data
    assert data["test_backend"]["status"] == "degraded"
    assert data["test_backend"]["consecutive_failures"] == 1


def test_state_loading():
    """Test that state is loaded from disk."""
    # Reset first to clear any existing state
    registry = BackendHealthRegistry()
    registry._reset()

    storage_path = Path.home() / ".search-knowledge" / "backend_health.json"

    # Create state file
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text(
        json.dumps(
            {
                "test_backend": {
                    "name": "test_backend",
                    "status": "down",
                    "consecutive_failures": 3,
                    "last_error": "Test error",
                    "next_retry": 0.0,
                }
            }
        )
    )

    # Create new registry instance to load state
    # Note: We need to bypass singleton to force reload
    registry._instance = None
    registry._initialized = False
    new_registry = BackendHealthRegistry()
    status = new_registry.get_status("test_backend")

    assert status is not None
    assert status.status == "down"
    assert status.consecutive_failures == 3
    assert status.last_error == "Test error"

    # Clean up
    new_registry._reset()


def test_recovery_after_success():
    """Test that backend recovers after success."""
    registry = BackendHealthRegistry()

    # Record failures
    for i in range(3):
        registry.record_result("test_backend", success=False, error=f"Error {i+1}")

    assert registry.get_status("test_backend").status == "down"

    # Record success
    registry.record_result("test_backend", success=True)

    status = registry.get_status("test_backend")
    assert status.status == "ready"
    assert status.consecutive_failures == 0
    assert status.last_error is None
