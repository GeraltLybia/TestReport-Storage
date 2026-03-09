from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse

from ...dependencies import get_storage_service
from ...schemas.history import HistoryInfo
from ...schemas.report import MessageResponse
from ...services.storage_service import StorageService

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get(
    "",
    summary="Скачать history.jsonl",
    description="Возвращает текущий файл `history.jsonl` из хранилища.",
    responses={404: {"description": "Файл history не найден"}},
)
async def download_history(service: StorageService = Depends(get_storage_service)):
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
    service: StorageService = Depends(get_storage_service),
):
    return await service.upload_history(file)


@router.get(
    "/info",
    response_model=HistoryInfo,
    summary="Получить метаданные history",
    description="Возвращает количество записей, время обновления и размер `history.jsonl`.",
)
async def get_history_info(service: StorageService = Depends(get_storage_service)):
    return service.history_info()
