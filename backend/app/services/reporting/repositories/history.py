import json
from pathlib import Path

from ..context import StorageContext
from ..models import HistoryIndexData


class HistoryRepository:
    def __init__(self, context: StorageContext):
        self.context = context
        self.context.ensure_directories()

    def history_exists(self) -> bool:
        return self.context.history_file.exists()

    def index_exists(self) -> bool:
        return self.context.history_index_file.exists()

    def get_history_path(self) -> Path:
        return self.context.history_file

    def read_history_stat(self):
        return self.context.history_file.stat()

    def create_upload_temp_path(self) -> Path:
        return self.context.history_file.with_suffix(".upload.tmp")

    def write_history_bytes(self, content: bytes, path: Path) -> None:
        path.write_bytes(content)

    def replace_history(self, source: Path) -> None:
        source.replace(self.context.history_file)

    def delete_temp_file(self, path: Path) -> None:
        path.unlink(missing_ok=True)

    def load_index(self) -> HistoryIndexData:
        payload = json.loads(self.context.history_index_file.read_text(encoding="utf-8"))
        return HistoryIndexData.from_dict(payload)

    def write_index(self, index: HistoryIndexData) -> None:
        temp_path = self.context.history_index_file.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(index.to_dict(), ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temp_path.replace(self.context.history_index_file)
