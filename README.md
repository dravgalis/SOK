# HH SaaS Monorepo (MVP)

Монорепозиторий MVP SaaS-приложения для работодателей/HR с интеграцией HeadHunter API.

## Структура

```text
project/
  app/      # React + TypeScript (Vite) — интерфейс сервиса
  backend/  # FastAPI backend — API и заготовка HH OAuth
  landing/  # Простой лендинг
```

## 1) Запуск backend (FastAPI)

```bash
cd project/backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Проверка: `GET http://localhost:8000/` → `{"status": "ok"}`.

## 2) Запуск app (frontend сервиса)

```bash
cd project/app
npm install
npm run dev
```

По умолчанию: `http://localhost:5173`.

## 3) Запуск landing

```bash
cd project/landing
npm install
npm run dev
```

По умолчанию: `http://localhost:5174`.

## Примечания

- Backend использует `python-dotenv` для загрузки переменных окружения.
- OAuth для HeadHunter пока реализован в формате MVP-заглушек, чтобы быстро продолжить разработку.
