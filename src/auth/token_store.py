"""In-memory token store for Bearer authentication."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.config import settings
from src.registry.agent_registry import agent_registry


@dataclass(frozen=True)
class TokenInfo:
    token: str
    agent_id: str | None
    is_master: bool


async def validate_token(token: str) -> TokenInfo | None:
    """Validate a bearer token against master token and agent registry.

    Returns TokenInfo if valid, None otherwise.
    """
    if settings.MASTER_TOKEN and token == settings.MASTER_TOKEN:
        return TokenInfo(token=token, agent_id=None, is_master=True)

    agents = await agent_registry.list_agents()
    for agent in agents:
        if agent.token == token:
            return TokenInfo(token=token, agent_id=agent.id, is_master=False)

    return None
