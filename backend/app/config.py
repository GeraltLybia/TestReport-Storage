import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Absolute default so the storage location does not depend on the process CWD.
DEFAULT_STORAGE_ROOT = Path(__file__).resolve().parent.parent / "storage"


def _parse_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got {raw!r}") from exc
    if value < 1:
        raise ValueError(f"Environment variable {name} must be a positive integer, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    storage_root: Path
    reports_folder: Path
    history_file: Path
    history_archive_folder: Path
    history_index_file: Path
    max_reports: int
    max_history_file_size_bytes: int
    max_upload_size_bytes: int
    max_indexed_runs: int
    cors_origins: list[str] = field(default_factory=list)
    api_title: str = "TestReport Storage API"


def get_settings() -> Settings:
    storage_root = Path(os.getenv("APP_STORAGE_ROOT", str(DEFAULT_STORAGE_ROOT)))
    if not storage_root.is_absolute():
        storage_root = storage_root.resolve()
    reports_folder = storage_root / "reports"
    history_file = storage_root / "history.jsonl"
    history_archive_folder = storage_root / "history_archive"
    history_index_file = storage_root / "history_index.json"

    max_reports = _parse_positive_int("APP_MAX_REPORTS", 10)
    max_history_size_mb = _parse_positive_int("APP_HISTORY_MAX_FILE_SIZE_MB", 100)
    max_upload_size_mb = _parse_positive_int("APP_MAX_UPLOAD_SIZE_MB", 512)
    max_indexed_runs = _parse_positive_int("APP_MAX_INDEXED_RUNS", 1000)
    cors_origins = [
        item.strip()
        for item in os.getenv("APP_CORS_ORIGINS", "").split(",")
        if item.strip()
    ]

    settings = Settings(
        storage_root=storage_root,
        reports_folder=reports_folder,
        history_file=history_file,
        history_archive_folder=history_archive_folder,
        history_index_file=history_index_file,
        max_reports=max_reports,
        max_history_file_size_bytes=max_history_size_mb * 1024 * 1024,
        max_upload_size_bytes=max_upload_size_mb * 1024 * 1024,
        max_indexed_runs=max_indexed_runs,
        cors_origins=cors_origins,
    )
    logger.info(
        "Resolved settings: storage_root=%s max_reports=%s max_history_file_size_mb=%s "
        "max_upload_size_mb=%s max_indexed_runs=%s cors_origins=%s",
        settings.storage_root,
        settings.max_reports,
        max_history_size_mb,
        max_upload_size_mb,
        settings.max_indexed_runs,
        settings.cors_origins or "same-origin",
    )
    return settings


@dataclass(frozen=True)
class JiraSettings:
    base_url: str | None
    token: str | None
    project_key: str | None
    issue_type: str
    default_labels: tuple[str, ...]
    verify: bool | str
    timeout_seconds: float
    max_attachment_bytes: int
    public_url: str | None
    stand_names: dict[str, str] = field(default_factory=dict)
    mask_keys: tuple[str, ...] = ()

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.token and self.project_key)


def _split_list(raw: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (raw or "").split(",") if item.strip())


def _parse_mapping(raw: str | None) -> dict[str, str]:
    """`host=name,host2=name2` → {"host": "name", ...}."""
    mapping = {}
    for item in _split_list(raw):
        key, sep, value = item.partition("=")
        if sep and key.strip() and value.strip():
            mapping[key.strip().lower()] = value.strip()
    return mapping


def get_jira_settings() -> JiraSettings:
    verify: bool | str = os.getenv("JIRA_CA_BUNDLE", "").strip() or True
    if os.getenv("JIRA_VERIFY_SSL", "").strip().lower() in {"0", "false", "no"}:
        verify = False
    base_url = os.getenv("JIRA_BASE_URL", "").strip().rstrip("/") or None
    public_url = os.getenv("APP_PUBLIC_URL", "").strip().rstrip("/") or None
    settings = JiraSettings(
        base_url=base_url,
        token=os.getenv("JIRA_TOKEN", "").strip() or None,
        project_key=os.getenv("JIRA_PROJECT_KEY", "").strip() or None,
        issue_type=os.getenv("JIRA_ISSUE_TYPE", "").strip() or "Bug",
        default_labels=_split_list(os.getenv("JIRA_DEFAULT_LABELS", "autotest")),
        verify=verify,
        timeout_seconds=float(_parse_positive_int("JIRA_TIMEOUT_SECONDS", 20)),
        max_attachment_bytes=_parse_positive_int("JIRA_MAX_ATTACHMENT_MB", 10) * 1024 * 1024,
        public_url=public_url,
        stand_names=_parse_mapping(os.getenv("JIRA_STAND_NAMES")),
        mask_keys=_split_list(os.getenv("JIRA_MASK_KEYS")),
    )
    logger.info(
        "Resolved Jira settings: enabled=%s base_url=%s project=%s issue_type=%s verify=%s",
        settings.enabled,
        settings.base_url,
        settings.project_key,
        settings.issue_type,
        settings.verify,
    )
    return settings