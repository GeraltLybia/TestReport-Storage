import json
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from app.config import JiraSettings
from app.schemas.jira import BugCommentRequest, BugContent, BugIssueRequest
from app.services.jira.client import JiraClient
from app.services.jira.masking import SecretMasker
from app.services.jira.report_source import load_report_test
from app.services.jira.service import JiraService, build_summary
from app.services.jira.stand import detect_stand
from app.services.jira.steps import build_step_sections, default_selection, iter_steps
from app.services.jira.wiki import escape, noformat
from app.services.reporting.context import StorageContext
from app.services.reporting.repositories.reports import ReportsRepository

REPORT_ID = "11111111-2222-4333-8444-555555555555"
ERROR = "AssertionError: Ожидаемый код статуса 200, полученный 409\nassert 409 == 200"


def _attach(attachment_id: str, ext: str = ".json", content_type: str = "application/json") -> dict:
    return {"type": "attachment", "link": {"id": attachment_id, "ext": ext, "contentType": content_type, "name": "Данные запроса и ответа АПИ"}}


def _step(name: str, status: str = "passed", steps: list | None = None, message: str | None = None) -> dict:
    step = {"type": "step", "name": name, "status": status, "duration": 10, "steps": steps or []}
    if message:
        step["message"] = message
    return step


def _poll(number: int) -> dict:
    return _step("Получаем статус заказа", steps=[_attach(f"poll{number}")])


CANCEL = {
    "id": "t1",
    "name": "Отмена заказа",
    "fullName": "Shop.orders#test_cancel",
    "status": "failed",
    "error": {"message": ERROR, "trace": "Traceback\n  File test.py, line 3\nAssertionError"},
    "labels": [{"name": "tag", "value": "regression"}, {"name": "tag", "value": "smoke test"}],
    "parameters": [{"name": "ins_type", "value": "'cargo'"}, {"name": "secret", "value": "x", "masked": True}],
    "setup": [{"name": "api_client", "type": "before", "status": "passed", "steps": []}],
    "steps": [
        _step("Устанавливаем роль 'client'"),
        _step("Создать заказ", steps=[_attach("create")]),
        _step("Ждём статус paid (попытка 3 x 1 сек)", steps=[_poll(1), _poll(2), _poll(3)]),
        _step("Устанавливаем роль 'client'"),
        _step(
            "Отменить заказ",
            "failed",
            message=ERROR,
            steps=[
                _attach("cancel"),
                _step("Сохраняем response"),
                _step("Сверяем HTTP статус ответа", "failed", message=ERROR),
            ],
        ),
        _step("Проверить статус заказа", "skipped"),
    ],
    "teardown": [{"name": "delete_customer", "type": "after", "status": "passed", "steps": []}],
    "attachments": [_attach("log", ".txt", "text/plain")],
}
REFUND = {
    "id": "t2",
    "name": "Возврат оплаты",
    "fullName": "Shop.payments#test_refund",
    "status": "broken",
    "error": {"message": ERROR},
    "steps": [_step("Сделать возврат", "broken", message=ERROR)],
}
ATTACHMENTS = {
    "create.json": {
        "request_line": "POST http://stand.local:4001/api/v1/orders",
        "request_body": {"sku": "SKU-1", "password": "hunter2"},
        "response_status_code": 201,
        "response_body": {"id": 1},
    },
    "cancel.json": {
        "request_line": "PATCH http://stand.local:4001/api/v1/orders/1/status",
        "request_body": {"status": "cancelled"},
        "response_status_code": 409,
        "response_body": {"error": "ORDER_LOCKED", "token": "abc123"},
    },
    "log.txt": "INFO Запрос: GET http://other:8090/x\nAuthorization: Bearer abcdefghijklmnop\nINFO done\n",
}
for number in (1, 2, 3):
    ATTACHMENTS[f"poll{number}.json"] = {
        "request_line": "GET http://stand.local:18081/api/v1/orders/1/status",
        "response_status_code": 200,
    }


