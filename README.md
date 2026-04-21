# FinOps AI Gateway

Платформа-шлюз для финансовых AI-агентов с балансировкой LLM-провайдеров, реестром агентов, телеметрией и защитой данных.

## Архитектура

```
┌─────────────────┐     ┌─────────────────┐
│  Market Analyst │     │  Risk Assessor  │
│     Agent       │     │     Agent       │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌───────────────────────┐
         │   FinOps AI Gateway   │
         │                       │
         │  ┌─────────────────┐  │
         │  │   Auth (Bearer) │  │
         │  ├─────────────────┤  │
         │  │   Guardrails    │  │
         │  │  • Prompt Inj.  │  │
         │  │  • Secret Leak  │  │
         │  │  • Financial PII│  │
         │  ├─────────────────┤  │
         │  │   Балансировщик  │  │
         │  │  • Round Robin  │  │
         │  │  • Weighted     │  │
         │  │  • Latency-based│  │
         │  │  • Cost-aware   │  │
         │  ├─────────────────┤  │
         │  │ Circuit Breaker │  │
         │  └─────────────────┘  │
         └───────────┬───────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │Provider │ │Provider │ │Provider │
    │(OpenAI) │ │(DeepSeek)│ │(Gemini) │
    └─────────┘ └─────────┘ └─────────┘
```

## Компоненты

### Gateway (основной сервис)

FastAPI-приложение, которое проксирует запросы к LLM-провайдерам через OpenAI-совместимый API (`/v1/chat/completions`).

**Балансировщик** поддерживает 4 стратегии:
- **Round Robin** — циклическое распределение между провайдерами
- **Weighted** — распределение по статическим весам
- **Latency-based** — приоритет провайдеру с наименьшей задержкой (EMA)
- **Cost-aware** — приоритет самому дешёвому провайдеру по цене за токен

**Circuit Breaker** отключает провайдера при накоплении ошибок (closed → open → half-open).

**Guardrails** — три уровня защиты:
- Обнаружение prompt injection в запросах
- Маскирование утечек секретов (API-ключи, токены) в ответах
- Обнаружение финансовых ПДн (номера карт с Luhn-валидацией, банковские счета, СНИЛС)

### Агенты

**Market Analyst** — финансовый аналитик с инструментами:
- `get_quote` — котировка акции по тикеру
- `compare_stocks` — сравнение нескольких акций
- `sector_overview` — обзор акций по сектору

**Risk Assessor** — риск-аналитик:
- `assess_portfolio` — оценка диверсификации и волатильности портфеля (индекс Херфиндаля)
- `check_volatility` — историческая волатильность актива
- `suggest_hedging` — рекомендации по хеджированию

### Наблюдаемость

- **OpenTelemetry** — трейсинг каждого HTTP-запроса
- **Prometheus** — метрики: requests total, duration (p50/p95), TTFT, TPOT, токены, стоимость
- **Grafana** — дашборды с визуализацией метрик
- **Langfuse** — LLM-специфичный трейсинг (промпты, ответы, стоимость)

## Быстрый старт

### Требования
- Docker и Docker Compose
- API-ключ OpenRouter (или другого LLM-провайдера)

### Запуск

```bash
# Создать docker-сеть
docker network create finops-net

# Скопировать конфигурацию
cp .env.example .env
# Вписать OPENROUTER_API_KEY и MASTER_TOKEN в .env

# Запустить все сервисы
docker compose up -d
```

### Проверка

```bash
# Health check
curl http://localhost:8000/health

# Запрос к LLM через Gateway
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $MASTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek/deepseek-chat",
    "messages": [{"role": "user", "content": "Привет!"}]
  }'
```

### Доступ к сервисам

| Сервис   | URL                    |
|----------|------------------------|
| Gateway  | http://localhost:8000  |
| Grafana  | http://localhost:3002  |
| Langfuse | http://localhost:3001  |
| Prometheus | http://localhost:9090 |

## API

### POST /v1/chat/completions
OpenAI-совместимый endpoint. Поддерживает streaming (SSE).

### POST /v1/embeddings
Генерация эмбеддингов.

### GET /agents — список зарегистрированных агентов
### POST /agents — регистрация нового агента
### GET /agents/{id} — карточка агента
### DELETE /agents/{id} — удаление агента

### GET /providers — список провайдеров
### POST /providers — регистрация провайдера
### DELETE /providers/{id} — удаление провайдера

### GET /health — проверка состояния
### GET /metrics — метрики Prometheus

## Тестирование

```bash
# Unit-тесты
pip install -e ".[dev]"
pytest tests/ -v

# Нагрузочные тесты (Locust)
cd loadtests
pip install -r requirements.txt
locust -f locustfile.py --host http://localhost:8000
```

## Стек

Python 3.12, FastAPI, httpx, Pydantic, OpenTelemetry, Prometheus, Grafana, Langfuse, Docker Compose, Locust
