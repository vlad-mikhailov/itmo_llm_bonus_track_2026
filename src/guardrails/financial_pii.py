"""Фильтр финансовых персональных данных.

Обнаруживает и маскирует:
- Номера банковских карт (Luhn-валидация)
- ИНН (10 и 12 цифр)
- Номера счетов
- СНИЛС
"""

from __future__ import annotations

import logging
import re

from src.guardrails.base import Guardrail, GuardrailResult

logger = logging.getLogger(__name__)

GUARDRAIL_NAME = "financial_pii"


def _luhn_check(digits: str) -> bool:
    """Проверка номера карты по алгоритму Луна."""
    nums = [int(d) for d in digits]
    nums.reverse()
    total = 0
    for i, n in enumerate(nums):
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


_CARD_PATTERN = re.compile(r"\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b")
_INN_PATTERN = re.compile(r"\b(\d{10}|\d{12})\b")
_ACCOUNT_PATTERN = re.compile(r"\b(40[0-9]{18}|30[0-9]{18})\b")  # расчётные/корр. счета РФ
_SNILS_PATTERN = re.compile(r"\b(\d{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2})\b")


def detect_financial_pii(text: str) -> list[dict[str, str]]:
    """Найти финансовые персональные данные в тексте."""
    findings: list[dict[str, str]] = []

    for match in _CARD_PATTERN.finditer(text):
        raw = match.group(1)
        digits = re.sub(r"[\s\-]", "", raw)
        if len(digits) == 16 and _luhn_check(digits):
            findings.append({
                "type": "bank_card",
                "value": raw,
                "masked": f"{digits[:4]} **** **** {digits[-4:]}",
            })

    for match in _ACCOUNT_PATTERN.finditer(text):
        val = match.group(1)
        findings.append({
            "type": "bank_account",
            "value": val,
            "masked": f"{val[:4]}...{val[-4:]}",
        })

    for match in _SNILS_PATTERN.finditer(text):
        raw = match.group(1)
        digits = re.sub(r"[\s\-]", "", raw)
        if len(digits) == 11:
            findings.append({
                "type": "snils",
                "value": raw,
                "masked": "***-***-*** **",
            })

    return findings


def mask_financial_pii(text: str) -> tuple[str, list[dict[str, str]]]:
    """Замаскировать найденные данные. Возвращает (маскированный текст, список находок)."""
    findings = detect_financial_pii(text)
    masked = text
    for f in findings:
        masked = masked.replace(f["value"], f["masked"])
    return masked, findings


class FinancialPIIGuardrail(Guardrail):
    """Обнаружение финансовых персональных данных в запросах и ответах."""

    async def check_request(self, messages: list[dict]) -> GuardrailResult:
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            findings = detect_financial_pii(content)
            if findings:
                types = ", ".join(f["type"] for f in findings)
                return GuardrailResult(
                    passed=False,
                    reason=f"Обнаружены финансовые ПДн в запросе: {types}",
                    guardrail_name=GUARDRAIL_NAME,
                )
        return GuardrailResult(passed=True, guardrail_name=GUARDRAIL_NAME)

    async def check_response(self, content: str) -> GuardrailResult:
        _, findings = mask_financial_pii(content)
        if findings:
            types = ", ".join(f["type"] for f in findings)
            logger.warning("Финансовые ПДн в ответе LLM: %s", types)
            return GuardrailResult(
                passed=False,
                reason=f"Обнаружены финансовые ПДн в ответе: {types}",
                guardrail_name=GUARDRAIL_NAME,
            )
        return GuardrailResult(passed=True, guardrail_name=GUARDRAIL_NAME)
