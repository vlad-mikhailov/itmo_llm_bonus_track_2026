"""In-memory provider registry with thread-safe operations."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.providers.models import Provider


class ProviderRegistry:
    """Thread-safe in-memory provider registry."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}
        self._lock = asyncio.Lock()

    async def add_provider(self, provider: Provider) -> Provider:
        """Register a provider, assigning a UUID id."""
        async with self._lock:
            new_id = uuid.uuid4().hex
            registered = provider.model_copy(update={"id": new_id})
            self._providers[new_id] = registered
            return registered

    async def remove_provider(self, provider_id: str) -> bool:
        """Remove provider by id. Returns True if found and removed."""
        async with self._lock:
            if provider_id in self._providers:
                del self._providers[provider_id]
                return True
            return False

    async def get_provider(self, provider_id: str) -> Provider | None:
        """Get provider by id."""
        async with self._lock:
            return self._providers.get(provider_id)

    async def get_providers_for_model(self, model: str) -> list[Provider]:
        """Return all active, healthy providers that serve a given model."""
        async with self._lock:
            return [
                p
                for p in self._providers.values()
                if model in p.models and p.is_active and p.health_status == "healthy"
            ]

    async def get_all(self) -> list[Provider]:
        """Return all registered providers."""
        async with self._lock:
            return list(self._providers.values())


provider_registry = ProviderRegistry()
