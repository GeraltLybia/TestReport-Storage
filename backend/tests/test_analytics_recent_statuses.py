from app.services.reporting.analytics import RECENT_STATUSES_LIMIT, HistoryAnalyticsService
from app.services.reporting.models import (
    HistoryFilterOptions,
    HistoryIndexData,
    HistoryResultRecord,
    HistoryRunRecord,
)


class _IndexServiceStub:
    @staticmethod
    def empty_filter_options() -> dict:
        return HistoryFilterOptions().to_dict()


def _result(run: int, status: str, key: str = "suite#test_a") -> HistoryResultRecord:
    return HistoryResultRecord(
        run_uuid=f"run-{run}",
        run_name=f"Run {run}",
        timestamp=run * 1000,
        test_key=key,
        name=key,
        status=status,
        duration=100,
        start=run * 1000,
        stop=run * 1000 + 100,
        environment="local",
        suite="suite",
        tags=[],
        signature="Boom" if status in {"failed", "broken"} else "",
        message=None,
    )


def _index(results: list[HistoryResultRecord]) -> HistoryIndexData:
    runs = {r.run_uuid: HistoryRunRecord(uuid=r.run_uuid, name=r.run_name, timestamp=r.timestamp) for r in results}
    return HistoryIndexData(
        version=1,
        source_size=0,
        source_mtime_ns=0,
        records=len(results),
        runs=list(runs.values()),
        results=results,
        filter_options=HistoryFilterOptions(),
    )


def test_unstable_tests_expose_recent_statuses_oldest_first():
    # Shuffled on purpose: order must come from `stop`, not from input order.
    results = [_result(3, "broken"), _result(1, "passed"), _result(2, "failed")]

    dashboard = HistoryAnalyticsService(_IndexServiceStub()).get_dashboard(_index(results))

    [unstable] = dashboard["topUnstableTests"]
    assert unstable["recentStatuses"] == ["passed", "failed", "broken"]


def test_recent_statuses_are_limited():
    statuses = ["passed", "failed"] * RECENT_STATUSES_LIMIT
    results = [_result(i, status) for i, status in enumerate(statuses)]

    dashboard = HistoryAnalyticsService(_IndexServiceStub()).get_dashboard(_index(results))

    [unstable] = dashboard["topUnstableTests"]
    assert len(unstable["recentStatuses"]) == RECENT_STATUSES_LIMIT
    assert unstable["recentStatuses"][-1] == statuses[-1]


def test_always_failing_tests_are_not_listed_as_unstable():
    results = [_result(1, "broken", key="suite#always_broken"), _result(2, "failed", key="suite#always_broken")]
    results += [_result(1, "passed", key="suite#flaky"), _result(2, "failed", key="suite#flaky")]

    dashboard = HistoryAnalyticsService(_IndexServiceStub()).get_dashboard(_index(results))

    assert [item["key"] for item in dashboard["topUnstableTests"]] == ["suite#flaky"]
    assert dashboard["stabilitySummary"]["alwaysFailed"] == 1
