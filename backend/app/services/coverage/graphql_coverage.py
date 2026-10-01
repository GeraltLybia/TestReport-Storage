"""GraphQL coverage: walks logged queries over the uploaded schema (SDL or introspection JSON)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from urllib.parse import urlsplit

from graphql import (
    GraphQLError,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLUnionType,
    TypeInfo,
    TypeInfoVisitor,
    Visitor,
    build_client_schema,
    build_schema,
    get_named_type,
    parse,
    validate,
    visit,
)

MAX_TESTS_PER_FIELD = 30
MAX_INVALID_SAMPLES = 20


class SchemaError(ValueError):
    pass


def load_schema(text: str) -> GraphQLSchema:
    stripped = text.lstrip()
    try:
        if stripped.startswith("{"):
            document = json.loads(stripped)
            introspection = document.get("data", document) if isinstance(document, dict) else None
            if not isinstance(introspection, dict) or "__schema" not in introspection:
                raise SchemaError("JSON не похож на результат интроспекции: нет __schema")
            return build_client_schema(introspection)
        return build_schema(text)
    except SchemaError:
        raise
    except (GraphQLError, TypeError, ValueError, KeyError) as exc:
        raise SchemaError(f"Не удалось прочитать схему: {exc}") from exc


def _endpoint_key(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.netloc}{parts.path.rstrip('/')}"


class _FieldCollector(Visitor):
    def __init__(self, type_info: TypeInfo, sink: list[tuple[str, str, tuple[str, ...]]]):
        super().__init__()
        self.type_info = type_info
        self.sink = sink

    def enter_field(self, node, *_args):
        parent = self.type_info.get_parent_type()
        field_def = self.type_info.get_field_def()
        if parent is None or field_def is None or node.name.value.startswith("__"):
            return
        args = tuple(argument.name.value for argument in node.arguments or ())
        self.sink.append((parent.name, node.name.value, args))


class GraphqlCoverage:
    def __init__(self, schema: GraphQLSchema, endpoint: str | None = None):
        self.schema = schema
        self.endpoint = _endpoint_key(endpoint) if endpoint else None
        self.field_calls: Counter = Counter()
        self.arg_calls: Counter = Counter()
        self.field_tests: dict[tuple[str, str], dict] = defaultdict(dict)
        self.total_calls = 0
        self.invalid: list[dict] = []
        self.invalid_calls = 0
        self.tests_with_calls: set[str] = set()

    def add_call(self, url: str, query: str, test_key: str, test: dict) -> None:
        if self.endpoint and _endpoint_key(url) != self.endpoint:
            return  # another GraphQL service
        self.total_calls += 1
        self.tests_with_calls.add(test_key)
        try:
            document = parse(query)
        except GraphQLError as exc:
            self._remember_invalid(query, exc.message)
            return
        errors = validate(self.schema, document)
        if errors:
            self._remember_invalid(query, errors[0].message)

        visited: list[tuple[str, str, tuple[str, ...]]] = []
        type_info = TypeInfo(self.schema)
        visit(document, TypeInfoVisitor(type_info, _FieldCollector(type_info, visited)))
        for type_name, field_name, args in visited:
            key = (type_name, field_name)
            self.field_calls[key] += 1
            for arg in args:
                self.arg_calls[(type_name, field_name, arg)] += 1
            tests = self.field_tests[key]
            if test_key not in tests and len(tests) < MAX_TESTS_PER_FIELD:
                tests[test_key] = test

    def _remember_invalid(self, query: str, message: str) -> None:
        self.invalid_calls += 1
        if len(self.invalid) < MAX_INVALID_SAMPLES:
            self.invalid.append({"query": query[:2000], "error": message})

    def result(self, total_tests: int) -> dict:
        roots = {}
        for kind, root in (("query", self.schema.query_type), ("mutation", self.schema.mutation_type), ("subscription", self.schema.subscription_type)):
            if root is not None:
                roots[root.name] = kind

        types = []
        total_fields = covered_fields = 0
        total_args = used_args = 0
        root_fields = covered_root_fields = 0
        covered_types = object_types = 0
        for named in sorted(self.schema.type_map.values(), key=lambda item: item.name):
            if named.name.startswith("__"):
                continue
            if isinstance(named, GraphQLUnionType):
                types.append({"name": named.name, "kind": "union", "root": None, "fields": [],
                              "possibleTypes": [member.name for member in named.types]})
                continue
            if not isinstance(named, (GraphQLObjectType, GraphQLInterfaceType)):
                continue
            object_types += 1
            fields = []
            for field_name, field_def in named.fields.items():
                calls = self.field_calls.get((named.name, field_name), 0)
                target = get_named_type(field_def.type)
                args = [{"name": arg, "calls": self.arg_calls.get((named.name, field_name, arg), 0)} for arg in field_def.args]
                fields.append({
                    "name": field_name,
                    "type": str(field_def.type),
                    "target": target.name if isinstance(target, (GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType)) else None,
                    "calls": calls,
                    "args": args,
                    "tests": list(self.field_tests.get((named.name, field_name), {}).values()),
                })
                total_fields += 1
                covered_fields += 1 if calls else 0
                total_args += len(args)
                used_args += sum(1 for arg in args if arg["calls"])
                if named.name in roots:
                    root_fields += 1
                    covered_root_fields += 1 if calls else 0
            if any(field["calls"] for field in fields):
                covered_types += 1
            types.append({
                "name": named.name,
                "kind": "interface" if isinstance(named, GraphQLInterfaceType) else "object",
                "root": roots.get(named.name),
                "fields": fields,
                "possibleTypes": [],
            })

        return {
            "kind": "graphql",
            "spec": {"roots": roots},
            "summary": {
                "fields": total_fields,
                "coveredFields": covered_fields,
                "types": object_types,
                "coveredTypes": covered_types,
                "rootFields": root_fields,
                "coveredRootFields": covered_root_fields,
                "args": total_args,
                "usedArgs": used_args,
                "calls": self.total_calls,
                "invalidCalls": self.invalid_calls,
                "testsWithCalls": len(self.tests_with_calls),
                "totalTests": total_tests,
                "coverage": round(covered_fields / total_fields * 100) if total_fields else 0,
            },
            "types": types,
            "invalid": self.invalid,
        }