def _context(root: Path) -> StorageContext:
    return StorageContext(
        reports_folder=root / "reports",
        history_file=root / "history.jsonl",
        history_archive_folder=root / "history_archive",
        history_index_file=root / "history_index.json",
        max_reports=10,
        max_history_file_size_bytes=1024 * 1024,
        max_upload_size_bytes=1024 * 1024,
        max_indexed_runs=1000,
    )


def _settings(**overrides) -> JiraSettings:
    values = dict(
        base_url="https://jira.local",
        token="pat-token",
        project_key="SHOP",
        issue_type="Bug",
        default_labels=("autotest",),
        verify=True,
        timeout_seconds=5,
        max_attachment_bytes=1024 * 1024,
        public_url="https://trs.local",
    )
    values.update(overrides)
    return JiraSettings(**values)


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        report_root = root / "reports" / REPORT_ID / "2026-09-28_05-00"
        (report_root / "data" / "test-results").mkdir(parents=True)
        (report_root / "data" / "attachments").mkdir(parents=True)
        (report_root / "widgets").mkdir()
        (report_root / "index.html").write_text("<html></html>", encoding="utf-8")
        (report_root / "widgets" / "variables.json").write_text(
            json.dumps({"Launch source": "local", "User": "qa-alice"}), encoding="utf-8"
        )
        (report_root / "test-results.json").write_text(
            json.dumps({"byId": {item["id"]: item for item in (CANCEL, REFUND)}}), encoding="utf-8"
        )
        for item in (CANCEL, REFUND):
            (report_root / "data" / "test-results" / f"{item['id']}.json").write_text(
                json.dumps(item, ensure_ascii=False), encoding="utf-8"
            )
        for name, content in ATTACHMENTS.items():
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            (report_root / "data" / "attachments" / name).write_text(text, encoding="utf-8")
        yield root


def _sections(storage: Path):
    test = load_report_test(ReportsRepository(_context(storage)), REPORT_ID, "t1")
    return test, build_step_sections(test)


def test_steps_fold_only_consecutive_repeats_and_mark_failure_path(storage):
    test, sections = _sections(storage)
    assert test.author == "qa-alice"
    assert [section.id for section in sections] == ["setup", "test", "teardown"]

    steps = sections[1].steps
    assert [step.title for step in steps].count("Устанавливаем роль 'client'") == 2  # scenario repeats stay
    poll = steps[2].children
    assert len(poll) == 1 and poll[0].kind == "group" and len(poll[0].attempts) == 3

    assert steps[1].call.label == "POST /api/v1/orders → 201"
    cancel = steps[4]
    assert cancel.on_failure_path and not cancel.failure_origin
    assert cancel.children[1].failure_origin  # deepest failed step with a message
    assert not steps[5].on_failure_path


def test_default_selection_is_path_to_failure(storage):
    _, sections = _sections(storage)
    selected = default_selection(sections)
    by_id = {step.id: step for section in sections for step in iter_steps(section.steps)}
    titles = [by_id[step_id].title for step_id in selected]

    assert "api_client" not in titles and "delete_customer" not in titles  # setup/teardown off
    assert "Проверить статус заказа" not in titles  # skipped
    assert "Сохраняем response" not in titles  # passed sub-step off the failure path
    assert "Сверяем HTTP статус ответа" in titles
    assert "Ждём статус paid (попытка 3 x 1 сек)" in titles
    assert "Получаем статус заказа" not in titles  # polling attempts are nested and passed


def test_stand_drops_ports_and_the_most_called_host_wins():
    stand = detect_stand(
        ["http://stand.local:4001/a", "http://stand.local:18081/b", "http://other:8090/c", "http://other:8090/d"]
        + ["http://stand.local:4001/e"],
        {"stand.local": "stage"},
    )
    assert (stand.host, stand.url, stand.name) == ("stand.local", "http://stand.local", "stage")
    assert stand.origins[0] == {"origin": "http://stand.local:4001", "count": 2}
    assert detect_stand([]) is None


