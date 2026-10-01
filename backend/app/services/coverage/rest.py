"""REST coverage: maps logged HTTP calls onto OpenAPI (3.x) / Swagger (2.0) operations."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlsplit

HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
UUID_SEGMENT_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
NUMERIC_SEGMENT_RE = re.compile(r"^\d+$")
MAX_TESTS_PER_OPERATION = 50


class SpecError(ValueError):
    pass


@dataclass
class Operation:
    method: str
    path: str
    tag: str
    summary: str
    response_codes: list[str]
    pattern: re.Pattern
    literal_segments: int
    calls: int = 0
    status_calls: Counter = field(default_factory=Counter)
    tests: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.method} {self.path}"


@dataclass
class RestSpec:
    title: str
    version: str
    base_path: str
    hosts: set[str]
    operations: list[Operation]


def _normalize_base(path: str) -> str:
    path = "/" + path.strip("/") if path and path.strip("/") else ""
    return path


def _template_to_regex(path: str) -> tuple[re.Pattern, int]:
    segments = [segment for segment in path.strip("/").split("/") if segment]
    parts, literals = [], 0
    for segment in segments:
        if "{" in segment:
            parts.append(re.sub(r"\\\{[^/]+?\\\}", "[^/]+", re.escape(segment)))
        else:
            parts.append(re.escape(segment))
            literals += 1
    return re.compile("^/" + "/".join(parts) + "/?$"), literals


def load_rest_spec(document: dict, base_path_override: str | None = None, host_override: str | None = None) -> RestSpec:
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        raise SpecError("Это не OpenAPI/Swagger: нет раздела paths")
    info = document.get("info") if isinstance(document.get("info"), dict) else {}

    hosts: set[str] = set()
    base_path = ""
    if isinstance(document.get("servers"), list) and document["servers"]:
        for server in document["servers"]:
            url = server.get("url") if isinstance(server, dict) else None
            if not isinstance(url, str):
                continue
            parts = urlsplit(url)
            if parts.netloc:
                hosts.add(parts.netloc)
            base_path = base_path or _normalize_base(parts.path)
    elif isinstance(document.get("basePath"), str):  # Swagger 2.0
        base_path = _normalize_base(document["basePath"])
        if isinstance(document.get("host"), str):
            hosts.add(document["host"])

    if base_path_override is not None:
        base_path = _normalize_base(base_path_override)
    if host_override:
        hosts = {host_override.strip()}

    operations = []
    for path, item in document["paths"].items():
        if not isinstance(item, dict):
            continue
        pattern, literals = _template_to_regex(path)
        for method in HTTP_METHODS:
            operation = item.get(method)
            if not isinstance(operation, dict):
                continue
            tags = operation.get("tags") if isinstance(operation.get("tags"), list) else []
            responses = operation.get("responses") if isinstance(operation.get("responses"), dict) else {}
            operations.append(
                Operation(
                    method=method.upper(),
                    path=path,
                    tag=str(tags[0]) if tags else "default",
                    summary=str(operation.get("summary") or operation.get("operationId") or ""),
                    response_codes=[str(code) for code in responses],
                    pattern=pattern,
                    literal_segments=literals,
                )
            )
    if not operations:
        raise SpecError("В спецификации нет ни одной операции")
    return RestSpec(
        title=str(info.get("title") or "API"),
        version=str(info.get("version") or ""),
        base_path=base_path,
        hosts=hosts,
        operations=operations,
    )


def _code_matches(documented: str, actual: str) -> bool:
    documented = documented.upper()
    if documented == actual:
        return True
    return len(documented) == 3 and documented.endswith("XX") and documented[0] == actual[0]


def _generalize_path(path: str) -> str:
    segments = []
    for segment in path.split("/"):
        if UUID_SEGMENT_RE.match(segment) or NUMERIC_SEGMENT_RE.match(segment):
            segments.append("{id}")
        else:
            segments.append(segment)
    return "/".join(segments)


class RestCoverage:
    def __init__(self, spec: RestSpec):
        self.spec = spec
        self.by_method: dict[str, list[Operation]] = defaultdict(list)
        for operation in spec.operations:
            self.by_method[operation.method].append(operation)
        for operations in self.by_method.values():
            operations.sort(key=lambda op: -op.literal_segments)
        self.unknown: dict[tuple[str, str], Counter] = defaultdict(Counter)
        self.total_calls = 0
        self.matched_calls = 0
        self.tests_with_calls: set[str] = set()

    def _relative_path(self, url: str) -> tuple[str | None, str]:
        parts = urlsplit(url)
        if self.spec.hosts and parts.netloc and parts.netloc not in self.spec.hosts:
            return None, parts.path
        path = parts.path or "/"
        base = self.spec.base_path
        if base:
            if path == base or path.startswith(base + "/"):
                return path[len(base) :] or "/", path
            return None, path
        return path, path

    def add_call(self, method: str, url: str, status: str | None, test_key: str, test: dict) -> None:
        relative, full_path = self._relative_path(url)
        if relative is None:
            return  # another service
        self.total_calls += 1
        self.tests_with_calls.add(test_key)
        for operation in self.by_method.get(method.upper(), []):
            if operation.pattern.match(relative):
                operation.calls += 1
                operation.status_calls[status or "?"] += 1
                if test_key not in operation.tests and len(operation.tests) < MAX_TESTS_PER_OPERATION:
                    operation.tests[test_key] = test
                self.matched_calls += 1
                return
        self.unknown[(method.upper(), _generalize_path(full_path))][status or "?"] += 1

    def result(self, total_tests: int) -> dict:
        operations = []
        documented_codes = covered_codes = 0
        for op in self.spec.operations:
            codes = []
            for code in op.response_codes:
                if code == "default":
                    calls = sum(
                        count for actual, count in op.status_calls.items()
                        if not any(_code_matches(other, actual) for other in op.response_codes if other != "default")
                    )
                else:
                    calls = sum(count for actual, count in op.status_calls.items() if _code_matches(code, actual))
                codes.append({"code": code, "calls": calls})
                documented_codes += 1
                covered_codes += 1 if calls else 0
            undocumented = [
                {"code": actual, "calls": count}
                for actual, count in sorted(op.status_calls.items())
                if actual != "?" and not any(_code_matches(code, actual) for code in op.response_codes)
            ]
            operations.append(
                {
                    "id": op.id,
                    "method": op.method,
                    "path": op.path,
                    "tag": op.tag,
                    "summary": op.summary,
                    "calls": op.calls,
                    "codes": codes,
                    "undocumentedCodes": undocumented,
                    "tests": list(op.tests.values()),
                }
            )
        covered_operations = sum(1 for op in operations if op["calls"])
        unknown = [
            {"method": method, "path": path, "calls": sum(statuses.values()), "codes": sorted(statuses)}
            for (method, path), statuses in sorted(self.unknown.items(), key=lambda item: -sum(item[1].values()))
        ]
        return {
            "kind": "rest",
            "spec": {"title": self.spec.title, "version": self.spec.version, "basePath": self.spec.base_path, "hosts": sorted(self.spec.hosts)},
            "summary": {
                "operations": len(operations),
                "coveredOperations": covered_operations,
                "codes": documented_codes,
                "coveredCodes": covered_codes,
                "calls": self.total_calls,
                "matchedCalls": self.matched_calls,
                "unknownCalls": len(unknown),
                "testsWithCalls": len(self.tests_with_calls),
                "totalTests": total_tests,
                "coverage": round(covered_operations / len(operations) * 100) if operations else 0,
            },
            "operations": operations,
            "unknown": unknown,
        }
