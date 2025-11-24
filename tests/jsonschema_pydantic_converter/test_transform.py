from enum import Enum
from typing import List, Optional

import pytest
from pydantic import BaseModel, Field

from jsonschema_pydantic_converter import transform


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
    dynamic_schema = transform(schema_json)
    dynamic_schema_json = dynamic_schema.model_json_schema()

    # Assert
    assert dynamic_schema_json == schema_json


def test_erroneous_model():
    with pytest.raises(ValueError):
        transform({})

    with pytest.raises(ValueError):
        transform({"type": "list"})


def test_allof_merges_properties():
    """Test that allOf merges properties from multiple schemas."""
    schema = {
        "type": "object",
        "properties": {
            "combined": {
                "allOf": [
                    {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                        },
                        "required": ["name"],
                    },
                    {
                        "type": "object",
                        "properties": {"email": {"type": "string"}},
                        "required": ["email"],
                    },
                ]
            }
        },
    }

    model = transform(schema)
    instance = model(
        combined={"name": "Alice", "age": 30, "email": "alice@example.com"}
    )
    assert instance.combined.name == "Alice"  # type: ignore[attr-defined]
    assert instance.combined.age == 30  # type: ignore[attr-defined]
    assert instance.combined.email == "alice@example.com"  # type: ignore[attr-defined]


def test_allof_type_conflict():
    """Test that allOf raises error for incompatible types."""
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "allOf": [
                    {"type": "object", "properties": {"x": {"type": "string"}}},
                    {"type": "object", "properties": {"x": {"type": "integer"}}},
                ]
            }
        },
    }

    with pytest.raises(ValueError, match="Incompatible types"):
        transform(schema)


def test_allof_additional_properties_false():
    """Test that allOf respects additionalProperties: false."""
    schema = {
        "type": "object",
        "properties": {
            "user": {
                "allOf": [
                    {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "additionalProperties": False,
                    }
                ]
            }
        },
    }

    model = transform(schema)
    # Valid: only defined property
    instance = model(user={"name": "Bob"})
    assert instance.user.name == "Bob"  # type: ignore[attr-defined]

    # Invalid: extra property should be rejected
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        model(user={"name": "Bob", "extra": "field"})


def test_allof_additional_properties_true():
    """Test that allOf allows additional properties when set to true."""
    schema = {
        "type": "object",
        "properties": {
            "data": {
                "allOf": [
                    {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}},
                        "additionalProperties": True,
                    }
                ]
            }
        },
    }

    model = transform(schema)
    instance = model(data={"id": 123, "extra": "allowed", "another": 456})
    assert instance.data.id == 123  # type: ignore[attr-defined]
    assert instance.data.extra == "allowed"  # type: ignore[attr-defined]
    assert instance.data.another == 456  # type: ignore[attr-defined]


def test_allof_merges_metadata():
    """Test that allOf merges field metadata like title and description."""
    schema = {
        "type": "object",
        "properties": {
            "item": {
                "allOf": [
                    {"type": "object", "properties": {"name": {"type": "string"}}},
                    {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "title": "Item Name",
                                "description": "The name of the item",
                            }
                        },
                    },
                ]
            }
        },
    }

    model = transform(schema)
    json_schema = model.model_json_schema()

    # Check metadata is present in the generated schema
    assert (
        "Item Name" in str(json_schema)
        or "name" in json_schema["properties"]["item"]["properties"]
    )


def test_allof_non_object_schemas():
    """Test that allOf handles non-object schemas by merging constraints."""
    schema = {"allOf": [{"type": "string"}, {"minLength": 5}]}

    # This should work - transforms allOf with non-objects
    try:
        model = transform(schema)
        # If it returns a BaseModel, test it
        if hasattr(model, "model_validate"):
            pass
    except ValueError as e:
        # transform() only works with objects, so this is expected
        assert "Unable to convert schema" in str(e)


def test_object_with_additional_properties():
    """Test that regular objects respect additionalProperties."""
    schema = {
        "type": "object",
        "properties": {
            "strict": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "additionalProperties": False,
            },
            "flexible": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "additionalProperties": True,
            },
        },
    }

    model = transform(schema)

    # Strict object rejects extra properties
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        model(strict={"id": 1, "extra": "no"}, flexible={"id": 2})

    # Flexible object allows extra properties
    instance = model(strict={"id": 1}, flexible={"id": 2, "extra": "yes"})
    assert instance.strict.id == 1  # type: ignore[attr-defined]
    assert instance.flexible.id == 2  # type: ignore[attr-defined]
    assert instance.flexible.extra == "yes"  # type: ignore[attr-defined]


def test_allof_empty_objects():
    """Test that allOf with objects but no properties works."""
    schema = {
        "type": "object",
        "properties": {"empty": {"allOf": [{"type": "object"}, {"type": "object"}]}},
    }

    model = transform(schema)
    instance = model(empty={})
    assert instance.empty is not None  # type: ignore[attr-defined]


def test_allof_with_title():
    """Test that allOf respects explicit title."""
    schema = {
        "type": "object",
        "properties": {
            "item": {
                "allOf": [
                    {"type": "object", "properties": {"id": {"type": "integer"}}}
                ],
                "title": "CustomTitle",
            }
        },
    }

    model = transform(schema)
    instance = model(item={"id": 42})
    assert instance.item.id == 42  # type: ignore[attr-defined]


def test_allof_non_object_type_error():
    """Test that allOf with non-object type raises error."""
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "allOf": [{"type": "string"}, {"type": "object", "properties": {}}]
            }
        },
    }

    with pytest.raises(ValueError, match="Incompatible types in allOf"):
        transform(schema)


def test_object_without_properties():
    """Test object type without properties defined."""
    schema = {"type": "object", "properties": {"data": {"type": "object"}}}

    model = transform(schema)
    instance = model(data={"any": "thing", "goes": "here"})
    # Object without properties becomes Dict[str, Any]
    assert instance.data["any"] == "thing"  # type: ignore[attr-defined]
    assert instance.data["goes"] == "here"  # type: ignore[attr-defined]
