import json
import re
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile


class StorageService:
    def __init__(self, reports_folder: Path, history_file: Path, max_reports: int):
        self.reports_folder = reports_folder
        self.history_file = history_file
        self.max_reports = max_reports
        self.reports_folder.mkdir(parents=True, exist_ok=True)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

    def list_reports(self) -> list[dict]:
        if not self.reports_folder.exists():
            return []

        reports: list[dict] = []
        for report_dir in self.reports_folder.iterdir():
            if not report_dir.is_dir():
                continue

            stat = report_dir.stat()
            size = sum(f.stat().st_size for f in report_dir.rglob("*") if f.is_file())
            report_root = self._resolve_report_root(report_dir)
            entry_path = self._build_entry_path(report_dir, report_root)
            summary = self._read_report_summary(report_dir, report_root)
            reports.append(
                {
                    "id": report_dir.name,
                    "name": summary.get("name") or report_dir.name,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "size": size,
                    "entry_path": entry_path,
                    "stats": summary.get("stats"),
                    "status": summary.get("status"),
                    "duration": summary.get("duration"),
                }
            )

        return sorted(reports, key=lambda x: x["created_at"], reverse=True)

    async def upload_report(self, file: UploadFile) -> dict:
        if not file.filename or not file.filename.endswith(".zip"):
            raise HTTPException(status_code=400, detail="Only ZIP files are supported")

        report_id = str(uuid.uuid4())
        report_path = self.reports_folder / report_id
        report_path.mkdir(parents=True, exist_ok=True)

        zip_path = report_path / "temp.zip"
        try:
            with zip_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            with zipfile.ZipFile(zip_path, "r") as archive:
                self._safe_extract_zip(archive, report_path)

            zip_path.unlink(missing_ok=True)
            self._apply_reports_retention()
            return {
                "id": report_id,
                "message": "Report uploaded and extracted successfully",
            }
        except zipfile.BadZipFile as exc:
            self._cleanup(report_path)
            raise HTTPException(status_code=400, detail="Invalid ZIP file") from exc
        except HTTPException:
            self._cleanup(report_path)
            raise
        except Exception as exc:
            self._cleanup(report_path)
            raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc
        finally:
            await file.close()

    def get_history_path(self) -> Path:
        if not self.history_file.exists():
            raise HTTPException(status_code=404, detail="History file not found")
        return self.history_file

    async def upload_history(self, file: UploadFile) -> dict:
        if not file.filename or not (
            file.filename.endswith(".jsonl") or file.filename.endswith(".json")
        ):
            raise HTTPException(status_code=400, detail="Only JSONL files are supported")

        try:
            content = await file.read()
            self._validate_jsonl(content)
            self.history_file.write_bytes(content)
            return {"message": "History file updated successfully"}
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSONL format") from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc
        finally:
            await file.close()

    def history_info(self) -> dict:
        if not self.history_file.exists():
            return {"records": 0, "updated_at": None, "size": 0}

        stat = self.history_file.stat()
        with self.history_file.open("r", encoding="utf-8") as source:
            records = sum(1 for line in source if line.strip())

        return {
            "records": records,
            "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size": stat.st_size,
        }

    def delete_report(self, report_id: str) -> dict:
        report_path = self.reports_folder / report_id
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="Report not found")

        try:
            shutil.rmtree(report_path)
            return {"message": "Report deleted successfully"}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Delete failed: {exc}") from exc

    def create_report_archive(self, report_id: str) -> tuple[Path, str]:
        report_path = self.reports_folder / report_id
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="Report not found")

        zip_path = self.reports_folder / f"{report_id}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", report_path)
        return zip_path, f"{report_id}.zip"

    def _resolve_report_root(self, report_dir: Path) -> Path | None:
        index_in_root = report_dir / "index.html"
        if index_in_root.exists():
            return report_dir

        candidates: list[Path] = []
        for index_path in report_dir.rglob("index.html"):
            if "__MACOSX" in index_path.parts:
                continue
            candidates.append(index_path.parent)

        if not candidates:
            return None

        candidates.sort(
            key=lambda path: (
                0 if self._is_date_like_dir(path.name) else 1,
                len(path.relative_to(report_dir).parts),
                path.as_posix(),
            )
        )
        return candidates[0]

    def _build_entry_path(self, report_dir: Path, report_root: Path | None) -> str | None:
        if report_root is None:
            return None
        relative_root = report_root.relative_to(report_dir)
        if not relative_root.parts:
            return f"{report_dir.name}/index.html"
        return f"{report_dir.name}/{relative_root.as_posix()}/index.html"

    def _validate_jsonl(self, content: bytes) -> None:
        lines = content.decode("utf-8").strip().split("\n")
        for line in lines:
            if line.strip():
                json.loads(line)

    def _read_report_summary(self, report_dir: Path, report_root: Path | None) -> dict:
        candidates: list[Path] = []
        if report_root is not None:
            candidates.append(report_root / "summary.json")
        candidates.append(report_dir / "summary.json")
        for summary_path in report_dir.rglob("summary.json"):
            if "__MACOSX" in summary_path.parts:
                continue
            if summary_path not in candidates:
                candidates.append(summary_path)

        for summary_path in candidates:
            if not summary_path.exists() or not summary_path.is_file():
                continue

            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
                stats = payload.get("stats") or {}
                total = self._coerce_int(stats.get("total"))
                passed = self._coerce_int(stats.get("passed"))
                failed = self._coerce_int(stats.get("failed"))
                flaky = self._coerce_int(stats.get("flaky"))
                broken = self._coerce_int(stats.get("broken"))
                duration = self._coerce_int(payload.get("duration"))
                status = payload.get("status")

                return {
                    "name": payload.get("name"),
                    "stats": {
                        "total": total,
                        "passed": passed,
                        "failed": failed,
                        "flaky": flaky,
                        "broken": broken,
                    },
                    "status": status if isinstance(status, str) else None,
                    "duration": duration,
                }
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                continue

        return {}

    def _is_date_like_dir(self, value: str) -> bool:
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}([_-].+)?$", value))

    def _coerce_int(self, value: object) -> int:
        if isinstance(value, bool):
            return 0
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _safe_extract_zip(self, archive: zipfile.ZipFile, destination: Path) -> None:
        destination_resolved = destination.resolve()

        for member in archive.infolist():
            member_path = (destination / member.filename).resolve()
            if destination_resolved not in member_path.parents and member_path != destination_resolved:
                raise HTTPException(status_code=400, detail="Archive contains invalid paths")

        archive.extractall(destination)

    def _cleanup(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)

    def _apply_reports_retention(self) -> None:
        report_dirs = [path for path in self.reports_folder.iterdir() if path.is_dir()]
        if len(report_dirs) <= self.max_reports:
            return

        report_dirs.sort(key=lambda path: path.stat().st_ctime)
        for old_report_dir in report_dirs[: len(report_dirs) - self.max_reports]:
            shutil.rmtree(old_report_dir)
