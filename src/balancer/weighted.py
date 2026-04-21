"""Weighted random balancer strategy."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from src.balancer.base import BalancerStrategy

if TYPE_CHECKING:
    from src.providers.models import Provider


class WeightedStrategy(BalancerStrategy):
    """Selects provider based on static weights using weighted random selection."""

    def select_provider(self, providers: list[Provider]) -> Provider:
        weights = [p.weight for p in providers]
        return random.choices(providers, weights=weights, k=1)[0]