def test_masker_hides_credentials_and_keeps_lookalikes():
    masker = SecretMasker(("x-session",))
    text = masker.mask(
        'Authorization: Bearer abcdefghijkl\n{"password": "p@ss", "token_storage": 1}\n'
        "url?access_token=zzz&page=2 x-session=42 eyJhbGciOi.eyJzdWIiOiIx.c2lnbmF0dXJl"
    )
    assert "abcdefghijkl" not in text and "p@ss" not in text and "zzz" not in text and "42" not in text
    assert text.startswith("Authorization: ***\n")
    assert '"password": "***"' in text and '"token_storage": 1' in text and "page=2" in text
    assert "eyJ" not in text


def test_wiki_escaping_and_blocks():
    assert escape("a_b *c* {x} [y|z] -strike- ok-ish #1") == r"a\_b \*c\* \{x\} \[y\|z\] \-strike\- ok-ish \#1"
    assert noformat("x {noformat} y") == "{noformat}\nx { noformat} y\n{noformat}"


def test_summary_splits_error_type():
    assert build_summary("Отмена заказа", ERROR) == (
        "[Автотест] Отмена заказа: AssertionError — Ожидаемый код статуса 200, полученный 409"
    )
    assert build_summary("x", "Ошибка без типа").endswith(": Ошибка без типа")
    assert len(build_summary("x" * 200, None)) == 110


def test_draft(storage):
    service = JiraService(_context(storage), _settings(base_url=None))
    draft = service.draft(REPORT_ID, "t1")

    assert draft["report"]["author"] == "qa-alice"
    assert draft["stand"]["host"] == "stand.local"  # step calls win over the log's other:8090
    assert draft["test"]["signature"] == "AssertionError: Ожидаемый код статуса 200, полученный 409"
    assert draft["test"]["parameters"] == [{"name": "ins_type", "value": "'cargo'"}]
    assert draft["suggested"]["labels"] == ["autotest", "regression", "smoke_test"]
    assert draft["suggested"]["assignee"] == {"name": "qa-alice", "displayName": "qa-alice", "found": None}
    attachments = {item["name"]: item for item in draft["attachments"]}
    assert attachments["log.txt"]["defaultSelected"] is True
    assert attachments["request.json"]["defaultSelected"] is False  # dump of the failing request
    assert draft["links"]["allure"] == f"https://trs.local/reports-static/{REPORT_ID}/2026-09-28_05-00/index.html#/t1"
    assert draft["duplicates"] == {"exact": None, "similar": []}

    with pytest.raises(HTTPException) as missing:
        service.draft(REPORT_ID, "nope")
    assert missing.value.status_code == 404


def test_preview_renders_chosen_steps_calls_and_masks(storage):
    service = JiraService(_context(storage), _settings(base_url=None))
    _, sections = _sections(storage)
    poll_attempts = sections[1].steps[2].children[0].attempts

    content = BugContent(
        reportId=REPORT_ID,
        testId="t1",
        steps=["t.1", poll_attempts[2].id, "t.4.1"],  # parent "Отменить заказ" unticked
        expected="Заказ отменяется",
    )
    text = service.preview(content)["description"]

    assert "# Создать заказ — {{POST /api/v1/orders → 201}}" in text
    assert "# Получаем статус заказа — попытка 3 из 3" in text
    # the failing sub-step moves up a level when its parent is not chosen
    assert "# {color:#de350b}*Сверяем HTTP статус ответа*{color}" in text
    assert "PATCH http://stand.local:4001/api/v1/orders/1/status → 409" not in text.split("h3. Запросы")[0]
    assert '"error": "ORDER_LOCKED"' in text and "abc123" not in text
    assert "Заказ отменяется" in text
    assert "* Стенд: http://stand.local" in text and "* [^log.txt]" in text

    full = service.preview(content.model_copy(update={"logMode": "full"}))["description"]
    assert "h3. Лог" in full and "abcdefghijklmnop" not in full


