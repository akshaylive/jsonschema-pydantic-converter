"""Test advanced JSON Schema features."""

import pytest
from pydantic import ValidationError

from jsonschema_pydantic_converter import create_type_adapter


def test_boolean_schema_true():
    """Test boolean schema: true accepts everything."""
    schema = True

    adapter = create_type_adapter(schema)

    # Should accept any value
    assert adapter.validate_python("string") == "string"
    assert adapter.validate_python(42) == 42
    assert adapter.validate_python([1, 2, 3]) == [1, 2, 3]
    assert adapter.validate_python({"key": "value"}) == {"key": "value"}
    assert adapter.validate_python(None) is None


def test_boolean_schema_false():
    """Test boolean schema: false rejects everything."""
    schema = False

    adapter = create_type_adapter(schema)

    # Should reject all values
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python("string")

    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python(42)

    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python([])


def test_tuple_validation_prefix_items():
    """Test prefixItems for tuple validation (draft 2020-12)."""
    schema = {
        "type": "array",
        "prefixItems": [{"type": "number"}, {"type": "string"}, {"type": "boolean"}],
    }

    adapter = create_type_adapter(schema)

    # Should accept correct tuple
    result = adapter.validate_python([1.5, "hello", True])
    assert result == (1.5, "hello", True)

    # Should reject wrong types
    with pytest.raises(ValidationError):
        adapter.validate_python(["string", 123, True])

    # Should reject wrong number of items
    with pytest.raises(ValidationError):
        adapter.validate_python([1.5, "hello"])  # Missing boolean


def test_tuple_validation_items_array():
    """Test old-style tuple validation with items as array."""
    schema = {"type": "array", "items": [{"type": "number"}, {"type": "string"}]}

    adapter = create_type_adapter(schema)

    # Should accept correct tuple
    result = adapter.validate_python([1.5, "hello"])
    assert result == (1.5, "hello")

    # Should reject wrong types
    with pytest.raises(ValidationError):
        adapter.validate_python(["string", 123])


def test_tuple_with_complex_types():
    """Test tuple validation with complex types."""
    schema = {
        "type": "array",
        "prefixItems": [
            {"type": "string", "minLength": 3},
            {"type": "integer", "minimum": 0},
            {
                "type": "object",
                "properties": {"active": {"type": "boolean"}},
                "required": ["active"],
            },
        ],
    }

    adapter = create_type_adapter(schema)

    # Valid tuple
    result = adapter.validate_python(["hello", 42, {"active": True}])
    assert result[0] == "hello"
    assert result[1] == 42
    assert result[2].active is True

    # String too short
    with pytest.raises(ValidationError):
        adapter.validate_python(["hi", 42, {"active": True}])

    # Negative integer
    with pytest.raises(ValidationError):
        adapter.validate_python(["hello", -1, {"active": True}])


def test_tuple_empty():
    """Test empty tuple validation."""
    schema = {"type": "array", "prefixItems": []}

    adapter = create_type_adapter(schema)

    # Empty prefix items creates empty tuple type, but validates to empty list
    result = adapter.validate_python([])
    assert len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
