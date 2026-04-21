"""Provider data models."""

from __future__ import annotations

from pydantic import BaseModel


class ProviderPricing(BaseModel):
    input: float  # $ per 1M tokens
    output: float  # $ per 1M tokens


class Provider(BaseModel):
    id: str = ""  # assigned on registration
    name: str
    base_url: str  # e.g. https://openrouter.ai/api/v1
    api_key: str = ""  # if empty, use platform's OPENROUTER_API_KEY
    models: list[str]  # e.g. ["deepseek/deepseek-chat"]
    weight: float = 1.0
    priority: int = 0
    pricing: ProviderPricing | None = None
    health_status: str = "healthy"  # healthy/degraded/unhealthy
    is_active: bool = True
