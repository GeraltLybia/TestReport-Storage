"""Coverage measurements: a snapshot of (spec or schema) x (selected reports)."""

from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from ..reporting.context import StorageContext
from ..reporting.repositories import ReportsRepository
from .graphql_coverage import GraphqlCoverage, SchemaError, load_schema
from .log_parser import parse_log
from .report_logs import iter_report_test_logs
from .rest import RestCoverage, SpecError, load_rest_spec

logger = logging.getLogger(__name__)

MEASUREMENT_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_SPEC_SIZE_BYTES = 20 * 1024 * 1024
KINDS = {"rest", "graphql"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CoverageService:
    def __init__(self, context: StorageContext):
        self.context = context
        self.reports = ReportsRepository(context)
        self.folder = context.reports_folder.parent / "coverage"
        self.folder.mkdir(parents=True, exist_ok=True)

    # ─── storage ───
    def _measurement_dir(self, measurement_id: str) -> Path | None:
        if not MEASUREMENT_ID_RE.match(measurement_id or ""):
            return None
        path = self.folder / measurement_id
        return path if path.is_dir() else None

    def list_measurements(self) -> list[dict]:
        items = []
        for path in self.folder.iterdir():
            meta_path = path / "meta.json"
            if not path.is_dir() or not meta_path.exists():
                continue
            try:
                items.append(json.loads(meta_path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                logger.warning("Broken coverage measurement skipped: %s", path.name)
        return sorted(items, key=lambda item: item.get("createdAt", ""), reverse=True)

    def get_measurement(self, measurement_id: str) -> dict:
        path = self._measurement_dir(measurement_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Measurement not found")
        meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
        result = json.loads((path / "result.json").read_text(encoding="utf-8"))
        return {**meta, "result": result}

    def delete_measurement(self, measurement_id: str) -> dict:
        path = self._measurement_dir(measurement_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Measurement not found")
        shutil.rmtree(path)
        return {"message": "Measurement deleted"}

    # ─── calculation ───
    def create_measurement(
        self,
        *,
        name: str,
        kind: str,
        spec_filename: str,
        spec_bytes: bytes,
        report_ids: list[str],
        base_path: str | None = None,
        host: str | None = None,
        endpoint: str | None = None,
    ) -> dict:
        if kind not in KINDS:
            raise HTTPException(status_code=400, detail="kind must be rest or graphql")
        if not spec_bytes:
            raise HTTPException(status_code=400, detail="Файл спецификации пустой")
        if len(spec_bytes) > MAX_SPEC_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="Файл спецификации слишком большой")
        report_ids = list(dict.fromkeys(item.strip() for item in report_ids if item.strip()))
        if not report_ids:
            raise HTTPException(status_code=400, detail="Выберите хотя бы один отчёт")
        unknown = [report_id for report_id in report_ids if not self.reports.report_exists(report_id)]
        if unknown:
            raise HTTPException(status_code=404, detail=f"Отчёты не найдены: {', '.join(unknown)}")

        text = spec_bytes.decode("utf-8", errors="replace")
        spec_info: dict
        try:
            if kind == "rest":
                try:
                    document = json.loads(text)
                except ValueError as exc:
                    raise SpecError("Ожидается openapi.json (JSON)") from exc
                spec = load_rest_spec(document, base_path_override=base_path or None, host_override=host or None)
                coverage = RestCoverage(spec)
                spec_info = {"title": spec.title, "version": spec.version, "basePath": spec.base_path,
                             "hosts": sorted(spec.hosts)}
            else:
                schema = load_schema(text)
                coverage = GraphqlCoverage(schema, endpoint=endpoint or None)
                spec_info = {"endpoint": endpoint or None}
        except (SpecError, SchemaError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        report_entries = {entry.id: entry for entry in self.reports.list_report_entries()}
        tests_with_logs = 0
        for report_id in report_ids:
            for log in iter_report_test_logs(self.reports, report_id):
                tests_with_logs += 1
                parsed = parse_log(log.text)
                test_key = f"{report_id}:{log.test_id}"
                test = {"name": log.name, "fullName": log.full_name, "reportId": report_id, "testId": log.test_id}
                if kind == "rest":
                    for call in parsed.rest:
                        coverage.add_call(call.method, call.url, call.status, test_key, test)
                else:
                    for call in parsed.graphql:
                        coverage.add_call(call.url, call.query, test_key, test)

        result = coverage.result(total_tests=tests_with_logs)
        measurement_id = str(uuid.uuid4())
        meta = {
            "id": measurement_id,
            "name": name.strip() or spec_filename,
            "kind": kind,
            "createdAt": _now(),
            "spec": {"filename": spec_filename, "size": len(spec_bytes), **spec_info},
            "reports": [
                {"id": report_id, "name": report_entries[report_id].name if report_id in report_entries else report_id}
                for report_id in report_ids
            ],
            "summary": result["summary"],
        }

        target = self.folder / measurement_id
        target.mkdir(parents=True)
        suffix = Path(spec_filename).suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,10}", Path(spec_filename).suffix.lower()) else ".txt"
        (target / f"spec{suffix}").write_bytes(spec_bytes)
        (target / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        (target / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        logger.info("Coverage measurement %s created: kind=%s reports=%s", measurement_id, kind, len(report_ids))
        return {**meta, "result": result}
