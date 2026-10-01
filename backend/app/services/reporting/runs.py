"""Run-level views over the history index.

Everything here works on the already-built index, so the client never has to
download `history.jsonl` to browse individual runs.
"""

from .common import normalize_status
from .models import HistoryIndexData, HistoryResultRecord

INCIDENT_STATUSES = {"failed", "broken"}
STATUS_ORDER = {"failed": 0, "broken": 1, "unknown": 2, "skipped": 3, "passed": 4}


CHANGE_KINDS = ("new_failure", "still_failing", "fixed", "new_test")


def matches_status_filter(status: str, status_filter: str | None, change: str | None = None) -> bool:
    if not status_filter or status_filter == "all":
        return True
    if status_filter == "incidents":
        return status in INCIDENT_STATUSES
    if status_filter == "changes":
        return change in {"new_failure", "fixed"} or (change == "new_test" and status in INCIDENT_STATUSES)
    return status == status_filter


def _result_moment(result: HistoryResultRecord) -> int:
    return result.stop or result.start or result.timestamp or 0


def build_previous_lookup(index: HistoryIndexData) -> dict[str, list[HistoryResultRecord]]:
    """test_key -> its results ordered by time, for "what was it last time" questions."""
    lookup: dict[str, list[HistoryResultRecord]] = {}
    for result in index.results:
        lookup.setdefault(result.test_key, []).append(result)
    for results in lookup.values():
        results.sort(key=_result_moment)
    return lookup


def annotate_changes(
    items: list[dict],
    lookup: dict[str, list[HistoryResultRecord]],
    before: int,
    exclude_run: str | None = None,
) -> dict:
    """Compares every item with the previous result of the same test before `before`.

    Sets `previous` and `change` on each item (new_failure / still_failing / fixed /
    new_test / None) and returns the counters.
    """
    counters = {"newFailures": 0, "stillFailing": 0, "fixed": 0, "newTests": 0}
    for item in items:
        previous = None
        for result in reversed(lookup.get(item["testKey"], [])):
            if result.run_uuid != exclude_run and _result_moment(result) < before:
                previous = result
                break
        now_incident = item["status"] in INCIDENT_STATUSES
        if previous is None:
            change = "new_test"
            counters["newTests"] += 1
        else:
            was_incident = normalize_status(previous.status) in INCIDENT_STATUSES
            if now_incident and was_incident:
                change, key = "still_failing", "stillFailing"
            elif now_incident:
                change, key = "new_failure", "newFailures"
            elif was_incident and item["status"] == "passed":
                change, key = "fixed", "fixed"
            else:
                change, key = None, None
            if key:
                counters[key] += 1
        item["change"] = change
        item["previous"] = (
            {
                "status": normalize_status(previous.status),
                "runName": previous.run_name,
                "runUuid": previous.run_uuid,
                "at": _result_moment(previous),
            }
            if previous
            else None
        )
    return counters


def resolve_run_status(passed: int, failed: int, broken: int, total: int) -> str:
    if failed:
        return "failed"
    if broken:
        return "broken"
    if total and passed == total:
        return "passed"
    return "unknown" if not total else "passed"


def build_run_summaries(index: HistoryIndexData) -> list[dict]:
    """One summary per run, newest first."""
    buckets: dict[str, dict] = {}
    for run in index.runs:
        buckets[run.uuid] = {
            "uuid": run.uuid,
            "name": run.name or run.uuid,
            "timestamp": run.timestamp,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "broken": 0,
            "other": 0,
            "start": None,
            "stop": None,
        }

    for result in index.results:
        if not result.run_uuid:
            continue
        bucket = buckets.get(result.run_uuid)
        if bucket is None:
            bucket = buckets[result.run_uuid] = {
                "uuid": result.run_uuid,
                "name": result.run_name or result.run_uuid,
                "timestamp": result.timestamp,
                "total": 0,
                "passed": 0,
                "failed": 0,
                "broken": 0,
                "other": 0,
                "start": None,
                "stop": None,
            }
        status = normalize_status(result.status)
        bucket["total"] += 1
        if status in {"passed", "failed", "broken"}:
            bucket[status] += 1
        else:
            bucket["other"] += 1
        if result.start:
            bucket["start"] = result.start if bucket["start"] is None else min(bucket["start"], result.start)
        if result.stop:
            bucket["stop"] = result.stop if bucket["stop"] is None else max(bucket["stop"], result.stop)

    summaries = []
    for bucket in buckets.values():
        start, stop = bucket.pop("start"), bucket.pop("stop")
        bucket["duration"] = stop - start if start and stop and stop >= start else None
        bucket["passRate"] = round(bucket["passed"] / bucket["total"] * 100) if bucket["total"] else 0
        bucket["status"] = resolve_run_status(bucket["passed"], bucket["failed"], bucket["broken"], bucket["total"])
        summaries.append(bucket)

    summaries.sort(key=lambda item: item["timestamp"], reverse=True)
    return summaries


def list_runs(
    index: HistoryIndexData,
    search: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    summaries = build_run_summaries(index)
    counts = {"all": len(summaries), "failed": 0, "broken": 0, "passed": 0}
    for item in summaries:
        if item["status"] in counts:
            counts[item["status"]] += 1

    needle = (search or "").strip().lower()
    filtered = [
        item
        for item in summaries
        if (not status or status == "all" or item["status"] == status)
        and (not needle or needle in item["name"].lower() or item["uuid"].startswith(needle))
    ]
    return {
        "total": len(filtered),
        "counts": counts,
        "items": filtered[offset : offset + limit],
    }


def to_result_item(result: HistoryResultRecord) -> dict:
    status = normalize_status(result.status)
    return {
        "id": result.test_key,
        "testKey": result.test_key,
        "signature": result.signature if status in INCIDENT_STATUSES else None,
        "name": result.name or result.test_key,
        "fullName": result.test_key,
        "status": status,
        "duration": result.duration,
        "message": result.message,
        "suite": result.suite or None,
        "tags": list(result.tags),
    }


CHANGE_ORDER = {"new_failure": 0, "new_test": 1, "still_failing": 2, "fixed": 3}


def sort_results(items: list[dict]) -> list[dict]:
    """Failures first, and among them the ones that broke in this run first."""
    return sorted(
        items,
        key=lambda item: (STATUS_ORDER.get(item["status"], 2), CHANGE_ORDER.get(item.get("change"), 4), item["name"]),
    )


def get_run_results(
    index: HistoryIndexData,
    run_uuid: str,
    status: str | None = "incidents",
    limit: int = 200,
    offset: int = 0,
) -> dict | None:
    summary = next((item for item in build_run_summaries(index) if item["uuid"] == run_uuid), None)
    if summary is None:
        return None
    all_items = [to_result_item(result) for result in index.results if result.run_uuid == run_uuid]
    run_start = min(
        (result.start or result.stop or result.timestamp for result in index.results if result.run_uuid == run_uuid),
        default=summary["timestamp"],
    )
    changes = annotate_changes(all_items, build_previous_lookup(index), before=run_start, exclude_run=run_uuid)
    items = sort_results([item for item in all_items if matches_status_filter(item["status"], status, item["change"])])
    return {"run": summary, "total": len(items), "items": items[offset : offset + limit], "changes": changes}
