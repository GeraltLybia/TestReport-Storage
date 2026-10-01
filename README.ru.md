# TestReport Storage

Веб-приложение для хранения и просмотра тестовых отчетов Allure.

Это независимый продукт для хранения, просмотра и анализа тестовых отчетов, сгенерированных Allure Report, включая отчеты из экосистемы [allure-framework/allure3](https://github.com/allure-framework/allure3).

## Структура проекта
- `frontend` - приложение на Vue 3 (интерфейс управления и просмотр отчетов)
- `backend` - сервис на FastAPI (загрузка/скачивание/список/удаление отчетов, работа с history)
- `storage` - runtime-директория для отчетов и `history.jsonl`, находится в `.gitignore`


## Backend-структура
Внутренний backend-код для домена отчетов и history теперь лежит в пакете `app/services/reporting`.

Логика разделена по слоям:
- `app/services/reporting/reports.py` - сервис работы с отчетами
- `app/services/reporting/history.py` - сервис работы с `history.jsonl`
- `app/services/reporting/history_index.py` - построение и обновление `history_index.json`
- `app/services/reporting/analytics.py` - агрегаты для dashboard
- `app/services/reporting/runs.py` - прогоны, восстановленные из history index
- `app/services/coverage/` - измерение покрытия API: разбор log-вложений, сопоставление с OpenAPI и GraphQL-схемой
- `app/services/reporting/repositories/` - файловые repository-слои
- `app/services/reporting/models.py` - внутренние typed-модели

Это сделано специально, чтобы не путать кодовый пакет с runtime-папкой `storage/`.

## Документация API (Swagger/OpenAPI)
Когда backend запущен:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

В Docker-развертывании (через прокси frontend):
- Swagger UI: `http://localhost:9999/docs`
- ReDoc: `http://localhost:9999/redoc`
- OpenAPI JSON: `http://localhost:9999/openapi.json`

## Запуск через Docker
Образы собираются пайплайном CI/CD компании; Dockerfile не хранятся в этом репозитории.
Обе сборки используют корень репозитория как контекст:
- Backend: `COPY ./backend/ ./` — uvicorn на порту 8000, хранилище в `/app/storage` (`APP_STORAGE_ROOT`)
- Frontend: multi-stage `node:22` → `nginx` — UI на порту 80; `/api` и `/reports-static` проксируются на backend (при запуске UI и backend на разных хостах задаётся build-арг `VITE_API_BASE`)

Адреса в развёртывании:
- UI приложения: `http://localhost:9999`
- Backend (внутри docker-сети): `allure-storage-backend:8000`

## Локальный запуск для разработки
### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm ci
npm run dev
```

Frontend dev server: `http://localhost:5173`

## Основные возможности
Продуктовое описание со скриншотами — в [README.md](./README.md).

- Дашборд качества по истории прогонов: pass rate и риск, тренд прогонов, нестабильные тесты с полосой последних запусков, сигнатуры падений, состояние по тегам
- Фильтры дашборда по suite, environment, сигнатуре сбоя, периоду и тегам (с поиском по тегам); фильтры сохраняются в query-параметрах URL
- Панель деталей теста: последний статус, pass rate, длительность по прогонам, история запусков с ошибками
- Загрузка Allure-отчётов (`.zip`), список с поиском и фильтром по статусу, встроенный просмотр, скачивание и удаление
- Вкладка «Результаты тестов» у отчёта: упавшие и все тесты из данных самого Allure-отчёта
- Раздел «Прогоны»: прогоны, восстановленные из `history.jsonl`, постранично с сервера, с результатами тестов
- Покрытие API: REST по OpenAPI/Swagger и GraphQL по схеме (SDL или интроспекция) на основе log-вложений тестов; граф схемы в стиле GraphQL Voyager
- Загрузка/скачивание `history.jsonl`, инкрементальное обновление индекса истории
- Светлая и тёмная темы
- Автоматическая ротация отчётов по лимиту (по умолчанию храним 10 последних)
- Healthcheck endpoint: `GET /health`

## Reports API
- `GET /api/reports` - получить список загруженных Allure-отчетов с метаданными
- `POST /api/reports/upload` - загрузить новый Allure-отчет в виде `ZIP`-архива (`multipart/form-data`, поле `file`)
- `GET /api/reports/{report_id}/download` - скачать конкретный отчет как `ZIP`-архив
- `DELETE /api/reports/{report_id}` - удалить отчет по его идентификатору
- `GET /api/reports/{report_id}/results?status=incidents|changes|all|failed|broken|passed` - результаты тестов отчета из его Allure-данных (по умолчанию только failed и broken). Каждый результат сравнивается с предыдущим запуском теста в истории (`change`: `new_failure` / `still_failing` / `fixed` / `new_test`, `previous`), счетчики — в `changes`; `status=changes` оставляет новые падения и починенные тесты

## History API
- `GET /api/history` - скачать текущий `history.jsonl`
- `POST /api/history` - загрузить новый `history.jsonl`
- `GET /api/history/info` - получить метаданные `history.jsonl`
- `GET /api/history/dashboard` - получить агрегаты dashboard без скачивания всего файла
- `GET /api/history/dashboard/tests/{test_key}` - получить детали выбранного теста для dashboard
- `GET /api/history/runs?search=&status=&limit=&offset=` - постраничный список прогонов из history index
- `GET /api/history/runs/{run_uuid}/results?status=incidents|changes|all|...` - результаты тестов прогона со сравнением с предыдущим запуском
- `POST /api/history/rebuild-index` - принудительно полностью перечитать `history.jsonl` и пересобрать `history_index.json`

## Coverage API
- `GET /api/coverage` - список измерений покрытия
- `POST /api/coverage` - новое измерение (`multipart/form-data`): `kind` (`rest` | `graphql`), `spec` (файл `openapi.json` или схема GraphQL — SDL или JSON интроспекции), `report_ids` (ID отчетов через запятую), `name`, для REST — `base_path` и `host` (необязательный фильтр, несколько через запятую), для GraphQL — `endpoint`
- `GET /api/coverage/{id}` - результат измерения
- `POST /api/coverage/{id}/recalculate` - пересчитать с сохраненной спецификацией и теми же отчетами
- `DELETE /api/coverage/{id}` - удалить измерение

Как считается покрытие:
- Источник — текстовые log-вложения тестов в загруженных отчетах (`data/attachments/*.txt`), записи `api_controller`: `Запрос: METHOD URL`, `Статус код ответа: NNN`, `Запрос: "URL" <graphql-запрос> Переменные: ...`
- REST: вызов сопоставляется с шаблоном пути из спецификации с учетом base path. Хост из `servers` не используется как фильтр (генераторы часто пишут туда адрес, откуда скачали спецификацию). Если хост не задан, сервису принадлежат хосты, у которых хотя бы один запрос совпал с операцией; остальные хосты показываются отдельно
- GraphQL: запросы проверяются по схеме через `graphql-core`, учитываются поля, аргументы, фрагменты и union
- Измерение хранится снимком в `storage/coverage/<id>/` (спецификация, параметры и результат) и не меняется при загрузке новых отчетов

## Интерфейс
Адреса страниц (`http://localhost:9999` в Docker-развертывании или `http://localhost:5173` в dev-режиме):
- `/dashboard` - дашборд качества
- `/reports`, `/reports/{id}` - загруженные отчеты
- `/runs`, `/runs/{uuid}` - прогоны из истории
- `/coverage`, `/coverage/new`, `/coverage/{id}` - измерения покрытия API

Что показывает Dashboard:
- KPI: pass rate с риском, прогоны, уникальные тесты, нестабильные тесты, P95 длительности
- Тренд последних прогонов по статусам `passed / failed / broken`; клик открывает отчет или прогон
- Общая стабильность: распределение статусов и списки «всегда проходят», «всегда падают», «инциденты»
- Самые нестабильные тесты (есть и успешные, и упавшие запуски) с полосой последних 10 статусов
- Топ сигнатур падений и состояние по тегам; клик включает соответствующий фильтр
- Проблемные прогоны по загруженным отчетам

Как используются данные:
- Summary и результаты тестов отчета берутся из распакованных Allure-отчетов
- QA-метрики, тренды и прогоны строятся по агрегированному индексу `storage/history_index.json`
- `history_index.json` создается лениво при первой обработке `history.jsonl` и не требуется для старта сервиса
- При загрузке нового `history.jsonl`, если файл дописан в конец, backend обычно дочитывает только новый хвост и обновляет индекс инкрементально
- Если индекс отсутствует, поврежден или есть сомнение в консистентности, можно вызвать `POST /api/history/rebuild-index` для полного rebuild из текущего `history.jsonl`
- Если `history.jsonl` не загружен, history-based виджеты показывают пустое состояние

## Конфигурация
Переменные окружения backend:
- `APP_STORAGE_ROOT` - путь к директории хранения (по умолчанию: `storage`)
- `APP_MAX_REPORTS` - максимальное количество хранимых отчетов (по умолчанию: `10`)
- `APP_MAX_UPLOAD_SIZE_MB` - максимальный размер загружаемого ZIP (по умолчанию: `512`)
- `APP_HISTORY_MAX_FILE_SIZE_MB` - максимальный размер `history.jsonl` (по умолчанию: `100`)
- `APP_MAX_INDEXED_RUNS` - сколько последних прогонов держать в индексе истории (по умолчанию: `1000`)
- `APP_CORS_ORIGINS` - разрешенные origin через запятую, если UI и backend на разных хостах

Поведение ротации:
- После загрузки нового отчета, если общее количество превышает `APP_MAX_REPORTS`,
  автоматически удаляются самые старые директории отчетов.