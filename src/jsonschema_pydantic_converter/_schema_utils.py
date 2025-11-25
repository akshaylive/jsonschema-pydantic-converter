"""Utility functions for JSON Schema processing."""

from typing import Any


def collect_definitions(
    schema_dict: dict[str, Any], path: str = ""
) -> dict[str, dict[str, Any]]:
    """Recursively collect all $defs/$definitions from schema.

    Args:
        schema_dict: The schema dictionary to collect definitions from.
        path: The current path in the schema hierarchy.

    Returns:
        A dictionary mapping full definition paths to their schemas.
    """
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


def resolve_ref_path(ref: str) -> str:
    """Resolve a $ref path to a namespace key.

    Args:
        ref: The $ref string (e.g., "#/$defs/Address/$defs/Country").

    Returns:
        The namespace key (e.g., "Address_Country").
    """
    if ref.startswith("#/"):
        # Remove leading #/ and split by /
        ref_path = ref[2:]
        # Extract the actual path (skip $defs/definitions keywords)
        parts = ref_path.split("/")
        # Filter out $defs and definitions, keep the actual definition names
        name_parts = [p for p in parts if p not in ("$defs", "definitions")]
        # Join with underscore and capitalize
        return "_".join(name_parts).capitalize()
    else:
        # External ref - just use the last part
        return ref.split("/")[-1].capitalize()


def is_allof_object_schemas(allof_schemas: list[dict[str, Any]]) -> bool:
    """Check if allOf contains object schemas.

    Args:
        allof_schemas: List of schemas in allOf.

    Returns:
        True if the schemas are objects that should be merged.
    """
    has_properties = any("properties" in s for s in allof_schemas)
    all_objects = all(
        s.get("type") == "object" or "properties" in s or "additionalProperties" in s
        for s in allof_schemas
    )
    return has_properties or all_objects


def merge_allof_object_schemas(
    allof_schemas: list[dict[str, Any]], title: str | None = None
) -> dict[str, Any]:
    """Merge allOf object schemas into a single schema.

    Args:
        allof_schemas: List of object schemas to merge.
        title: Optional title for the merged schema.

    Returns:
        A merged object schema.

    Raises:
        ValueError: If schemas have incompatible types.
    """
    merged_properties: dict[str, Any] = {}
    merged_required: list[str] = []
    merged_additional_properties: bool | dict[str, Any] | None = None

    for sub_schema in allof_schemas:
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
                merged_additional_properties = sub_schema["additionalProperties"]

        # Get properties and required fields from each sub-schema
        if "properties" in sub_schema:
            for prop_name, prop_schema in sub_schema["properties"].items():
                if prop_name in merged_properties:
                    # Property exists in multiple schemas - validate compatibility
                    existing = merged_properties[prop_name]

                    # Check type compatibility
                    existing_type = existing.get("type")
                    new_type = prop_schema.get("type")

                    if existing_type and new_type and existing_type != new_type:
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
    all_objects = all(
        s.get("type") == "object" or "properties" in s or "additionalProperties" in s
        for s in allof_schemas
    )
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

    # Add title if provided
    if title:
        merged_schema["title"] = title

    return merged_schema


def merge_allof_constraint_schemas(
    allof_schemas: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge allOf non-object schemas by combining constraints.

    Args:
        allof_schemas: List of constraint schemas to merge.

    Returns:
        A merged schema with combined constraints.

    Raises:
        ValueError: If schemas have incompatible types.
    """
    # Start with first schema as base
    merged_schema = allof_schemas[0].copy() if allof_schemas else {}

    # Merge constraints from all schemas
    for sub_schema in allof_schemas[1:]:
        for key, value in sub_schema.items():
            if key == "type":
                # Validate type consistency
                if "type" in merged_schema and merged_schema["type"] != value:
                    raise ValueError(
                        f"Incompatible types in allOf: '{merged_schema['type']}' vs '{value}'"
                    )
                merged_schema["type"] = value
            elif key not in merged_schema:
                # Add new constraint
                merged_schema[key] = value

    return merged_schema
