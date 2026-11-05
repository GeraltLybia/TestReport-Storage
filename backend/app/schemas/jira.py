from typing import Any, Literal

from pydantic import BaseModel, Field


class BugContent(BaseModel):
    """What goes into the description; omitted lists fall back to the draft defaults."""

    reportId: str
    testId: str
    steps: list[str] | None = Field(None, description="ID шагов; null — набор «Путь до падения»")
    logMode: Literal["calls", "full", "none"] = "calls"
    attachments: list[str] | None = Field(None, description="ID вложений; null — вложения по умолчанию")
    expected: str = ""
    includeTrace: bool = True


class BugIssueRequest(BugContent):
    projectKey: str | None = None
    description: str | None = Field(None, min_length=1, description="Отредактированное описание в разметке Jira; null — собрать автоматически")
    extraFields: dict[str, Any] = Field(default_factory=dict, description="Дополнительные поля из fieldDefinitions в /api/jira/meta")
    summary: str = Field(..., min_length=1, max_length=255)
    priority: str | None = Field(None, description="ID приоритета из /api/jira/meta")
    components: list[str] = Field(default_factory=list, description="ID компонентов")
    labels: list[str] | None = None
    assignee: str | None = Field(None, description="Логин пользователя Jira")


class BugCommentRequest(BugContent):
    pass
