import json
import tempfile
from pathlib import Path

import pytest

from app.services.coverage.graphql_coverage import GraphqlCoverage, SchemaError, load_schema
from app.services.coverage.log_parser import parse_log
from app.services.coverage.rest import RestCoverage, SpecError, load_rest_spec
from app.services.coverage.service import CoverageService
from app.services.reporting.context import StorageContext

LOG = (
    "\x1b[32mINFO    \x1b[0m my_log:api_controller.py:116 Запрос: POST http://h:4001/api/driver/v1/claim\n"
    "INFO     my_log:api_controller.py:120 Тело запроса: {\n  \"a\": 1\n}\n"
    "INFO     my_log:api_controller.py:152 Статус код ответа: 200\n"
    "INFO     my_log:api_controller.py:116 Запрос: GET http://h:4001/api/driver/v1/claim/adjust/8b166afe-4081-40f6-8cbf-301a82fc8ee6\n"
    "WARNING  my_log:api_controller.py:147 Получен не ожидаемый HTTP статус-код ответа от АПИ '404'\n"
    # glued records, multi-line GraphQL query with an inline fragment
    "INFO     my_log:claims.py:86 Проверка флага \"x\". Ожидаемое: True"
    "INFO     my_log:api_controller.py:72 Запрос: \"http://h:4002/graphql\" query ($page: Int) {\n"
    "    handbook(page: $page) {\n      content { ... on Reason { uid name } }\n    }} Переменные: {'page': 0}\n"
    "INFO     my_log:api_controller.py:77 Ответ: {'handbook': {}}\n"
    "INFO     my_log:api_controller.py:72 Запрос: \"http://h:4001/graphql\" {claimExtraData(claimUid: \"1\"){isClaimAutoCreated, hasPaymentDetails}} Переменные: None\n"
)

OPENAPI = {
    "openapi": "3.0.3",
    "info": {"title": "Driver API", "version": "2.14.0"},
    "servers": [{"url": "http://h:4001/api/driver/v1"}],
    "paths": {
        "/claim": {"post": {"tags": ["Claim"], "summary": "Create", "responses": {"200": {}, "400": {}}}},
        "/claim/{claimUid}": {"get": {"tags": ["Claim"], "responses": {"200": {}, "404": {}}}},
        "/claim/adjust/{claimUid}": {"get": {"tags": ["Claim"], "responses": {"2XX": {}, "default": {}}}},
    },
}

SDL = """
type Query { claimExtraData(claimUid: ID!): ClaimExtraData  handbook(page: Int): Page  claim(uid: ID!): Claim }
type ClaimExtraData { isClaimAutoCreated: Boolean! hasPaymentDetails: Boolean! source: String }
type Page { content: [Item!]! total: Int }
union Item = Reason | Other
type Reason { uid: ID! name: String! }
type Other { id: ID! }
type Claim { uid: ID! }
"""


def test_log_parser_handles_glued_records_and_multiline_graphql():
    parsed = parse_log(LOG)

    assert [(c.method, c.status) for c in parsed.rest] == [("POST", "200"), ("GET", "404")]
    assert [c.url for c in parsed.graphql] == ["http://h:4002/graphql", "http://h:4001/graphql"]
    assert "... on Reason" in parsed.graphql[0].query
    assert parsed.graphql[0].variables == "{'page': 0}"
    assert parsed.graphql[1].variables is None


def test_rest_coverage_matches_templates_codes_and_unknown_calls():
    coverage = RestCoverage(load_rest_spec(OPENAPI))
    test = {"name": "t"}
    for call in parse_log(LOG).rest:
        coverage.add_call(call.method, call.url, call.status, "r:t1", test)
    coverage.add_call("GET", "http://h:4001/api/driver/v1/claim/42/files", "200", "r:t1", test)
    coverage.add_call("GET", "http://other:18081/api/claims/1/history", "200", "r:t1", test)  # other service

    result = coverage.result(total_tests=1)
    ops = {op["id"]: op for op in result["operations"]}

    assert ops["POST /claim"]["calls"] == 1
    assert {c["code"]: c["calls"] for c in ops["POST /claim"]["codes"]} == {"200": 1, "400": 0}
    # 404 is not 2XX, so it falls into "default"
    assert {c["code"]: c["calls"] for c in ops["GET /claim/adjust/{claimUid}"]["codes"]} == {"2XX": 0, "default": 1}
    assert ops["GET /claim/{claimUid}"]["calls"] == 0
    assert result["unknown"] == [{"method": "GET", "path": "/api/driver/v1/claim/{id}/files", "calls": 1, "codes": ["200"]}]
    assert result["summary"]["coveredOperations"] == 2 and result["summary"]["calls"] == 3


def test_rest_spec_errors():
    with pytest.raises(SpecError):
        load_rest_spec({"openapi": "3.0.0"})


