"""Abstract guardrail interface and result model."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class GuardrailResult(BaseModel):
    passed: bool
    reason: str | None = None
    guardrail_name: str


class Guardrail(ABC):
    """Base class for request/response guardrails."""

    @abstractmethod
    async def check_request(self, messages: list[dict]) -> GuardrailResult:
        """Check incoming messages before sending to LLM."""

    @abstractmethod
    async def check_response(self, content: str) -> GuardrailResult:
        """Check LLM response before returning to client."""
