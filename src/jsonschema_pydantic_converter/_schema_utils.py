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
