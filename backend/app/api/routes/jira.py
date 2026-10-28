from fastapi import APIRouter, Depends

from ...dependencies import get_jira_service
from ...schemas.jira import BugCommentRequest, BugContent, BugIssueRequest
from ...services.jira.service import JiraService

router = APIRouter(prefix="/api/jira", tags=["jira"])


@router.get("/config", summary="Настройки интеграции с Jira")
def get_config(service: JiraService = Depends(get_jira_service)):
    return service.config()


@router.get(
    "/meta",
    summary="Поля задачи",
    description="Тип задачи, приоритеты и компоненты проекта из createmeta Jira. Кэшируется на 10 минут.",
)
def get_meta(service: JiraService = Depends(get_jira_service)):
    return service.meta()


@router.get(
    "/draft",
    summary="Черновик бага по тесту отчёта",
    description=(
        "Шаги по секциям с свёрнутыми повторами и путём до падения, стенд, автор, вложения, "
        "предлагаемые заголовок и метки, уже заведённые задачи."
    ),
    responses={404: {"description": "Отчёт или тест не найден"}},
)
def get_draft(report_id: str, test_id: str, service: JiraService = Depends(get_jira_service)):
    return service.draft(report_id, test_id)


@router.post("/preview", summary="Описание задачи в разметке Jira")
def preview(request: BugContent, service: JiraService = Depends(get_jira_service)):
    return service.preview(request)


@router.post(
    "/issues",
    summary="Создать баг в Jira",
    responses={400: {"description": "Jira отклонила поля задачи"}, 503: {"description": "Интеграция не настроена"}},
)
def create_issue(request: BugIssueRequest, service: JiraService = Depends(get_jira_service)):
    return service.create_issue(request)


@router.post("/issues/{key}/comments", summary="Добавить повторное падение комментарием в задачу")
def add_comment(key: str, request: BugCommentRequest, service: JiraService = Depends(get_jira_service)):
    return service.add_comment(key, request)


@router.get("/links", summary="Заведённые задачи по тестам отчёта")
def get_links(report_id: str, service: JiraService = Depends(get_jira_service)):
    return service.report_links(report_id)
