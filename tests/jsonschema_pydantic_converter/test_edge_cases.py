"""Test edge cases and missing coverage scenarios."""

import pytest
from pydantic import ValidationError

from jsonschema_pydantic_converter import create_type_adapter


def test_not_with_non_validation_error():
    """Test not keyword when the negated schema raises a non-ValidationError."""
    schema = {"not": {"type": "string"}}

    adapter = create_type_adapter(schema)

    # Should accept non-strings
    assert adapter.validate_python(42) == 42
    assert adapter.validate_python([1, 2, 3]) == [1, 2, 3]
    assert adapter.validate_python({"key": "value"}) == {"key": "value"}

    # Should reject strings
    with pytest.raises(ValueError):
        adapter.validate_python("hello")


def test_standalone_enum_with_strings():
    """Test enum without type keyword with string values."""
    schema = {"enum": ["red", "green", "blue"]}

    adapter = create_type_adapter(schema)

    # Valid enum values
    result = adapter.validate_python("red")
    assert result in ["red", "green", "blue"]

    # Invalid value
    with pytest.raises(ValidationError):
        adapter.validate_python("yellow")


def test_standalone_enum_with_integers():
    """Test enum without type keyword with integer values."""
    schema = {"enum": [1, 2, 3]}

    adapter = create_type_adapter(schema)

    # Valid enum values
    result = adapter.validate_python(1)
    assert result in [1, 2, 3]

    # Invalid value
    with pytest.raises(ValidationError):
        adapter.validate_python(4)


def test_standalone_enum_with_floats():
    """Test enum without type keyword with float values."""
    schema = {"enum": [1.5, 2.5, 3.5]}

    adapter = create_type_adapter(schema)

    # Valid enum values
    result = adapter.validate_python(1.5)
    assert result in [1.5, 2.5, 3.5]


def test_standalone_enum_with_booleans():
    """Test enum without type keyword with boolean values.

    Note: Booleans can't be Enum bases, so we use Literal instead.
    """
    schema = {"enum": [True, False]}

    adapter = create_type_adapter(schema)

    # Valid enum values (Literal type)
    result = adapter.validate_python(True)
    assert result is True

    result2 = adapter.validate_python(False)
    assert result2 is False


def test_standalone_enum_with_mixed_types():
    """Test enum without type keyword with mixed type values.

    Note: Mixed types can't be Enum bases, so we use Literal instead.
    """
    schema = {"enum": [None, 1, "test"]}

    adapter = create_type_adapter(schema)

    # Valid enum values (Literal type)
    assert adapter.validate_python(None) is None
    assert adapter.validate_python(1) == 1
    assert adapter.validate_python("test") == "test"

    # Invalid value
    with pytest.raises(ValidationError):
        adapter.validate_python("other")


def test_standalone_enum_empty():
    """Test enum without type keyword with empty values.

    Note: Empty enum uses empty Literal which rejects everything.
    """
    adapter = create_type_adapter({"enum": []})

    # Should reject all values since enum is empty
    with pytest.raises(ValidationError):
        adapter.validate_python("anything")

    with pytest.raises(ValidationError):
        adapter.validate_python(None)


def test_if_then_else_with_type():
    """Test if-then-else conditional with a type field."""
    schema = {"if": {"type": "string"}, "then": {"minLength": 5}, "type": "string"}

    adapter = create_type_adapter(schema)

    # Should accept strings (type is used, conditionals not enforced)
    result = adapter.validate_python("hi")
    assert result == "hi"


def test_if_then_else_without_type():
    """Test if-then-else conditional without a type field."""
    schema = {"if": {"type": "string"}, "then": {"minLength": 5}}

    adapter = create_type_adapter(schema)

    # Should accept anything (returns Any)
    assert adapter.validate_python("test") == "test"
    assert adapter.validate_python(42) == 42
    assert adapter.validate_python([1, 2]) == [1, 2]


def test_constraint_only_schema_numeric():
    """Test schema with only numeric constraints (no type field)."""
    schema = {"minimum": 0, "maximum": 100}

    adapter = create_type_adapter(schema)

    # Should infer number type and apply constraints
    result = adapter.validate_python(50)
    assert result == 50

    # Should reject values outside constraints
    with pytest.raises(ValidationError):
        adapter.validate_python(-1)

    with pytest.raises(ValidationError):
        adapter.validate_python(101)


def test_constraint_only_schema_exclusive_numeric():
    """Test schema with exclusive numeric constraints."""
    schema = {"exclusiveMinimum": 0, "exclusiveMaximum": 100}

    adapter = create_type_adapter(schema)

    # Should accept values within range
    result = adapter.validate_python(50)
    assert result == 50

    # Should reject boundary values
    with pytest.raises(ValidationError):
        adapter.validate_python(0)

    with pytest.raises(ValidationError):
        adapter.validate_python(100)


