import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

try:
    from fastapi import HTTPException
except ModuleNotFoundError:
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)


def coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def coerce_optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_status(value: object) -> str:
    return value.strip().lower() if isinstance(value, str) and value.strip() else "unknown"


def percentile(values: list[int], q: int) -> int | None:
    if not values:
        return None
    index = min(len(values) - 1, round((q / 100) * (len(values) - 1)))
    return values[index]


def is_date_like_dir(value: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}([_-].+)?$", value))


def cleanup_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    destination_resolved = destination.resolve()
    for member in archive.infolist():
        member_path = (destination / member.filename).resolve()
        if destination_resolved not in member_path.parents and member_path != destination_resolved:
            raise HTTPException(status_code=400, detail="Archive contains invalid paths")
    archive.extractall(destination)


def validate_jsonl(content: bytes) -> None:
    lines = content.decode("utf-8").strip().split("\n")
    for line in lines:
        if line.strip():
            json.loads(line)


def files_share_prefix(left: Path, right: Path, size: int) -> bool:
    if size <= 0:
        return True
    chunk_size = 1024 * 1024
    with left.open("rb") as left_file, right.open("rb") as right_file:
        remaining = size
        while remaining > 0:
            current_chunk = min(chunk_size, remaining)
            if left_file.read(current_chunk) != right_file.read(current_chunk):
                return False
            remaining -= current_chunk
    return True


def build_run_label(name: object, timestamp: object, fallback: str) -> str:
    if isinstance(name, str) and name.strip():
        return name
    try:
        date = datetime.fromtimestamp(coerce_int(timestamp) / 1000)
        return date.isoformat(sep=" ", timespec="minutes")
    except Exception:
        return fallback
