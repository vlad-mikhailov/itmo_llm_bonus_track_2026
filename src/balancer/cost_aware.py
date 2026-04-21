"""Cost-aware balancer strategy.

Выбирает провайдера с минимальной стоимостью за токен.
При одинаковой цене — fallback на round-robin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.balancer.base import BalancerStrategy
from src.balancer.round_robin import RoundRobinStrategy

if TYPE_CHECKING:
    from src.providers.models import Provider


class CostAwareStrategy(BalancerStrategy):
    """Выбирает провайдера с наименьшей ценой за токен.

    Если у нескольких провайдеров одинаковая цена (или цена не задана),
    используется round-robin для равномерного распределения.
    """

    def __init__(self) -> None:
        self._fallback = RoundRobinStrategy()

    @staticmethod
    def _avg_cost(provider: Provider) -> float | None:
        """Средняя цена за 1M токенов (input + output) / 2.

        Возвращает None если прайсинг не задан.
        """
        if provider.pricing is None:
            return None
        return (provider.pricing.input + provider.pricing.output) / 2

    def select_provider(self, providers: list[Provider]) -> Provider:
        """Выбрать самого дешёвого провайдера.

        Провайдеры без pricing считаются бесплатными (приоритет).
        При равной цене — round-robin.
        """
        free = [p for p in providers if self._avg_cost(p) is None]
        priced = [p for p in providers if self._avg_cost(p) is not None]

        # Бесплатные провайдеры — наивысший приоритет
        if free:
            return self._fallback.select_provider(free)

        if not priced:
            return self._fallback.select_provider(providers)

        min_cost = min(self._avg_cost(p) for p in priced)  # type: ignore[arg-type]
        cheapest = [p for p in priced if self._avg_cost(p) == min_cost]

        if len(cheapest) == 1:
            return cheapest[0]

        return self._fallback.select_provider(cheapest)
