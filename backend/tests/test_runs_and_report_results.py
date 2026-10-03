import json
import tempfile
from pathlib import Path

from app.services.reporting import runs
from app.services.reporting.context import StorageContext
from app.services.reporting.models import HistoryFilterOptions, HistoryIndexData, HistoryResultRecord, HistoryRunRecord
from app.services.reporting.repositories.reports import ReportsRepository

REPORT_ID = "11111111-2222-4333-8444-555555555555"


def _result(run: str, key: str, status: str, start: int, message: str | None = None) -> HistoryResultRecord:
    return HistoryResultRecord(
        run_uuid=run,
        run_name=f"Run {run}",
        timestamp=start,
        test_key=key,
        name=key,
        status=status,
        duration=10,
        start=start,
        stop=start + 10,
        environment="local",
        suite="suite",
        tags=["smoke"],
        signature="",
        message=message,
    )


def _index() -> HistoryIndexData:
    results = [
        _result("old", "t#a", "passed", 1000),
        _result("old", "t#b", "passed", 1010),
        _result("new", "t#a", "passed", 2000),
        _result("new", "t#b", "broken", 2010, "IndexError: boom"),
        _result("new", "t#c", "failed", 2020, "AssertionError: nope"),
    ]
    return HistoryIndexData(
        version=1,
        source_size=0,
        source_mtime_ns=0,
        records=2,
        runs=[HistoryRunRecord("old", "Run old", 1000), HistoryRunRecord("new", "Run new", 2000)],
        results=results,
        filter_options=HistoryFilterOptions(),
    )


def test_list_runs_newest_first_with_counts_and_status():
    listing = runs.list_runs(_index())

    assert [item["uuid"] for item in listing["items"]] == ["new", "old"]
    newest = listing["items"][0]
    assert (newest["total"], newest["passed"], newest["failed"], newest["broken"]) == (3, 1, 1, 1)
    assert newest["status"] == "failed"
    assert newest["duration"] == 30
    assert listing["counts"] == {"all": 2, "failed": 1, "broken": 0, "passed": 1}


def test_list_runs_filters_and_pages():
    assert [i["uuid"] for i in runs.list_runs(_index(), status="passed")["items"]] == ["old"]
    assert [i["uuid"] for i in runs.list_runs(_index(), search="OLD")["items"]] == ["old"]
    page = runs.list_runs(_index(), limit=1, offset=1)
    assert page["total"] == 2 and [i["uuid"] for i in page["items"]] == ["old"]


def test_run_results_default_to_incidents_failed_first():
    results = runs.get_run_results(_index(), "new")

    assert results["total"] == 2
    assert [(i["id"], i["status"]) for i in results["items"]] == [("t#c", "failed"), ("t#b", "broken")]
    assert results["items"][1]["message"] == "IndexError: boom"
    assert runs.get_run_results(_index(), "new", status="all")["total"] == 3
    assert runs.get_run_results(_index(), "missing") is None


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


def test_report_results_read_allure3_data_with_error_details():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        report_root = root / "reports" / REPORT_ID / "2026-09-25_11-27"
        (report_root / "data" / "test-results").mkdir(parents=True)
        (report_root / "index.html").write_text("<html></html>", encoding="utf-8")
        (report_root / "test-results.json").write_text(
            json.dumps(
                {
                    "byId": {
                        "aaa": {"id": "aaa", "name": "Green", "duration": 5, "status": "passed"},
                        "bbb": {"id": "bbb", "name": "Red", "duration": 7, "status": "broken"},
                    }
                }
            ),
            encoding="utf-8",
        )
        (report_root / "data" / "test-results" / "bbb.json").write_text(
            json.dumps(
                {
                    "fullName": "Claims.Tests.mod#test_red",
                    "error": {"message": "PostgresConnectError: no route\n"},
                    "labels": [{"name": "suite", "value": "Robot"}, {"name": "tag", "value": "robot_new"}],
                }
            ),
            encoding="utf-8",
        )

        repo = ReportsRepository(_context(root))
        results = {item["id"]: item for item in repo.read_report_results(REPORT_ID)}

        assert results["aaa"]["message"] is None
        assert results["bbb"]["fullName"] == "Claims.Tests.mod#test_red"
        assert results["bbb"]["message"] == "PostgresConnectError: no route"
        assert (results["bbb"]["suite"], results["bbb"]["tags"]) == ("Robot", ["robot_new"])
        assert repo.read_report_results("22222222-2222-4333-8444-555555555555") is None


def _changes_index() -> HistoryIndexData:
    results = [
        _result("r1", "t#stable", "passed", 1000),
        _result("r1", "t#breaks", "passed", 1010),
        _result("r1", "t#heals", "failed", 1020, "AssertionError: x"),
        _result("r1", "t#stuck", "broken", 1030, "KeyError: 'items'"),
        _result("r2", "t#stable", "passed", 2000),
        _result("r2", "t#breaks", "failed", 2010, "AssertionError: y"),
        _result("r2", "t#heals", "passed", 2020),
        _result("r2", "t#stuck", "broken", 2030, "KeyError: 'items'"),
        _result("r2", "t#fresh", "failed", 2040, "TimeoutError"),
    ]
    for item in results:
        item.signature = item.message or ""
    return HistoryIndexData(
        version=1,
        source_size=0,
        source_mtime_ns=0,
        records=2,
        runs=[HistoryRunRecord("r1", "Run r1", 1000), HistoryRunRecord("r2", "Run r2", 2000)],
        results=results,
        filter_options=HistoryFilterOptions(),
    )


def test_run_results_compare_with_previous_run():
    results = runs.get_run_results(_changes_index(), "r2", status="all")
    by_key = {item["testKey"]: item for item in results["items"]}

    assert results["changes"] == {"newFailures": 1, "stillFailing": 1, "fixed": 1, "newTests": 1}
    assert by_key["t#breaks"]["change"] == "new_failure"
    assert by_key["t#breaks"]["previous"] == {"status": "passed", "runName": "Run r1", "runUuid": "r1", "at": 1020}
    assert by_key["t#stuck"]["change"] == "still_failing"
    assert by_key["t#heals"]["change"] == "fixed"
    assert by_key["t#fresh"]["change"] == "new_test" and by_key["t#fresh"]["previous"] is None
    assert by_key["t#stable"]["change"] is None
    assert by_key["t#breaks"]["signature"] == "AssertionError: y"
    assert by_key["t#heals"]["signature"] is None
    # New failures go before failures that were already red.
    failed = [item["testKey"] for item in results["items"] if item["status"] == "failed"]
    assert failed == ["t#breaks", "t#fresh"]


def test_run_results_changes_filter_and_first_run():
    changed = runs.get_run_results(_changes_index(), "r2", status="changes")
    assert sorted(item["testKey"] for item in changed["items"]) == ["t#breaks", "t#fresh", "t#heals"]

    first = runs.get_run_results(_changes_index(), "r1", status="all")
    assert first["changes"]["newTests"] == 4
    assert all(item["previous"] is None for item in first["items"])


def test_annotate_changes_ignores_results_after_cutoff():
    lookup = runs.build_previous_lookup(_changes_index())
    items = [{"testKey": "t#breaks", "status": "failed"}]

    # A report uploaded between r1 and r2 compares with r1 only.
    counters = runs.annotate_changes(items, lookup, before=1500)
    assert counters["newFailures"] == 1 and items[0]["previous"]["runUuid"] == "r1"

    # The same run in history (same start) is excluded by the cutoff.
    runs.annotate_changes(items, lookup, before=2010)
    assert items[0]["previous"]["runUuid"] == "r1"
