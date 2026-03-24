"""Tests for reserved and underscore-prefixed property name handling."""

import copy

import pytest
from pydantic import ValidationError

from jsonschema_pydantic_converter import (
    create_type_adapter,
    transform,
    transform_with_modules,
)
from jsonschema_pydantic_converter._property_renaming import (
    compute_safe_name,
    needs_rename,
    rename_properties,
)

# ---------------------------------------------------------------------------
# Unit tests for _property_renaming helpers
# ---------------------------------------------------------------------------


class TestNeedsRename:
    def test_underscore_prefix(self):
        assert needs_rename("_hidden") is True
        assert needs_rename("__dunder") is True

    def test_reserved_names(self):
        assert needs_rename("schema") is True
        assert needs_rename("copy") is True
        assert needs_rename("validate") is True
        assert needs_rename("model_fields") is True
        assert needs_rename("model_validate") is True
        assert needs_rename("model_dump") is True
        assert needs_rename("model_json_schema") is True

    def test_normal_names(self):
        assert needs_rename("name") is False
        assert needs_rename("age") is False
        assert needs_rename("email") is False


class TestComputeSafeName:
    def test_strip_underscore(self):
        assert compute_safe_name("_hidden", set()) == "hidden"

    def test_strip_multiple_underscores(self):
        assert compute_safe_name("___deep", set()) == "deep"

    def test_empty_after_strip(self):
        assert compute_safe_name("_", set()) == "field"
        assert compute_safe_name("___", set()) == "field"

    def test_reserved_after_strip(self):
        # _schema strips to "schema" which is reserved -> "schema_"
        assert compute_safe_name("_schema", set()) == "schema_"

    def test_collision_with_taken(self):
        assert compute_safe_name("_hidden", {"hidden"}) == "hidden_"

    def test_double_collision(self):
        assert compute_safe_name("_hidden", {"hidden", "hidden_"}) == "hidden__"

    def test_reserved_name_directly(self):
        assert compute_safe_name("copy", set()) == "copy_"

    def test_reserved_collision_with_taken(self):
        # "schema" -> reserved -> "schema_", but schema_ is taken -> "schema__"
        assert compute_safe_name("schema", {"schema_"}) == "schema__"


class TestRenameProperties:
    def test_no_renames_needed(self):
        properties = {"name": {"type": "string"}, "age": {"type": "integer"}}
        field_map, required = rename_properties(properties, ["name"])
        assert field_map == {"name": ("name", "name"), "age": ("age", "age")}
        assert required == ["name"]

    def test_simple_underscore_rename(self):
        properties = {"_hidden": {"type": "string"}}
        field_map, required = rename_properties(properties, ["_hidden"])
        assert field_map["_hidden"] == ("hidden", "_hidden")
        assert required == ["hidden"]

    def test_reserved_name_rename(self):
        properties = {"schema": {"type": "string"}}
        field_map, _ = rename_properties(properties, [])
        assert field_map["schema"] == ("schema_", "schema")

    def test_collision_both_exist(self):
        properties = {"_hidden": {"type": "string"}, "hidden": {"type": "integer"}}
        field_map, _ = rename_properties(properties, [])
        assert field_map["_hidden"] == ("hidden_", "_hidden")
        assert field_map["hidden"] == ("hidden", "hidden")

    def test_reserved_collision_both_exist(self):
        properties = {"schema": {"type": "string"}, "schema_": {"type": "integer"}}
        field_map, _ = rename_properties(properties, [])
        assert field_map["schema"] == ("schema__", "schema")
        assert field_map["schema_"] == ("schema_", "schema_")

    def test_normal_properties_untouched(self):
        properties = {"name": {"type": "string"}, "age": {"type": "integer"}}
        field_map, _ = rename_properties(properties, [])
        for name in properties:
            assert field_map[name] == (name, name)  # alias equals field name


# ---------------------------------------------------------------------------
# Integration tests: single renamed field round-trips
# ---------------------------------------------------------------------------


_SINGLE_FIELD_CASES = [
    ("_hidden", "hidden", "_hidden"),
    ("_schema", "schema_", "_schema"),
    ("schema", "schema_", "schema"),
    ("copy", "copy_", "copy"),
    ("validate", "validate_", "validate"),
    ("model_fields", "model_fields_", "model_fields"),
]