class FakeJira:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.created: dict | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        assert request.headers["authorization"] == "Bearer pat-token"
        if path.endswith("/createmeta/SHOP/issuetypes"):
            return httpx.Response(200, json={"values": [{"id": "3", "name": "Task"}, {"id": "1", "name": "Bug"}]})
        if path.endswith("/createmeta/SHOP/issuetypes/1"):
            return httpx.Response(
                200,
                json={
                    "values": [
                        {"fieldId": "summary", "required": True},
                        {"fieldId": "priority", "required": False, "defaultValue": {"id": "3"}, "allowedValues": [{"id": "2", "name": "High"}, {"id": "3", "name": "Medium"}]},
                        {"fieldId": "components", "required": False, "allowedValues": [{"id": "10", "name": "orders"}]},
                        {"fieldId": "labels", "required": False},
                        {"fieldId": "assignee", "required": False},
                        {"fieldId": "environment", "required": False},
                        {"fieldId": "customfield_1", "name": "Team", "required": True},
                    ]
                },
            )
        if path.endswith("/rest/api/2/user"):
            return httpx.Response(200, json={"name": "qa-alice", "displayName": "Alice QA", "active": True})
        if path.endswith("/rest/api/2/issue"):
            self.created = json.loads(request.content)["fields"]
            return httpx.Response(201, json={"id": "100", "key": "SHOP-1432"})
        if path.endswith("/attachments"):
            assert request.headers["x-atlassian-token"] == "no-check"
            return httpx.Response(200, json=[{"id": "1"}])
        if path.endswith("/comment"):
            return httpx.Response(201, json={"id": "5"})
        if path.endswith("/search"):
            return httpx.Response(200, json={"issues": [{"key": "SHOP-1432", "fields": {"summary": "s", "status": {"name": "Открыта", "statusCategory": {"key": "new"}}}}]})
        return httpx.Response(404, json={"errorMessages": [f"unexpected {path}"]})


def _service(storage: Path, fake: FakeJira) -> JiraService:
    settings = _settings()
    return JiraService(_context(storage), settings, JiraClient(settings, transport=httpx.MockTransport(fake)))


def test_create_issue_files_bug_attaches_masked_log_and_links_failure(storage):
    fake = FakeJira()
    service = _service(storage, fake)

    meta = service.meta()
    assert meta["issueType"] == {"id": "1", "name": "Bug"}
    assert meta["defaultPriority"] == "3"
    assert meta["unsupportedRequired"] == [{"id": "customfield_1", "name": "Team"}]

    result = service.create_issue(
        BugIssueRequest(
            reportId=REPORT_ID,
            testId="t1",
            summary="  [Автотест]  Отмена заказа ",
            expected="Заказ отменяется",
            priority="2",
            components=["10"],
            assignee="qa-alice",
            attachments=["log", "cancel"],
        )
    )
    assert result["key"] == "SHOP-1432" and result["url"] == "https://jira.local/browse/SHOP-1432"
    assert sorted(result["attachments"]) == ["log.txt", "request.json"] and result["warnings"] == []

    fields = fake.created
    assert fields["project"] == {"key": "SHOP"} and fields["issuetype"] == {"id": "1"}
    assert fields["summary"] == "[Автотест] Отмена заказа"
    assert fields["priority"] == {"id": "2"} and fields["components"] == [{"id": "10"}]
    assert fields["assignee"] == {"name": "qa-alice"}
    assert fields["labels"] == ["autotest", "regression", "smoke_test"]
    assert fields["environment"].startswith("http://stand.local")
    log_upload = next(r for r in fake.requests if r.url.path.endswith("/attachments") and b'filename="log.txt"' in r.content)
    assert b"abcdefghijklmnop" not in log_upload.content and b"Authorization: ***\n" in log_upload.content

    # the same failure now points at the issue: in the report, in a new draft, as a hint for other tests
    links = service.report_links(REPORT_ID)["items"]
    assert links["t1"]["key"] == "SHOP-1432" and links["t1"]["status"] == "Открыта"
    assert "t2" not in links
    assert service.draft(REPORT_ID, "t1")["duplicates"]["exact"]["key"] == "SHOP-1432"
    similar = service.draft(REPORT_ID, "t2")["duplicates"]
    assert similar["exact"] is None and [item["key"] for item in similar["similar"]] == ["SHOP-1432"]

    comment = service.add_comment("SHOP-1432", BugCommentRequest(reportId=REPORT_ID, testId="t2", attachments=[]))
    assert comment["key"] == "SHOP-1432"
    body = json.loads([r for r in fake.requests if r.url.path.endswith("/comment")][0].content)["body"]
    assert body.startswith("h3. Повторное падение") and "Ожидаемый результат" not in body
    assert service.report_links(REPORT_ID)["items"]["t2"]["key"] == "SHOP-1432"


