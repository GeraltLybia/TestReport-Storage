import json
import shutil
from datetime import datetime
from pathlib import Path

from ..common import coerce_int, is_date_like_dir
from ..context import StorageContext
from ..models import ReportEntry, ReportSummary


class ReportsRepository:
    def __init__(self, context: StorageContext):
        self.context = context
        self.context.ensure_directories()

    def list_report_entries(self) -> list[ReportEntry]:
        if not self.context.reports_folder.exists():
            return []

        entries: list[ReportEntry] = []
        for report_dir in self.context.reports_folder.iterdir():
            if not report_dir.is_dir():
                continue

            stat = report_dir.stat()
            size = sum(file_path.stat().st_size for file_path in report_dir.rglob("*") if file_path.is_file())
            report_root = self.resolve_report_root(report_dir)
            entry_path = self.build_entry_path(report_dir, report_root)
            summary = self.read_report_summary(report_dir, report_root)
            entries.append(
                ReportEntry(
                    id=report_dir.name,
                    name=summary.name or report_dir.name,
                    created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    size=size,
                    entry_path=entry_path,
                    stats=summary.stats,
                    status=summary.status,
                    duration=summary.duration,
                )
            )

        return sorted(entries, key=lambda item: item.created_at, reverse=True)

    def create_report_directory(self, report_id: str) -> Path:
        report_path = self.context.reports_folder / report_id
        report_path.mkdir(parents=True, exist_ok=True)
        return report_path

    def report_exists(self, report_id: str) -> bool:
        return (self.context.reports_folder / report_id).exists()

    def delete_report(self, report_id: str) -> None:
        shutil.rmtree(self.context.reports_folder / report_id)

    def create_archive(self, report_id: str) -> tuple[Path, str]:
        report_path = self.context.reports_folder / report_id
        zip_path = self.context.reports_folder / f"{report_id}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", report_path)
        return zip_path, f"{report_id}.zip"

    def remove_path(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)

    def apply_retention(self) -> None:
        report_dirs = [path for path in self.context.reports_folder.iterdir() if path.is_dir()]
        if len(report_dirs) <= self.context.max_reports:
            return

        report_dirs.sort(key=lambda path: path.stat().st_ctime)
        for old_report_dir in report_dirs[: len(report_dirs) - self.context.max_reports]:
            shutil.rmtree(old_report_dir)

    def resolve_report_root(self, report_dir: Path) -> Path | None:
        index_in_root = report_dir / "index.html"
        if index_in_root.exists():
            return report_dir

        candidates: list[Path] = []
        for index_path in report_dir.rglob("index.html"):
            if "__MACOSX" not in index_path.parts:
                candidates.append(index_path.parent)

        if not candidates:
            return None

        candidates.sort(
            key=lambda path: (
                0 if is_date_like_dir(path.name) else 1,
                len(path.relative_to(report_dir).parts),
                path.as_posix(),
            )
        )
        return candidates[0]

    def build_entry_path(self, report_dir: Path, report_root: Path | None) -> str | None:
        if report_root is None:
            return None
        relative_root = report_root.relative_to(report_dir)
        if not relative_root.parts:
            return f"{report_dir.name}/index.html"
        return f"{report_dir.name}/{relative_root.as_posix()}/index.html"

    def read_report_summary(self, report_dir: Path, report_root: Path | None) -> ReportSummary:
        candidates: list[Path] = []
        if report_root is not None:
            candidates.append(report_root / "summary.json")
        candidates.append(report_dir / "summary.json")

        for summary_path in report_dir.rglob("summary.json"):
            if "__MACOSX" not in summary_path.parts and summary_path not in candidates:
                candidates.append(summary_path)

        for summary_path in candidates:
            if not summary_path.exists() or not summary_path.is_file():
                continue

            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
                stats = payload.get("stats") or {}
                status = payload.get("status")
                return ReportSummary(
                    name=payload.get("name") if isinstance(payload.get("name"), str) else None,
                    stats={
                        "total": coerce_int(stats.get("total")),
                        "passed": coerce_int(stats.get("passed")),
                        "failed": coerce_int(stats.get("failed")),
                        "flaky": coerce_int(stats.get("flaky")),
                        "broken": coerce_int(stats.get("broken")),
                    },
                    status=status if isinstance(status, str) else None,
                    duration=coerce_int(payload.get("duration")),
                )
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                continue

        return ReportSummary()
