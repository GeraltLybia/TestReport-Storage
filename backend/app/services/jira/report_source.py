"""One test result of an uploaded Allure 3 report, with its attachments and report metadata."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..reporting.repositories import ReportsRepository

TEST_ID_RE = re.compile(r"^[0-9A-Za-z_-]{1,128}$")
LOG_EXTENSIONS = {".txt", ".log"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_JSON_ATTACHMENT_BYTES = 2 * 1024 * 1024


@dataclass
class Attachment:
    id: str
    name: str | None
    ext: str
    content_type: str
    size: int | None
    path: Path

    @property
    def kind(self) -> str:
        if self.ext in LOG_EXTENSIONS or self.content_type == "text/plain":
            return "log"
        if self.ext == ".json" or self.content_type == "application/json":
            return "json"
        if self.ext in IMAGE_EXTENSIONS or self.content_type.startswith("image/"):
            return "image"
        return "other"

    def read_bytes(self) -> bytes | None:
        try:
            return self.path.read_bytes()
        except OSError:
            return None

    def read_text(self) -> str | None:
        data = self.read_bytes()
        return data.decode("utf-8", errors="replace") if data is not None else None

    def read_json(self) -> object | None:
        if self.size is not None and self.size > MAX_JSON_ATTACHMENT_BYTES:
            return None
        text = self.read_text()
        if text is None:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None


@dataclass
class ReportTest:
    report_id: str
    report_name: str
    report_created_at: str | None
    entry_path: str | None
    variables: dict
    result: dict
    attachments_dir: Path
    _attachments: dict[str, Attachment] = field(default_factory=dict)

    @property
    def test_id(self) -> str:
        return str(self.result.get("id") or "")

    @property
    def author(self) -> str | None:
        user = self.variables.get("User")
        return user.strip() if isinstance(user, str) and user.strip() else None

    def attachment(self, link: object) -> Attachment | None:
        """Attachment behind an Allure `link` object; None for broken or unsafe links."""
        if not isinstance(link, dict) or not isinstance(link.get("id"), str):
            return None
        attachment_id = link["id"]
        if attachment_id in self._attachments:
            return self._attachments[attachment_id]
        if not TEST_ID_RE.match(attachment_id) or link.get("missed"):
            return None
        ext = (link.get("ext") or "").lower()
        if ext and not re.fullmatch(r"\.[0-9a-z]{1,10}", ext):
            return None
        path = self.attachments_dir / f"{attachment_id}{ext}"
        if not path.is_file():
            return None
        size = link.get("contentLength")
        attachment = Attachment(
            id=attachment_id,
            name=link.get("name") if isinstance(link.get("name"), str) else None,
            ext=ext,
            content_type=(link.get("contentType") or "").lower(),
            size=size if isinstance(size, int) else path.stat().st_size,
            path=path,
        )
        self._attachments[attachment_id] = attachment
        return attachment

    def all_attachments(self) -> list[Attachment]:
        """Every attachment of the test, wherever it is nested, in document order."""
        found: list[Attachment] = []
        seen: set[str] = set()

        def walk(node: object) -> None:
            if isinstance(node, dict):
                attachment = self.attachment(node.get("link"))
                if attachment is not None and attachment.id not in seen:
                    seen.add(attachment.id)
                    found.append(attachment)
                for value in node.values():
                    if isinstance(value, (dict, list)):
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(self.result)
        return found


def _read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_report_test(repository: ReportsRepository, report_id: str, test_id: str) -> ReportTest | None:
    if not TEST_ID_RE.match(test_id or ""):
        return None
    report_dir = repository.resolve_report_dir(report_id)
    if report_dir is None:
        return None
    report_root = repository.resolve_report_root(report_dir)
    if report_root is None:
        return None
    result = _read_json(report_root / "data" / "test-results" / f"{test_id}.json")
    if not isinstance(result, dict):
        return None
    result.setdefault("id", test_id)

    variables = _read_json(report_root / "widgets" / "variables.json")
    if not isinstance(variables, dict):
        variables = _read_json(report_root / "widgets" / "default" / "variables.json")
    meta = repository.read_report_meta(report_dir) or repository.build_report_meta(report_dir)
    return ReportTest(
        report_id=report_id,
        report_name=meta.get("name") or report_id,
        report_created_at=meta.get("created_at"),
        entry_path=meta.get("entry_path"),
        variables=variables if isinstance(variables, dict) else {},
        result=result,
        attachments_dir=report_root / "data" / "attachments",
    )
