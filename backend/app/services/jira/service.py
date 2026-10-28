"""Bug drafts from report tests and their filing in Jira under the service account."""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException

from ...config import JiraSettings
from ...schemas.jira import BugCommentRequest, BugContent, BugIssueRequest
from ..reporting.common import normalize_status
from ..reporting.context import StorageContext
from ..reporting.history_index import HistoryIndexService
from ..reporting.repositories import ReportsRepository
from .client import JiraClient, JiraError
from .links import ISSUE_KEY_RE, JiraLinksRepository
from .masking import SecretMasker
from .report_source import Attachment, ReportTest, load_report_test
from .stand import Stand, detect_stand, urls_in_text
from .steps import (
    INCIDENT_STATUSES,
    StepNode,
    StepSection,
    all_step_calls,
    build_step_sections,
    default_selection,
    iter_steps,
)
from .wiki import DescriptionInput, build_description

logger = logging.getLogger(__name__)

SUMMARY_LIMIT = 110
META_TTL_SECONDS = 600
STATUS_TTL_SECONDS = 60
# fields the bug form fills itself; any other required field cannot be created from here
HANDLED_FIELDS = {
    "project",
    "issuetype",
    "summary",
    "description",
    "reporter",
    "priority",
    "components",
    "labels",
    "assignee",
    "environment",
    "attachment",
}


@dataclass
class DraftAttachment:
    attachment: Attachment
    filename: str
    title: str
    default: bool

    def to_dict(self) -> dict:
        return {
            "id": self.attachment.id,
            "name": self.filename,
            "title": self.title,
            "kind": self.attachment.kind,
            "size": self.attachment.size,
            "defaultSelected": self.default,
        }


@dataclass
class Prepared:
    test: ReportTest
    sections: list[StepSection]
    default_steps: list[str]
    attachments: list[DraftAttachment]
    stand: Stand | None
    test_key: str
    signature: str | None
    message: str | None
    trace: str | None


def build_summary(name: str, message: str | None) -> str:
    """`[Автотест] Отмена заказа: AssertionError — Ожидаемый код 200, полученный 409`."""
    summary = f"[Автотест] {name}"
    first = (message or "").strip().splitlines()[0].strip() if (message or "").strip() else ""
    if first:
        kind, sep, rest = first.partition(":")
        if sep and re.fullmatch(r"[\w.]+", kind.strip()):
            summary += f": {kind.strip()} — {rest.strip()}" if rest.strip() else f": {kind.strip()}"
        else:
            summary += f": {first}"
    summary = " ".join(summary.split())
    return summary if len(summary) <= SUMMARY_LIMIT else summary[: SUMMARY_LIMIT - 1].rstrip() + "…"


def _label(value: str) -> str:
    return re.sub(r"\s+", "_", value.strip())[:255]


def _unique_name(base: str, ext: str, taken: set[str]) -> str:
    safe = re.sub(r"[\\/:*?\"<>|\s]+", "_", base).strip("._") or "attachment"
    name, number = f"{safe}{ext}", 2
    while name.lower() in taken:
        name, number = f"{safe}-{number}{ext}", number + 1
    taken.add(name.lower())
    return name


