"""Round-Robin balancer strategy."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from src.balancer.base import BalancerStrategy

if TYPE_CHECKING:
    from src.providers.models import Provider


class RoundRobinStrategy(BalancerStrategy):
    """Cycles through providers in order, tracking position per model."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._lock = threading.Lock()

    def select_provider(self, providers: list[Provider]) -> Provider:
        """Select next provider in round-robin order.

        Uses the sorted provider ids as a stable key to track position.
        """
        key = ",".join(sorted(p.id for p in providers))
        with self._lock:
            idx = self._counters.get(key, 0)
            selected = providers[idx % len(providers)]
            self._counters[key] = idx + 1
            return selected
