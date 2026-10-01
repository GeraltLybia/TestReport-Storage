from fastapi import APIRouter, Depends, File, Form, UploadFile

from ...dependencies import get_coverage_service
from ...schemas.report import MessageResponse
from ...services.coverage.service import MAX_SPEC_SIZE_BYTES, CoverageService

router = APIRouter(prefix="/api/coverage", tags=["coverage"])


@router.get("", summary="Список измерений покрытия")
def list_measurements(service: CoverageService = Depends(get_coverage_service)):
    return service.list_measurements()


@router.post(
    "",
    summary="Новое измерение покрытия",
    description=(
        "Принимает OpenAPI JSON (kind=rest) или GraphQL-схему SDL/интроспекцию (kind=graphql) и список отчётов. "
        "Покрытие считается по log-вложениям тестов и сохраняется снимком."
    ),
    responses={400: {"description": "Некорректная спецификация или параметры"}, 404: {"description": "Отчёт не найден"}},
)
async def create_measurement(
    kind: str = Form(...),
    report_ids: str = Form(..., description="ID отчётов через запятую"),
    name: str = Form(""),
    base_path: str | None = Form(None),
    host: str | None = Form(None),
    endpoint: str | None = Form(None),
    spec: UploadFile = File(...),
    service: CoverageService = Depends(get_coverage_service),
):
    spec_bytes = await spec.read(MAX_SPEC_SIZE_BYTES + 1)
    await spec.close()
    return service.create_measurement(
        name=name,
        kind=kind,
        spec_filename=spec.filename or "spec",
        spec_bytes=spec_bytes,
        report_ids=report_ids.split(","),
        base_path=base_path,
        host=host,
        endpoint=endpoint,
    )


@router.get("/{measurement_id}", summary="Результат измерения")
def get_measurement(measurement_id: str, service: CoverageService = Depends(get_coverage_service)):
    return service.get_measurement(measurement_id)


@router.delete("/{measurement_id}", response_model=MessageResponse, summary="Удалить измерение")
def delete_measurement(measurement_id: str, service: CoverageService = Depends(get_coverage_service)):
    return service.delete_measurement(measurement_id)