def test_graphql_coverage_counts_fields_through_unions_and_filters_endpoint():
    coverage = GraphqlCoverage(load_schema(SDL), endpoint="http://h:4002/graphql")
    for call in parse_log(LOG).graphql:
        coverage.add_call(call.url, call.query, "r:t1", {"name": "t"})

    result = coverage.result(total_tests=1)
    fields = {(t["name"], f["name"]): f for t in result["types"] for f in t["fields"]}

    assert result["summary"]["calls"] == 1  # :4001 call belongs to another service
    assert fields[("Query", "handbook")]["calls"] == 1
    assert fields[("Query", "handbook")]["args"] == [{"name": "page", "calls": 1}]
    assert fields[("Reason", "uid")]["calls"] == 1 and fields[("Reason", "name")]["calls"] == 1
    assert fields[("Query", "claimExtraData")]["calls"] == 0
    assert next(t for t in result["types"] if t["name"] == "Item")["possibleTypes"] == ["Reason", "Other"]


def test_graphql_invalid_query_and_bad_schema():
    coverage = GraphqlCoverage(load_schema(SDL))
    coverage.add_call("http://h/graphql", "{ claimExtraData(claimUid: \"1\") { missingField } }", "k", {})
    coverage.add_call("http://h/graphql", "{ not valid", "k", {})
    result = coverage.result(total_tests=1)
    assert result["summary"]["invalidCalls"] == 2
    assert result["summary"]["coveredFields"] == 1  # claimExtraData itself is still known
    with pytest.raises(SchemaError):
        load_schema('{"data": {}}')


def test_service_end_to_end_with_allure3_report_layout():
    report_id = "11111111-2222-4333-8444-555555555555"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        report_root = root / "reports" / report_id / "2026-09-25_12-30"
        (report_root / "data" / "test-results").mkdir(parents=True)
        (report_root / "data" / "attachments").mkdir(parents=True)
        (report_root / "index.html").write_text("<html></html>", encoding="utf-8")
        (report_root / "data" / "attachments" / "abc.txt").write_text(LOG, encoding="utf-8")
        (report_root / "data" / "test-results" / "t1.json").write_text(
            json.dumps({
                "id": "t1",
                "name": "Создание претензии",
                "fullName": "Claims.Tests.mod#test_create",
                "steps": [{"type": "attachment", "link": {"id": "abc", "ext": ".txt", "contentType": "text/plain"}}],
            }),
            encoding="utf-8",
        )
        context = StorageContext(
            reports_folder=root / "reports",
            history_file=root / "history.jsonl",
            history_archive_folder=root / "history_archive",
            history_index_file=root / "history_index.json",
            max_reports=10,
            max_history_file_size_bytes=1024 * 1024,
            max_upload_size_bytes=1024 * 1024,
            max_indexed_runs=1000,
        )
        service = CoverageService(context)

        created = service.create_measurement(
            name="Регресс", kind="rest", spec_filename="openapi.json",
            spec_bytes=json.dumps(OPENAPI).encode(), report_ids=[report_id],
        )

        assert created["summary"]["coveredOperations"] == 2
        create_op = next(op for op in created["result"]["operations"] if op["id"] == "POST /claim")
        assert create_op["tests"] == [{"name": "Создание претензии", "fullName": "Claims.Tests.mod#test_create", "reportId": report_id, "testId": "t1"}]
        assert [m["id"] for m in service.list_measurements()] == [created["id"]]
        recalculated = service.recalculate_measurement(created["id"])
        assert recalculated["summary"] == created["summary"] and recalculated["missingReports"] == []
        assert service.get_measurement(created["id"])["result"]["kind"] == "rest"
        service.delete_measurement(created["id"])
        assert service.list_measurements() == []


def test_rest_ignores_generated_server_host_and_detects_service_hosts():
    """springdoc writes the download host into servers; tests run against another stand."""
    spec = dict(OPENAPI, servers=[{"url": "http://10.101.3.120:4002", "description": "Generated server url"}])
    spec["paths"] = {"/api/driver/v1" + path: item for path, item in OPENAPI["paths"].items()}
    coverage = RestCoverage(load_rest_spec(spec))
    test = {"name": "t"}
    coverage.add_call("POST", "http://stand:4002/api/driver/v1/claim", "200", "r:t1", test)
    coverage.add_call("GET", "http://stand:4002/api/driver/v1/unknown/1", "200", "r:t1", test)
    coverage.add_call("GET", "http://stand:18081/api/claims/1/history", "200", "r:t1", test)

    result = coverage.result(total_tests=1)

    assert next(op for op in result["operations"] if op["id"] == "POST /api/driver/v1/claim")["calls"] == 1
    assert result["spec"]["hosts"] == ["stand:4002"]
    assert result["spec"]["otherHosts"] == [{"host": "stand:18081", "calls": 1}]
    assert [u["path"] for u in result["unknown"]] == ["/api/driver/v1/unknown/{id}"]
    assert result["summary"]["calls"] == 2


def test_explicit_host_filter_excludes_other_hosts():
    coverage = RestCoverage(load_rest_spec(OPENAPI, host_override="h:4001"))
    coverage.add_call("POST", "http://other:4001/api/driver/v1/claim", "200", "r:t1", {})
    coverage.add_call("POST", "http://h:4001/api/driver/v1/claim", "200", "r:t1", {})
    result = coverage.result(total_tests=1)
    assert result["summary"]["matchedCalls"] == 1 and result["spec"]["hosts"] == ["h:4001"]