def test_constraint_only_schema_multiple_of():
    """Test schema with only multipleOf constraint."""
    schema = {"multipleOf": 5}

    adapter = create_type_adapter(schema)

    # Should accept multiples
    result = adapter.validate_python(10)
    assert result == 10

    # Should reject non-multiples
    with pytest.raises(ValidationError):
        adapter.validate_python(7)


def test_constraint_only_schema_string():
    """Test schema with only string constraints (no type field)."""
    schema = {"minLength": 3, "maxLength": 10}

    adapter = create_type_adapter(schema)

    # Should infer string type and apply constraints
    result = adapter.validate_python("hello")
    assert result == "hello"

    # Should reject values outside constraints
    with pytest.raises(ValidationError):
        adapter.validate_python("hi")

    with pytest.raises(ValidationError):
        adapter.validate_python("this is too long")


def test_constraint_only_schema_pattern():
    """Test schema with only pattern constraint."""
    schema = {"pattern": "^[a-z]+$"}

    adapter = create_type_adapter(schema)

    # Should infer string type and apply pattern
    result = adapter.validate_python("hello")
    assert result == "hello"

    # Should reject values that don't match pattern
    with pytest.raises(ValidationError):
        adapter.validate_python("Hello123")


def test_constraint_only_schema_array():
    """Test schema with only array constraints (no type field)."""
    schema = {"minItems": 2, "maxItems": 5}

    adapter = create_type_adapter(schema)

    # Should infer array type and apply constraints
    result = adapter.validate_python([1, 2, 3])
    assert result == [1, 2, 3]

    # Should reject values outside constraints
    with pytest.raises(ValidationError):
        adapter.validate_python([1])

    with pytest.raises(ValidationError):
        adapter.validate_python([1, 2, 3, 4, 5, 6])


def test_constraint_only_schema_object_properties():
    """Test schema with object-related keywords but no type."""
    schema = {"properties": {"name": {"type": "string"}}}

    adapter = create_type_adapter(schema)

    # Should infer object type
    result = adapter.validate_python({"name": "Alice"})
    assert result == {"name": "Alice"}


def test_constraint_only_schema_object_required():
    """Test schema with required keyword but no type."""
    schema = {"required": ["name"]}

    adapter = create_type_adapter(schema)

    # Should infer object type (Dict[str, Any])
    result = adapter.validate_python({"name": "Alice", "age": 30})
    assert result == {"name": "Alice", "age": 30}


def test_constraint_only_schema_object_additional_properties():
    """Test schema with additionalProperties keyword but no type."""
    schema = {"additionalProperties": False}

    adapter = create_type_adapter(schema)

    # Should infer object type (Dict[str, Any])
    result = adapter.validate_python({"name": "Alice"})
    assert result == {"name": "Alice"}


def test_empty_schema():
    """Test completely empty schema."""
    adapter = create_type_adapter({})

    # Should accept anything (returns Any)
    assert adapter.validate_python("test") == "test"
    assert adapter.validate_python(42) == 42
    assert adapter.validate_python([1, 2]) == [1, 2]
    assert adapter.validate_python({"key": "value"}) == {"key": "value"}


def test_null_type():
    """Test null type."""
    schema = {"type": "null"}

    adapter = create_type_adapter(schema)

    # Should only accept None
    assert adapter.validate_python(None) is None

    # Should reject non-None values
    with pytest.raises(ValidationError):
        adapter.validate_python("test")

    with pytest.raises(ValidationError):
        adapter.validate_python(0)


def test_array_with_no_items():
    """Test array type without items specification."""
    schema = {"type": "array"}

    adapter = create_type_adapter(schema)

    # Should accept any array
    result = adapter.validate_python([1, "two", 3.0, True, None])
    assert result == [1, "two", 3.0, True, None]


def test_object_without_properties():
    """Test object type without properties specification."""
    schema = {"type": "object"}

    adapter = create_type_adapter(schema)

    # Should accept any object (Dict[str, Any])
    result = adapter.validate_python({"any": "value", "another": 42})
    assert result == {"any": "value", "another": 42}


def test_enum_with_type_string():
    """Test enum with explicit string type."""
    schema = {"type": "string", "enum": ["small", "medium", "large"]}

    adapter = create_type_adapter(schema)

    # Valid enum value
    result = adapter.validate_python("medium")
    assert result == "medium" or result.value == "medium"

    # Invalid enum value
    with pytest.raises(ValidationError):
        adapter.validate_python("extra-large")


def test_enum_with_type_integer():
    """Test enum with explicit integer type."""
    schema = {"type": "integer", "enum": [1, 2, 3]}

    adapter = create_type_adapter(schema)

    # Valid enum value
    result = adapter.validate_python(2)
    assert result == 2 or result.value == 2

    # Invalid enum value
    with pytest.raises(ValidationError):
        adapter.validate_python(4)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
