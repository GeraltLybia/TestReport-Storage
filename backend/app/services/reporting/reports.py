import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .common import safe_extract_zip
from .context import StorageContext
from .repositories import ReportsRepository


class ReportStorageService:
    def __init__(self, context: StorageContext):
        self.context = context
        self.context.ensure_directories()
        self.repository = ReportsRepository(context)

    def list_reports(self) -> list[dict]:
        return [entry.to_dict() for entry in self.repository.list_report_entries()]

    async def upload_report(self, file: UploadFile) -> dict:
        if not file.filename or not file.filename.endswith(".zip"):
            raise HTTPException(status_code=400, detail="Only ZIP files are supported")

        report_id = str(uuid.uuid4())
        report_path = self.repository.create_report_directory(report_id)
        zip_path = report_path / "temp.zip"

        try:
            with zip_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            with zipfile.ZipFile(zip_path, "r") as archive:
                safe_extract_zip(archive, report_path)

            zip_path.unlink(missing_ok=True)
            self.repository.apply_retention()
            return {
                "id": report_id,
                "message": "Report uploaded and extracted successfully",
            }
        except zipfile.BadZipFile as exc:
            self.repository.remove_path(report_path)
            raise HTTPException(status_code=400, detail="Invalid ZIP file") from exc
        except HTTPException:
            self.repository.remove_path(report_path)
            raise
        except Exception as exc:
            self.repository.remove_path(report_path)
            raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc
        finally:
            await file.close()

    def delete_report(self, report_id: str) -> dict:
        if not self.repository.report_exists(report_id):
            raise HTTPException(status_code=404, detail="Report not found")

        try:
            self.repository.delete_report(report_id)
            return {"message": "Report deleted successfully"}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Delete failed: {exc}") from exc

    def create_report_archive(self, report_id: str) -> tuple[Path, str]:
        if not self.repository.report_exists(report_id):
            raise HTTPException(status_code=404, detail="Report not found")
        return self.repository.create_archive(report_id)