def test_create_issue_validation_and_disabled_integration(storage):
    service = _service(storage, FakeJira())
    request = BugIssueRequest(reportId=REPORT_ID, testId="t1", summary="s", expected=" ")
    with pytest.raises(HTTPException) as no_expected:
        service.create_issue(request)
    assert no_expected.value.status_code == 400

    with pytest.raises(HTTPException) as bad_key:
        service.add_comment("shop-1 OR 1=1", BugCommentRequest(reportId=REPORT_ID, testId="t1"))
    assert bad_key.value.status_code == 400

    disabled = JiraService(_context(storage), _settings(token=None))
    assert disabled.config()["enabled"] is False
    with pytest.raises(HTTPException) as off:
        disabled.create_issue(request.model_copy(update={"expected": "x"}))
    assert off.value.status_code == 503


def test_jira_errors_are_readable(storage):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issue"):
            return httpx.Response(400, json={"errorMessages": [], "errors": {"components": "Компонент обязателен"}})
        return FakeJira()(request)

    settings = _settings()
    service = JiraService(_context(storage), settings, JiraClient(settings, transport=httpx.MockTransport(handler)))
    with pytest.raises(HTTPException) as error:
        service.create_issue(BugIssueRequest(reportId=REPORT_ID, testId="t1", summary="s", expected="x"))
    assert error.value.status_code == 400 and "components: Компонент обязателен" in error.value.detail

    def unauthorized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    service = JiraService(_context(storage), settings, JiraClient(settings, transport=httpx.MockTransport(unauthorized)))
    with pytest.raises(HTTPException) as denied:
        service.meta()
    assert "JIRA_TOKEN" in denied.value.detail


def test_routes(storage):
    from fastapi.testclient import TestClient

    from app.dependencies import get_jira_service
    from app.main import app

    app.dependency_overrides[get_jira_service] = lambda: _service(storage, FakeJira())
    try:
        client = TestClient(app)
        assert client.get("/api/jira/config").json()["enabled"] is True
        draft = client.get("/api/jira/draft", params={"report_id": REPORT_ID, "test_id": "t1"})
        assert draft.status_code == 200 and draft.json()["defaultSteps"]
        preview = client.post("/api/jira/preview", json={"reportId": REPORT_ID, "testId": "t1", "logMode": "none"})
        assert "h3. Запросы" not in preview.json()["description"]
        created = client.post(
            "/api/jira/issues", json={"reportId": REPORT_ID, "testId": "t1", "summary": "s", "expected": "x"}
        )
        assert created.json()["key"] == "SHOP-1432"
        assert client.get("/api/jira/links", params={"report_id": REPORT_ID}).json()["items"]["t1"]["key"] == "SHOP-1432"
        assert client.get("/api/jira/draft", params={"report_id": REPORT_ID, "test_id": "../x"}).status_code == 404
    finally:
        app.dependency_overrides.clear()
