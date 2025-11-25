from enum import Enum
from typing import List, Optional

import pytest
from pydantic import BaseModel, Field, ValidationError

from jsonschema_pydantic_converter import create_type_adapter


def test_dynamic_schema():
    # Arrange
    class InnerSchema(BaseModel):
        """Inner schema description including a self-reference."""

        self_reference: Optional["InnerSchema"] = None

    class CustomEnum(str, Enum):
        KEY_1 = "VALUE_1"
        KEY_2 = "VALUE_2"

    class Schema(BaseModel):
        """Schema description."""

        string: str = Field(
            default="", title="String Title", description="String Description"
        )
        optional_string: Optional[str] = Field(
            default=None,
            title="Optional String Title",
            description="Optional String Description",
        )
        list_str: List[str] = Field(
            default=[], title="List String", description="List String Description"
        )

        integer: int = Field(
            default=0, title="Integer Title", description="Integer Description"
        )
        optional_integer: Optional[int] = Field(
            default=None,
            title="Option Integer Title",
            description="Option Integer Description",
        )
        list_integer: List[int] = Field(
            default=[],
            title="List Integer Title",
            description="List Integer Description",
        )

        floating: float = Field(
            default=0.0, title="Floating Title", description="Floating Description"
        )
        optional_floating: Optional[float] = Field(
            default=None,
            title="Option Floating Title",
            description="Option Floating Description",
        )
        list_floating: List[float] = Field(
            default=[],
            title="List Floating Title",
            description="List Floating Description",
        )

        boolean: bool = Field(
            default=False, title="Boolean Title", description="Boolean Description"
        )
        optional_boolean: Optional[bool] = Field(
            default=None,
            title="Option Boolean Title",
            description="Option Boolean Description",
        )
        list_boolean: List[bool] = Field(
            default=[],
            title="List Boolean Title",
            description="List Boolean Description",
        )

        nested_object: InnerSchema = Field(
            default=InnerSchema(self_reference=None),
            title="Nested Object Title",
            description="Nested Object Description",
        )
        optional_nested_object: Optional[InnerSchema] = Field(
            default=None,
            title="Optional Nested Object Title",
            description="Optional Nested Object Description",
        )
        list_nested_object: List[InnerSchema] = Field(
            default=[],
            title="List Nested Object Title",
            description="List Nested Object Description",
        )

        enum: CustomEnum = Field(
            default=CustomEnum.KEY_1,
            title="Enum Title",
            description="Enum Description",
        )

    schema_json = Schema.model_json_schema()

    # Act
    dynamic_schema = create_type_adapter(schema_json)
    dynamic_schema_json = dynamic_schema.json_schema()

    # Assert
    assert dynamic_schema_json == schema_json


def test_primitives_models():
    assert create_type_adapter({}).json_schema() == {}
    assert create_type_adapter({"type": "boolean"}).json_schema() == {"type": "boolean"}
    assert create_type_adapter({"type": "integer"}).json_schema() == {"type": "integer"}
    assert create_type_adapter({"type": "number"}).json_schema() == {"type": "number"}
    assert create_type_adapter({"type": "array"}).json_schema() == {
        "type": "array",
        "items": {},
    }
    assert create_type_adapter({"type": "null"}).json_schema() == {"type": "null"}
    assert create_type_adapter({"type": "object"}).json_schema() == {
        "additionalProperties": True,
        "type": "object",
    }


def test_anyof_union():
    """Test that anyOf creates a Union type that accepts multiple types."""
    # Arrange
    schema = {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
        ]
    }

    # Act
    adapter = create_type_adapter(schema)

    # Assert - should validate both string and integer
    validated_string = adapter.validate_python("hello")
    assert validated_string == "hello"

    validated_int = adapter.validate_python(42)
    assert validated_int == 42


