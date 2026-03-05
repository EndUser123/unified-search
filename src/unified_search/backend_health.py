"""Backend Health Registry - Track success/failure with exponential backoff."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

# Define project root - adjusted for package structure
# When installed as a package, this will resolve to the installation location
# For development, it will resolve to the package source directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

HealthStatus = Literal["ready", "degraded", "down"]


@dataclass
class BackendHealth:
    """Health status for a single backend."""
    name: str
    status: HealthStatus
    consecutive_failures: int
    last_error: str | None
    next_retry: float

    def should_retry(self) -> bool:
        """Check if enough time has passed to retry."""
        return time.time() >= self.next_retry

    def record_success(self) -> None:
        """Reset failure count on success."""
        self.consecutive_failures = 0
        self.status = "ready"
        self.last_error = None

    def record_failure(self, error: str) -> None:
        """Record failure with exponential backoff."""
        self.consecutive_failures += 1
        self.last_error = error

        # Calculate backoff: 5s -> 10s -> 20s -> 40s -> 80s -> 160s -> 300s max
        backoffs = [5, 10, 20, 40, 80, 160, 300]
        idx = min(self.consecutive_failures - 1, len(backoffs) - 1)
        backoff_seconds = backoffs[idx]

        self.next_retry = time.time() + backoff_seconds

        if self.consecutive_failures >= 3:
            self.status = "down"
        else:
            self.status = "degraded"


class BackendHealthRegistry:
    """Registry for tracking backend health with thread-safe operations."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._health: dict[str, BackendHealth] = {}
        self._lock = threading.Lock()
        # Storage path - adjusted for package use
        # Uses user's home directory for package installations
        self._storage_path = Path.home() / ".search-knowledge" / "backend_health.json"
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_state()
        self._initialized = True

    def get_status(self, backend: str) -> BackendHealth | None:
        """Get health status for a specific backend."""
        with self._lock:
            return self._health.get(backend)

    def get_all_status(self) -> dict[str, BackendHealth]:
        """Get status of all backends."""
        with self._lock:
            return dict(self._health)

    def is_available(self, backend: str) -> bool:
        """
        Check if backend is available for search.

        Returns:
            True if backend is ready or degraded (can retry)
            False if backend is down (within backoff period)
        """
        health = self.get_status(backend)
        if health is None:
            return True  # Unknown backend, assume available

        # Always allow retry if backoff period passed
        if health.status == "down" and health.should_retry():
            return True

        return health.status in ("ready", "degraded")

    def record_result(
        self,
        backend: str,
        success: bool,
        error: str | None = None
    ) -> None:
        """Record backend result and update health status."""
        with self._lock:
            if backend not in self._health:
                self._health[backend] = BackendHealth(
                    name=backend,
                    status="ready",
                    consecutive_failures=0,
                    last_error=None,
                    next_retry=0.0
                )

            health = self._health[backend]
            if success:
                health.record_success()
            else:
                health.record_failure(error or "Unknown error")

            self._save_state()

    def _load_state(self) -> None:
        """Load health state from disk."""
        if not self._storage_path.exists():
            return

        try:
            data = json.loads(self._storage_path.read_text())
            for name, health_data in data.items():
                self._health[name] = BackendHealth(**health_data)
        except Exception:
            pass  # Start fresh on load error

    def _save_state(self) -> None:
        """Save health state to disk."""
        try:
            data = {
                name: asdict(health)
                for name, health in self._health.items()
            }
            self._storage_path.write_text(json.dumps(data, indent=2))
        except Exception:
            pass  # Don't fail if save fails

    def _reset(self) -> None:
        """Reset all state. For testing only."""
        with self._lock:
            self._health.clear()
            if self._storage_path.exists():
                try:
                    self._storage_path.unlink()
                except Exception:
                    pass
