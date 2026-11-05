import pytest

from .fields import apply_fields, field_metadata


@pytest.mark.parametrize("schema,default", [
    ({"type": "string"}, "Default text"),
    ({"type": "number"}, 0),
    ({"type": "boolean"}, False),
    ({"type": "option"}, {"id": "10", "value": "Default option"}),
    ({"type": "array", "items": "option"}, [{"id": "10"}]),
    ({"type": "user"}, {"name": "alice"}),
])
@pytest.mark.parametrize("required", [False, True])
def test_default_without_choices_is_used_even_if_client_sends_other_input(schema, default, required):
    definition = field_metadata({
        "fieldId": "customfield_fixed", "name": "Fixed", "schema": schema,
        "defaultValue": default, "required": required,
    })
    fields = {}
    apply_fields(fields, {"customfield_fixed": "Wrong user input"}, [definition])
    assert fields["customfield_fixed"] == default


def test_default_with_choices_remains_editable():
    definition = field_metadata({
        "fieldId": "customfield_choice", "schema": {"type": "option"},
        "defaultValue": {"id": "1"}, "allowedValues": [{"id": "1"}, {"id": "2"}],
    })
    fields = {}
    apply_fields(fields, {"customfield_choice": {"id": "2"}}, [definition])
    assert fields["customfield_choice"] == {"id": "2"}


def test_fixed_builtin_default_is_applied_and_a_missing_default_does_not_lock_a_field():
    definitions = [
        field_metadata({"fieldId": "assignee", "schema": {"type": "user"}, "defaultValue": {"name": "alice"}}),
        field_metadata({"fieldId": "customfield_text", "schema": {"type": "string"}, "hasDefaultValue": True}),
    ]
    fields = {"assignee": {"name": "other"}}
    apply_fields(fields, {"customfield_text": "Editable"}, definitions)
    assert fields == {"assignee": {"name": "alice"}, "customfield_text": "Editable"}
