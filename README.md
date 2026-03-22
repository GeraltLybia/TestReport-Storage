# Allure Reports Storage

- English: see [README.en.md](./README.en.md)
- Русский: см. [README.ru.md](./README.ru.md)

This repository contains a production-ready split architecture:
- `frontend` (Vue 3 + Vite + Nginx)
- `backend` (FastAPI)
- `storage` (runtime data: reports and history files, ignored by git)

Backend service code uses the internal package `app/services/reporting` for report/history domain logic.

For API docs (Swagger/OpenAPI), run the backend and open:
- `/docs` (Swagger UI)
- `/redoc` (ReDoc)
- `/openapi.json` (OpenAPI spec)
