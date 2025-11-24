"""Test Pydantic-native constraint support."""

import pytest
from pydantic import ValidationError

from jsonschema_pydantic_converter import create_type_adapter


def test_string_minlength():
    """Test minLength constraint on strings."""
    schema = {"type": "string", "minLength": 3}

    adapter = create_type_adapter(schema)

    # Should accept strings >= 3 characters
    assert adapter.validate_python("abc") == "abc"
    assert adapter.validate_python("hello") == "hello"

    # Should reject strings < 3 characters
    with pytest.raises(ValidationError):
        adapter.validate_python("ab")


def test_string_maxlength():
    """Test maxLength constraint on strings."""
    schema = {"type": "string", "maxLength": 5}

    adapter = create_type_adapter(schema)

    # Should accept strings <= 5 characters
    assert adapter.validate_python("hello") == "hello"
    assert adapter.validate_python("hi") == "hi"

    # Should reject strings > 5 characters
    with pytest.raises(ValidationError):
        adapter.validate_python("toolong")


def test_string_pattern():
    """Test pattern constraint on strings."""
    schema = {"type": "string", "pattern": "^[A-Z][a-z]+$"}

    adapter = create_type_adapter(schema)

    # Should accept matching pattern
    assert adapter.validate_python("Hello") == "Hello"
    assert adapter.validate_python("World") == "World"

    # Should reject non-matching pattern
    with pytest.raises(ValidationError):
        adapter.validate_python("hello")  # lowercase first letter

    with pytest.raises(ValidationError):
        adapter.validate_python("HELLO")  # all uppercase


def test_string_all_constraints():
    """Test multiple string constraints together."""
    schema = {
        "type": "string",
        "minLength": 3,
        "maxLength": 10,
        "pattern": "^[A-Za-z]+$",
    }

    adapter = create_type_adapter(schema)

    # Should accept valid strings
    assert adapter.validate_python("Hello") == "Hello"

    # Too short
    with pytest.raises(ValidationError):
        adapter.validate_python("Hi")

    # Too long
    with pytest.raises(ValidationError):
        adapter.validate_python("VeryLongString")

    # Invalid pattern (contains numbers)
    with pytest.raises(ValidationError):
        adapter.validate_python("Hello123")


def test_integer_minimum():
    """Test minimum constraint on integers."""
    schema = {"type": "integer", "minimum": 0}

    adapter = create_type_adapter(schema)

    # Should accept >= 0
    assert adapter.validate_python(0) == 0
    assert adapter.validate_python(5) == 5

    # Should reject < 0
    with pytest.raises(ValidationError):
        adapter.validate_python(-1)


def test_integer_maximum():
    """Test maximum constraint on integers."""
    schema = {"type": "integer", "maximum": 100}

    adapter = create_type_adapter(schema)

    # Should accept <= 100
    assert adapter.validate_python(100) == 100
    assert adapter.validate_python(50) == 50

    # Should reject > 100
    with pytest.raises(ValidationError):
        adapter.validate_python(101)


def test_integer_exclusive_minimum():
    """Test exclusiveMinimum constraint."""
    schema = {"type": "integer", "exclusiveMinimum": 0}

    adapter = create_type_adapter(schema)

    # Should accept > 0
    assert adapter.validate_python(1) == 1
    assert adapter.validate_python(5) == 5

    # Should reject <= 0
    with pytest.raises(ValidationError):
        adapter.validate_python(0)

    with pytest.raises(ValidationError):
        adapter.validate_python(-1)


def test_integer_exclusive_maximum():
    """Test exclusiveMaximum constraint."""
    schema = {"type": "integer", "exclusiveMaximum": 100}

    adapter = create_type_adapter(schema)

    # Should accept < 100
    assert adapter.validate_python(99) == 99

    # Should reject >= 100
    with pytest.raises(ValidationError):
        adapter.validate_python(100)


def test_number_multiple_of():
    """Test multipleOf constraint."""
    schema = {"type": "number", "multipleOf": 5}

    adapter = create_type_adapter(schema)

    # Should accept multiples of 5
    assert adapter.validate_python(0) == 0
    assert adapter.validate_python(5) == 5
    assert adapter.validate_python(10) == 10
    assert adapter.validate_python(-5) == -5

    # Should reject non-multiples
    with pytest.raises(ValidationError):
        adapter.validate_python(3)

    with pytest.raises(ValidationError):
        adapter.validate_python(7)


def test_number_all_constraints():
    """Test multiple numeric constraints together."""
    schema = {"type": "number", "minimum": 0, "maximum": 100, "multipleOf": 5}

    adapter = create_type_adapter(schema)

    # Should accept valid values
    assert adapter.validate_python(0) == 0
    assert adapter.validate_python(50) == 50
    assert adapter.validate_python(100) == 100

    # Too small
    with pytest.raises(ValidationError):
        adapter.validate_python(-5)

    # Too large
    with pytest.raises(ValidationError):
        adapter.validate_python(105)

    # Not a multiple
    with pytest.raises(ValidationError):
        adapter.validate_python(7)


def test_array_minitems():
    """Test minItems constraint on arrays."""
    schema = {"type": "array", "items": {"type": "string"}, "minItems": 2}

    adapter = create_type_adapter(schema)

    # Should accept arrays with >= 2 items
    assert adapter.validate_python(["a", "b"]) == ["a", "b"]
    assert adapter.validate_python(["a", "b", "c"]) == ["a", "b", "c"]

    # Should reject arrays with < 2 items
    with pytest.raises(ValidationError):
        adapter.validate_python(["a"])

    with pytest.raises(ValidationError):
        adapter.validate_python([])


def test_array_maxitems():
    """Test maxItems constraint on arrays."""
    schema = {"type": "array", "items": {"type": "integer"}, "maxItems": 3}

    adapter = create_type_adapter(schema)

    # Should accept arrays with <= 3 items
    assert adapter.validate_python([1, 2, 3]) == [1, 2, 3]
    assert adapter.validate_python([1]) == [1]

    # Should reject arrays with > 3 items
    with pytest.raises(ValidationError):
        adapter.validate_python([1, 2, 3, 4])


def test_constraints_in_object_properties():
    """Test that constraints work within object properties."""
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

    # Valid data
    result = adapter.validate_python(
        {"username": "john_doe", "age": 25, "tags": ["python", "coding"]}
    )
    assert result.username == "john_doe"
    assert result.age == 25

    # Invalid username - too short
    with pytest.raises(ValidationError):
        adapter.validate_python({"username": "ab"})

    # Invalid username - invalid pattern
    with pytest.raises(ValidationError):
        adapter.validate_python({"username": "John-Doe"})

    # Invalid age - too large
    with pytest.raises(ValidationError):
        adapter.validate_python({"username": "john_doe", "age": 200})

    # Invalid tags - too many
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"username": "john_doe", "tags": ["a", "b", "c", "d", "e", "f"]}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
