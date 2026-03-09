# Allure Reports Storage

Веб-приложение для хранения и просмотра тестовых отчетов Allure.

## Структура проекта
- `frontend` - приложение на Vue 3 (интерфейс управления и просмотр отчетов)
- `backend` - сервис на FastAPI (загрузка/скачивание/список/удаление отчетов, работа с history)
- `storage` - постоянное хранилище отчетов и `history.jsonl`
- `docker-compose.yml` - orchestration контейнеров для production-like запуска

## Документация API (Swagger/OpenAPI)
Когда backend запущен:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

В Docker-развертывании (через прокси frontend):
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`
- OpenAPI JSON: `http://localhost:8080/openapi.json`

## Запуск через Docker (Рекомендуется)
```bash
cd /Users/zaharpirozenko/Documents/allure3_folder
docker compose up --build
```

Адреса:
- UI приложения: `http://localhost:8080`
- Backend (внутри docker-сети): `backend:8000`

Остановка:
```bash
docker compose down
```

## Локальный запуск для разработки
### Backend
```bash
cd /Users/zaharpirozenko/Documents/allure3_folder/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd /Users/zaharpirozenko/Documents/allure3_folder/frontend
npm ci
npm run dev
```

Frontend dev server: `http://localhost:5173`

## Основные возможности
- Загрузка архивов отчетов Allure (`.zip`)
- Просмотр списка загруженных отчетов
- Встроенный просмотр отчетов в iframe
- Скачивание и удаление отчетов
- Загрузка/скачивание `history.jsonl`
- Автоматическая ротация отчетов по лимиту (по умолчанию храним 10 последних)
- Healthcheck endpoint: `GET /health`

## Конфигурация
Переменные окружения backend:
- `APP_STORAGE_ROOT` - путь к директории хранения (по умолчанию: `storage`)
- `APP_MAX_REPORTS` - максимальное количество хранимых отчетов (по умолчанию: `10`)

Поведение ротации:
- После загрузки нового отчета, если общее количество превышает `APP_MAX_REPORTS`,
  автоматически удаляются самые старые директории отчетов.
