"""Risk Assessor Agent — оценка рисков инвестиционного портфеля.

Агент предоставляет инструменты для:
- Расчёта диверсификации портфеля
- Оценки волатильности
- Генерации рекомендаций по снижению рисков
"""

from __future__ import annotations

import json
import logging
import math
import os
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from pydantic import BaseModel

from agents.common.platform_client import PlatformClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL = os.getenv("ASSESSOR_MODEL", "deepseek/deepseek-chat")

# --- Мок-данные по волатильности и корреляциям ---

VOLATILITY_MAP: dict[str, float] = {
    "AAPL": 0.22,
    "GOOGL": 0.25,
    "SBER": 0.45,
    "GAZP": 0.52,
    "TSLA": 0.58,
    "BTC": 0.72,
    "GOLD": 0.15,
    "BONDS": 0.05,
}

SECTOR_MAP: dict[str, str] = {
    "AAPL": "tech",
    "GOOGL": "tech",
    "TSLA": "auto",
    "SBER": "finance",
    "GAZP": "energy",
    "BTC": "crypto",
    "GOLD": "commodities",
    "BONDS": "fixed_income",
}

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "assess_portfolio",
            "description": "Оценить риск портфеля: диверсификацию, волатильность, концентрацию",
            "parameters": {
                "type": "object",
                "properties": {
                    "holdings": {
                        "type": "object",
                        "description": "Словарь тикер -> доля в портфеле (от 0 до 1). Пример: {\"AAPL\": 0.4, \"SBER\": 0.6}",
                        "additionalProperties": {"type": "number"},
                    },
                },
                "required": ["holdings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_volatility",
            "description": "Показать историческую волатильность актива",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Тикер актива",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_hedging",
            "description": "Предложить инструменты хеджирования для данного портфеля",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Текущие тикеры в портфеле",
                    },
                },
                "required": ["tickers"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Ты — риск-аналитик. Оцениваешь инвестиционные портфели: "
    "диверсификацию, волатильность, концентрацию по секторам. "
    "Используй инструменты: assess_portfolio, check_volatility, suggest_hedging. "
    "Давай чёткие рекомендации по снижению рисков. "
    "Отвечай на русском. Указывай, что данные демонстрационные."
)


# --- Реализация инструментов ---


def _tool_assess_portfolio(holdings: dict[str, float]) -> str:
    total_weight = sum(holdings.values())
    if abs(total_weight - 1.0) > 0.05:
        return json.dumps(
            {"warning": f"Сумма долей = {total_weight:.2f}, ожидается ~1.0"},
            ensure_ascii=False,
        )

    # Концентрация (индекс Херфиндаля)
    hhi = sum(w ** 2 for w in holdings.values())

    # Средневзвешенная волатильность
    weighted_vol = 0.0
    unknown = []
    sectors: dict[str, float] = {}
    for ticker, weight in holdings.items():
        t = ticker.upper()
        vol = VOLATILITY_MAP.get(t)
        if vol is None:
            unknown.append(t)
            continue
        weighted_vol += weight * vol
        sec = SECTOR_MAP.get(t, "other")
        sectors[sec] = sectors.get(sec, 0) + weight

    # Уровень риска
    if weighted_vol < 0.15:
        risk_level = "низкий"
    elif weighted_vol < 0.35:
        risk_level = "средний"
    else:
        risk_level = "высокий"

    # Оценка диверсификации
    unique_sectors = len(sectors)
    if unique_sectors >= 4:
        diversification = "хорошая"
    elif unique_sectors >= 2:
        diversification = "умеренная"
    else:
        diversification = "слабая"

    result = {
        "risk_level": risk_level,
        "weighted_volatility": round(weighted_vol, 4),
        "hhi_concentration": round(hhi, 4),
        "diversification": diversification,
        "sectors": {k: round(v, 2) for k, v in sectors.items()},
        "num_assets": len(holdings),
    }
    if unknown:
        result["unknown_tickers"] = unknown

    return json.dumps(result, ensure_ascii=False, indent=2)


def _tool_check_volatility(ticker: str) -> str:
    t = ticker.upper()
    vol = VOLATILITY_MAP.get(t)
    if vol is None:
        available = ", ".join(VOLATILITY_MAP.keys())
        return json.dumps(
            {"error": f"Тикер {t} не найден. Доступные: {available}"},
            ensure_ascii=False,
        )

    if vol < 0.15:
        category = "низкая"
    elif vol < 0.35:
        category = "средняя"
    elif vol < 0.55:
        category = "высокая"
    else:
        category = "очень высокая"

    return json.dumps(
        {
            "ticker": t,
            "annualized_volatility": f"{vol * 100:.1f}%",
            "category": category,
            "daily_move_estimate": f"±{vol / math.sqrt(252) * 100:.2f}%",
        },
        ensure_ascii=False,
    )


def _tool_suggest_hedging(tickers: list[str]) -> str:
    tickers_upper = [t.upper() for t in tickers]
    sectors = {SECTOR_MAP.get(t, "other") for t in tickers_upper}

    suggestions = []

    if "fixed_income" not in sectors:
        suggestions.append({
            "instrument": "BONDS",
            "reason": "Облигации снижают общую волатильность портфеля",
        })

    if "commodities" not in sectors:
        suggestions.append({
            "instrument": "GOLD",
            "reason": "Золото — традиционный защитный актив",
        })

    has_high_vol = any(
        VOLATILITY_MAP.get(t, 0) > 0.5 for t in tickers_upper
    )
    if has_high_vol:
        suggestions.append({
            "action": "Снизить долю высоковолатильных активов",
            "reason": "В портфеле есть активы с волатильностью > 50%",
        })

    if len(sectors) < 3:
        suggestions.append({
            "action": "Добавить активы из других секторов",
            "reason": f"Портфель сконцентрирован в {len(sectors)} секторах",
        })

    if not suggestions:
        suggestions.append({"status": "Портфель выглядит сбалансированным"})

    return json.dumps(suggestions, ensure_ascii=False, indent=2)


_TOOL_HANDLERS: dict[str, Any] = {
    "assess_portfolio": lambda args: _tool_assess_portfolio(args["holdings"]),
    "check_volatility": lambda args: _tool_check_volatility(args["ticker"]),
    "suggest_hedging": lambda args: _tool_suggest_hedging(args["tickers"]),
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
        agent_name="risk-assessor",
        agent_description=(
            "Риск-аналитик: оценка портфеля, волатильность, хеджирование"
        ),
        methods=["run"],
        endpoint_url="http://risk-assessor:8002",
    )
    await _platform.register()
    yield
    await _platform.close()


app = FastAPI(title="Risk Assessor Agent", lifespan=lifespan)


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
                    {"role": "user", "content": "Проанализируй результаты и дай рекомендации."},
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
