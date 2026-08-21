"""In-process provider health — MODE A only; not a distributed circuit breaker."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock

from deepscout_core.types import ProviderKind


@dataclass
class ProviderHealthState:
    failures: int = 0
    open_until: float = 0.0
    last_error: str | None = None


@dataclass
class ProviderHealthRegistry:
    """Simple open/closed health gate after repeated transient failures."""

    failure_threshold: int = 3
    cooldown_s: float = 30.0
    _states: dict[ProviderKind, ProviderHealthState] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def is_available(self, provider: ProviderKind) -> bool:
        with self._lock:
            state = self._states.get(provider)
            if state is None:
                return True
            if state.open_until and time.monotonic() < state.open_until:
                return False
            if state.open_until and time.monotonic() >= state.open_until:
                state.failures = 0
                state.open_until = 0.0
            return True

    def record_success(self, provider: ProviderKind) -> None:
        with self._lock:
            self._states[provider] = ProviderHealthState()

    def record_failure(self, provider: ProviderKind, *, reason: str) -> None:
        with self._lock:
            state = self._states.setdefault(provider, ProviderHealthState())
            state.failures += 1
            state.last_error = reason[:200]
            if state.failures >= self.failure_threshold:
                state.open_until = time.monotonic() + self.cooldown_s


DEFAULT_PROVIDER_HEALTH = ProviderHealthRegistry()
