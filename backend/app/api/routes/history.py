import asyncio

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse

from ...dependencies import get_history_service
from ...schemas.history import (
    HistoryDashboardSummary,
    HistoryInfo,
    HistoryRunList,
    HistoryRunResults,
    HistorySelectedTestDetails,
)
from ...schemas.report import MessageResponse
from ...services.reporting import HistoryService

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get(
    "",
    summary="Скачать history.jsonl",
    description="Возвращает текущий файл `history.jsonl` из хранилища.",
    responses={404: {"description": "Файл history не найден"}},
)
async def download_history(service: HistoryService = Depends(get_history_service)):
    history_path = service.get_history_path()
    return FileResponse(
        path=history_path,
        filename="history.jsonl",
        media_type="application/x-jsonlines",
    )


@router.post(
    "",
    response_model=MessageResponse,
    summary="Загрузить history.jsonl",
    description="Принимает и валидирует JSONL-файл истории, затем сохраняет его в хранилище.",
    responses={
        400: {"description": "Некорректный формат файла history"},
        500: {"description": "Внутренняя ошибка при сохранении history"},
    },
)
async def upload_history(
    file: UploadFile = File(...),
    service: HistoryService = Depends(get_history_service),
):
    temp_path = await service.stream_upload_to_temp(file)
    await file.close()
    return await asyncio.to_thread(service.finalize_upload, temp_path)


@router.post(
    "/rebuild-index",
    response_model=MessageResponse,
    summary="Полностью перестроить history index",
    description="Принудительно перечитывает активный `history.jsonl` и архивы из хранилища, затем заново собирает `history_index.json`.",
    responses={
        404: {"description": "Файл history не найден"},
        500: {"description": "Внутренняя ошибка при перестроении index"},
    },
)
def rebuild_history_index(service: HistoryService = Depends(get_history_service)):
    return service.rebuild_history_index()


@router.get(
    "/info",
    response_model=HistoryInfo,
    summary="Получить метаданные history",
    description="Возвращает количество записей, время обновления и размер `history.jsonl`.",
)
def get_history_info(service: HistoryService = Depends(get_history_service)):
    return service.history_info()


@router.get(
    "/dashboard",
    response_model=HistoryDashboardSummary,
    summary="Получить агрегаты dashboard",
    description="Возвращает агрегированные метрики dashboard из history index без скачивания всего JSONL.",
)
def get_history_dashboard(
    tags: str | None = None,
    suite: str | None = None,
    environment: str | None = None,
    signature: str | None = None,
    stopFrom: int | None = None,
    stopTo: int | None = None,
    service: HistoryService = Depends(get_history_service),
):
    parsed_tags = [item.strip() for item in (tags or "").split(",") if item.strip()]
    return service.get_history_dashboard(
        tags=parsed_tags,
        suite=suite,
        environment=environment,
        signature=signature,
        stop_from=stopFrom,
        stop_to=stopTo,
    )


@router.get(
    "/dashboard/tests/{test_key:path}",
    response_model=HistorySelectedTestDetails,
    summary="Получить детали теста для dashboard",
    description="Возвращает историю выбранного теста из индекса с учётом фильтров dashboard.",
    responses={404: {"description": "Тест не найден для текущего набора фильтров"}},
)
def get_history_test_details(
    test_key: str,
    tags: str | None = None,
    suite: str | None = None,
    environment: str | None = None,
    signature: str | None = None,
    stopFrom: int | None = None,
    stopTo: int | None = None,
    service: HistoryService = Depends(get_history_service),
):
    parsed_tags = [item.strip() for item in (tags or "").split(",") if item.strip()]
    details = service.get_history_test_details(
        test_key=test_key,
        tags=parsed_tags,
        suite=suite,
        environment=environment,
        signature=signature,
        stop_from=stopFrom,
        stop_to=stopTo,
    )
    if details is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return details


@router.get(
    "/runs",
    response_model=HistoryRunList,
    summary="Список прогонов из history",
    description="Постраничный список прогонов, восстановленных из history index (без скачивания JSONL).",
)
def list_history_runs(
    search: str | None = None,
    status: str | None = Query(default=None, pattern="^(all|failed|broken|passed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: HistoryService = Depends(get_history_service),
):
    return service.list_history_runs(search=search, status=status, limit=limit, offset=offset)


@router.get(
    "/runs/{run_uuid}/results",
    response_model=HistoryRunResults,
    summary="Результаты тестов прогона",
    description="Результаты тестов одного прогона из history index; по умолчанию только failed и broken.",
    responses={404: {"description": "Прогон не найден"}},
)
def get_history_run_results(
    run_uuid: str,
    status: str = Query(default="incidents", pattern="^(all|incidents|changes|failed|broken|passed)$"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: HistoryService = Depends(get_history_service),
):
    results = service.get_history_run_results(run_uuid, status=status, limit=limit, offset=offset)
    if results is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return results
