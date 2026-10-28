"""Jira Server / Data Center 9.x REST API v2 client authorised with a Personal Access Token."""

from __future__ import annotations

import logging

import httpx

from ...config import JiraSettings

logger = logging.getLogger(__name__)


class JiraError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _error_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300] or response.reason_phrase
    if not isinstance(payload, dict):
        return response.reason_phrase
    messages = [str(item) for item in payload.get("errorMessages") or []]
    errors = payload.get("errors")
    if isinstance(errors, dict):
        messages.extend(f"{field}: {text}" for field, text in errors.items())
    return "; ".join(messages) or response.reason_phrase


class JiraClient:
    def __init__(self, settings: JiraSettings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._http = httpx.Client(
            base_url=f"{settings.base_url}/rest/api/2",
            headers={"Authorization": f"Bearer {settings.token}", "Accept": "application/json"},
            verify=settings.verify,
            timeout=settings.timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def issue_url(self, key: str) -> str:
        return f"{self.settings.base_url}/browse/{key}"

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            logger.warning("Jira request failed: %s %s: %s", method, path, exc)
            raise JiraError(502, f"Jira недоступна: {exc.__class__.__name__}") from None
        if response.status_code == 401:
            raise JiraError(502, "Jira отклонила токен: проверьте JIRA_TOKEN")
        if response.status_code == 403:
            raise JiraError(502, f"Сервисному аккаунту не хватает прав в Jira: {_error_text(response)}")
        if response.status_code >= 400:
            logger.warning("Jira error %s on %s %s: %s", response.status_code, method, path, response.text[:500])
            raise JiraError(502 if response.status_code >= 500 else 400, f"Jira: {_error_text(response)}")
        return response

    def _json(self, method: str, path: str, **kwargs):
        response = self._request(method, path, **kwargs)
        return response.json() if response.content else None

    # ─── create metadata (Jira 9 removed `createmeta?expand=…`) ───
    def issue_types(self, project: str) -> list[dict]:
        payload = self._json("GET", f"/issue/createmeta/{project}/issuetypes", params={"maxResults": 100})
        return [item for item in (payload or {}).get("values", []) if isinstance(item, dict)]

    def issue_fields(self, project: str, issue_type_id: str) -> list[dict]:
        payload = self._json(
            "GET", f"/issue/createmeta/{project}/issuetypes/{issue_type_id}", params={"maxResults": 200}
        )
        return [item for item in (payload or {}).get("values", []) if isinstance(item, dict)]

    def find_user(self, username: str) -> dict | None:
        try:
            payload = self._json("GET", "/user", params={"username": username})
        except JiraError as exc:
            if exc.status_code == 400:
                return None
            raise
        if not isinstance(payload, dict) or not payload.get("name") or payload.get("active") is False:
            return None
        return {"name": payload["name"], "displayName": payload.get("displayName") or payload["name"]}

    # ─── issues ───
    def create_issue(self, fields: dict) -> dict:
        payload = self._json("POST", "/issue", json={"fields": fields})
        return {"id": payload.get("id"), "key": payload["key"]}

    def add_attachment(self, key: str, filename: str, content: bytes, content_type: str) -> None:
        self._request(
            "POST",
            f"/issue/{key}/attachments",
            headers={"X-Atlassian-Token": "no-check"},
            files={"file": (filename, content, content_type or "application/octet-stream")},
        )

    def add_comment(self, key: str, body: str) -> None:
        self._request("POST", f"/issue/{key}/comment", json={"body": body})

    def issue_statuses(self, keys: list[str]) -> dict[str, dict]:
        if not keys:
            return {}
        payload = self._json(
            "POST",
            "/search",
            json={
                "jql": f"key in ({','.join(keys)})",
                "fields": ["status", "summary"],
                "maxResults": len(keys),
                # deleted or moved issues must not fail the whole lookup
                "validateQuery": False,
            },
        )
        statuses = {}
        for issue in (payload or {}).get("issues", []):
            fields = issue.get("fields") or {}
            status = fields.get("status") or {}
            category = (status.get("statusCategory") or {}).get("key")
            statuses[issue["key"]] = {
                "status": status.get("name"),
                "statusCategory": category,
                "summary": fields.get("summary"),
            }
        return statuses