def test_allof_two_objects():
    """Test that allOf validates against all object schemas."""
    # Arrange
    schema = {
        "allOf": [
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name"],
            },
            {
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "active": {"type": "boolean"},
                },
                "required": ["email"],
            },
        ]
    }

    # Act
    adapter = create_type_adapter(schema)

    # Assert - should validate object with all properties from both schemas
    validated = adapter.validate_python(
        {"name": "Alice", "age": 30, "email": "alice@example.com", "active": True}
    )
    # allOf validates all schemas and returns the validated value
    assert validated["name"] == "Alice"
    assert validated["age"] == 30
    assert validated["email"] == "alice@example.com"
    assert validated["active"] is True


def test_allof_mixed_types():
    """Test that allOf with mixed non-object types fails appropriately."""
    # Arrange
    schema = {"allOf": [{"type": "string"}, {"type": "integer"}]}

    # Act & Assert - should raise an error during validation
    # because you can't satisfy both string and integer types
    adapter = create_type_adapter(schema)
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python("test")


def test_allof_integer_and_number():
    """Test allOf with integer and number (numeric types)."""
    # Arrange
    schema = {"allOf": [{"type": "integer"}, {"type": "number"}]}

    # Act
    adapter = create_type_adapter(schema)
    # Validate that both integer (which is also a number) passes
    validated = adapter.validate_python(42)
    # allOf validates all schemas and returns the value
    assert validated == 42


def test_allof_with_ref():
    """Test that allOf works correctly with $ref references."""
    # Arrange
    schema = {
        "$defs": {
            "Address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "zipCode": {"type": "string"},
                },
                "required": ["city"],
            },
            "ContactInfo": {
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                },
                "required": ["email"],
            },
        },
        "allOf": [
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "address": {"$ref": "#/$defs/Address"},
                },
                "required": ["name"],
            },
            {"$ref": "#/$defs/ContactInfo"},
        ],
    }

    # Act
    adapter = create_type_adapter(schema)

    # Assert - should validate object with all properties including refs
    validated = adapter.validate_python(
        {
            "name": "Bob",
            "age": 25,
            "address": {"city": "Seattle", "street": "456 Oak Ave", "zipCode": "98101"},
            "email": "bob@example.com",
            "phone": "555-1234",
        }
    )

    # allOf validates all schemas and returns the validated value
    assert validated["name"] == "Bob"
    assert validated["age"] == 25
    assert validated["address"]["city"] == "Seattle"
    assert validated["address"]["street"] == "456 Oak Ave"
    assert validated["email"] == "bob@example.com"
    assert validated["phone"] == "555-1234"


def test_allof_json_schema_output():
    """Test that allOf preserves the original schema structure in json_schema()."""
    # Arrange
    schema = {
        "allOf": [
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            {
                "type": "object",
                "properties": {"email": {"type": "string"}},
                "required": ["email"],
            },
        ]
    }

    # Act
    adapter = create_type_adapter(schema)
    generated_schema = adapter.json_schema()

    # Assert - generated schema should match original allOf structure
    assert generated_schema == schema


def test_allof_empty():
    """Test that empty allOf accepts any value."""
    adapter = create_type_adapter({"allOf": []})

    # Should accept anything
    assert adapter.validate_python({"anything": "goes"}) == {"anything": "goes"}
    assert adapter.validate_python("string") == "string"
    assert adapter.validate_python(42) == 42


def test_allof_single_schema():
    """Test that allOf with single schema works correctly."""
    schema = {"allOf": [{"type": "string"}]}
    adapter = create_type_adapter(schema)

    # Should validate as string
    assert adapter.validate_python("hello") == "hello"

    # Should reject non-string
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python(42)


