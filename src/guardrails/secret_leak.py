"""Secret leak detection guardrail for LLM responses."""

from __future__ import annotations

import logging
import re

from src.guardrails.base import Guardrail, GuardrailResult

logger = logging.getLogger(__name__)

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("api_key", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("bearer_token", re.compile(r"Bearer\s+[a-zA-Z0-9\-_.]{20,}")),
    ("aws_key", re.compile(r"AKIA[A-Z0-9]{16}")),
    ("generic_token", re.compile(r"token[=:]\s*[a-zA-Z0-9\-_.]{20,}")),
    ("password", re.compile(r"password[=:]\s*\S+")),
    ("private_key", re.compile(r"-----BEGIN[A-Z\s]*PRIVATE KEY-----")),
)

GUARDRAIL_NAME = "secret_leak"


def mask_secrets(text: str) -> tuple[str, list[str]]:
    """Replace detected secrets with [REDACTED]. Returns masked text and list of detections."""
    detections: list[str] = []
    masked = text
    for secret_type, pattern in _SECRET_PATTERNS:
        matches = pattern.findall(masked)
        for match in matches:
            detections.append(f"{secret_type}: {match[:8]}...")
            masked = masked.replace(match, "[REDACTED]")
    return masked, detections


class SecretLeakGuardrail(Guardrail):
    """Detect and mask secrets leaked in LLM responses."""

    async def check_request(self, messages: list[dict]) -> GuardrailResult:
        return GuardrailResult(passed=True, guardrail_name=GUARDRAIL_NAME)

    async def check_response(self, content: str) -> GuardrailResult:
        _masked, detections = mask_secrets(content)
        if detections:
            logger.warning("Secret leak detected in response: %s", detections)
            return GuardrailResult(
                passed=False,
                reason=f"Secrets detected: {', '.join(detections)}",
                guardrail_name=GUARDRAIL_NAME,
            )
        return GuardrailResult(passed=True, guardrail_name=GUARDRAIL_NAME)
