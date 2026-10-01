"""Run-level views over the history index.

Everything here works on the already-built index, so the client never has to
download `history.jsonl` to browse individual runs.
"""

from .common import normalize_status
from .models import HistoryIndexData, HistoryResultRecord

INCIDENT_STATUSES = {"failed", "broken"}
STATUS_ORDER = {"failed": 0, "broken": 1, "unknown": 2, "skipped": 3, "passed": 4}


def matches_status_filter(status: str, status_filter: str | None) -> bool:
    if not status_filter or status_filter == "all":
        return True
    if status_filter == "incidents":
        return status in INCIDENT_STATUSES
    return status == status_filter


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
    return {
        "id": result.test_key,
        "name": result.name or result.test_key,
        "fullName": result.test_key,
        "status": normalize_status(result.status),
        "duration": result.duration,
        "message": result.message,
        "suite": result.suite or None,
        "tags": list(result.tags),
    }


def sort_results(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: (STATUS_ORDER.get(item["status"], 2), item["name"]))


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
    items = sort_results(
        [
            to_result_item(result)
            for result in index.results
            if result.run_uuid == run_uuid and matches_status_filter(normalize_status(result.status), status)
        ]
    )
    return {"run": summary, "total": len(items), "items": items[offset : offset + limit]}
