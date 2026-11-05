from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from ...schemas.jira import BugIssueRequest
from ...config import get_jira_settings
from .masking import SecretMasker
from .service import JiraService


def service():
    instance = object.__new__(JiraService)
    instance.settings = Mock(enabled=True)
    instance.settings.default_labels = ()
    instance._client = Mock()
    instance._client.create_issue.return_value = {"key": "QA-1"}
    instance.meta = Mock(return_value={
        "projectKey": "QA", "issueType": {"id": "1"}, "fields": [], "fieldDefinitions": [],
    })
    instance._prepare = Mock(return_value=Mock(signature=None, test=Mock(result={})))
    instance._chosen_attachments = Mock(return_value=[])
    instance._description = Mock(return_value={
        "text": "h3. Generated", "steps": 1, "logLines": 0, "environment": "Test stand",
    })
    instance._upload = Mock(return_value=([], []))
    instance.masker = SecretMasker()
    return instance


@pytest.mark.parametrize("description,expected", [
    (None, "h3. Generated"),
    ("h3. Edited\n# Custom step\n", "h3. Edited\n# Custom step\n"),
    ("h3. Edited\npassword=secret-value", "h3. Edited\npassword=***"),
])
def test_create_issue_uses_reviewed_text_or_legacy_generated_description(description, expected):
    instance = service()
    request = BugIssueRequest(
        reportId="report-1", testId="test-1", summary="Title", expected="Expected result",
        description=description,
    )
    instance.create_issue(request)
    assert instance._client.create_issue.call_args.args[0]["description"] == expected


def test_blank_reviewed_description_is_rejected_before_contacting_jira():
    instance = service()
    request = BugIssueRequest(
        reportId="report-1", testId="test-1", summary="Title", expected="Expected result",
        description=" \n ",
    )
    with pytest.raises(HTTPException, match="Заполните описание задачи"):
        instance.create_issue(request)
    instance._client.create_issue.assert_not_called()


@pytest.mark.parametrize("raw,keys", [
    ("QA", ("QA",)),
    (" QA , CORE, QA, , APP ", ("QA", "CORE", "APP")),
    (", ,", ()),
    ("", ()),
])
def test_projects_from_existing_environment_variable(monkeypatch, raw, keys):
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_TOKEN", "test-token")
    monkeypatch.setenv("JIRA_PROJECT_KEY", raw)
    settings = get_jira_settings()
    assert settings.project_keys == keys
    assert settings.enabled == bool(keys)
    instance = service()
    instance.settings = settings
    assert instance.config()["projectKeys"] == list(keys)
    assert instance.config()["projectKey"] == (keys[0] if keys else None)


def project_service(monkeypatch, projects="QA,CORE"):
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example")
    monkeypatch.setenv("JIRA_TOKEN", "test-token")
    monkeypatch.setenv("JIRA_PROJECT_KEY", projects)
    monkeypatch.setenv("JIRA_ISSUE_TYPE", "Defect")
    instance = service()
    instance.settings = get_jira_settings()
    del instance.meta
    instance._meta = {}
    instance._client.issue_types.side_effect = lambda project: [{"id": "1" if project == "QA" else "2", "name": "Defect"}]
    instance._client.issue_fields.side_effect = lambda project, issue_type: [
        {"fieldId": f"customfield_{project}", "name": project, "schema": {"type": "string"}},
    ]
    return instance


def test_project_metadata_cache_is_separate_and_issue_type_is_shared(monkeypatch):
    instance = project_service(monkeypatch)
    qa = instance.meta()
    core = instance.meta(project_key="CORE")
    assert qa["projectKey"] == "QA"
    assert core["projectKey"] == "CORE"
    assert qa["fields"] == ["customfield_QA"]
    assert core["fields"] == ["customfield_CORE"]
    assert qa["issueType"] == {"id": "1", "name": "Defect"}
    assert core["issueType"] == {"id": "2", "name": "Defect"}
    assert instance.meta() == qa
    assert instance.meta(project_key="CORE") == core
    assert instance._client.issue_fields.call_count == 2
    instance.meta(refresh=True, project_key="CORE")
    assert instance._client.issue_fields.call_count == 3
    assert instance.meta() == qa
    assert instance._client.issue_fields.call_count == 3


@pytest.mark.parametrize("project,configured", [(None, "QA"), ("QA", "QA"), ("CORE", "QA,CORE")])
def test_filing_uses_selected_project_or_single_project_default(monkeypatch, project, configured):
    instance = project_service(monkeypatch, configured)
    instance.create_issue(BugIssueRequest(
        reportId="report-1", testId="test-1", summary="Title", expected="Expected",
        projectKey=project,
    ))
    fields = instance._client.create_issue.call_args.args[0]
    assert fields["project"] == {"key": project or "QA"}
    assert fields["issuetype"] == {"id": "2" if project == "CORE" else "1"}


def test_unconfigured_project_is_rejected_for_metadata_and_creation(monkeypatch):
    instance = project_service(monkeypatch, "QA")
    with pytest.raises(HTTPException, match="Проект Jira не настроен"):
        instance.meta(project_key="CORE")
    with pytest.raises(HTTPException, match="Проект Jira не настроен"):
        instance.create_issue(BugIssueRequest(
            reportId="report-1", testId="test-1", summary="Title", expected="Expected", projectKey="CORE",
        ))
    instance._client.issue_types.assert_not_called()
    instance._client.create_issue.assert_not_called()


def test_project_selection_through_http_api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from ...api.routes.jira import router
    from ...dependencies import get_jira_service

    instance = project_service(monkeypatch)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_jira_service] = lambda: instance
    with TestClient(app) as client:
        assert client.get("/api/jira/config").json()["projectKeys"] == ["QA", "CORE"]
        assert client.get("/api/jira/meta").json()["projectKey"] == "QA"
        assert client.get("/api/jira/meta?project_key=CORE&refresh=true").json()["projectKey"] == "CORE"
        assert client.get("/api/jira/meta?project_key=OTHER").status_code == 400
        instance._client.issue_url.return_value = "https://jira.example/browse/QA-1"
        response = client.post("/api/jira/issues", json={
            "reportId": "report-1", "testId": "test-1", "summary": "Title", "expected": "Expected", "projectKey": "CORE",
        })
        assert response.status_code == 200
        assert instance._client.create_issue.call_args.args[0]["project"] == {"key": "CORE"}
