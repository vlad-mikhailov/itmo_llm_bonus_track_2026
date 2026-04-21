"""Unit tests for balancer strategies and model router."""

from __future__ import annotations

from collections import Counter

import pytest
from fastapi import HTTPException

from src.balancer.round_robin import RoundRobinStrategy
from src.balancer.router import ModelRouter
from src.balancer.weighted import WeightedStrategy
from src.providers.models import Provider
from src.providers.registry import ProviderRegistry


def _make_provider(id: str, name: str = "", weight: float = 1.0) -> Provider:
    return Provider(
        id=id,
        name=name or f"provider-{id}",
        base_url="https://openrouter.ai/api/v1",
        models=["test-model"],
        weight=weight,
    )


# --- Round-Robin ---


class TestRoundRobin:
    def test_cycles_through_providers(self) -> None:
        strategy = RoundRobinStrategy()
        providers = [_make_provider("a"), _make_provider("b"), _make_provider("c")]

        results = [strategy.select_provider(providers).id for _ in range(6)]
        assert results == ["a", "b", "c", "a", "b", "c"]

    def test_single_provider(self) -> None:
        strategy = RoundRobinStrategy()
        providers = [_make_provider("only")]

        results = [strategy.select_provider(providers).id for _ in range(3)]
        assert results == ["only", "only", "only"]

    def test_independent_tracking_per_provider_set(self) -> None:
        strategy = RoundRobinStrategy()
        set_a = [_make_provider("a1"), _make_provider("a2")]
        set_b = [_make_provider("b1"), _make_provider("b2"), _make_provider("b3")]

        assert strategy.select_provider(set_a).id == "a1"
        assert strategy.select_provider(set_b).id == "b1"
        assert strategy.select_provider(set_a).id == "a2"
        assert strategy.select_provider(set_b).id == "b2"
        assert strategy.select_provider(set_a).id == "a1"
        assert strategy.select_provider(set_b).id == "b3"


# --- Weighted ---


class TestWeighted:
    def test_respects_weights_distribution(self) -> None:
        strategy = WeightedStrategy()
        providers = [
            _make_provider("heavy", weight=100.0),
            _make_provider("light", weight=1.0),
        ]

        counts: Counter[str] = Counter()
        for _ in range(1000):
            selected = strategy.select_provider(providers)
            counts[selected.id] += 1

        assert counts["heavy"] > counts["light"] * 5

    def test_single_provider_always_selected(self) -> None:
        strategy = WeightedStrategy()
        providers = [_make_provider("solo", weight=1.0)]

        for _ in range(10):
            assert strategy.select_provider(providers).id == "solo"

    def test_zero_weight_never_selected(self) -> None:
        strategy = WeightedStrategy()
        providers = [
            _make_provider("active", weight=1.0),
            _make_provider("zero", weight=0.0),
        ]

        for _ in range(100):
            assert strategy.select_provider(providers).id == "active"

    def test_equal_weights_roughly_even(self) -> None:
        strategy = WeightedStrategy()
        providers = [_make_provider("a", weight=1.0), _make_provider("b", weight=1.0)]

        counts: Counter[str] = Counter()
        for _ in range(1000):
            counts[strategy.select_provider(providers).id] += 1

        assert counts["a"] > 300
        assert counts["b"] > 300


# --- Provider Registry ---


class TestProviderRegistry:
    @pytest.fixture
    def registry(self) -> ProviderRegistry:
        return ProviderRegistry()

    async def test_add_and_get(self, registry: ProviderRegistry) -> None:
        p = Provider(
            name="test",
            base_url="https://example.com",
            models=["model-a"],
        )
        registered = await registry.add_provider(p)
        assert registered.id != ""
        assert registered.name == "test"

        fetched = await registry.get_provider(registered.id)
        assert fetched is not None
        assert fetched.id == registered.id

    async def test_get_nonexistent_returns_none(self, registry: ProviderRegistry) -> None:
        assert await registry.get_provider("nonexistent") is None

    async def test_remove_provider(self, registry: ProviderRegistry) -> None:
        p = Provider(name="rm", base_url="https://x.com", models=["m"])
        registered = await registry.add_provider(p)
        assert await registry.remove_provider(registered.id) is True
        assert await registry.get_provider(registered.id) is None
        assert await registry.remove_provider(registered.id) is False

    async def test_get_providers_for_model(self, registry: ProviderRegistry) -> None:
        await registry.add_provider(
            Provider(name="a", base_url="https://x.com", models=["shared", "only-a"])
        )
        await registry.add_provider(
            Provider(name="b", base_url="https://x.com", models=["shared", "only-b"])
        )

        shared = await registry.get_providers_for_model("shared")
        assert len(shared) == 2

        only_a = await registry.get_providers_for_model("only-a")
        assert len(only_a) == 1
        assert only_a[0].name == "a"

    async def test_inactive_provider_excluded(self, registry: ProviderRegistry) -> None:
        await registry.add_provider(
            Provider(name="active", base_url="https://x.com", models=["m"], is_active=True)
        )
        await registry.add_provider(
            Provider(name="inactive", base_url="https://x.com", models=["m"], is_active=False)
        )

        providers = await registry.get_providers_for_model("m")
        assert len(providers) == 1
        assert providers[0].name == "active"

    async def test_unhealthy_provider_excluded(self, registry: ProviderRegistry) -> None:
        await registry.add_provider(
            Provider(name="healthy", base_url="https://x.com", models=["m"])
        )
        await registry.add_provider(
            Provider(
                name="sick", base_url="https://x.com", models=["m"],
                health_status="unhealthy",
            )
        )

        providers = await registry.get_providers_for_model("m")
        assert len(providers) == 1
        assert providers[0].name == "healthy"

    async def test_get_all(self, registry: ProviderRegistry) -> None:
        await registry.add_provider(
            Provider(name="a", base_url="https://x.com", models=["m"])
        )
        await registry.add_provider(
            Provider(name="b", base_url="https://x.com", models=["m"])
        )
        all_providers = await registry.get_all()
        assert len(all_providers) == 2


# --- Model Router ---


class TestModelRouter:
    async def test_route_returns_provider(self) -> None:
        registry = ProviderRegistry()
        await registry.add_provider(
            Provider(name="p", base_url="https://x.com", models=["gpt-4"])
        )
        router = ModelRouter(registry=registry, strategy=RoundRobinStrategy())
        provider = await router.route("gpt-4")
        assert provider.name == "p"

    async def test_route_unknown_model_raises_404(self) -> None:
        registry = ProviderRegistry()
        router = ModelRouter(registry=registry, strategy=RoundRobinStrategy())
        with pytest.raises(HTTPException) as exc_info:
            await router.route("nonexistent-model")
        assert exc_info.value.status_code == 404