def test_allof_missing_required_field():
    """Test that allOf enforces required fields from all schemas."""
    schema = {
        "allOf": [
            {
                "type": "object",
                "properties": {"a": {"type": "string"}},
                "required": ["a"],
            },
            {
                "type": "object",
                "properties": {"b": {"type": "string"}},
                "required": ["b"],
            },
        ]
    }
    adapter = create_type_adapter(schema)

    # Should accept when all required fields present
    result = adapter.validate_python({"a": "value_a", "b": "value_b"})
    assert result["a"] == "value_a"
    assert result["b"] == "value_b"

    # Should reject when missing required field
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python({"a": "value"})  # Missing 'b'


def test_allof_nested():
    """Test that nested allOf works correctly."""
    schema = {"allOf": [{"type": "string"}, {"allOf": [{"type": "string"}]}]}
    adapter = create_type_adapter(schema)

    # Should validate as string
    assert adapter.validate_python("hello") == "hello"


def test_allof_conflicting_primitives():
    """Test that allOf with non-overlapping primitives fails."""
    schema = {"allOf": [{"type": "string"}, {"type": "integer"}]}
    adapter = create_type_adapter(schema)

    # Should reject both string and integer since they can't satisfy both
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python("test")

    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python(42)


def test_allof_conflicting_property_types():
    """Test that allOf with conflicting property types fails validation."""
    schema = {
        "allOf": [
            {"type": "object", "properties": {"x": {"type": "string"}}},
            {"type": "object", "properties": {"x": {"type": "integer"}}},
        ]
    }
    adapter = create_type_adapter(schema)

    # Should reject string since x must also be integer
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python({"x": "string"})

    # Should reject integer since x must also be string
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python({"x": 42})


def test_allof_arrays():
    """Test that allOf works with array types."""
    schema = {
        "allOf": [
            {"type": "array", "items": {"type": "integer"}},
            {"type": "array"},
        ]
    }
    adapter = create_type_adapter(schema)

    # Should accept array of integers
    result = adapter.validate_python([1, 2, 3])
    assert result == [1, 2, 3]

    # Should reject array of strings
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python(["a", "b"])


def test_allof_with_empty_schema():
    """Test that allOf with empty schema (which accepts anything) works."""
    schema = {"allOf": [{"type": "string"}, {}]}  # {} accepts anything
    adapter = create_type_adapter(schema)

    # Should accept string (satisfies both schemas)
    assert adapter.validate_python("hello") == "hello"

    # Should reject non-string (fails first schema)
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python(42)


def test_oneof_basic():
    """Test oneOf with different types - treated as Union."""
    schema = {"oneOf": [{"type": "string"}, {"type": "integer"}]}

    adapter = create_type_adapter(schema)

    # Should accept string
    assert adapter.validate_python("hello") == "hello"

    # Should accept integer
    assert adapter.validate_python(42) == 42

    # Note: oneOf exclusivity constraint is not enforced, treated as Union


def test_not_keyword():
    """Test not keyword - validates that value does NOT match schema."""
    schema = {"not": {"type": "string"}}

    adapter = create_type_adapter(schema)

    # Should accept non-string values
    assert adapter.validate_python(42) == 42
    assert adapter.validate_python([1, 2, 3]) == [1, 2, 3]
    assert adapter.validate_python({"key": "value"}) == {"key": "value"}

    # Should reject string values (matches the "not" schema)
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python("hello")


def test_not_with_object():
    """Test not keyword with object schema."""
    schema = {
        "not": {
            "type": "object",
            "properties": {"foo": {"type": "string"}},
            "required": ["foo"],
        }
    }

    adapter = create_type_adapter(schema)

    # Should accept non-objects
    assert adapter.validate_python(42) == 42
    assert adapter.validate_python("string") == "string"

    # Should accept objects without required 'foo' field
    assert adapter.validate_python({"bar": "value"}) == {"bar": "value"}

    # Should reject objects with required 'foo' field
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python({"foo": "value"})


def test_const_keyword():
    """Test const keyword - validates exact value match."""
    schema = {"type": "object", "properties": {"country": {"const": "United States"}}}

    adapter = create_type_adapter(schema)

    # Should accept exact match
    result = adapter.validate_python({"country": "United States"})
    assert result.country == "United States"

    # Should reject different value
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python({"country": "Canada"})


