# SOK — структура проекта и как мы работаем

Этот README написан как «карта проекта» для нового человека в команде.
Если коротко: у нас **монорепозиторий**, в котором есть backend на **FastAPI** и несколько фронтов на **React + Vite + TypeScript**.

---

## 1) Что это за репозиторий

SOK — это монорепо, где лежат:

- backend API (Python/FastAPI);
- клиентское приложение (кабинет работодателя);
- админка;
- лендинг;
- а также часть legacy/MVP-структуры в корне (`app/`, `frontend/`).

---

## 2) Технологический стек

### Backend

- **Python 3**
- **FastAPI**
- **Uvicorn**
- **SQLAlchemy**
- **psycopg (PostgreSQL driver)**
- **python-dotenv**
- **httpx** (запросы во внешние API, например HH)

См. зависимости: `project/backend/requirements.txt`.

### Frontend (приложение + админка)

- **React 18**
- **TypeScript**
- **Vite**
- **react-router-dom**

См. зависимости: `project/app/package.json`, `project/admin/package.json`.

### Landing

- **Vite** + статическая верстка (HTML/CSS).

См. `project/landing/package.json`.

---

## 3) Актуальная структура папок (верхнеуровнево)

```text
SOK/
├── README.md
├── requirements.txt                # Общие python-зависимости (если используются локально)
├── .env.example
│
├── project/                        # Основная актуальная структура продукта
│   ├── backend/                    # FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py             # Точка входа API
│   │   │   ├── api/                # Роуты (auth/admin/...)
│   │   │   ├── core/               # Конфиг, БД, базовые сервисы
│   │   │   ├── models/             # ORM-модели (по мере развития)
│   │   │   ├── schemas/            # Pydantic-схемы (по мере развития)
│   │   │   └── services/           # Интеграции и бизнес-логика (HH OAuth, клиенты)
│   │   ├── requirements.txt
│   │   └── .env.example
│   │
│   ├── app/                        # Основной frontend (кабинет/интерфейс продукта)
│   │   ├── src/
│   │   │   ├── main.tsx            # Вход в React-приложение
│   │   │   ├── AppRouter.tsx       # Маршрутизация
│   │   │   ├── pages/              # Страницы (Login, Dashboard, VacancyDetails...)
│   │   │   ├── config.ts           # Константы/URL/роуты фронта
│   │   │   └── styles.css          # Базовые стили
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   ├── admin/                      # Админ-панель
│   │   ├── src/
│   │   │   ├── main.tsx
│   │   │   ├── AppRouter.tsx
│   │   │   ├── pages/              # AdminLogin, Dashboard, user details и т.п.
│   │   │   ├── config.ts
│   │   │   └── styles.css
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   └── landing/                    # Лендинг
│       ├── index.html
│       ├── styles.css
│       ├── public/images/
│       └── package.json
│
├── app/                            # Legacy backend/MVP-слой (исторически)
│   ├── main.py
│   ├── api/
│   ├── core/
│   └── services/
│
└── frontend/                       # Legacy frontend для HH-логина/колбэка (исторически)
    ├── src/
    │   ├── AppRouter.tsx
    │   ├── pages/
    │   ├── components/
    │   ├── config/
    │   └── types/
    └── ...
```

---

## 4) Что за что отвечает (по-простому)

### `project/backend`

Серверная часть. Здесь:

- принимаются запросы от фронтов;
- реализуются auth/admin endpoint’ы;
- живет интеграция с HeadHunter (OAuth/HTTP-клиенты);
- инициализируется таблица пользователей и конфигурация приложения.

Главная точка входа: `project/backend/app/main.py`.

### `project/app`

Основное клиентское приложение (кабинет пользователя/работодателя).

- роуты и экран логина;
- дашборд;
- просмотр деталей вакансии.

Точка входа: `project/app/src/main.tsx`.

### `project/admin`

Отдельный фронт для административных задач.

- вход администратора;
- админ-дашборд;
- страницы деталей пользователей/откликов.

Точка входа: `project/admin/src/main.tsx`.

### `project/landing`

Публичный маркетинговый лендинг продукта.

### `app/` и `frontend/` в корне

Это **исторические (legacy/MVP) директории**, которые частично дублируют backend/frontend-логику.
Их держим для совместимости и миграции, но для новой разработки ориентируемся в первую очередь на `project/*`.

---

## 5) Ветки и workflow (как мы работаем)

На текущий момент в локальном репозитории есть рабочая ветка:

- `work` — активная ветка разработки.

Рекомендуемый рабочий процесс:

1. Берем актуальную базовую ветку (`work` или `main`, если появится).
2. Создаем задачу в отдельной ветке:
   - `feature/<short-name>` — новая функциональность;
   - `fix/<short-name>` — багфикс;
   - `chore/<short-name>` — техдолг/рефактор/документация.
3. Делаем PR обратно в базовую ветку команды.
4. После ревью — merge.

Если команда официально введет `main/develop`, этот README можно обновить под финальную стратегию.

---

## 6) Быстрый запуск по сервисам

### Backend

```bash
cd project/backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Проверка: `GET http://localhost:8000/` → `{"status": "ok"}`.

### Frontend (основное приложение)

```bash
cd project/app
npm install
npm run dev
```

### Admin panel

```bash
cd project/admin
npm install
npm run dev
```

### Landing

```bash
cd project/landing
npm install
npm run dev
```

---

## 7) Правило ориентации по коду

Если не знаете, где менять код:

- API / интеграции / серверная логика → `project/backend`;
- пользовательский интерфейс продукта → `project/app`;
- админский интерфейс → `project/admin`;
- маркетинговые страницы → `project/landing`;
- legacy-правки делаем в `app` и `frontend` только если это специально требуется задачей.
