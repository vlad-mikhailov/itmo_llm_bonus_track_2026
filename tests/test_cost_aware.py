"""Тесты для cost-aware стратегии балансировки."""

from __future__ import annotations

import pytest

from src.balancer.cost_aware import CostAwareStrategy
from src.providers.models import Provider, ProviderPricing


def _make_provider(
    id: str,
    pricing: ProviderPricing | None = None,
) -> Provider:
    return Provider(
        id=id,
        name=f"provider-{id}",
        base_url="https://openrouter.ai/api/v1",
        models=["test-model"],
        pricing=pricing,
    )


class TestCostAwareStrategy:
    def test_selects_cheapest_provider(self) -> None:
        strategy = CostAwareStrategy()
        providers = [
            _make_provider("expensive", ProviderPricing(input=10.0, output=30.0)),
            _make_provider("cheap", ProviderPricing(input=0.5, output=1.5)),
            _make_provider("mid", ProviderPricing(input=3.0, output=6.0)),
        ]
        selected = strategy.select_provider(providers)
        assert selected.id == "cheap"

    def test_prefers_free_providers(self) -> None:
        strategy = CostAwareStrategy()
        providers = [
            _make_provider("paid", ProviderPricing(input=1.0, output=2.0)),
            _make_provider("free"),  # pricing=None → бесплатный
        ]
        selected = strategy.select_provider(providers)
        assert selected.id == "free"

    def test_round_robin_among_equal_cost(self) -> None:
        strategy = CostAwareStrategy()
        same_price = ProviderPricing(input=5.0, output=5.0)
        providers = [
            _make_provider("a", same_price),
            _make_provider("b", same_price),
        ]

        results = [strategy.select_provider(providers).id for _ in range(4)]
        assert results == ["a", "b", "a", "b"]

    def test_round_robin_among_free(self) -> None:
        strategy = CostAwareStrategy()
        providers = [
            _make_provider("free1"),
            _make_provider("free2"),
        ]

        results = [strategy.select_provider(providers).id for _ in range(4)]
        assert results == ["free1", "free2", "free1", "free2"]

    def test_single_provider(self) -> None:
        strategy = CostAwareStrategy()
        providers = [_make_provider("only", ProviderPricing(input=2.0, output=4.0))]
        assert strategy.select_provider(providers).id == "only"
