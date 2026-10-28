"""Step tree of a test result prepared for a bug: sections, collapsed repeats, failure path.

Allure keeps steps in execution order. Consecutive sibling steps with the same name
(polling, retries: "Получаем историю претензии" ×4 inside "Ждём события …") are folded
into a group whose attempts are selected one by one; steps repeated elsewhere in the
scenario stay separate, they are meaningful actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .report_source import Attachment, ReportTest

INCIDENT_STATUSES = {"failed", "broken"}
# (section, title, step id prefix)
SECTIONS = (("setup", "Подготовка", "s"), ("test", "Тест", "t"), ("teardown", "Завершение", "d"))


@dataclass
class ApiCall:
    method: str
    url: str
    status: str | None
    request_body: object = None
    response_body: object = None

    @property
    def path(self) -> str:
        parts = urlsplit(self.url)
        return parts.path + (f"?{parts.query}" if parts.query else "") if parts.netloc else self.url

    @property
    def label(self) -> str:
        return f"{self.method} {self.path}" + (f" → {self.status}" if self.status else "")

    def to_dict(self) -> dict:
        return {"method": self.method, "url": self.url, "path": self.path, "status": self.status}


@dataclass
class StepNode:
    id: str
    title: str
    status: str
    duration: int | None
    kind: str = "step"  # "step" | "group"
    message: str | None = None
    calls: list[ApiCall] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    children: list["StepNode"] = field(default_factory=list)
    attempts: list["StepNode"] = field(default_factory=list)
    on_failure_path: bool = False
    failure_origin: bool = False

    @property
    def call(self) -> ApiCall | None:
        return self.calls[-1] if self.calls else None

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "duration": self.duration,
            "onFailurePath": self.on_failure_path,
            "failureOrigin": self.failure_origin,
        }
        if self.kind == "group":
            data["attempts"] = [attempt.to_dict() for attempt in self.attempts]
        else:
            data["message"] = self.message
            data["call"] = self.call.to_dict() if self.call else None
            data["children"] = [child.to_dict() for child in self.children]
        return data


@dataclass
class StepSection:
    id: str
    title: str
    steps: list[StepNode]

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "steps": [step.to_dict() for step in self.steps]}


def _status(raw: object) -> str:
    return raw.strip().lower() if isinstance(raw, str) and raw.strip() else "unknown"


def parse_api_call(payload: object) -> ApiCall | None:
    """`{"request_line": "POST http://…", "response_status_code": 201, …}` written by the test framework."""
    if not isinstance(payload, dict) or not isinstance(payload.get("request_line"), str):
        return None
    method, _, url = payload["request_line"].strip().partition(" ")
    if not method or not url:
        return None
    status = payload.get("response_status_code")
    return ApiCall(
        method=method.upper(),
        url=url.strip(),
        status=str(status) if status is not None else None,
        request_body=payload.get("request_body"),
        response_body=payload.get("response_body"),
    )


def _build_nodes(test: ReportTest, raw_steps: object, prefix: str) -> list[StepNode]:
    nodes: list[StepNode] = []
    if not isinstance(raw_steps, list):
        return nodes
    for raw in raw_steps:
        if not isinstance(raw, dict) or raw.get("type") == "attachment":
            continue
        node_id = f"{prefix}.{len(nodes)}"
        message = raw.get("message") if isinstance(raw.get("message"), str) else None
        node = StepNode(
            id=node_id,
            title=raw["name"].strip() if isinstance(raw.get("name"), str) and raw["name"].strip() else "Без названия",
            status=_status(raw.get("status")),
            duration=raw.get("duration") if isinstance(raw.get("duration"), int) else None,
            message=message.strip() if message and message.strip() else None,
            children=_build_nodes(test, raw.get("steps"), node_id),
        )
        for child in raw.get("steps") or []:
            if isinstance(child, dict) and child.get("type") == "attachment":
                attachment = test.attachment(child.get("link"))
                if attachment is None:
                    continue
                node.attachments.append(attachment)
                if attachment.kind == "json":
                    call = parse_api_call(attachment.read_json())
                    if call is not None:
                        node.calls.append(call)
        nodes.append(node)
    return _group_repeats(nodes)


def _group_repeats(nodes: list[StepNode]) -> list[StepNode]:
    grouped: list[StepNode] = []
    index = 0
    while index < len(nodes):
        end = index + 1
        while end < len(nodes) and nodes[end].title == nodes[index].title:
            end += 1
        run = nodes[index:end]
        if len(run) > 1:
            durations = [step.duration for step in run if step.duration is not None]
            grouped.append(
                StepNode(
                    id=f"{run[0].id}~",
                    title=run[0].title,
                    status=run[-1].status,
                    duration=sum(durations) if durations else None,
                    kind="group",
                    attempts=run,
                )
            )
        else:
            grouped.append(run[0])
        index = end
    return grouped


def _members(node: StepNode) -> list[StepNode]:
    """Children for traversal: the attempts of a group, the sub-steps of a step."""
    return node.attempts if node.kind == "group" else node.children


def iter_steps(nodes: list[StepNode]):
    """All step nodes (not groups) depth-first, in execution order."""
    for node in nodes:
        if node.kind == "step":
            yield node
        yield from iter_steps(_members(node))


def _incident_paths(node: StepNode, trail: list[StepNode]):
    path = trail + [node]
    if node.kind == "group":
        # Only the last attempt decides the outcome; earlier failed attempts were retried.
        yield from _incident_paths(node.attempts[-1], path)
        return
    if node.status in INCIDENT_STATUSES:
        yield path
    for child in node.children:
        yield from _incident_paths(child, path)


def _mark_failure_path(sections: list[StepSection]) -> None:
    """Marks the step where the test broke and its ancestors.

    The branch is the last failed/broken top-level step (test steps first, then
    setup and teardown); inside it the origin is the deepest failed/broken step
    with an error message, or the deepest one when no step carries a message.
    """
    ordered = sorted(sections, key=lambda section: section.id != "test")
    for section in ordered:
        top = [node for node in section.steps if node.status in INCIDENT_STATUSES]
        if not top:
            continue
        paths = list(_incident_paths(top[-1], []))
        if not paths:
            continue
        pool = [path for path in paths if path[-1].message] or paths
        deepest = max(len(path) for path in pool)
        path = [path for path in pool if len(path) == deepest][-1]
        for node in path:
            node.on_failure_path = True
        path[-1].failure_origin = True
        return


def build_step_sections(test: ReportTest) -> list[StepSection]:
    sections = []
    for section_id, title, prefix in SECTIONS:
        key = "steps" if section_id == "test" else section_id
        steps = _build_nodes(test, test.result.get(key), prefix)
        if steps:
            sections.append(StepSection(id=section_id, title=title, steps=steps))
    _mark_failure_path(sections)
    return sections


def default_selection(sections: list[StepSection]) -> list[str]:
    """«Путь до падения»: test steps of the top level without skipped ones, the steps
    leading to the failure, and only the last attempt of each folded repeat.
    Setup and teardown are off unless the test broke there."""
    selected: list[str] = []

    def visit(nodes: list[StepNode], top_level: bool, section_id: str) -> None:
        for node in nodes:
            if node.kind == "group":
                last = node.attempts[-1]
                wanted = node.on_failure_path or (top_level and section_id == "test")
                for attempt in node.attempts:
                    if attempt.on_failure_path or (wanted and attempt is last and last.status != "skipped"):
                        selected.append(attempt.id)
                    visit(attempt.children, False, section_id)
                continue
            if node.on_failure_path or (top_level and section_id == "test" and node.status != "skipped"):
                selected.append(node.id)
            visit(node.children, False, section_id)

    for section in sections:
        visit(section.steps, True, section.id)
    return selected


def all_step_calls(sections: list[StepSection]) -> list[ApiCall]:
    return [call for section in sections for step in iter_steps(section.steps) for call in step.calls]