class TestSingleRenamedField:
    @pytest.mark.parametrize(
        "prop_name,expected_field,expected_alias", _SINGLE_FIELD_CASES
    )
    def test_transform_roundtrip(self, prop_name, expected_field, expected_alias):
        schema = {
            "type": "object",
            "properties": {prop_name: {"type": "string"}},
            "required": [prop_name],
        }

        Model, ns = transform_with_modules(schema)

        # Field exists under internal name
        assert expected_field in Model.model_fields

        # Validate with original JSON property name
        instance = Model.model_validate({expected_alias: "val"})

        # model_dump uses alias by default (no by_alias=True needed)
        dumped = instance.model_dump()
        assert dumped[expected_alias] == "val"

        # model_dump mode=json also defaults to alias
        dumped_json = instance.model_dump(mode="json")
        assert dumped_json[expected_alias] == "val"

        # model_dump_json defaults to alias
        import json

        dumped_json_str = json.loads(instance.model_dump_json())
        assert dumped_json_str[expected_alias] == "val"

        # model_json_schema shows original name
        json_schema = Model.model_json_schema()
        assert expected_alias in json_schema.get("properties", {})

    @pytest.mark.parametrize(
        "prop_name,expected_field,expected_alias", _SINGLE_FIELD_CASES
    )
    def test_explicit_by_alias_false(self, prop_name, expected_field, expected_alias):
        """by_alias=False must return internal Python field names."""
        schema = {
            "type": "object",
            "properties": {prop_name: {"type": "string"}},
            "required": [prop_name],
        }
        Model = transform(schema)
        instance = Model.model_validate({expected_alias: "val"})

        dumped = instance.model_dump(by_alias=False)
        assert expected_field in dumped

    @pytest.mark.parametrize(
        "prop_name,expected_field,expected_alias", _SINGLE_FIELD_CASES
    )
    def test_basemodel_methods_intact(self, prop_name, expected_field, expected_alias):
        schema = {
            "type": "object",
            "properties": {prop_name: {"type": "string"}},
            "required": [prop_name],
        }
        Model = transform(schema)
        instance = Model.model_validate({expected_alias: "val"})

        # Core BaseModel methods must remain callable
        assert callable(Model.model_json_schema)
        assert callable(Model.model_validate)
        assert callable(instance.model_dump)
        assert callable(instance.model_dump_json)
        assert callable(instance.model_copy)

        # Actually call them to verify they work
        Model.model_json_schema()
        instance.model_dump()
        instance.model_dump_json()
        instance.model_copy()


# ---------------------------------------------------------------------------
# Collision scenario tests
# ---------------------------------------------------------------------------


class TestCollisionScenarios:
    def test_underscore_and_plain_collision(self):
        """_hidden + hidden both exist."""
        schema = {
            "type": "object",
            "properties": {
                "_hidden": {"type": "string"},
                "hidden": {"type": "integer"},
            },
            "required": ["_hidden", "hidden"],
        }
        Model = transform(schema)

        # hidden_ is the renamed _hidden, hidden is the original
        assert "hidden_" in Model.model_fields
        assert "hidden" in Model.model_fields

        instance = Model.model_validate({"_hidden": "text", "hidden": 42})
        dumped = instance.model_dump()
        assert dumped["_hidden"] == "text"
        assert dumped["hidden"] == 42

    def test_reserved_and_suffixed_collision(self):
        """schema + schema_ both exist."""
        schema = {
            "type": "object",
            "properties": {
                "schema": {"type": "string"},
                "schema_": {"type": "integer"},
            },
            "required": ["schema", "schema_"],
        }
        Model = transform(schema)

        # schema__ is the renamed schema, schema_ is the original
        assert "schema__" in Model.model_fields
        assert "schema_" in Model.model_fields

        instance = Model.model_validate({"schema": "text", "schema_": 42})
        dumped = instance.model_dump()
        assert dumped["schema"] == "text"
        assert dumped["schema_"] == 42


# ---------------------------------------------------------------------------
# Normal fields: no renaming, no aliases
# ---------------------------------------------------------------------------


class TestNormalFieldsUnchanged:
    def test_plain_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        Model = transform(schema)
        assert "name" in Model.model_fields
        assert "age" in Model.model_fields

        # All fields now have aliases for consistency
        fi = Model.model_fields["name"]
        assert fi.alias == "name"


# ---------------------------------------------------------------------------
# Nested / $defs round-trips
# ---------------------------------------------------------------------------


class TestNestedSchemas:
    def test_schema_property_inside_defs(self):
        """Property named 'schema' inside $defs.Inner must be renamed."""
        schema = {
            "type": "object",
            "properties": {"inner": {"$ref": "#/$defs/Inner"}},
            "$defs": {
                "Inner": {
                    "type": "object",
                    "properties": {"schema": {"type": "string"}},
                    "required": ["schema"],
                }
            },
        }

        Model, ns = transform_with_modules(schema)
        instance = Model.model_validate({"inner": {"schema": "val"}})

        inner_dump = instance.inner.model_dump()  # type: ignore[attr-defined]
        assert inner_dump["schema"] == "val"

        # JSON schema shows original name
        full_schema = Model.model_json_schema()
        # The Inner definition should have "schema" as property name
        defs = full_schema.get("$defs", {})
        inner_schema = next(iter(defs.values()))
        assert "schema" in inner_schema["properties"]
        assert inner_schema["required"] == ["schema"]

    def test_underscore_property_inside_items(self):
        """Property named '_file' inside array items must be renamed."""
        schema = {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"_file": {"type": "string"}},
                        "required": ["_file"],
                    },
                }
            },
        }

        Model = transform(schema)
        instance = Model.model_validate({"files": [{"_file": "a.txt"}]})
        dumped = instance.model_dump()
        assert dumped["files"][0]["_file"] == "a.txt"

    def test_definitions_key(self):
        """Renaming must work with 'definitions' (not just '$defs')."""
        schema = {
            "type": "object",
            "properties": {"ref": {"$ref": "#/definitions/Item"}},
            "definitions": {
                "Item": {
                    "type": "object",
                    "properties": {"_value": {"type": "integer"}},
                    "required": ["_value"],
                }
            },
        }
        Model = transform(schema)
        instance = Model.model_validate({"ref": {"_value": 10}})
        assert instance.ref.model_dump()["_value"] == 10  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# create_type_adapter integration
