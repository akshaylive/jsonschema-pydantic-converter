"""Convert JSON Schema definitions to Pydantic TypeAdapters with dynamically generated models.

This module provides functionality to transform JSON Schema dictionaries into Pydantic v2
models at runtime, wrapped in TypeAdapters for validation and serialization.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import BeforeValidator, Field, TypeAdapter, create_model


def create_type_adapter(
    schema: dict[str, Any],
) -> TypeAdapter[Any]:
    """Convert a JSON Schema dict to a Pydantic TypeAdapter.

    This function dynamically generates Pydantic models from JSON Schema definitions
    and returns a TypeAdapter that wraps the generated model. The TypeAdapter provides
    methods for validation and serialization.

    Args:
        schema: JSON schema dictionary following the JSON Schema specification.
                Supports primitive types, objects, arrays, enums, references ($ref),
                and schema composition (allOf, anyOf).

    Returns:
        A Pydantic TypeAdapter wrapping the dynamically generated model.
        Use adapter.validate_python(data) to validate Python objects,
        adapter.validate_json(json_str) to validate JSON strings, and
        adapter.dump_python(obj) to serialize validated objects.

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "name": {"type": "string"},
        ...         "age": {"type": "integer"}
        ...     },
        ...     "required": ["name"]
        ... }
        >>> adapter = create_type_adapter(schema)
        >>> obj = adapter.validate_python({"name": "Alice", "age": 30})
    """
    dynamic_type_counter = 0
    namespace: dict[str, Any] = {}

    def _create_intersection_type(sub_schemas: list[dict[str, Any]]) -> Any:
        """Create an Intersection type that validates against all sub-schemas."""
        converted_types = [convert_type(sub) for sub in sub_schemas]

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

        def json_schema_extra(schema_dict: dict[str, Any]) -> None:
            """Override the generated schema with the original allOf structure."""
            schema_dict.clear()
            schema_dict["allOf"] = sub_schemas

        return Annotated[
            Any,
            BeforeValidator(validate_all),
            Field(json_schema_extra=json_schema_extra),
        ]

    def convert_type(prop: dict[str, Any]) -> Any:
        nonlocal dynamic_type_counter

        if "$ref" in prop:
            return prop["$ref"].split("/")[-1].capitalize()

        if "allOf" in prop:
            return _create_intersection_type(prop["allOf"])

        if "anyOf" in prop:
            unioned_types = tuple(convert_type(sub) for sub in prop["anyOf"])
            return Union[unioned_types]

        if "type" in prop:
            type_mapping = {
                "string": str,
                "number": float,
                "integer": int,
                "boolean": bool,
                "array": List,
                "object": Dict[str, Any],
                "null": None,
            }

            type_ = prop["type"]

            if "enum" in prop:
                base_type: Any = type_mapping.get(type_, Any)
                dynamic_members = {
                    f"KEY_{i}": value for i, value in enumerate(prop["enum"])
                }

                class DynamicEnum(base_type, Enum):
                    pass

                return DynamicEnum(prop.get("title", "DynamicEnum"), dynamic_members)  # type: ignore[call-arg]

            if type_ == "array":
                item_type: Any = convert_type(prop.get("items", {}))
                return List[item_type]

            if type_ == "object":
                if "properties" not in prop:
                    return Dict[str, Any]

                # Generate title for the model
                if "title" in prop and prop["title"]:
                    title = prop["title"]
                else:
                    title = f"DynamicType_{dynamic_type_counter}"
                    dynamic_type_counter += 1

                # Build fields
                fields: dict[str, Any] = {}
                required_fields = prop.get("required", [])

                for name, property in prop["properties"].items():
                    pydantic_type = convert_type(property)
                    field_kwargs = {}

                    if "default" in property:
                        field_kwargs["default"] = property["default"]
                    elif name not in required_fields:
                        pydantic_type = Optional[pydantic_type]
                        field_kwargs["default"] = None

                    if "description" in property:
                        field_kwargs["description"] = property["description"]
                    if "title" in property:
                        field_kwargs["title"] = property["title"]

                    fields[name] = (pydantic_type, Field(**field_kwargs))

                object_model = create_model(title, **fields)
                if "description" in prop:
                    object_model.__doc__ = prop["description"]
                return object_model

            return type_mapping.get(type_, Any)

        if not prop or prop == {}:
            return Any

        raise ValueError(f"Unsupported schema: {prop}")

    # Populate namespace with definitions
    for name, definition in schema.get("$defs", schema.get("definitions", {})).items():
        model = convert_type(definition)
        namespace[name.capitalize()] = model

    # Convert the main schema
    model = convert_type(schema)
    type_adapter = TypeAdapter(model)
    type_adapter.rebuild(force=True, _types_namespace=namespace)
    return type_adapter
