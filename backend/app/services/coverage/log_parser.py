"""Extracts API calls from the plain-text log attached to every Allure test.

The test framework logs through `api_controller.py` in two shapes:

REST::

    INFO     my_log:api_controller.py:116 Запрос: POST http://host:4001/api/driver/v1/claim
    INFO     my_log:api_controller.py:120 Тело запроса: {...}
    INFO     my_log:api_controller.py:152 Статус код ответа: 200

GraphQL (the query can span many lines and ends at "Переменные:")::

    INFO     my_log:api_controller.py:72 Запрос: "http://host:4001/graphql" { claimExtraData(...) {...} } Переменные: None
    INFO     my_log:api_controller.py:77 Ответ: {...}

Records are split on the "LEVEL logger:file.py:LINE" prefix rather than on
newlines: in real logs two records are sometimes glued without a line break.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
RECORD_RE = re.compile(r"(?:DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+[\w.-]+:[\w.-]+\.py:\d+\s")

REST_REQUEST_RE = re.compile(r"^Запрос:\s+([A-Z]+)\s+(\S+)")
GQL_REQUEST_RE = re.compile(r'^Запрос:\s+"([^"]+)"\s+(.*?)\s+Переменные:\s*(.*)$', re.S)
STATUS_RE = re.compile(r"^Статус код ответа:\s*(\d{3})")
UNEXPECTED_STATUS_RE = re.compile(r"статус-код ответа от АПИ '(\d{3})'")


@dataclass
class RestCall:
    method: str
    url: str
    status: str | None = None


@dataclass
class GraphqlCall:
    url: str
    query: str
    variables: str | None = None


@dataclass
class ParsedLog:
    rest: list[RestCall] = field(default_factory=list)
    graphql: list[GraphqlCall] = field(default_factory=list)


def split_records(text: str) -> list[str]:
    """Message part of every log record, in order."""
    text = ANSI_RE.sub("", text)
    starts = [match for match in RECORD_RE.finditer(text)]
    messages = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        messages.append(text[match.end() : end].strip())
    return messages


def parse_log(text: str) -> ParsedLog:
    parsed = ParsedLog()
    pending_rest: RestCall | None = None
    for message in split_records(text):
        gql = GQL_REQUEST_RE.match(message)
        if gql:
            variables = gql.group(3).strip()
            parsed.graphql.append(
                GraphqlCall(url=gql.group(1), query=gql.group(2).strip(), variables=None if variables == "None" else variables)
            )
            pending_rest = None
            continue

        rest = REST_REQUEST_RE.match(message)
        if rest:
            pending_rest = RestCall(method=rest.group(1), url=rest.group(2))
            parsed.rest.append(pending_rest)
            continue

        if pending_rest is not None and pending_rest.status is None:
            status = STATUS_RE.match(message) or UNEXPECTED_STATUS_RE.search(message)
            if status:
                pending_rest.status = status.group(1)
    return parsed
