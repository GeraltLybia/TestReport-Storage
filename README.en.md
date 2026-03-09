# Allure Reports Storage

Web application for storing and viewing Allure test reports.

## Project Structure
- `frontend` - Vue 3 application (UI for report management and viewer)
- `backend` - FastAPI service (upload/download/list/delete reports, history management)
- `storage` - persistent report files and `history.jsonl`
- `docker-compose.yml` - production-like container orchestration

## API Documentation (Swagger/OpenAPI)
When backend is running:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

In Docker deployment (through frontend proxy):
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`
- OpenAPI JSON: `http://localhost:8080/openapi.json`

## Run with Docker (Recommended)
```bash
cd /Users/zaharpirozenko/Documents/allure3_folder
docker compose up --build
```

Endpoints:
- App UI: `http://localhost:8080`
- Backend (internal): `backend:8000`

Stop:
```bash
docker compose down
```

## Local Development Run
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

## Main Features
- Upload Allure report archives (`.zip`)
- Browse stored reports
- Preview reports directly in iframe viewer
- Download and delete reports
- Upload/download `history.jsonl`
- Automatic report retention by limit (default 10 latest reports)
- Healthcheck endpoint: `GET /health`

## Configuration
Backend environment variables:
- `APP_STORAGE_ROOT` - storage directory path (default: `storage`)
- `APP_MAX_REPORTS` - maximum number of stored reports (default: `10`)

Retention behavior:
- After uploading a new report, if the total count exceeds `APP_MAX_REPORTS`,
  the oldest report directories are removed automatically.