# ---------------------------------------------------------------------------


class TestCreateTypeAdapterIntegration:
    def test_adapter_validate_with_original_name(self):
        schema = {
            "type": "object",
            "properties": {
                "_hidden": {"type": "string"},
                "copy": {"type": "integer"},
            },
            "required": ["_hidden", "copy"],
        }
        adapter = create_type_adapter(schema)
        obj = adapter.validate_python({"_hidden": "secret", "copy": 42})
        assert obj.hidden == "secret"
        assert obj.copy_ == 42

    def test_adapter_does_not_mutate_input(self):
        schema = {
            "type": "object",
            "properties": {"_file": {"type": "string"}},
        }
        original = copy.deepcopy(schema)
        create_type_adapter(schema)
        assert schema == original


# ---------------------------------------------------------------------------
# model_json_schema round-trip
# ---------------------------------------------------------------------------


class TestJsonSchemaRoundTrip:
    def test_json_schema_preserves_original_names(self):
        schema = {
            "type": "object",
            "properties": {
                "_hidden": {"type": "string"},
                "schema": {"type": "string"},
                "copy": {"type": "string"},
                "normal": {"type": "string"},
            },
            "required": ["_hidden", "schema", "copy", "normal"],
        }
        Model = transform(schema)
        json_schema = Model.model_json_schema()

        props = json_schema["properties"]
        assert "_hidden" in props
        assert "schema" in props
        assert "copy" in props
        assert "normal" in props

        req = json_schema["required"]
        assert "_hidden" in req
        assert "schema" in req
        assert "copy" in req
        assert "normal" in req


# ---------------------------------------------------------------------------
# Multiple reserved in one object
# ---------------------------------------------------------------------------


class TestMultipleReserved:
    def test_several_reserved_and_underscore(self):
        schema = {
            "type": "object",
            "properties": {
                "_file": {"type": "string"},
                "_attachment": {"type": "string"},
                "validate": {"type": "integer"},
                "dict": {"type": "boolean"},
                "name": {"type": "string"},
            },
            "required": ["_file", "_attachment", "validate", "dict", "name"],
        }
        Model = transform(schema)

        instance = Model.model_validate(
            {
                "_file": "a.txt",
                "_attachment": "b.pdf",
                "validate": 1,
                "dict": True,
                "name": "test",
            }
        )
        dumped = instance.model_dump()
        assert dumped["_file"] == "a.txt"
        assert dumped["_attachment"] == "b.pdf"
        assert dumped["validate"] == 1
        assert dumped["dict"] is True
        assert dumped["name"] == "test"


# ---------------------------------------------------------------------------
# Boolean property schemas
# ---------------------------------------------------------------------------


class TestBooleanPropertySchema:
    def test_boolean_property_in_object(self):
        """A property defined as a boolean schema (true) should fall back to Any."""
        schema = {
            "type": "object",
            "properties": {
                "_flag": True,
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        Model = transform(schema)

        # _flag is renamed; accepts any value because its schema is `true`
        instance = Model.model_validate({"_flag": 42, "name": "test"})
        dumped = instance.model_dump()
        assert dumped["_flag"] == 42
        assert dumped["name"] == "test"

    def test_boolean_false_property_in_object(self):
        """A property defined as boolean schema (false) should also fall back to Any."""
        schema = {
            "type": "object",
            "properties": {
                "schema": False,
                "normal": {"type": "string"},
            },
            "required": ["normal"],
        }
        Model = transform(schema)

        instance = Model.model_validate({"schema": "anything", "normal": "ok"})
        dumped = instance.model_dump()
        assert dumped["schema"] == "anything"
        assert dumped["normal"] == "ok"


class TestValidateByAliasOnly:
    def test_reject_internal_field_name(self):
        schema = {
            "type": "object",
            "properties": {"_hidden": {"type": "string"}},
            "required": ["_hidden"],
        }
        Model = transform(schema)

        # Accept by alias (original JSON property name)
        instance = Model.model_validate({"_hidden": "val"})
        assert instance.model_dump()["_hidden"] == "val"

        # Reject by internal field name — users should not need to know internals
        with pytest.raises(ValidationError):
            Model.model_validate({"hidden": "val2"})
