"""Abstract base class for balancer strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.providers.models import Provider


class BalancerStrategy(ABC):
    """Strategy for selecting a provider from a list of candidates."""

    @abstractmethod
    def select_provider(self, providers: list[Provider]) -> Provider:
        """Select one provider from the given list.

        The list is guaranteed to be non-empty by the caller.
        """
