from fastapi import APIRouter

from .routes import coverage, history, reports

api_router = APIRouter()
api_router.include_router(reports.router)
api_router.include_router(history.router)
api_router.include_router(coverage.router)
