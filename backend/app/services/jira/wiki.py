"""Jira Server / Data Center wiki markup for the bug description."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from .steps import ApiCall, StepNode, StepSection

# Jira text fields hold 32 767 characters; leave room for the footer and the server.
DESCRIPTION_LIMIT = 32000
BODY_LIMIT = 4000
TRACE_LINES = 40

_ALWAYS = re.compile(r"([\\{}\[\]|*_+^~!?])")
# `-` and `#` only matter at a word edge (strikethrough, lists): keep UUIDs and kebab-case readable
_EDGE = re.compile(r"(?:(?<=\s)|^)([-#])|([-#])(?=\s|$)")


def escape(text: str) -> str:
    text = _ALWAYS.sub(r"\\\1", text)
    text = _EDGE.sub(lambda m: "\\" + (m.group(1) or m.group(2)), text)
    return " ".join(text.split())


def mono(text: str) -> str:
    return "{{" + escape(text) + "}}"


def noformat(text: str) -> str:
    safe = text.replace("{noformat}", "{ noformat}").rstrip()
    return "{noformat}\n" + safe + "\n{noformat}"


def code_json(value: object) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        text = str(value)
    if len(text) > BODY_LIMIT:
        text = text[:BODY_LIMIT] + "\n… обрезано"
    return "{code:json}\n" + text.replace("{code", "{ code").rstrip() + "\n{code}"


def link(title: str, url: str) -> str:
    return f"[{escape(title)}|{url}]"


@dataclass
class SelectedStep:
    node: StepNode
    depth: int
    label: str


def selected_steps(sections: list[StepSection], selected: set[str]) -> list[tuple[StepSection, list[SelectedStep]]]:
    """Chosen steps in execution order; depth counts chosen ancestors only, so a sub-step
    whose parent was unticked moves up a level instead of hanging under nothing."""
    out = []

    def visit(nodes: list[StepNode], depth: int, bucket: list[SelectedStep]) -> None:
        for node in nodes:
            if node.kind == "group":
                total = len(node.attempts)
                for number, attempt in enumerate(node.attempts, start=1):
                    label = f"{attempt.title} — попытка {number} из {total}"
                    take(attempt, depth, bucket, label)
                continue
            take(node, depth, bucket, node.title)

    def take(node: StepNode, depth: int, bucket: list[SelectedStep], label: str) -> None:
        if node.id in selected:
            bucket.append(SelectedStep(node=node, depth=depth, label=label))
            visit(node.children, depth + 1, bucket)
        else:
            visit(node.children, depth, bucket)

    for section in sections:
        bucket: list[SelectedStep] = []
        visit(section.steps, 1, bucket)
        if bucket:
            out.append((section, bucket))
    return out


def failure_call(sections: list[StepSection]) -> ApiCall | None:
    """The request the test broke on: the deepest call on the failure path."""
    found = None

    def visit(nodes: list[StepNode]) -> None:
        nonlocal found
        for node in nodes:
            if not node.on_failure_path:
                continue
            if node.call is not None:
                found = node.call
            visit(node.attempts if node.kind == "group" else node.children)

    for section in sections:
        visit(section.steps)
    return found


def _identity(text: str) -> str:
    return text


@dataclass
class DescriptionInput:
    sections: list[StepSection]
    selected: set[str]
    error_message: str | None
    error_trace: str | None
    include_trace: bool
    expected: str | None  # None: no «Ожидаемый результат» block (comments)
    log_mode: str  # "calls" | "full" | "none"
    log_text: str | None
    stand_line: str | None
    run_line: str
    test_full_name: str | None
    parameters: list[tuple[str, str]] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    attachment_names: list[str] = field(default_factory=list)
    mask: Callable[[str], str] = _identity


def render_steps(data: DescriptionInput) -> tuple[list[str], int]:
    chosen = selected_steps(data.sections, data.selected)
    lines: list[str] = []
    count = 0
    show_sections = len(chosen) > 1 or (chosen and chosen[0][0].id != "test")
    for section, steps in chosen:
        if show_sections:
            lines.append(f"*{escape(section.title)}*")
        for step in steps:
            count += 1
            text = escape(step.label)
            if step.node.failure_origin:
                text = "{color:#de350b}*" + text + "*{color}"
            extra = []
            if step.node.call is not None:
                extra.append(mono(step.node.call.label))
            if step.node.failure_origin and step.node.message:
                extra.append(mono(step.node.message.splitlines()[0]))
            elif step.node.status == "skipped":
                extra.append("_не выполнялся_")
            lines.append("#" * step.depth + " " + " — ".join([text] + extra))
    return lines, count


def render_calls(data: DescriptionInput) -> tuple[str | None, int]:
    """Requests of the chosen steps, plus request/response bodies of the failing one."""
    calls: list[str] = []
    for _, steps in selected_steps(data.sections, data.selected):
        for step in steps:
            calls.extend(f"{call.method} {call.url} → {call.status or '—'}" for call in step.node.calls)
    parts = []
    if calls:
        parts.append(noformat(data.mask("\n".join(calls))))
    broken = failure_call(data.sections)
    if broken is not None:
        parts.append(f"Запрос, на котором упал тест: {mono(broken.label)}")
        if broken.request_body is not None:
            parts.append("Тело запроса:\n" + code_json(_mask_value(broken.request_body, data.mask)))
        if broken.response_body is not None:
            parts.append("Ответ:\n" + code_json(_mask_value(broken.response_body, data.mask)))
    return ("\n\n".join(parts) if parts else None), len(calls)


def _mask_value(value: object, mask) -> object:
    if isinstance(value, (dict, list)):
        try:
            return json.loads(mask(json.dumps(value, ensure_ascii=False)))
        except ValueError:
            return mask(json.dumps(value, ensure_ascii=False, indent=2))
    return mask(str(value))


def build_description(data: DescriptionInput) -> dict:
    """Description text with the numbers the UI shows after creation."""
    blocks: list[str] = []
    step_lines, step_count = render_steps(data)
    blocks.append("h3. Шаги воспроизведения\n" + ("\n".join(step_lines) if step_lines else "_Шаги не выбраны_"))

    actual = noformat(data.mask(data.error_message or "Тест упал без сообщения об ошибке"))
    if data.include_trace and data.error_trace:
        trace = data.error_trace.strip().splitlines()[-TRACE_LINES:]
        actual += "\n\nТрассировка (последние строки):\n" + noformat(data.mask("\n".join(trace)))
    blocks.append("h3. Фактический результат\n" + actual)
    if data.expected is not None:
        blocks.append("h3. Ожидаемый результат\n" + (data.expected.strip() or "_Не указан_"))

    log_lines = 0
    log_block = None
    if data.log_mode == "calls":
        text, log_lines = render_calls(data)
        if text:
            log_block = "h3. Запросы\n" + text
    elif data.log_mode == "full" and data.log_text:
        log_text = data.mask(data.log_text)
        log_lines = len(log_text.splitlines())
        log_block = ("h3. Лог", log_text)

    env = []
    if data.stand_line:
        env.append(f"* Стенд: {data.stand_line}")
    env.append(f"* Прогон: {escape(data.run_line)}")
    if data.test_full_name:
        env.append(f"* Тест: {mono(data.test_full_name)}")
    if data.parameters:
        env.append("* Параметры: " + ", ".join(mono(f"{name}={value}") for name, value in data.parameters))
    env.extend(f"* {link(title, url)}" for title, url in data.links)
    env.extend(f"* [^{name}]" for name in data.attachment_names)
    env_block = "h3. Окружение и ссылки\n" + "\n".join(env)

    head = "\n\n".join(blocks)
    if isinstance(log_block, tuple):
        title, log_text = log_block
        room = DESCRIPTION_LIMIT - len(head) - len(env_block) - 200
        truncated = len(log_text) > room
        if truncated:
            # keep the tail: the end of the log is where the test broke
            log_text = "… начало обрезано, полный лог во вложении\n" + log_text[-max(room, 0):]
        log_block = f"{title}\n" + noformat(log_text)
    parts = [head] + ([log_block] if log_block else []) + [env_block]
    text = "\n\n".join(parts)
    if len(text) > DESCRIPTION_LIMIT:
        text = text[: DESCRIPTION_LIMIT - 40] + "\n\n_… описание обрезано_"
    return {"text": text, "steps": step_count, "logLines": log_lines}
