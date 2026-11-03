"""Which Jira issue was filed for which failure.

A link is keyed by the test and its error signature: the same test failing the same
way in a later run shows the same issue. The signature alone only suggests a
possible duplicate — short signatures (`KeyError: 'items'`) repeat across tests.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,31}-\d{1,9}$")


class JiraLinksRepository:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> list[dict]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            logger.warning("Broken Jira links file ignored: %s", self.path)
            return []
        items = payload.get("items") if isinstance(payload, dict) else None
        return [item for item in items or [] if isinstance(item, dict) and ISSUE_KEY_RE.match(str(item.get("key")))]

    def _write(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temp, self.path)

    def add(self, *, key: str, test_key: str, signature: str, report_id: str, test_id: str, summary: str) -> dict:
        record = {
            "key": key,
            "testKey": test_key,
            "signature": signature,
            "reportId": report_id,
            "testId": test_id,
            "summary": summary,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            items = [
                item
                for item in self._read()
                if not (item["key"] == key and item.get("testKey") == test_key and item.get("signature") == signature)
            ]
            items.append(record)
            self._write(items)
        return record

    def find_exact(self, test_key: str, signature: str) -> dict | None:
        """Latest issue filed for this test failing with this signature."""
        matches = [
            item for item in self._read() if item.get("testKey") == test_key and item.get("signature") == signature
        ]
        return matches[-1] if matches else None

    def find_similar(self, signature: str, exclude_test_key: str) -> list[dict]:
        """Issues of other tests with the same signature, newest first, one per issue."""
        seen: set[str] = set()
        out = []
        for item in reversed(self._read()):
            if item.get("signature") != signature or item.get("testKey") == exclude_test_key or item["key"] in seen:
                continue
            seen.add(item["key"])
            out.append(item)
        return out

    def exact_index(self) -> dict[tuple[str, str], dict]:
        index: dict[tuple[str, str], dict] = {}
        for item in self._read():
            index[(item.get("testKey"), item.get("signature"))] = item
        return index
