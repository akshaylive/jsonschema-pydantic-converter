"""Custom validators for JSON Schema constraints."""

from typing import Annotated, Any

from pydantic import BeforeValidator, Field, TypeAdapter


def create_intersection_validator(
    sub_schemas: list[dict[str, Any]],
    convert_type_fn: Any,
    namespace: dict[str, Any],
) -> Any:
    """Create an Intersection type that validates against all sub-schemas.

    Args:
        sub_schemas: List of sub-schemas that must all be satisfied.
        convert_type_fn: Function to convert schema to type.
        namespace: Type namespace for forward references.

    Returns:
        An Annotated type with validation logic.
    """
    converted_types = [convert_type_fn(sub) for sub in sub_schemas]

    def validate_all(value: Any) -> Any:
        """Validate that the value satisfies all sub-schemas."""
        for converted_type in converted_types:
            try:
                adapter = TypeAdapter(converted_type)
                adapter.rebuild(force=True, _types_namespace=namespace)
                adapter.validate_python(value)
            except Exception as e:
                raise ValueError(
                    f"Value does not satisfy all schemas in allOf: {e}"
                ) from e
        return value

    # Check if any sub-schema contains $ref
    has_refs = any("$ref" in sub for sub in sub_schemas)

    if has_refs:
        # Don't override json_schema when $refs are present
        return Annotated[Any, BeforeValidator(validate_all)]
    else:

        def json_schema_extra(schema_dict: dict[str, Any]) -> None:
            """Override the generated schema with the original allOf structure."""
            schema_dict.clear()
            schema_dict["allOf"] = sub_schemas

        return Annotated[
            Any,
            BeforeValidator(validate_all),
            Field(json_schema_extra=json_schema_extra),
        ]


def create_not_validator(
    not_schema: dict[str, Any], convert_type_fn: Any, namespace: dict[str, Any]
) -> Any:
    """Create a type that validates against the negation of a schema.

    Args:
        not_schema: The schema to negate.
        convert_type_fn: Function to convert schema to type.
        namespace: Type namespace for forward references.

    Returns:
        An Annotated type with negation validation logic.
    """
    not_type = convert_type_fn(not_schema)

    def validate_not(value: Any) -> Any:
        """Validate that the value does NOT satisfy the not schema."""
        try:
            adapter = TypeAdapter(not_type)
            adapter.rebuild(force=True, _types_namespace=namespace)
            adapter.validate_python(value)
            # If validation succeeds, the value is invalid for 'not'
            raise ValueError(
                f"Value {value!r} should not match the 'not' schema but it does"
            )
        except Exception as e:
            # If it's our ValueError, re-raise it
            if "should not match the 'not' schema" in str(e):
                raise
            # Any other exception means validation failed, so value is valid for 'not'
            return value

    def json_schema_extra(schema_dict: dict[str, Any]) -> None:
        """Override the generated schema with the original not structure."""
        schema_dict.clear()
        schema_dict["not"] = not_schema

    return Annotated[
        Any,
        BeforeValidator(validate_not),
        Field(json_schema_extra=json_schema_extra),
    ]


def create_const_validator(const_value: Any) -> Any:
    """Create a type that validates against an exact constant value.

    Args:
        const_value: The exact value that must be matched.

    Returns:
        An Annotated type with const validation logic.
    """

    def validate_const(value: Any) -> Any:
        """Validate that the value equals the const value."""
        if value != const_value:
            raise ValueError(f"Value must be exactly {const_value!r}, got {value!r}")
        return value

    def json_schema_extra(schema_dict: dict[str, Any]) -> None:
        """Override the generated schema with the original const structure."""
        schema_dict.clear()
        schema_dict["const"] = const_value

    return Annotated[
        Any,
        BeforeValidator(validate_const),
        Field(json_schema_extra=json_schema_extra),
    ]


def create_empty_enum_validator() -> Any:
    """Create a validator for empty enums that rejects all values.

    Returns:
        An Annotated type that rejects all input.
    """

    def reject_all(v: Any) -> Any:
        raise ValueError("No values are allowed for empty enum")

    return Annotated[Any, BeforeValidator(reject_all)]
