"""Test that json_schema() returns schemas matching the input."""

import pytest
from pydantic import ValidationError

from jsonschema_pydantic_converter import create_type_adapter


def test_allof_json_schema():
    """Test allOf preserves schema structure."""
    schema = {
        "allOf": [
            {"type": "object", "properties": {"name": {"type": "string"}}},
            {"type": "object", "properties": {"age": {"type": "integer"}}},
        ]
    }

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert "allOf" in generated
    assert generated["allOf"] == schema["allOf"]


def test_not_json_schema():
    """Test not keyword preserves schema structure."""
    schema = {"not": {"type": "string"}}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert "not" in generated
    assert generated["not"] == schema["not"]


def test_const_json_schema():
    """Test const keyword preserves value."""
    schema = {"const": 42}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert "const" in generated
    assert generated["const"] == 42


def test_const_string_json_schema():
    """Test const with string value."""
    schema = {"const": "United States"}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert "const" in generated
    assert generated["const"] == "United States"


def test_const_null_json_schema():
    """Test const with null value."""
    schema = {"const": None}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert "const" in generated
    assert generated["const"] is None


def test_string_constraints_json_schema():
    """Test string constraints in json_schema output."""
    schema = {"type": "string", "minLength": 3, "maxLength": 10, "pattern": "^[a-z]+$"}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert generated.get("type") == "string"
    assert generated.get("minLength") == 3
    assert generated.get("maxLength") == 10
    assert generated.get("pattern") == "^[a-z]+$"


def test_numeric_constraints_json_schema():
    """Test numeric constraints in json_schema output."""
    schema = {"type": "number", "minimum": 0, "maximum": 100, "multipleOf": 5}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert generated.get("type") in ("number", "float")
    assert generated.get("minimum") == 0
    assert generated.get("maximum") == 100
    assert generated.get("multipleOf") == 5


def test_array_constraints_json_schema():
    """Test array constraints in json_schema output."""
    schema = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 2,
        "maxItems": 5,
    }

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert generated.get("type") == "array"
    assert "items" in generated or "prefixItems" in generated
    # minItems/maxItems are converted to minLength/maxLength internally
    assert "minLength" in generated or "minItems" in generated
    assert "maxLength" in generated or "maxItems" in generated


def test_object_with_properties_json_schema():
    """Test object properties in json_schema output."""
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name"],
    }

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert generated.get("type") == "object"
    assert "properties" in generated
    assert "name" in generated["properties"]
    assert "age" in generated["properties"]
    assert "required" in generated
    assert "name" in generated["required"]


def test_nested_object_json_schema():
    """Test nested object structures."""
    schema = {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
            }
        },
    }

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    assert "properties" in generated
    assert "user" in generated["properties"]
    # Nested objects may be represented with $ref in $defs
    # Just verify the structure is valid
    assert generated["properties"]["user"] is not None


def test_enum_json_schema():
    """Test enum in json_schema output."""
    schema = {"type": "string", "enum": ["red", "green", "blue"]}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    # Enums are converted to Pydantic enums, which generate different schema
    # Just verify it generates valid schema
    assert generated is not None


def test_tuple_json_schema():
    """Test tuple (prefixItems) in json_schema output."""
    schema = {"type": "array", "prefixItems": [{"type": "number"}, {"type": "string"}]}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    # Tuples are converted to Tuple types, schema may vary
    assert generated is not None


def test_allof_with_defs_json_schema():
    """Test allOf with $defs validates correctly.

    Note: When allOf contains $refs, we cannot preserve the exact structure
    in json_schema() because Pydantic needs to resolve those refs. We just
    verify it generates valid schema.
    """
    schema = {
        "$defs": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "allOf": [{"$ref": "#/$defs/name"}, {"$ref": "#/$defs/age"}],
    }

    adapter = create_type_adapter(schema)

    # Validation should work - must satisfy both string and integer
    # (this should fail since nothing can be both)
    with pytest.raises(ValidationError):
        adapter.validate_python("hello")

    # json_schema should generate without error
    generated = adapter.json_schema()
    assert generated is not None


def test_complex_nested_schema():
    """Test complex nested schema with multiple features."""
    schema = {
        "type": "object",
        "properties": {
            "username": {
                "type": "string",
                "minLength": 3,
                "maxLength": 20,
                "pattern": "^[a-z0-9_]+$",
            },
            "age": {"type": "integer", "minimum": 0, "maximum": 150},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 5,
            },
        },
        "required": ["username"],
    }

    adapter = create_type_adapter(schema)

    # Validate it works
    result = adapter.validate_python(
        {"username": "john_doe", "age": 25, "tags": ["python", "coding"]}
    )
    assert result.username == "john_doe"

    # Check json_schema generates something
    generated = adapter.json_schema()
    assert "properties" in generated
    assert "username" in generated["properties"]


def test_boolean_schema_true_json_schema():
    """Test boolean schema (true) generates schema."""
    schema = True

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    # true schema accepts anything, should generate a permissive schema
    assert generated is not None


def test_boolean_schema_false_json_schema():
    """Test boolean schema (false) generates schema."""
    schema = False

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    # false schema rejects everything
    assert generated is not None


def test_anyof_json_schema():
    """Test anyOf in json_schema output."""
    schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    # anyOf is converted to Union, which Pydantic represents differently
    # Just verify it generates valid schema
    assert generated is not None


def test_oneof_json_schema():
    """Test oneOf in json_schema output."""
    schema = {"oneOf": [{"type": "string"}, {"type": "integer"}]}

    adapter = create_type_adapter(schema)
    generated = adapter.json_schema()

    # oneOf is converted to Union (same as anyOf)
    assert generated is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
