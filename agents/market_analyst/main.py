"""Market Analyst Agent — анализ акций и финансовых инструментов.

Агент предоставляет инструменты для:
- Получения котировок (мок-данные)
- Сравнения финансовых инструментов
- Расчёта базовых метрик (P/E, дивидендная доходность)
"""

from __future__ import annotations

import json
import logging
import os
import random
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from pydantic import BaseModel

from agents.common.platform_client import PlatformClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL = os.getenv("ANALYST_MODEL", "deepseek/deepseek-chat")

# --- Мок-данные по акциям ---

MOCK_STOCKS: dict[str, dict[str, Any]] = {
    "AAPL": {
        "name": "Apple Inc.",
        "price": 178.52,
        "currency": "USD",
        "pe_ratio": 28.4,
        "dividend_yield": 0.55,
        "market_cap_b": 2780,
        "sector": "Technology",
        "change_1d": 1.23,
        "change_1m": -2.15,
        "change_1y": 12.8,
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "price": 141.80,
        "currency": "USD",
        "pe_ratio": 24.1,
        "dividend_yield": 0.0,
        "market_cap_b": 1760,
        "sector": "Technology",
        "change_1d": -0.45,
        "change_1m": 3.22,
        "change_1y": 18.5,
    },
    "SBER": {
        "name": "Сбербанк",
        "price": 295.60,
        "currency": "RUB",
        "pe_ratio": 4.2,
        "dividend_yield": 12.1,
        "market_cap_b": 6650,
        "sector": "Financials",
        "change_1d": 0.78,
        "change_1m": 5.40,
        "change_1y": 45.2,
    },
    "GAZP": {
        "name": "Газпром",
        "price": 148.30,
        "currency": "RUB",
        "pe_ratio": 3.1,
        "dividend_yield": 0.0,
        "market_cap_b": 3510,
        "sector": "Energy",
        "change_1d": -1.10,
        "change_1m": -4.80,
        "change_1y": -15.3,
    },
    "TSLA": {
        "name": "Tesla Inc.",
        "price": 245.90,
        "currency": "USD",
        "pe_ratio": 62.7,
        "dividend_yield": 0.0,
        "market_cap_b": 782,
        "sector": "Consumer Discretionary",
        "change_1d": 3.45,
        "change_1m": 8.90,
        "change_1y": -5.2,
    },
}

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_quote",
            "description": "Получить текущую котировку акции по тикеру",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Тикер акции, например AAPL, SBER",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_stocks",
            "description": "Сравнить несколько акций по ключевым метрикам",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список тикеров для сравнения",
                    },
                },
                "required": ["tickers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sector_overview",
            "description": "Показать обзор акций по выбранному сектору",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {
                        "type": "string",
                        "description": "Сектор: Technology, Financials, Energy, Consumer Discretionary",
                    },
                },
                "required": ["sector"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Ты — финансовый аналитик. Помогаешь пользователям анализировать акции, "
    "сравнивать инструменты и оценивать рыночные данные. "
    "Используй доступные инструменты: get_quote (котировка), "
    "compare_stocks (сравнение), sector_overview (обзор сектора). "
    "Отвечай на русском языке, давай краткие но информативные ответы. "
    "Обязательно указывай, что данные являются демонстрационными."
)


# --- Реализация инструментов ---


def _tool_get_quote(ticker: str) -> str:
    ticker = ticker.upper()
    stock = MOCK_STOCKS.get(ticker)
    if not stock:
        available = ", ".join(MOCK_STOCKS.keys())
        return json.dumps(
            {"error": f"Тикер {ticker} не найден. Доступные: {available}"},
            ensure_ascii=False,
        )
    return json.dumps(
        {"ticker": ticker, **stock},
        ensure_ascii=False,
    )


def _tool_compare_stocks(tickers: list[str]) -> str:
    results = []
    for t in tickers:
        t = t.upper()
        stock = MOCK_STOCKS.get(t)
        if stock:
            results.append({
                "ticker": t,
                "name": stock["name"],
                "price": f"{stock['price']} {stock['currency']}",
                "P/E": stock["pe_ratio"],
                "div_yield": f"{stock['dividend_yield']}%",
                "change_1y": f"{stock['change_1y']}%",
            })
        else:
            results.append({"ticker": t, "error": "не найден"})

    return json.dumps(results, ensure_ascii=False, indent=2)


def _tool_sector_overview(sector: str) -> str:
    matches = [
        {"ticker": t, "name": s["name"], "price": s["price"], "pe_ratio": s["pe_ratio"]}
        for t, s in MOCK_STOCKS.items()
        if s["sector"].lower() == sector.lower()
    ]
    if not matches:
        return json.dumps(
            {"error": f"Сектор '{sector}' не найден или пуст"},
            ensure_ascii=False,
        )
    return json.dumps(matches, ensure_ascii=False, indent=2)


_TOOL_HANDLERS: dict[str, Any] = {
    "get_quote": lambda args: _tool_get_quote(args["ticker"]),
    "compare_stocks": lambda args: _tool_compare_stocks(args["tickers"]),
    "sector_overview": lambda args: _tool_sector_overview(args["sector"]),
}


_platform: PlatformClient | None = None
_sessions: dict[str, list[dict[str, Any]]] = {}
_MAX_TOOL_ROUNDS = 5


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _platform  # noqa: PLW0603

    _platform = PlatformClient(
        platform_url=os.getenv("PLATFORM_URL", "http://app:8000"),
        master_token=os.getenv("MASTER_TOKEN", ""),
        agent_name="market-analyst",
        agent_description=(
            "Финансовый аналитик: котировки, сравнение акций, обзор секторов"
        ),
        methods=["run"],
        endpoint_url="http://market-analyst:8001",
    )
    await _platform.register()
    yield
    await _platform.close()


app = FastAPI(title="Market Analyst Agent", lifespan=lifespan)


class RunRequest(BaseModel):
    message: str
    session_id: str | None = None


class RunResponse(BaseModel):
    response: str
    session_id: str
    tools_used: list[str]


def _execute_tool(name: str, arguments: dict[str, Any]) -> str:
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Неизвестный инструмент: {name}"})
    result = handler(arguments)
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


@app.post("/run", response_model=RunResponse)
async def run(body: RunRequest) -> RunResponse:
    assert _platform is not None  # noqa: S101

    session_id = body.session_id or str(uuid.uuid4())

    if session_id not in _sessions:
        _sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    _sessions[session_id].append({"role": "user", "content": body.message})

    tools_used: list[str] = []

    for _round in range(_MAX_TOOL_ROUNDS):
        result: dict[str, Any] = await _platform.chat(
            messages=_sessions[session_id],
            model=MODEL,
            tools=TOOLS_SPEC,
        )

        choice = result["choices"][0]
        message = choice["message"]

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            content = message.get("content") or ""
            if not content.strip() and tools_used:
                _sessions[session_id].append(
                    {"role": "user", "content": "Сделай выводы на основе данных инструментов."},
                )
                continue
            _sessions[session_id].append({"role": "assistant", "content": content})
            return RunResponse(
                response=content,
                session_id=session_id,
                tools_used=tools_used,
            )

        _sessions[session_id].append(message)

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"])
            tools_used.append(fn_name)

            tool_result = _execute_tool(fn_name, fn_args)

            _sessions[session_id].append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })

    return RunResponse(
        response="Превышен лимит раундов обработки.",
        session_id=session_id,
        tools_used=tools_used,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