class JiraService:
    def __init__(self, context: StorageContext, settings: JiraSettings, client: JiraClient | None = None):
        self.settings = settings
        self.reports = ReportsRepository(context)
        self.links = JiraLinksRepository(context.reports_folder.parent / "jira" / "links.json")
        self.masker = SecretMasker(settings.mask_keys)
        self._client = client
        self._lock = threading.Lock()
        self._meta: tuple[float, dict] | None = None
        self._statuses: dict[str, tuple[float, dict]] = {}
        self._users: dict[str, dict | None] = {}

    # ─── plumbing ───
    @property
    def client(self) -> JiraClient:
        if not self.settings.enabled:
            raise HTTPException(status_code=503, detail="Интеграция с Jira не настроена: задайте JIRA_BASE_URL, JIRA_TOKEN и JIRA_PROJECT_KEY")
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = JiraClient(self.settings)
        return self._client

    @staticmethod
    def _http_error(exc: JiraError) -> HTTPException:
        return HTTPException(status_code=exc.status_code, detail=exc.message)

    def config(self) -> dict:
        return {
            "enabled": self.settings.enabled,
            "baseUrl": self.settings.base_url,
            "projectKey": self.settings.project_key,
            "issueType": self.settings.issue_type,
        }

    def meta(self) -> dict:
        cached = self._meta
        if cached and time.monotonic() - cached[0] < META_TTL_SECONDS:
            return cached[1]
        project = self.settings.project_key
        try:
            types = self.client.issue_types(project)
            wanted = self.settings.issue_type.lower()
            issue_type = next(
                (item for item in types if str(item.get("name", "")).lower() == wanted or str(item.get("id")) == wanted),
                None,
            )
            if issue_type is None:
                raise HTTPException(status_code=400, detail=f"В проекте {project} нет типа задачи «{self.settings.issue_type}»")
            fields = self.client.issue_fields(project, str(issue_type["id"]))
        except JiraError as exc:
            raise self._http_error(exc) from None

        by_id = {str(item.get("fieldId")): item for item in fields}

        def allowed(field_id: str) -> list[dict]:
            values = (by_id.get(field_id) or {}).get("allowedValues") or []
            return [{"id": str(v["id"]), "name": v.get("name"), "iconUrl": v.get("iconUrl")} for v in values if "id" in v]

        default_priority = (by_id.get("priority") or {}).get("defaultValue") or {}
        meta = {
            "projectKey": project,
            "issueType": {"id": str(issue_type["id"]), "name": issue_type.get("name")},
            "priorities": allowed("priority"),
            "defaultPriority": str(default_priority["id"]) if "id" in default_priority else None,
            "components": allowed("components"),
            "fields": sorted(by_id),
            "unsupportedRequired": [
                {"id": field_id, "name": item.get("name")}
                for field_id, item in by_id.items()
                if item.get("required") and field_id not in HANDLED_FIELDS and not item.get("hasDefaultValue")
            ],
        }
        self._meta = (time.monotonic(), meta)
        return meta

    # ─── draft ───
    def _prepare(self, report_id: str, test_id: str) -> Prepared:
        test = load_report_test(self.reports, report_id, test_id)
        if test is None:
            raise HTTPException(status_code=404, detail="Тест не найден в отчёте")
        sections = build_step_sections(test)
        error = test.result.get("error") if isinstance(test.result.get("error"), dict) else {}
        message = error.get("message").strip() if isinstance(error.get("message"), str) and error["message"].strip() else None
        trace = error.get("trace") if isinstance(error.get("trace"), str) and error["trace"].strip() else None
        status = normalize_status(test.result.get("status"))
        signature = (
            HistoryIndexService.build_signature({"message": message})
            if status in INCIDENT_STATUSES
            else None
        )
        name = test.result.get("name") if isinstance(test.result.get("name"), str) else test_id
        full_name = test.result.get("fullName") if isinstance(test.result.get("fullName"), str) else None

        attachments = self._draft_attachments(test, sections)
        urls = [call.url for call in all_step_calls(sections)]
        if not urls:
            for item in attachments:
                if item.attachment.kind == "log":
                    urls.extend(urls_in_text(item.attachment.read_text() or ""))
        return Prepared(
            test=test,
            sections=sections,
            default_steps=default_selection(sections),
            attachments=attachments,
            stand=detect_stand(urls, self.settings.stand_names),
            test_key=full_name or name,
            signature=signature,
            message=message,
            trace=trace,
        )

    @staticmethod
    def _draft_attachments(test: ReportTest, sections: list[StepSection]) -> list[DraftAttachment]:
        """Logs and screenshots of the test, plus the request dumps of the steps it broke on."""
        failure_dumps: dict[str, StepNode] = {}
        for section in sections:
            for step in iter_steps(section.steps):
                if step.on_failure_path:
                    for attachment in step.attachments:
                        if attachment.kind == "json":
                            failure_dumps[attachment.id] = step
        taken: set[str] = set()
        out = []
        for attachment in test.all_attachments():
            kind = attachment.kind
            if kind == "log":
                out.append(DraftAttachment(attachment, _unique_name("log", attachment.ext or ".txt", taken), attachment.name or "Лог теста", True))
            elif kind == "image":
                out.append(DraftAttachment(attachment, _unique_name(attachment.name or "screenshot", attachment.ext, taken), attachment.name or "Скриншот", True))
            elif attachment.id in failure_dumps:
                step = failure_dumps[attachment.id]
                out.append(DraftAttachment(attachment, _unique_name("request", ".json", taken), f"Запрос и ответ: {step.title}", False))
        return out

    def _assignee(self, author: str | None) -> dict | None:
        if not author:
            return None
        suggestion = {"name": author, "displayName": author, "found": None}
        if not self.settings.enabled:
            return suggestion
        if author not in self._users:
            try:
                self._users[author] = self.client.find_user(author)
            except (JiraError, HTTPException):
                return suggestion
        user = self._users[author]
        return {**user, "found": True} if user else {**suggestion, "found": False}

    def _with_statuses(self, records: list[dict]) -> list[dict]:
        keys = [record["key"] for record in records if ISSUE_KEY_RE.match(record["key"])]
        statuses = self._statuses_for(keys)
        return [
            {
                "key": record["key"],
                "url": self._issue_url(record["key"]),
                "summary": (statuses.get(record["key"]) or {}).get("summary") or record.get("summary"),
                "status": (statuses.get(record["key"]) or {}).get("status"),
                "statusCategory": (statuses.get(record["key"]) or {}).get("statusCategory"),
                "testKey": record.get("testKey"),
                "createdAt": record.get("createdAt"),
            }
            for record in records
        ]

    def _issue_url(self, key: str) -> str | None:
        return f"{self.settings.base_url}/browse/{key}" if self.settings.base_url else None

    def _statuses_for(self, keys: list[str]) -> dict[str, dict]:
        if not keys or not self.settings.enabled:
            return {}
        now = time.monotonic()
        fresh = {key: value for key, (at, value) in self._statuses.items() if key in keys and now - at < STATUS_TTL_SECONDS}
        missing = sorted(set(keys) - set(fresh))
        if missing:
            try:
                loaded = self.client.issue_statuses(missing)
            except JiraError as exc:
                logger.info("Jira statuses unavailable: %s", exc.message)
                loaded = {}
            for key in missing:
                value = loaded.get(key, {})
                self._statuses[key] = (now, value)
                fresh[key] = value
        return fresh

    def draft(self, report_id: str, test_id: str) -> dict:
        prepared = self._prepare(report_id, test_id)
        test = prepared.test
        result = test.result
        exact = self.links.find_exact(prepared.test_key, prepared.signature) if prepared.signature else None
        similar = self.links.find_similar(prepared.signature, prepared.test_key)[:3] if prepared.signature else []
        tags = prepared_tags(prepared)
        return {
            "report": {
                "id": test.report_id,
                "name": test.report_name,
                "createdAt": test.report_created_at,
                "author": test.author,
                "launchSource": test.variables.get("Launch source"),
            },
            "test": {
                "id": test.test_id,
                "name": result.get("name"),
                "fullName": result.get("fullName"),
                "testKey": prepared.test_key,
                "status": normalize_status(result.get("status")),
                "duration": result.get("duration"),
                "signature": prepared.signature,
                "tags": tags,
                "parameters": [{"name": name, "value": value} for name, value in self._parameters(result)],
            },
            "error": {"message": prepared.message, "trace": prepared.trace},
            "stand": prepared.stand.to_dict() if prepared.stand else None,
            "sections": [section.to_dict() for section in prepared.sections],
            "defaultSteps": prepared.default_steps,
            "attachments": [item.to_dict() for item in prepared.attachments],
            "suggested": {
                "summary": build_summary(str(result.get("name") or test.test_id), prepared.message),
                "labels": self._labels(tags),
                "assignee": self._assignee(test.author),
            },
            "duplicates": {
                "exact": self._with_statuses([exact])[0] if exact else None,
                "similar": self._with_statuses(similar),
            },
            "links": dict(self._links(test)),
        }

    @staticmethod
    def _parameters(result: dict) -> list[tuple[str, str]]:
        return [
            (str(item.get("name")), str(item.get("value")))
            for item in result.get("parameters") or []
            if isinstance(item, dict) and item.get("name") and not item.get("hidden") and not item.get("masked")
        ]

    def _labels(self, tags: list[str]) -> list[str]:
        labels: list[str] = []
        for value in list(self.settings.default_labels) + tags:
            label = _label(value)
            if label and label not in labels:
                labels.append(label)
        return labels

    def _links(self, test: ReportTest) -> list[tuple[str, str]]:
        base = self.settings.public_url
        if not base:
            return []
        links = [("report", f"{base}/reports/{test.report_id}")]
        if test.entry_path:
            links.append(("allure", f"{base}/reports-static/{test.entry_path}#/{test.test_id}"))
        return links

    # ─── description ───
    def _description(self, prepared: Prepared, content: BugContent, expected: str | None, attachments: list[DraftAttachment]) -> dict:
        test = prepared.test
        known = {step.id for section in prepared.sections for step in iter_steps(section.steps)}
        selected = set(prepared.default_steps if content.steps is None else content.steps) & known
        log_text = None
        if content.logMode == "full":
            texts = [item.attachment.read_text() or "" for item in prepared.attachments if item.attachment.kind == "log"]
            log_text = "\n".join(text for text in texts if text) or None
        stand = prepared.stand
        stand_line = None
        if stand:
            stand_line = f"{stand.name} — {stand.url}" if stand.name else stand.url
        run_line = test.report_name
        if test.report_created_at:
            try:
                run_line += " · " + datetime.fromisoformat(test.report_created_at).strftime("%d.%m.%Y %H:%M")
            except ValueError:
                pass
        if test.author and test.author not in run_line:
            run_line += f" · {test.author}"
        titles = {"report": "Отчёт в TestReport Storage", "allure": "Тест в Allure-отчёте"}
        return build_description(
            DescriptionInput(
                sections=prepared.sections,
                selected=selected,
                error_message=prepared.message,
                error_trace=prepared.trace,
                include_trace=content.includeTrace,
                expected=expected,
                log_mode=content.logMode,
                log_text=log_text,
                stand_line=stand_line,
                run_line=run_line,
                test_full_name=test.result.get("fullName"),
                parameters=self._parameters(test.result),
                links=[(titles[kind], url) for kind, url in self._links(test)],
                attachment_names=[item.filename for item in attachments],
                mask=self.masker.mask,
            )
        ) | {"environment": "\n".join(filter(None, [stand_line, run_line]))}

    @staticmethod
    def _chosen_attachments(prepared: Prepared, content: BugContent) -> list[DraftAttachment]:
        if content.attachments is None:
            return [item for item in prepared.attachments if item.default]
        wanted = set(content.attachments)
        return [item for item in prepared.attachments if item.attachment.id in wanted]

    def preview(self, content: BugContent) -> dict:
        prepared = self._prepare(content.reportId, content.testId)
        description = self._description(prepared, content, content.expected, self._chosen_attachments(prepared, content))
        return {"description": description["text"], "steps": description["steps"], "logLines": description["logLines"]}

    # ─── filing ───
    def _upload(self, key: str, attachments: list[DraftAttachment]) -> tuple[list[str], list[str]]:
        uploaded, warnings = [], []
        for item in attachments:
            attachment = item.attachment
            if attachment.size and attachment.size > self.settings.max_attachment_bytes:
                warnings.append(f"{item.filename}: больше {self.settings.max_attachment_bytes // (1024 * 1024)} МБ, не приложен")
                continue
            if attachment.kind in {"log", "json"}:
                text = attachment.read_text()
                content = self.masker.mask(text).encode("utf-8") if text is not None else None
                content_type = "text/plain; charset=utf-8" if attachment.kind == "log" else "application/json"
            else:
                content = attachment.read_bytes()
                content_type = attachment.content_type
            if content is None:
                warnings.append(f"{item.filename}: файл не найден в отчёте")
                continue
            try:
                self.client.add_attachment(key, item.filename, content, content_type)
                uploaded.append(item.filename)
            except JiraError as exc:
                warnings.append(f"{item.filename}: {exc.message}")
        return uploaded, warnings

    def create_issue(self, request: BugIssueRequest) -> dict:
        if not request.expected.strip():
            raise HTTPException(status_code=400, detail="Заполните ожидаемый результат")
        client = self.client
        meta = self.meta()
        prepared = self._prepare(request.reportId, request.testId)
        attachments = self._chosen_attachments(prepared, request)
        description = self._description(prepared, request, request.expected, attachments)
        available = set(meta["fields"])
        fields: dict = {
            "project": {"key": meta["projectKey"]},
            "issuetype": {"id": meta["issueType"]["id"]},
            "summary": " ".join(request.summary.split())[:255],
            "description": description["text"],
        }
        labels = self._labels(request.labels) if request.labels is not None else self._labels(prepared_tags(prepared))
        if "labels" in available and labels:
            fields["labels"] = labels
        if "priority" in available and request.priority:
            fields["priority"] = {"id": request.priority}
        if "components" in available and request.components:
            fields["components"] = [{"id": component} for component in request.components]
        if "assignee" in available and request.assignee:
            fields["assignee"] = {"name": request.assignee}
        if "environment" in available:
            fields["environment"] = description["environment"]
        try:
            created = client.create_issue(fields)
        except JiraError as exc:
            raise self._http_error(exc) from None
        key = created["key"]
        uploaded, warnings = self._upload(key, attachments)
        if prepared.signature:
            self.links.add(
                key=key,
                test_key=prepared.test_key,
                signature=prepared.signature,
                report_id=request.reportId,
                test_id=request.testId,
                summary=fields["summary"],
            )
        logger.info("Jira issue created: %s for %s/%s", key, request.reportId, request.testId)
        return {
            "key": key,
            "url": client.issue_url(key),
            "summary": fields["summary"],
            "steps": description["steps"],
            "logLines": description["logLines"],
            "attachments": uploaded,
            "warnings": warnings,
        }

    def add_comment(self, key: str, request: BugCommentRequest) -> dict:
        if not ISSUE_KEY_RE.match(key or ""):
            raise HTTPException(status_code=400, detail="Некорректный ключ задачи")
        client = self.client
        prepared = self._prepare(request.reportId, request.testId)
        attachments = self._chosen_attachments(prepared, request)
        description = self._description(prepared, request, None, attachments)
        body = f"h3. Повторное падение\n{description['environment']}\n\n{description['text']}"
        try:
            client.add_comment(key, body)
        except JiraError as exc:
            raise self._http_error(exc) from None
        uploaded, warnings = self._upload(key, attachments)
        if prepared.signature:
            self.links.add(
                key=key,
                test_key=prepared.test_key,
                signature=prepared.signature,
                report_id=request.reportId,
                test_id=request.testId,
                summary="",
            )
        self._statuses.pop(key, None)
        return {"key": key, "url": client.issue_url(key), "attachments": uploaded, "warnings": warnings}

    def report_links(self, report_id: str) -> dict:
        """Issues filed for the failures of a report, by test id."""
        results = self.reports.read_report_results(report_id)
        if results is None:
            raise HTTPException(status_code=404, detail="Report not found")
        index = self.links.exact_index()
        matched: dict[str, dict] = {}
        for item in results:
            if item["status"] not in INCIDENT_STATUSES:
                continue
            signature = HistoryIndexService.build_signature({"message": item.get("message")})
            record = index.get((item["testKey"], signature))
            if record:
                matched[item["id"]] = record
        enriched = self._with_statuses(list(matched.values()))
        return {"items": {test_id: link for test_id, link in zip(matched, enriched)}}


def prepared_tags(prepared: Prepared) -> list[str]:
    return [
        label["value"]
        for label in prepared.test.result.get("labels") or []
        if isinstance(label, dict) and label.get("name") == "tag" and isinstance(label.get("value"), str)
    ]
