from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from ...dependencies import get_storage_service
from ...schemas.report import MessageResponse, ReportItem, UploadResponse
from ...services.storage_service import StorageService

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get(
    "",
    response_model=list[ReportItem],
    summary="Получить список отчетов",
    description="Возвращает список загруженных Allure-отчетов с метаданными.",
)
async def get_reports(service: StorageService = Depends(get_storage_service)):
    return service.list_reports()


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Загрузить отчет (ZIP)",
    description="Принимает ZIP-архив с отчетом Allure, распаковывает его и добавляет в хранилище.",
    responses={
        400: {"description": "Некорректный ZIP-файл или неверный формат"},
        500: {"description": "Внутренняя ошибка при обработке загрузки"},
    },
)
async def upload_report(
    file: UploadFile = File(...),
    service: StorageService = Depends(get_storage_service),
):
    return await service.upload_report(file)


@router.delete(
    "/{report_id}",
    response_model=MessageResponse,
    summary="Удалить отчет",
    description="Удаляет отчет из хранилища по его идентификатору.",
    responses={
        404: {"description": "Отчет не найден"},
        500: {"description": "Ошибка удаления отчета"},
    },
)
async def delete_report(
    report_id: str,
    service: StorageService = Depends(get_storage_service),
):
    return service.delete_report(report_id)


@router.get(
    "/{report_id}/download",
    summary="Скачать отчет как ZIP",
    description="Формирует ZIP-архив отчета и возвращает его для скачивания.",
    responses={404: {"description": "Отчет не найден"}},
)
async def download_report(
    report_id: str,
    service: StorageService = Depends(get_storage_service),
):
    zip_path, filename = service.create_report_archive(report_id)
    return FileResponse(
        path=zip_path,
        filename=filename,
        media_type="application/zip",
        background=BackgroundTask(zip_path.unlink, missing_ok=True),
    )
