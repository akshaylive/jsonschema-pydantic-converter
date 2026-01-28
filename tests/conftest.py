"""Test utilities and fixtures."""

from typing import Any

import pytest


def normalize_schema_additional_properties(schema: Any) -> Any:
    """Recursively add additionalProperties: True to objects that don't have it.

    This is used to normalize schemas for comparison, accounting for the fact
    that when additionalProperties is not specified, it defaults to True.
    """
    if isinstance(schema, dict):
        # If this looks like an object schema without additionalProperties, add it
        if schema.get("type") == "object" and "additionalProperties" not in schema:
            schema = {**schema, "additionalProperties": True}

        # Recursively process nested schemas
        result: dict[str, Any] = {}
        for key, value in schema.items():
            if key == "$defs" and isinstance(value, dict):
                result[key] = {
                    k: normalize_schema_additional_properties(v)
                    for k, v in value.items()
                }
            elif key == "properties" and isinstance(value, dict):
                result[key] = {
                    k: normalize_schema_additional_properties(v)
                    for k, v in value.items()
                }
            elif key in (
                "items",
                "prefixItems",
                "then",
                "else",
                "not",
                "allOf",
                "anyOf",
                "oneOf",
            ):
                if isinstance(value, dict):
                    result[key] = normalize_schema_additional_properties(value)
                elif isinstance(value, list):
                    result[key] = [
                        normalize_schema_additional_properties(v)
                        if isinstance(v, dict)
                        else v
                        for v in value
                    ]
                else:
                    result[key] = value
            else:
                result[key] = value
        return result
    return schema


@pytest.fixture
def normalize_schema():
    """Fixture to normalize schemas for comparison."""
    return normalize_schema_additional_properties
