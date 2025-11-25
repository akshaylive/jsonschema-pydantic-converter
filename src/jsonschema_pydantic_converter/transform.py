"""Json schema to dynamic pydantic model."""

import inspect
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, ConfigDict, Field, create_model
from typing_extensions import deprecated


@deprecated(
    "Use create_type_adapter instead. Json schemas are better represented as type adapters as BaseModels can only represent 'objects'."
)
def transform(
    schema: dict[str, Any],
) -> Type[BaseModel]:
    """Convert a schema dict to a pydantic model.

    Args:
        schema: JSON schema.

    Returns: Pydantic model.
    """
    dynamic_type_counter = 0
    combined_model_counter = 0

    def convert_type(prop: dict[str, Any]) -> Any:
        nonlocal dynamic_type_counter, combined_model_counter
        if "$ref" in prop:
            # Handle $ref with nested paths like #/$defs/Address/$defs/Country
            ref = prop["$ref"]
            if ref.startswith("#/"):
                # Remove leading #/ and split by /
                ref_path = ref[2:]
                # Extract the actual path (skip $defs/definitions keywords)
                parts = ref_path.split("/")
                # Filter out $defs and definitions, keep the actual definition names
                name_parts = [p for p in parts if p not in ("$defs", "definitions")]
                # Join with underscore and capitalize
                full_name = "_".join(name_parts).capitalize()
                return full_name
            else:
                # External ref - just use the last part
                return ref.split("/")[-1].capitalize()

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

                    # Handle additionalProperties
                    config = None
                    if "additionalProperties" in prop:
                        if prop["additionalProperties"] is False:
                            config = ConfigDict(extra="forbid")
                        elif prop["additionalProperties"] is True:
                            config = ConfigDict(extra="allow")

                    if config:
                        object_model = create_model(title, __config__=config, **fields)
                    else:
                        object_model = create_model(title, **fields)

                    if "description" in prop:
                        object_model.__doc__ = prop["description"]
                    return object_model
                else:
                    return Dict[str, Any]
            else:
                return type_mapping.get(type_, Any)

        elif "allOf" in prop:
            # Check if all schemas in allOf are objects (or have properties)
            has_properties = any("properties" in s for s in prop["allOf"])
            all_objects = all(
                s.get("type") == "object"
                or "properties" in s
                or "additionalProperties" in s
                for s in prop["allOf"]
            )

            # If we have object schemas, merge them
            if has_properties or all_objects:
                # Merge all properties and required fields from each sub-schema
                merged_properties: dict[str, Any] = {}
                merged_required: list[str] = []
                merged_additional_properties: bool | dict[str, Any] | None = None

                for sub_schema in prop["allOf"]:
                    # Capture type if specified
                    if "type" in sub_schema:
                        if sub_schema["type"] != "object":
                            raise ValueError(
                                f"Incompatible types in allOf: expected 'object', got '{sub_schema['type']}'"
                            )

                    # Handle additionalProperties - most restrictive wins
                    if "additionalProperties" in sub_schema:
                        if sub_schema["additionalProperties"] is False:
                            merged_additional_properties = False
                        elif merged_additional_properties is None:
                            merged_additional_properties = sub_schema[
                                "additionalProperties"
                            ]

                    # Get properties and required fields from each sub-schema
                    if "properties" in sub_schema:
                        for prop_name, prop_schema in sub_schema["properties"].items():
                            if prop_name in merged_properties:
                                # Property exists in multiple schemas - validate compatibility
                                existing = merged_properties[prop_name]

                                # Check type compatibility
                                existing_type = existing.get("type")
                                new_type = prop_schema.get("type")

                                if (
                                    existing_type
                                    and new_type
                                    and existing_type != new_type
                                ):
                                    raise ValueError(
                                        f"Incompatible types for property '{prop_name}' in allOf: "
                                        f"'{existing_type}' vs '{new_type}'"
                                    )

                                # Merge metadata (prefer values from later schemas if not set)
                                for key in ["title", "description", "default", "type"]:
                                    if key in prop_schema and key not in existing:
                                        existing[key] = prop_schema[key]
                            else:
                                merged_properties[prop_name] = prop_schema.copy()

                    if "required" in sub_schema:
                        merged_required.extend(sub_schema["required"])

                # If no properties were found but all are objects, create empty object
                if not merged_properties and all_objects:
                    merged_properties = {}

                # Remove duplicates from required list
                merged_required = list(set(merged_required))

                # Build the merged schema
                merged_schema: dict[str, Any] = {
                    "type": "object",
                    "properties": merged_properties,
                }
                if merged_required:
                    merged_schema["required"] = merged_required

                # Add additionalProperties if specified
                if merged_additional_properties is not None:
                    merged_schema["additionalProperties"] = merged_additional_properties

                # Title for the combined model
                if "title" in prop:
                    merged_schema["title"] = prop["title"]
                else:
                    merged_schema["title"] = f"CombinedModel_{combined_model_counter}"
                    combined_model_counter += 1

                # Convert the merged schema to a model
                return convert_type(merged_schema)

            else:
                # Non-object schemas: merge constraints and type information
                # Start with first schema as base
                merged_schema = prop["allOf"][0].copy() if prop["allOf"] else {}

                # Merge constraints from all schemas
                for sub_schema in prop["allOf"][1:]:
                    for key, value in sub_schema.items():
                        if key == "type":
                            # Validate type consistency
                            if (
                                "type" in merged_schema
                                and merged_schema["type"] != value
                            ):
                                raise ValueError(
                                    f"Incompatible types in allOf: '{merged_schema['type']}' vs '{value}'"
                                )
                            merged_schema["type"] = value
                        elif key not in merged_schema:
                            # Add new constraint
                            merged_schema[key] = value

                # Convert the merged non-object schema
                return convert_type(merged_schema)

        elif "anyOf" in prop:
            unioned_types = tuple(
                convert_type(sub_schema) for sub_schema in prop["anyOf"]
            )
            return Union[unioned_types]
        elif prop == {} or "type" not in prop:
            return Any
        else:
            raise ValueError(f"Unsupported schema: {prop}")

    # Recursively collect all definitions (including nested ones)
    def collect_definitions(
        schema_dict: dict[str, Any], path: str = ""
    ) -> dict[str, dict[str, Any]]:
        """Recursively collect all $defs/$definitions from schema."""
        defs: dict[str, dict[str, Any]] = {}

        # Get definitions at current level
        current_defs = schema_dict.get("$defs", schema_dict.get("definitions", {}))

        for def_name, definition in current_defs.items():
            # Build full path for nested definitions
            full_name = f"{path}/{def_name}" if path else def_name
            defs[full_name] = definition

            # Recursively collect nested definitions
            if isinstance(definition, dict):
                nested_defs = collect_definitions(definition, full_name)
                defs.update(nested_defs)

        return defs

    # Collect all definitions (top-level and nested)
    all_definitions = collect_definitions(schema)

    namespace: dict[str, Any] = {}
    for name, definition in all_definitions.items():
        model = convert_type(definition)
        # Use the full path as the key, but capitalize for consistency
        namespace[name.replace("/", "_").capitalize()] = model
    model = convert_type(schema)
    if not (inspect.isclass(model) and issubclass(model, BaseModel)):
        raise ValueError("Unable to convert schema.")
    model.model_rebuild(force=True, _types_namespace=namespace)
    return model
