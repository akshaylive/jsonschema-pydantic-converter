"""Convert JSON Schema definitions to Pydantic TypeAdapters with dynamically generated models.

This module provides functionality to transform JSON Schema dictionaries into Pydantic v2
models at runtime, wrapped in TypeAdapters for validation and serialization.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import Field, TypeAdapter, create_model


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
        >>> adapter = transform(schema)
        >>> obj = adapter.validate_python({"name": "Alice", "age": 30})
    """
    dynamic_type_counter = 0
    combined_model_counter = 0

    def convert_type(prop: dict[str, Any]) -> Any:
        nonlocal dynamic_type_counter, combined_model_counter
        if "$ref" in prop:
            # This is the full path. It will be updated in update_forward_refs.
            return prop["$ref"].split("/")[-1].capitalize()

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
                dynamic_members = {
                    f"KEY_{i}": value for i, value in enumerate(prop["enum"])
                }

                base_type: Any = type_mapping.get(type_, Any)

                class DynamicEnum(base_type, Enum):
                    pass

                type_ = DynamicEnum(prop.get("title", "DynamicEnum"), dynamic_members)  # type: ignore[call-arg]
                return type_
            elif type_ == "array":
                item_type: Any = convert_type(prop.get("items", {}))
                return List[item_type]  # noqa F821
            elif type_ == "object":
                if "properties" in prop:
                    if "title" in prop and prop["title"]:
                        title = prop["title"]
                    else:
                        title = f"DynamicType_{dynamic_type_counter}"
                        dynamic_type_counter += 1

                    fields: dict[str, Any] = {}
                    required_fields = prop.get("required", [])

                    for name, property in prop.get("properties", {}).items():
                        pydantic_type = convert_type(property)
                        field_kwargs = {}
                        if "default" in property:
                            field_kwargs["default"] = property["default"]
                        if name not in required_fields:
                            if "default" not in field_kwargs:
                                # If default is present, Optional is not needed as instantiation will be successful.
                                # Otherwise, explicitly treat is as optional with default None.
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
                else:
                    return Dict[str, Any]
            else:
                return type_mapping.get(type_, Any)

        elif "allOf" in prop:
            combined_fields = {}
            for sub_schema in prop["allOf"]:
                model = convert_type(sub_schema)
                combined_fields.update(model.__annotations__)
            combined_model = create_model(
                f"CombinedModel_{combined_model_counter}", **combined_fields
            )
            combined_model_counter += 1
            return combined_model

        elif "anyOf" in prop:
            unioned_types = tuple(
                convert_type(sub_schema) for sub_schema in prop["anyOf"]
            )
            return Union[unioned_types]
        elif prop == {} or "type" not in prop:
            return Any
        else:
            raise ValueError(f"Unsupported schema: {prop}")

    namespace: dict[str, Any] = {}
    for name, definition in schema.get("$defs", schema.get("definitions", {})).items():
        model = convert_type(definition)
        namespace[name.capitalize()] = model
    model = convert_type(schema)
    type_adapter = TypeAdapter(model)
    type_adapter.rebuild(force=True, _types_namespace=namespace)
    return type_adapter
