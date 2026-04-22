# AI Adventure Guide

Персональный туристический AI-агент с культурным и историческим контекстом, работающий через Telegram.

---

## Задача и боль

Туристические приложения дают поверхностную информацию: часы работы, адрес, пара фактов. Путешественник не понимает культурного контекста места, не знает что спросить, не получает персонализированных рекомендаций. Гид-человек стоит дорого, а Google выдаёт одно и то же всем подряд.

**Для кого:** самостоятельные путешественники, которые хотят глубже понять места, а не просто "поставить галочку".

---

## Что умеет агент

- **RAG по Wikivoyage** — отвечает на вопросы о местах, используя базу знаний из Wikivoyage через FAISS-индекс
- **Распознавание фото** — пользователь отправляет фото достопримечательности, агент определяет место и рассказывает о нём
- **Погода в реальном времени** — при вопросе "какая погода в Токио?" подтягивает актуальные данные из OpenWeatherMap
- **Wikipedia fallback** — если FAISS не нашёл релевантного контекста, дополнительно ищет в Wikipedia
- **Память пользователя** — помнит историю диалога, позволяет задавать follow-up вопросы ("а что там ещё посмотреть?")
- **Команда /forget** — полное удаление профиля и истории по запросу пользователя
- **Guardrails** — блокирует prompt injection и off-topic запросы, пропускает follow-up вопросы
- **Structured logging** — логирует latency каждого этапа, FAISS score, intent, использование Wikipedia/Weather

---

## Архитектура

```
Пользователь (Telegram)
   текст или фото
        ↓
[Telegram Bot] — aiogram, принимает сообщения, передаёт user_id
        ↓
[RAG API] — FastAPI (http://travel-rag-app:8001)
        ↓
[Guardrails] — prompt injection + off-topic фильтр
        ↓
[Query Rewriter] — LLM анализирует intent, извлекает entities
        ↓
[Tool Router] — решает какие инструменты нужны
   ├── FAISS Retriever (Wikivoyage)    — основной источник
   ├── Wikipedia API                    — fallback при низком FAISS score
   ├── OpenWeatherMap API               — текущая погода
   └── Vision Model (Multimodal LLM)   — распознавание фото
        ↓
[Generator] — синтезирует ответ из контекста + истории диалога
        ↓
[Memory Manager] — сохраняет в профиль пользователя (SHA-256)
        ↓
Ответ → Пользователь
```

---

## Структура проекта

```
ai-adventure-guide/
├── README.md
├── LICENSE
├── docs/
│   ├── governance.md            # риски, логи, безопасность, PII
│   └── product-proposal.md      # метрики, сценарии, ограничения
└── ai_guide/
    ├── .env.example             # шаблон переменных окружения
    ├── docker-compose.yaml
    ├── data/                    # FAISS-индекс и чанки (скачать отдельно)
    ├── rag-app/                 # RAG-сервис (FastAPI)
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   └── src/
    │       ├── api.py               # /answer, /answer-image, /forget, /health
    │       ├── rag_pipeline.py      # основной pipeline
    │       ├── guardrails.py        # prompt injection + off-topic
    │       ├── memory.py            # история диалога по user_id
    │       ├── generation/
    │       │   └── generator.py     # LLM генерация через OpenRouter
    │       ├── preprocessing/
    │       │   ├── question_understanding.py  # LLM анализ intent
    │       │   └── pixtral_parser.py          # парсинг JSON от vision-модели
    │       ├── retrieval/
    │       │   ├── retriever.py     # FAISS поиск с scores
    │       │   ├── embedder.py      # sentence-transformers эмбеддинги
    │       │   └── build_index.py   # скрипт построения индекса
    │       └── tools/
    │           ├── weather.py       # OpenWeatherMap API
    │           └── wikipedia.py     # Wikipedia API fallback
    └── telegram-bot/            # Telegram-бот (aiogram)
        ├── Dockerfile
        ├── requirements.txt
        └── bot.py               # /start, /forget, обработка текста и фото
```

---

## Быстрый старт

### Требования

- Docker и Docker Compose
- API-ключ [OpenRouter](https://openrouter.ai/keys)
- Telegram-бот (создать через [@BotFather](https://t.me/BotFather))
- *(опционально)* API-ключ [OpenWeatherMap](https://openweathermap.org/api) — бесплатный тариф

### 1. Скачать data-файлы

FAISS-индекс и эмбеддинги Wikivoyage не хранятся в Git из-за размера. Скачайте их с Google Drive:

**→ [Скачать data-файлы (Google Drive)](https://drive.google.com/drive/folders/1jJWPumvpW9k0c80gB8_sjZABgVnwHA4d?usp=sharing)**

После скачивания положите файлы в папку `ai_guide/data/`:

```
ai_guide/data/
├── wikivoyage.index       # FAISS-индекс (векторный поиск)
├── embeddings.npy         # numpy-массив эмбеддингов
├── chunked_texts.pkl      # pickle со списком текстовых чанков
└── metadata.json          # метаданные чанков
```

### 2. Создать .env файл

```bash
cd ai_guide
cp .env.example .env
```

Заполните `.env`:

```
OPENROUTER_API_KEY=sk-or-ваш-ключ
TELEGRAM_BOT_TOKEN=1234567890:AAF-ваш-токен-от-botfather
OPENWEATHER_API_KEY=ваш-ключ-openweathermap  # опционально
```

### 3. Запустить

```bash
cd ai_guide
docker compose up -d --build
```

Первый запуск займёт 5-10 минут (скачивание зависимостей и модели эмбеддингов).

### 4. Проверить

```bash
# Статус контейнеров
docker compose ps

# Health check
curl http://localhost:8001/health

# Тестовый запрос
curl -X POST http://localhost:8001/answer \
  -H "Content-Type: application/json" \
  -d '{"text": "Best time to visit Japan?", "user_id": "test"}'
```

После этого откройте бота в Telegram и напишите ему любой вопрос о путешествиях.

---

## API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/answer` | Текстовый вопрос (JSON: `text`, `user_id`) |
| POST | `/answer-image` | Фото + подпись (multipart: `file`, `caption`, `user_id`) |
| POST | `/forget` | Удалить профиль пользователя (JSON: `user_id`) |
| GET | `/health` | Проверка состояния сервиса |

---

## Что НЕ делает PoC (out-of-scope)

- Не бронирует отели, билеты, экскурсии
- Не поддерживает голосовые сообщения
- Не поддерживает групповые чаты
- Не имеет веб-интерфейса — только Telegram
- Не покрывает все страны и города (база знаний ограничена Wikivoyage)
- Маршруты строятся по популярным местам из базы знаний — не учитывают личный транспорт и часы работы в реальном времени

---

## Стек

Python 3.11, FastAPI, aiogram, sentence-transformers, FAISS, OpenRouter (DeepSeek, Gemini), OpenWeatherMap API, Wikipedia API, Docker Compose

---

## Документация

- [Product Proposal](docs/product-proposal.md) — метрики, сценарии использования, архитектура
- [Governance](docs/governance.md) — риски, логирование, работа с ПДн, защита от инъекций

