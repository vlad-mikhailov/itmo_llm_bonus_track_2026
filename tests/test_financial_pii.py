"""Тесты для фильтра финансовых персональных данных."""

from __future__ import annotations

import pytest

from src.guardrails.financial_pii import (
    FinancialPIIGuardrail,
    _luhn_check,
    detect_financial_pii,
    mask_financial_pii,
)


class TestLuhnCheck:
    def test_valid_visa(self) -> None:
        assert _luhn_check("4539578763621486") is True

    def test_valid_mastercard(self) -> None:
        assert _luhn_check("5425233430109903") is True

    def test_invalid_number(self) -> None:
        assert _luhn_check("1234567890123456") is False

    def test_valid_mir(self) -> None:
        # МИР карта (начинается с 2200)
        assert _luhn_check("2200000000000000") is False  # рандомный — невалидный


class TestDetection:
    def test_detects_card_with_spaces(self) -> None:
        text = "Мой номер карты 4539 5787 6362 1486 пожалуйста"
        findings = detect_financial_pii(text)
        assert len(findings) == 1
        assert findings[0]["type"] == "bank_card"

    def test_detects_card_with_dashes(self) -> None:
        text = "Карта: 5425-2334-3010-9903"
        findings = detect_financial_pii(text)
        assert len(findings) == 1
        assert findings[0]["type"] == "bank_card"

    def test_ignores_invalid_card(self) -> None:
        text = "Число 1234567890123456 не карта"
        findings = detect_financial_pii(text)
        card_findings = [f for f in findings if f["type"] == "bank_card"]
        assert len(card_findings) == 0

    def test_detects_bank_account(self) -> None:
        text = "Счёт получателя: 40817810099910004312"
        findings = detect_financial_pii(text)
        assert any(f["type"] == "bank_account" for f in findings)

    def test_detects_snils(self) -> None:
        text = "СНИЛС: 123-456-789-01"
        findings = detect_financial_pii(text)
        assert any(f["type"] == "snils" for f in findings)

    def test_no_false_positives_on_clean_text(self) -> None:
        text = "Акции AAPL выросли на 5% за квартал, P/E = 28.4"
        findings = detect_financial_pii(text)
        assert len(findings) == 0


class TestMasking:
    def test_masks_card_number(self) -> None:
        text = "Оплата с карты 4539578763621486"
        masked, findings = mask_financial_pii(text)
        assert "4539 **** **** 1486" in masked
        assert "4539578763621486" not in masked

    def test_masks_account(self) -> None:
        text = "Перевод на 40817810099910004312"
        masked, findings = mask_financial_pii(text)
        assert "4081...4312" in masked


class TestGuardrailIntegration:
    @pytest.fixture
    def guardrail(self) -> FinancialPIIGuardrail:
        return FinancialPIIGuardrail()

    async def test_blocks_request_with_card(self, guardrail: FinancialPIIGuardrail) -> None:
        messages = [{"role": "user", "content": "Переведи на карту 4539578763621486"}]
        result = await guardrail.check_request(messages)
        assert result.passed is False
        assert "bank_card" in result.reason

    async def test_passes_clean_request(self, guardrail: FinancialPIIGuardrail) -> None:
        messages = [{"role": "user", "content": "Какой курс доллара?"}]
        result = await guardrail.check_request(messages)
        assert result.passed is True

    async def test_detects_pii_in_response(self, guardrail: FinancialPIIGuardrail) -> None:
        content = "Ваш счёт: 40817810099910004312"
        result = await guardrail.check_response(content)
        assert result.passed is False

    async def test_passes_clean_response(self, guardrail: FinancialPIIGuardrail) -> None:
        content = "Рекомендую диверсифицировать портфель"
        result = await guardrail.check_response(content)
        assert result.passed is True

    async def test_ignores_system_messages(self, guardrail: FinancialPIIGuardrail) -> None:
        messages = [
            {"role": "system", "content": "Карта 4539578763621486"},
            {"role": "user", "content": "Привет"},
        ]
        result = await guardrail.check_request(messages)
        assert result.passed is True
