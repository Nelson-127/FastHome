# Fast Home Tbilisi — Telegram + API

Сервис заявок на подбор жилья: бот (aiogram) → REST API (FastAPI) → PostgreSQL. Оплата: **либо ручной перевод (IBAN)**, **либо TBC tpay** при `TBC_ENABLED=true`.

## Требования

- Python 3.12+
- PostgreSQL 14+
- Переменные окружения (см. `.env.example`)

## Быстрый старт (локально)

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Отредактируйте .env: BOT_TOKEN, DATABASE_URL, ADMIN_IDS, пароль админки
```

Создайте БД и примените таблицы при первом запуске API (создаются автоматически в `lifespan`).

**Терминал 1 — API:**

```bash
export PYTHONPATH=.
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**Терминал 2 — бот:**

```bash
export PYTHONPATH=.
python main.py
```

Или: `python -m bot.main`.

### Ошибка `TelegramConflictError` / «only one bot instance»

Telegram разрешает **один** активный способ получения апдейтов на токен:

1. **Два процесса с `main.py`** (два терминала, Docker + локально, фоновый процесс) — оставьте только один: `ps aux | grep main.py` / Activity Monitor / остановите лишний контейнер.
2. **У бота был включён webhook** (хостинг, тесты, BotFather) — при старте бот вызывает `delete_webhook`. Если конфликт остаётся, проверьте п.1.
3. **Режим в проде:** либо везде **polling** (этот проект по умолчанию), либо везде **webhook** — не смешивайте на одном токене.

## Docker

```bash
cp .env.example .env
# Заполните BOT_TOKEN, ADMIN_IDS, INTERNAL_API_KEY, скорректируйте DATABASE_URL под сервис db
docker compose up --build
```

API: `http://localhost:8000`, документация: `/docs`. Бот использует `BACKEND_BASE_URL` (в compose — `http://api:8000`).

## Релиз (чеклист)

1. **Секреты**: только в `.env` или секретах оркестратора; `.env` в `.gitignore`.
2. **`INTERNAL_API_KEY`**: задать в проде; бот шлёт заголовок `X-Internal-Key`.
3. **`ADMIN_PASSWORD`**: надёжный пароль для Basic auth (`/admin`, `/admin/ui`).
4. **HTTPS**: публичный URL для API; для TBC — валидный `TBC_CALLBACK_URL`.
5. **PostgreSQL**: бэкапы, `DATABASE_URL` с SSL при необходимости.
6. **Логи**: stdout; при деплое подключите сбор логов.
7. **TBC**: пока выключено (`TBC_ENABLED=false`); включение — `docs/TBC_SETUP.md`.

## Структура

- `bot/` — только UI и HTTP к backend
- `backend/` — FastAPI, бизнес-логика
- `database/` — SQLAlchemy модели
- `payments/tbc/` — интеграция TBC (активна при `TBC_ENABLED=true`)
- `parsing/` — парсинг объявлений, планировщик
- `admin_panel/` — простая HTML-админка
- `translations/` — строки интерфейса




# uvicorn

uvicorn backend.main:app

uvicorn backend.main:app --reload 

uvicorn backend.main:app --reload --reload-dir backend

uvicorn backend.main:app --reload --reload-exclude ".venv"

uvicorn backend.main:app --reload --reload-exclude __pycache__ --reload-exclude *.pyc

# tg bot

python3 main.py

# database


psql postgres 

\c fast_home
