"""Finds the text log attachments of every test in an uploaded Allure 3 report."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..reporting.repositories import ReportsRepository

ATTACHMENT_ID_RE = re.compile(r"^[0-9A-Za-z_-]{1,128}$")
LOG_EXTENSIONS = {".txt", ".log"}
LOG_CONTENT_TYPES = {"text/plain"}


@dataclass
class TestLog:
    report_id: str
    test_id: str
    name: str
    full_name: str | None
    text: str


def _iter_attachment_links(node: object) -> Iterator[dict]:
    """Every attachment link in a test result, wherever it is nested (test, steps, fixtures)."""
    if isinstance(node, dict):
        link = node.get("link")
        if isinstance(link, dict) and isinstance(link.get("id"), str):
            yield link
        for value in node.values():
            if isinstance(value, (dict, list)):
                yield from _iter_attachment_links(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_attachment_links(item)


def _is_log(link: dict) -> bool:
    ext = (link.get("ext") or "").lower()
    return ext in LOG_EXTENSIONS or (link.get("contentType") or "").lower() in LOG_CONTENT_TYPES


def iter_report_test_logs(repository: ReportsRepository, report_id: str) -> Iterator[TestLog]:
    report_dir = repository.resolve_report_dir(report_id)
    if report_dir is None:
        return
    report_root = repository.resolve_report_root(report_dir)
    if report_root is None:
        return
    results_dir = report_root / "data" / "test-results"
    attachments_dir = report_root / "data" / "attachments"
    if not results_dir.is_dir():
        return

    for result_path in sorted(results_dir.glob("*.json")):
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(result, dict):
            continue
        texts = []
        seen: set[str] = set()
        for link in _iter_attachment_links(result):
            attachment_id = link["id"]
            if attachment_id in seen or not ATTACHMENT_ID_RE.match(attachment_id) or not _is_log(link):
                continue
            seen.add(attachment_id)
            ext = (link.get("ext") or "").lower()
            path: Path = attachments_dir / f"{attachment_id}{ext}"
            try:
                texts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
        if not texts:
            continue
        yield TestLog(
            report_id=report_id,
            test_id=str(result.get("id") or result_path.stem),
            name=result["name"] if isinstance(result.get("name"), str) else result_path.stem,
            full_name=result.get("fullName") if isinstance(result.get("fullName"), str) else None,
            text="\n".join(texts),
        )