def test_const_with_number():
    """Test const keyword with numeric value."""
    schema = {"const": 42}

    adapter = create_type_adapter(schema)

    # Should accept exact match
    assert adapter.validate_python(42) == 42

    # Should reject different value
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python(43)

    # Should reject different type
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python("42")


def test_const_with_null():
    """Test const keyword with null value."""
    schema = {"const": None}

    adapter = create_type_adapter(schema)

    # Should accept None
    assert adapter.validate_python(None) is None

    # Should reject non-None values
    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python(0)

    with pytest.raises((ValidationError, ValueError)):
        adapter.validate_python("")


def test_if_then_else():
    """Test if-then-else conditionals - schema accepted but constraints not enforced."""
    schema = {
        "type": "object",
        "properties": {
            "street_address": {"type": "string"},
            "country": {"type": "string"},
        },
        "if": {"properties": {"country": {"const": "United States"}}},
        "then": {"properties": {"postal_code": {"type": "string"}}},
        "else": {"properties": {"postal_code": {"type": "string"}}},
    }

    adapter = create_type_adapter(schema)

    # Should accept valid data
    result = adapter.validate_python(
        {
            "street_address": "123 Main St",
            "country": "United States",
            "postal_code": "12345",
        }
    )
    assert result.country == "United States"


def test_nested_definitions():
    """Test that nested $defs are properly resolved."""
    schema = {
        "type": "object",
        "properties": {"address": {"$ref": "#/$defs/Address"}},
        "$defs": {
            "Address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "country": {"$ref": "#/$defs/Address/$defs/Country"},
                },
                "$defs": {
                    "Country": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "code": {"type": "string"},
                        },
                        "required": ["name"],
                    }
                },
            }
        },
    }

    adapter = create_type_adapter(schema)

    # Valid data
    data = {
        "address": {"street": "123 Main St", "country": {"name": "USA", "code": "US"}}
    }

    result = adapter.validate_python(data)
    dumped = adapter.dump_python(result)

    assert dumped["address"]["street"] == "123 Main St"
    assert dumped["address"]["country"]["name"] == "USA"
    assert dumped["address"]["country"]["code"] == "US"

    # Missing required field should fail
    invalid_data = {
        "address": {
            "street": "123 Main St",
            "country": {
                "code": "US"  # missing required 'name'
            },
        }
    }

    with pytest.raises(ValidationError):
        adapter.validate_python(invalid_data)


def test_deeply_nested_definitions():
    """Test definitions nested multiple levels deep."""
    schema = {
        "type": "object",
        "properties": {"org": {"$ref": "#/$defs/Organization"}},
        "$defs": {
            "Organization": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"$ref": "#/$defs/Organization/$defs/Address"},
                },
                "$defs": {
                    "Address": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"},
                            "location": {
                                "$ref": "#/$defs/Organization/$defs/Address/$defs/Coordinates"
                            },
                        },
                        "$defs": {
                            "Coordinates": {
                                "type": "object",
                                "properties": {
                                    "lat": {"type": "number"},
                                    "lon": {"type": "number"},
                                },
                            }
                        },
                    }
                },
            }
        },
    }

    adapter = create_type_adapter(schema)

    data = {
        "org": {
            "name": "Acme Corp",
            "address": {
                "city": "San Francisco",
                "location": {"lat": 37.7749, "lon": -122.4194},
            },
        }
    }

    result = adapter.validate_python(data)
    dumped = adapter.dump_python(result)

    assert dumped["org"]["name"] == "Acme Corp"
    assert dumped["org"]["address"]["city"] == "San Francisco"
    assert dumped["org"]["address"]["location"]["lat"] == 37.7749
    assert dumped["org"]["address"]["location"]["lon"] == -122.4194
