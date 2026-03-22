import json
import uuid
from pathlib import Path

from fastapi import HTTPException

from .common import coerce_int, coerce_optional_int, files_share_prefix
from .context import StorageContext
from .models import HistoryFilterOptions, HistoryIndexData, HistoryResultRecord, HistoryRunRecord
from .repositories import HistoryRepository


class HistoryIndexService:
    def __init__(self, context: StorageContext):
        self.context = context
        self.context.ensure_directories()
        self.repository = HistoryRepository(context)

    def ensure_index(self) -> None:
        history_file = self.repository.get_history_path()
        if not self.repository.history_exists():
            return

        if not self.repository.index_exists():
            self.write_index(self.build_history_index(history_file))
            return

        try:
            index = self.load_index()
        except HTTPException:
            self.write_index(self.build_history_index(history_file))
            return

        history_stat = history_file.stat()
        source_size = index.source_size
        source_mtime_ns = index.source_mtime_ns

        if source_size == history_stat.st_size and source_mtime_ns == history_stat.st_mtime_ns:
            return

        if history_stat.st_size > source_size and source_size >= 0:
            index = self.append_index_from_offset(index, history_file, source_size)
            self.write_index(index)
            return

        self.write_index(self.build_history_index(history_file))

    def refresh_index(self, new_history_path: Path) -> None:
        if not self.repository.history_exists() or not self.repository.index_exists():
            self.write_index(self.build_history_index(new_history_path))
            return

        index = self.load_index()
        old_size = index.source_size
        if new_history_path.stat().st_size >= old_size and files_share_prefix(
            self.repository.get_history_path(),
            new_history_path,
            old_size,
        ):
            index = self.append_index_from_offset(index, new_history_path, old_size)
            self.write_index(index)
            return

        self.write_index(self.build_history_index(new_history_path))

    def rebuild_index(self) -> dict:
        if not self.repository.history_exists():
            raise HTTPException(status_code=404, detail="History file not found")

        self.write_index(self.build_history_index(self.repository.get_history_path()))
        return {"message": "History index rebuilt successfully"}

    def build_history_index(self, source_path: Path) -> HistoryIndexData:
        index = HistoryIndexData.empty(
            source_size=source_path.stat().st_size,
            source_mtime_ns=source_path.stat().st_mtime_ns,
        )
        index = self.append_index_from_offset(index, source_path, 0)
        return index

    def append_index_from_offset(
        self,
        index: HistoryIndexData,
        source_path: Path,
        offset: int,
    ) -> HistoryIndexData:
        run_ids = {run.uuid for run in index.runs}
        results = list(index.results)
        runs = list(index.runs)
        tags = set(index.filter_options.tags)
        suites = set(index.filter_options.suites)
        environments = set(index.filter_options.environments)
        records = index.records

        with source_path.open("r", encoding="utf-8") as source:
            if offset:
                source.seek(offset)
            for raw_line in source:
                line = raw_line.strip()
                if not line:
                    continue

                run = json.loads(line)
                records += 1
                run_uuid = run.get("uuid")
                run_name = run.get("name") or run_uuid
                run_timestamp = coerce_int(run.get("timestamp"))

                if isinstance(run_uuid, str) and run_uuid not in run_ids:
                    runs.append(HistoryRunRecord(uuid=run_uuid, name=run_name, timestamp=run_timestamp))
                    run_ids.add(run_uuid)

                for result in (run.get("testResults") or {}).values():
                    compact = self.compact_history_result(result, run_uuid, run_name, run_timestamp)
                    results.append(compact)
                    tags.update(compact.tags)
                    if compact.suite:
                        suites.add(compact.suite)
                    environments.add(compact.environment)

        stat = source_path.stat()
        return HistoryIndexData(
            version=index.version,
            source_size=stat.st_size,
            source_mtime_ns=stat.st_mtime_ns,
            records=records,
            runs=runs,
            results=results,
            filter_options=HistoryFilterOptions(
                tags=sorted(tags),
                suites=sorted(suites),
                environments=sorted(environments),
            ),
        )

    def load_index(self) -> HistoryIndexData:
        try:
            return self.repository.load_index()
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"History index is invalid: {exc}") from exc

    def write_index(self, index: HistoryIndexData) -> None:
        self.repository.write_index(index)

    def compact_history_result(
        self,
        result: dict,
        run_uuid: str | None,
        run_name: str | None,
        run_timestamp: int,
    ) -> HistoryResultRecord:
        labels = result.get("labels") or []
        tags = sorted(
            {
                label.get("value")
                for label in labels
                if isinstance(label, dict)
                and label.get("name") == "tag"
                and isinstance(label.get("value"), str)
            }
        )
        suite = next(
            (
                label.get("value")
                for label in labels
                if isinstance(label, dict)
                and label.get("name") in {"suite", "parentSuite"}
                and isinstance(label.get("value"), str)
            ),
            "unknown",
        )
        environment = result.get("environment")
        environment_value = (
            environment.strip()
            if isinstance(environment, str) and environment.strip()
            else "unknown"
        )
        test_key = (
            result.get("fullName")
            or result.get("name")
            or result.get("historyId")
            or result.get("id")
            or str(uuid.uuid4())
        )
        return HistoryResultRecord(
            run_uuid=run_uuid,
            run_name=run_name,
            timestamp=run_timestamp,
            test_key=test_key,
            name=result.get("fullName") or result.get("name") or test_key,
            status=result.get("status") if isinstance(result.get("status"), str) else None,
            duration=coerce_optional_int(result.get("duration")),
            start=coerce_optional_int(result.get("start")),
            stop=coerce_optional_int(result.get("stop")),
            environment=environment_value,
            suite=suite if isinstance(suite, str) and suite else "unknown",
            tags=tags,
            signature=self.build_signature(result),
            message=self.extract_message(result),
        )

    @staticmethod
    def build_signature(result: dict) -> str:
        message = result.get("message")
        if isinstance(message, str) and message.strip():
            line = message.split("\n", 1)[0].strip()
            return f"{line[:90]}…" if len(line) > 90 else line
        trace = result.get("trace")
        if isinstance(trace, str) and trace.strip():
            line = trace.split("\n", 1)[0].strip()
            return f"{line[:90]}…" if len(line) > 90 else line
        return "Unknown failure"

    @staticmethod
    def extract_message(result: dict) -> str | None:
        message = result.get("message")
        if isinstance(message, str) and message.strip():
            return message.split("\n", 1)[0].strip()
        trace = result.get("trace")
        if isinstance(trace, str) and trace.strip():
            return trace.split("\n", 1)[0].strip()
        return None

    def empty_filter_options(self) -> dict:
        return HistoryFilterOptions().to_dict()
