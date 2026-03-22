from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageContext:
    reports_folder: Path
    history_file: Path
    history_index_file: Path
    max_reports: int

    def ensure_directories(self) -> None:
        self.reports_folder.mkdir(parents=True, exist_ok=True)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
