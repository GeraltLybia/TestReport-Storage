"""Create-screen metadata and validation shared by the form and issue creation."""
import math
import re
from datetime import date, datetime

from fastapi import HTTPException

# Generated or fixed fields cannot be overridden by arbitrary request data.
GENERATED = {"project", "issuetype", "summary", "description", "reporter", "attachment"}
BUILTIN = GENERATED | {"priority", "components", "labels", "assignee", "environment"}


def field_metadata(item: dict) -> dict:
    schema = item.get("schema") or {}
    kind = schema.get("type")
    if not kind and item.get("fieldId") in {"components", "versions", "fixVersions"}:
        kind = "array"
    custom = str(schema.get("custom", "")).split(":")[-1]
    values = item.get("allowedValues")
    options = values if isinstance(values, list) else []
    control = "unsupported"
    if custom == "cascadingselect":
        control = "cascade"
    elif options or kind in {"option", "version", "component"} or custom in {"select", "multiselect", "radiobuttons", "multicheckboxes"} or (kind == "array" and schema.get("items") in {"option", "version", "component"}):
        control = "multiselect" if kind == "array" else "select"
    elif item.get("fieldId") == "duedate":
        control = "date"
    elif kind == "string":
        control = {"datepicker": "date", "datetime": "datetime-local", "textarea": "textarea"}.get(custom, "text")
    elif kind in {"number", "integer"}:
        control = "number"
    elif kind == "boolean":
        control = "boolean"
    elif kind == "date":
        control = "date"
    elif kind == "datetime":
        control = "datetime-local"
    elif kind == "user":
        control = "user"
    elif kind == "array" and schema.get("items") in {"string", "user"}:
        control = "users" if schema.get("items") == "user" else "strings"
    operations = item.get("operations")
    if operations and "set" not in operations:
        control = "unsupported"
    return {
        "id": str(item.get("fieldId") or item.get("key")),
        "name": item.get("name") or item.get("fieldId"),
        "required": bool(item.get("required")),
        "schema": schema,
        "control": control,
        "allowedValues": options,
        "hasDefaultValue": bool(item.get("hasDefaultValue") or item.get("defaultValue") is not None),
        "defaultValue": item.get("defaultValue"),
    }


def empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {} or (isinstance(value, str) and not value.strip())


def fixed_default(field: dict) -> bool:
    return field["id"] != "assignee" and field["defaultValue"] is not None and not field["allowedValues"]


def option_key(value):
    if isinstance(value, dict):
        return next(((k, str(value[k])) for k in ("id", "name", "value", "key") if k in value), None)
    return ("literal", value)


def validate_value(field: dict, value) -> None:
    control = field["control"]
    valid = True
    if control in {"select", "multiselect", "cascade"}:
        options = field["allowedValues"]
        def allowed(v, choices):
            return any(option_key(v) == option_key(choice) for choice in choices)
        if control == "multiselect":
            valid = isinstance(value, list) and all(allowed(v, options) for v in value)
        else:
            valid = allowed(value, options)
            if valid and control == "cascade" and isinstance(value, dict) and value.get("child"):
                parent = next(v for v in options if option_key(v) == option_key(value))
                valid = allowed(value["child"], parent.get("children") or [])
    elif control == "number":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        if valid and field["schema"].get("type") == "integer":
            valid = int(value) == value
    elif control == "boolean":
        valid = isinstance(value, bool)
    elif control in {"user", "users"}:
        def user(v):
            return isinstance(v, dict) and isinstance(v.get("name"), str) and bool(v["name"].strip())
        valid = user(value) if control == "user" else isinstance(value, list) and all(user(v) for v in value)
    elif control == "strings":
        valid = isinstance(value, list) and all(isinstance(v, str) for v in value)
    elif control in {"date", "datetime-local"}:
        try:
            if control == "date":
                valid = isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
                date.fromisoformat(value)
            else:
                parsed = datetime.fromisoformat(value)
                valid = parsed.tzinfo is not None
        except (ValueError, TypeError):
            valid = False
    else:
        valid = isinstance(value, str)
    if not valid:
        raise HTTPException(400, f"Некорректное значение поля «{field['name']}»")


def apply_fields(fields: dict, submitted: dict, definitions: list[dict]) -> None:
    by_id = {f["id"]: f for f in definitions}
    for key, value in submitted.items():
        definition = by_id.get(key)
        if key in BUILTIN or not definition or definition["control"] == "unsupported":
            raise HTTPException(400, f"Поле «{key}» нельзя задать в этой форме")
        if not fixed_default(definition) and not empty(value):
            validate_value(definition, value)
            if definition["control"] == "datetime-local":
                parsed = datetime.fromisoformat(value)
                value = parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond // 1000:03d}" + parsed.strftime("%z")
            fields[key] = value
    for definition in definitions:
        key = definition["id"]
        if key in GENERATED:
            continue
        if fixed_default(definition):
            # Jira's own default is authoritative when it offers no choices.
            fields[key] = definition["defaultValue"]
            continue
        # Jira applies its own defaults when an optional field is omitted.
        if empty(fields.get(key)) and definition["required"]:
            default = definition["defaultValue"]
            if not empty(default):
                fields[key] = default
            elif not definition["hasDefaultValue"]:
                raise HTTPException(400, f"Заполните обязательное поле «{definition['name']}»")
        if key in fields and not empty(fields[key]) and definition["control"] != "unsupported":
            validate_value(definition, fields[key])
